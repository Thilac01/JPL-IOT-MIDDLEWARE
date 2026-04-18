import asyncio
import logging
import decimal
from pymysqlreplication import BinLogStreamReader
from pymysqlreplication.row_event import WriteRowsEvent, UpdateRowsEvent, DeleteRowsEvent
from config import settings
import json

logger = logging.getLogger(__name__)

class CDCHandler:
    def __init__(self, broadcast_callback):
        self.broadcast_callback = broadcast_callback
        self.stream = None
        self._stop_event = asyncio.Event()

    async def start(self):
        logger.info("Starting CDC Stream Reader...")
        
        # MySQL Binlog configuration
        mysql_settings = {
            "host": settings.REPLICA_HOST,
            "port": settings.REPLICA_PORT,
            "user": settings.CDC_USER,
            "passwd": settings.CDC_PASSWORD
        }

        try:
            # Note: server_id must be unique across all replication clients
            self.stream = BinLogStreamReader(
                connection_settings=mysql_settings,
                server_id=settings.CDC_SERVER_ID,
                blocking=True,
                only_events=[WriteRowsEvent, UpdateRowsEvent, DeleteRowsEvent],
                only_schemas=[settings.REPLICA_DB],
                resume_stream=False 
            )

            logger.info(f"CDC Stream connected to {settings.REPLICA_DB}")

            while not self._stop_event.is_set():
                # run_in_executor since stream.fetchone() is a blocking call
                try:
                    event = await asyncio.get_event_loop().run_in_executor(None, self.stream.fetchone)
                    if event:
                        await self.handle_event(event)
                except Exception as stream_err:
                    logger.error(f"Error fetching from binlog: {stream_err}")
                    await asyncio.sleep(5) # Wait before retry
                
                await asyncio.sleep(0.01)

        except Exception as e:
            logger.error(f"CDC initialization failed: {e}")
        finally:
            if self.stream:
                self.stream.close()

    def stop(self):
        self._stop_event.set()

    async def handle_event(self, event):
        for row in event.rows:
            try:
                event_type = "UNKNOWN"
                if isinstance(event, WriteRowsEvent): event_type = "INSERT"
                elif isinstance(event, UpdateRowsEvent): event_type = "UPDATE"
                elif isinstance(event, DeleteRowsEvent): event_type = "DELETE"

                data = row.get("values") if event_type != "UPDATE" else row.get("after_values")
                serialized_data = self._serialize_data(data)

                # Build a human-readable alert for circulation events
                alert = None
                table = event.table.lower()
                if table == "issues" and event_type == "INSERT":
                    item = serialized_data.get('itemnumber', '') if serialized_data else ''
                    borrower = serialized_data.get('borrowernumber', '') if serialized_data else ''
                    due = serialized_data.get('date_due', '') if serialized_data else ''
                    alert = {"level": "success", "title": "📚 Book Checked Out!", "msg": f"Item #{item} issued to borrower #{borrower}. Due: {str(due)[:10]}"}
                elif table == "old_issues" and event_type == "INSERT":
                    item = serialized_data.get('itemnumber', '') if serialized_data else ''
                    borrower = serialized_data.get('borrowernumber', '') if serialized_data else ''
                    alert = {"level": "info", "title": "↩️ Book Returned!", "msg": f"Item #{item} returned by borrower #{borrower}"}
                elif table == "issues" and event_type == "DELETE":
                    before = self._serialize_data(row.get('before_values')) or {}
                    item = before.get('itemnumber', 'unknown')
                    alert = {"level": "warning", "title": "⚠️ Issue Cancelled", "msg": f"Item #{item} issue record was removed"}

                payload = {
                    "table": event.table,
                    "type": event_type,
                    "data": serialized_data,
                    "old_data": self._serialize_data(row.get("before_values")) if event_type == "UPDATE" else None,
                    "timestamp": getattr(event, 'timestamp', 0),
                    "alert": alert
                }
                
                logger.info(f"CDC Event: {event_type} on {event.table}")
                await self.broadcast_callback(payload)
            except Exception as e:
                logger.error(f"Error processing row event: {e}")

    def _serialize_data(self, data):
        """Handle Decimal, bytes, datetime and other non-JSON-serializable MySQL types"""
        if not data: return None
        serialized = {}
        for k, v in data.items():
            if isinstance(v, decimal.Decimal):
                serialized[k] = float(v)
            elif isinstance(v, bytes):
                try:
                    serialized[k] = v.decode('utf-8')
                except Exception:
                    serialized[k] = v.hex()
            elif hasattr(v, 'isoformat'):
                serialized[k] = v.isoformat()
            elif v is None:
                serialized[k] = None
            else:
                serialized[k] = str(v) if not isinstance(v, (int, float, bool, str)) else v
        return serialized
