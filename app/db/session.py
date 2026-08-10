import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Tuple, Union
import aiomysql
from app.core.config import settings
from app.db.tunnel import SSHTunnelManager

logger = logging.getLogger("db.session")

class DatabaseManager:
    def __init__(self):
        self.pool: Optional[aiomysql.Pool] = None
        self.ssh_mgr = SSHTunnelManager()
        self.status: str = "DISCONNECTED"  # DISCONNECTED, CONNECTING, HEALTHY, DEGRADED, RECONNECTING
        self.last_error: Optional[str] = None
        self.last_connected_at: Optional[float] = None
        self.last_ping_at: Optional[float] = None
        self.queries_count: int = 0
        self.failed_queries_count: int = 0
        self._reconnect_task: Optional[asyncio.Task] = None
        self._is_shutting_down: bool = False
        self._lock = asyncio.Lock()

    @property
    def tunnel(self):
        """Backward compatibility property returning underlying SSHTunnelForwarder if present."""
        return self.ssh_mgr.tunnel

    @property
    def ssh_status(self) -> str:
        return self.ssh_mgr.status

    async def initialize(self):
        """Start database connection and launch background resilience worker."""
        self._is_shutting_down = False
        await self.connect()
        self._reconnect_task = asyncio.create_task(self._health_check_loop())
        logger.info("Database resilience supervisor started.")

    async def connect(self) -> bool:
        """Attempt connection to SSH tunnel and MySQL pool in a non-blocking thread."""
        async with self._lock:
            if self._is_shutting_down:
                return False

            self.status = "CONNECTING"
            logger.info("Connecting to MySQL Database / SSH Gateway...")

            # 1. Establish SSH Tunnel if enabled
            if settings.USE_SSH:
                ssh_ok = await self.ssh_mgr.start()
                if not ssh_ok:
                    self.status = "DISCONNECTED"
                    self.last_error = self.ssh_mgr.last_error
                    return False

            # 2. Establish aiomysql connection pool
            try:
                if self.pool:
                    self.pool.close()
                    await self.pool.wait_closed()
                    self.pool = None

                self.pool = await asyncio.wait_for(
                    aiomysql.create_pool(
                        host=settings.REPLICA_HOST,
                        port=settings.REPLICA_PORT,
                        user=settings.REPLICA_USER,
                        password=settings.REPLICA_PASSWORD,
                        db=settings.REPLICA_DB,
                        minsize=settings.DB_POOL_MIN_SIZE,
                        maxsize=settings.DB_POOL_MAX_SIZE,
                        pool_recycle=settings.DB_POOL_RECYCLE,
                        autocommit=True,
                        charset='utf8mb4',
                        connect_timeout=settings.DB_CONNECT_TIMEOUT
                    ),
                    timeout=settings.DB_CONNECT_TIMEOUT
                )

                self.status = "HEALTHY"
                self.last_connected_at = time.time()
                self.last_error = None
                logger.info(f"MySQL Connection Pool initialized successfully (Min: {settings.DB_POOL_MIN_SIZE}, Max: {settings.DB_POOL_MAX_SIZE}).")
                return True
            except Exception as e:
                self.status = "DISCONNECTED"
                self.last_error = f"MySQL Pool Failure: {e}"
                logger.warning(f"Failed to connect to MySQL Pool: {e}")
                if settings.USE_SSH:
                    await self.ssh_mgr.stop()
                return False

    async def disconnect(self):
        """Gracefully disconnect pool, tunnel, and background supervisor."""
        self._is_shutting_down = True
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass

        if self.pool:
            logger.info("Closing MySQL connection pool...")
            self.pool.close()
            await self.pool.wait_closed()
            self.pool = None

        if settings.USE_SSH:
            await self.ssh_mgr.stop()

        self.status = "DISCONNECTED"
        logger.info("Database Manager shut down cleanly.")

    async def _health_check_loop(self):
        """Continuous supervisor that tests DB connection and auto-reconnects with backoff."""
        backoff = 5
        max_backoff = 30

        while not self._is_shutting_down:
            try:
                await asyncio.sleep(settings.DB_RECONNECT_INTERVAL if self.is_healthy() else backoff)

                if self._is_shutting_down:
                    break

                if self.pool:
                    # Ping database
                    try:
                        async with asyncio.timeout(5):
                            result = await self.fetch_one("SELECT 1 as ping")
                            if result and result.get("ping") == 1:
                                self.status = "HEALTHY"
                                self.last_ping_at = time.time()
                                backoff = 5
                                continue
                            else:
                                raise Exception("Ping returned unexpected result")
                    except Exception as ping_err:
                        logger.warning(f"Database ping check failed: {ping_err}")
                        self.status = "DEGRADED"

                # If disconnected or degraded, attempt reconnection
                if not self.is_healthy():
                    self.status = "RECONNECTING"
                    logger.info("Initiating auto-reconnect attempt to database...")
                    connected = await self.connect()
                    if connected:
                        logger.info("Database successfully reconnected by supervisor.")
                        backoff = 5
                    else:
                        backoff = min(backoff * 2, max_backoff)
                        logger.debug(f"Next reconnect attempt in {backoff}s")

            except asyncio.CancelledError:
                break
            except Exception as loop_err:
                logger.error(f"Unexpected error in health check loop: {loop_err}")
                await asyncio.sleep(5)

    def is_healthy(self) -> bool:
        return self.pool is not None and self.status == "HEALTHY"

    async def fetch_all(self, query: str, params: Optional[Union[List, Tuple, Dict]] = None) -> List[Dict[str, Any]]:
        """Execute query safely and return all rows as dicts."""
        if not self.pool:
            return []
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(query, params)
                    self.queries_count += 1
                    return await cur.fetchall()
        except Exception as e:
            self.failed_queries_count += 1
            self.last_error = str(e)
            logger.error(f"Query fetch_all error: {e} | SQL: {query[:120]}")
            return []

    async def fetch_one(self, query: str, params: Optional[Union[List, Tuple, Dict]] = None) -> Optional[Dict[str, Any]]:
        """Execute query safely and return single row as dict."""
        if not self.pool:
            return None
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(query, params)
                    self.queries_count += 1
                    return await cur.fetchone()
        except Exception as e:
            self.failed_queries_count += 1
            self.last_error = str(e)
            logger.error(f"Query fetch_one error: {e} | SQL: {query[:120]}")
            return None

    async def execute(self, query: str, params: Optional[Union[List, Tuple, Dict]] = None) -> int:
        """Execute a write/update statement and return affected rows count."""
        if not self.pool:
            return 0
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    affected = await cur.execute(query, params)
                    self.queries_count += 1
                    return affected
        except Exception as e:
            self.failed_queries_count += 1
            self.last_error = str(e)
            logger.error(f"Query execute error: {e} | SQL: {query[:120]}")
            return 0

    def get_health(self) -> Dict[str, Any]:
        """Return diagnostic health info for /api/health and UI."""
        return {
            "status": self.status,
            "ssh_tunnel": self.ssh_mgr.get_status(),
            "database": {
                "database_name": settings.REPLICA_DB,
                "pool_connected": self.pool is not None,
                "free_connections": self.pool.freesize if self.pool else 0,
                "total_connections": self.pool.size if self.pool else 0,
                "max_connections": settings.DB_POOL_MAX_SIZE,
                "queries_executed": self.queries_count,
                "failed_queries": self.failed_queries_count,
                "last_connected_at": self.last_connected_at,
                "last_ping_at": self.last_ping_at
            },
            "last_error": self.last_error
        }

# Global singleton database manager instance
db = DatabaseManager()
