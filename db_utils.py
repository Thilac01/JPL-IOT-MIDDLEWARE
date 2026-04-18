import aiomysql
import logging
from config import settings
from sshtunnel import SSHTunnelForwarder

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self.pool = None
        self.tunnel = None

    async def connect(self):
        try:
            # Start SSH Tunnel if enabled
            if settings.USE_SSH:
                logger.info(f"Establishing SSH Tunnel to {settings.SSH_HOST}...")
                self.tunnel = SSHTunnelForwarder(
                    (settings.SSH_HOST, settings.SSH_PORT),
                    ssh_username=settings.SSH_USER,
                    ssh_password=settings.SSH_PASSWORD,
                    remote_bind_address=('127.0.0.1', 3306),
                    local_bind_address=('127.0.0.1', settings.REPLICA_PORT)
                )
                self.tunnel.start()
                logger.info(f"SSH Tunnel active on 127.0.0.1:{settings.REPLICA_PORT}")

            self.pool = await aiomysql.create_pool(
                host=settings.REPLICA_HOST,
                port=settings.REPLICA_PORT,
                user=settings.REPLICA_USER,
                password=settings.REPLICA_PASSWORD,
                db=settings.REPLICA_DB,
                autocommit=True
            )
            logger.info("Successfully connected to MySQL Pool")
        except Exception as e:
            logger.error(f"Failed to connect to MySQL: {e}")
            if self.tunnel:
                self.tunnel.stop()
            raise

    async def disconnect(self):
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()
        if self.tunnel:
            self.tunnel.stop()
            logger.info("SSH Tunnel closed.")

    async def fetch_all(self, query, params=None):
        if not self.pool:
            return []
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                try:
                    await cur.execute(query, params)
                    return await cur.fetchall()
                except Exception as e:
                    logger.error(f"Query Error: {e}")
                    return []

    async def fetch_one(self, query, params=None):
        if not self.pool:
            return None
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                try:
                    await cur.execute(query, params)
                    return await cur.fetchone()
                except Exception as e:
                    logger.error(f"Query Error: {e}")
                    return None

db = DatabaseManager()
