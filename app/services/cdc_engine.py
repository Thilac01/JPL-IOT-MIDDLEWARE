import asyncio
import decimal
import datetime
import json
import logging
import os
import threading
import time
from typing import Any, Callable, Dict, Optional
from app.core.config import settings
from app.services.smtp_service import smtp_service

logger = logging.getLogger("services.cdc")

# Try importing BinLogStreamReader
try:
    from pymysqlreplication import BinLogStreamReader
    from pymysqlreplication.row_event import WriteRowsEvent, UpdateRowsEvent, DeleteRowsEvent
    HAS_PYMYSQL_REPLICATION = True
except ImportError:
    HAS_PYMYSQL_REPLICATION = False
    logger.warning("pymysqlreplication not found. CDC will operate in standby mode.")

class CDCEngine:
    def __init__(self, broadcast_callback: Callable[[Dict[str, Any]], Any]):
        self.broadcast_callback = broadcast_callback
        self.stream: Optional[Any] = None
        self.is_running = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        
        # Metrics & Position Tracking
        self.events_processed = 0
        self.last_event_time: Optional[float] = None
        self.status = "STOPPED"  # STOPPED, RUNNING, RECONNECTING, FAILED
        self.last_log_file: Optional[str] = settings.CDC_LOG_FILE
        self.last_log_pos: Optional[int] = settings.CDC_LOG_POS
        self.last_error: Optional[str] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        # Load persisted position if available
        self._load_state()

    def _load_state(self):
        """Load persisted CDC position from state file."""
        if os.path.exists(settings.CDC_STATE_FILE):
            try:
                with open(settings.CDC_STATE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.last_log_file = data.get("log_file") or self.last_log_file
                    self.last_log_pos = data.get("log_pos") or self.last_log_pos
                    logger.info(f"Loaded CDC state from {settings.CDC_STATE_FILE}: {self.last_log_file}:{self.last_log_pos}")
            except Exception as e:
                logger.warning(f"Could not read CDC state file: {e}")

    def _save_state(self):
        """Persist current CDC position to state file."""
        if not self.last_log_file or not self.last_log_pos:
            return
        try:
            with open(settings.CDC_STATE_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "log_file": self.last_log_file,
                    "log_pos": self.last_log_pos,
                    "updated_at": time.time(),
                    "events_processed": self.events_processed
                }, f, indent=2)
        except Exception as e:
            logger.debug(f"Could not persist CDC state: {e}")

    async def start(self):
        """Start the live CDC worker thread."""
        self._loop = asyncio.get_running_loop()
        self.is_running = True
        self._stop_event.clear()

        # Start live CDC stream thread if enabled
        if settings.CDC_ENABLED and HAS_PYMYSQL_REPLICATION:
            self._thread = threading.Thread(target=self._run_cdc_worker, name="CDCWorkerThread", daemon=True)
            self._thread.start()
            logger.info("CDC Subsystem started successfully.")
        else:
            self.status = "DISABLED"
            logger.info("Live CDC disabled or pymysqlreplication missing.")

    def stop(self):
        """Signal the CDC worker to terminate cleanly."""
        self.is_running = False
        self._stop_event.set()
        if self.stream:
            try:
                self.stream.close()
            except Exception:
                pass
            self.stream = None

        self._save_state()
        self.status = "STOPPED"
        logger.info("CDC Subsystem stopped.")

    def _run_cdc_worker(self):
        """Dedicated background worker thread for blocking MySQL BinLog stream reader."""
        backoff = 5
        max_backoff = 30

        while not self._stop_event.is_set():
            # Check if MySQL/SSH is ready
            from app.db.session import db
            if not db.is_healthy():
                self.status = "RECONNECTING" if self.is_running else "STOPPED"
                time.sleep(3)
                continue

            try:
                self.status = "RUNNING"
                mysql_settings = {
                    "host": settings.REPLICA_HOST,
                    "port": settings.REPLICA_PORT,
                    "user": settings.CDC_USER,
                    "passwd": settings.CDC_PASSWORD or ""
                }

                logger.info(f"Attaching BinLogStreamReader to {settings.REPLICA_HOST}:{settings.REPLICA_PORT} (Server ID: {settings.CDC_SERVER_ID})...")
                
                stream_kwargs = {
                    "connection_settings": mysql_settings,
                    "server_id": settings.CDC_SERVER_ID,
                    "blocking": True,
                    "only_events": [WriteRowsEvent, UpdateRowsEvent, DeleteRowsEvent],
                    "only_schemas": [settings.REPLICA_DB],
                    "resume_stream": settings.CDC_RESUME_STREAM
                }

                if self.last_log_file and self.last_log_pos:
                    stream_kwargs["log_file"] = self.last_log_file
                    stream_kwargs["log_pos"] = self.last_log_pos

                self.stream = BinLogStreamReader(**stream_kwargs)
                logger.info(f"CDC Binlog stream connected to database '{settings.REPLICA_DB}'")
                backoff = 5

                for binlogevent in self.stream:
                    if self._stop_event.is_set():
                        break

                    # Track binlog coordinate
                    if hasattr(binlogevent, 'packet'):
                        self.last_log_file = getattr(self.stream, 'log_file', self.last_log_file)
                        self.last_log_pos = getattr(self.stream, 'log_pos', self.last_log_pos)

                    self._process_event_sync(binlogevent)

            except Exception as stream_err:
                self.last_error = str(stream_err)
                self.status = "RECONNECTING"
                logger.warning(f"CDC Stream disconnected: {stream_err}. Retrying in {backoff}s...")
                if self.stream:
                    try:
                        self.stream.close()
                    except Exception:
                        pass
                    self.stream = None
                time.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)

        self.status = "STOPPED"

    def _process_event_sync(self, event: Any):
        """Process incoming binlog event synchronously and dispatch to async loop."""
        if not self._loop or self._loop.is_closed():
            return

        try:
            event_type = "UNKNOWN"
            if isinstance(event, WriteRowsEvent):
                event_type = "INSERT"
            elif isinstance(event, UpdateRowsEvent):
                event_type = "UPDATE"
            elif isinstance(event, DeleteRowsEvent):
                event_type = "DELETE"

            for row in event.rows:
                data = row.get("values") if event_type != "UPDATE" else row.get("after_values")
                serialized_data = self._serialize_data(data)
                old_data = self._serialize_data(row.get("before_values")) if event_type == "UPDATE" else None

                # Build rich circulation alerts
                alert = self._build_circulation_alert(event.table, event_type, serialized_data, old_data)

                payload = {
                    "table": event.table,
                    "type": event_type,
                    "data": serialized_data,
                    "old_data": old_data,
                    "timestamp": getattr(event, 'timestamp', int(time.time())),
                    "alert": alert,
                    "source": "live_binlog"
                }

                self.events_processed += 1
                self.last_event_time = time.time()
                
                # Periodically persist position
                if self.events_processed % 50 == 0:
                    self._save_state()

                # Schedule broadcast on main event loop
                asyncio.run_coroutine_threadsafe(
                    self._handle_event_async(payload, alert),
                    self._loop
                )

        except Exception as e:
            logger.error(f"Error processing CDC row event: {e}")

    async def _handle_event_async(self, payload: Dict[str, Any], alert: Optional[Dict[str, Any]]):
        """Async dispatch of WebSocket broadcast and email notifications."""
        # 1. WebSocket Broadcast
        await self.broadcast_callback(payload)

        # 2. SMTP Alert Dispatch
        if alert and smtp_service.is_configured():
            try:
                await smtp_service.send_alert_email(
                    subject=alert.get("title", "Security Alert"),
                    message=alert.get("msg", ""),
                    level=alert.get("level", "info"),
                    details=payload.get("data")
                )
            except Exception as e:
                logger.debug(f"SMTP dispatch caught: {e}")

    def _build_circulation_alert(
        self,
        table: str,
        event_type: str,
        data: Optional[Dict[str, Any]],
        old_data: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Construct human-readable notifications for circulation and security changes."""
        if not data:
            return None

        table_lower = table.lower()
        if table_lower == "issues" and event_type == "INSERT":
            barcode = data.get("barcode") or data.get("itemnumber", "Item")
            borrower = data.get("borrowernumber", "Borrower")
            due = str(data.get("date_due", "N/A"))[:10]
            return {
                "level": "success",
                "title": "📚 Book Checked Out",
                "msg": f"Item #{barcode} issued to borrower #{borrower}. Due date: {due}"
            }
        elif table_lower == "old_issues" and event_type == "INSERT":
            barcode = data.get("barcode") or data.get("itemnumber", "Item")
            borrower = data.get("borrowernumber", "Borrower")
            return {
                "level": "info",
                "title": "↩️ Book Returned",
                "msg": f"Item #{barcode} safely returned by borrower #{borrower} to shelf"
            }
        elif table_lower == "issues" and event_type == "DELETE":
            item = (old_data or {}).get("itemnumber", "unknown")
            return {
                "level": "warning",
                "title": "⚠️ Loan Record Removed",
                "msg": f"Active loan for item #{item} was deleted or resolved"
            }
        elif table_lower == "borrowers":
            name = f"{data.get('firstname', '')} {data.get('surname', '')}".strip() or data.get('cardnumber', 'Member')
            return {
                "level": "info",
                "title": "👤 Member Profile Updated",
                "msg": f"Patron #{data.get('borrowernumber', '')} ({name}) record modified"
            }
        return None

    def _serialize_data(self, data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Industrial serializer converting non-standard MySQL types to JSON-safe primitives."""
        if not data:
            return None

        serialized = {}
        for k, v in data.items():
            if isinstance(v, decimal.Decimal):
                serialized[k] = float(v)
            elif isinstance(v, (datetime.datetime, datetime.date, datetime.time)):
                serialized[k] = v.isoformat()
            elif isinstance(v, datetime.timedelta):
                serialized[k] = str(v)
            elif isinstance(v, (bytes, bytearray)):
                try:
                    serialized[k] = v.decode("utf-8")
                except Exception:
                    serialized[k] = v.hex()
            elif isinstance(v, (set, frozenset)):
                serialized[k] = list(v)
            elif v is None:
                serialized[k] = None
            else:
                serialized[k] = v if isinstance(v, (int, float, bool, str)) else str(v)
        return serialized

    def get_health(self) -> Dict[str, Any]:
        """Return diagnostic health info for /api/health."""
        return {
            "status": self.status,
            "is_running": self.is_running,
            "events_processed": self.events_processed,
            "last_event_at": self.last_event_time,
            "binlog_position": {
                "file": self.last_log_file,
                "position": self.last_log_pos
            },
            "last_error": self.last_error
        }
