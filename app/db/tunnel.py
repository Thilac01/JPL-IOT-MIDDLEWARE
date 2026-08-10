import asyncio
import logging
from typing import Any, Dict, Optional
import paramiko
from app.core.config import settings

# Paramiko 5.0+ compatibility shim for sshtunnel
if not hasattr(paramiko, 'DSSKey'):
    class DSSKey:
        pass
    paramiko.DSSKey = DSSKey

from sshtunnel import SSHTunnelForwarder

logger = logging.getLogger("db.tunnel")

class SSHTunnelManager:
    def __init__(self):
        self.tunnel: Optional[SSHTunnelForwarder] = None
        self.status: str = "DISCONNECTED"  # DISCONNECTED, CONNECTING, HEALTHY, FAILED
        self.local_bind_port: Optional[int] = None
        self.last_error: Optional[str] = None

    async def start(self) -> bool:
        """Start SSH tunnel asynchronously in threadpool with timeout protection."""
        if not settings.USE_SSH:
            self.status = "DISABLED"
            return True

        self.status = "CONNECTING"
        logger.info(f"Establishing SSH Tunnel to {settings.SSH_HOST}:{settings.SSH_PORT}...")

        def _open_tunnel() -> SSHTunnelForwarder:
            tunnel = SSHTunnelForwarder(
                (settings.SSH_HOST, settings.SSH_PORT),
                ssh_username=settings.SSH_USER,
                ssh_password=settings.SSH_PASSWORD,
                ssh_pkey=settings.SSH_PKEY,
                remote_bind_address=('127.0.0.1', 3306),
                local_bind_address=('127.0.0.1', 0),
                set_missing_host_key_policy='AutoAddPolicy'
            )
            tunnel.start()
            return tunnel

        try:
            self.tunnel = await asyncio.wait_for(
                asyncio.to_thread(_open_tunnel),
                timeout=settings.SSH_TIMEOUT
            )
            self.local_bind_port = self.tunnel.local_bind_port
            settings.REPLICA_PORT = self.local_bind_port
            self.status = "HEALTHY"
            self.last_error = None
            logger.info(f"SSH Tunnel active -> 127.0.0.1:{self.local_bind_port} (forwarded to remote 3306)")
            return True
        except Exception as e:
            self.status = "FAILED"
            self.last_error = str(e)
            logger.warning(f"SSH Tunnel could not be established: {e}")
            self.stop_sync()
            return False

    def stop_sync(self):
        """Synchronously terminate SSH tunnel."""
        if self.tunnel:
            try:
                self.tunnel.stop()
            except Exception as e:
                logger.debug(f"Error stopping SSH tunnel: {e}")
            self.tunnel = None
        self.status = "DISCONNECTED"

    async def stop(self):
        """Asynchronously terminate SSH tunnel in thread."""
        await asyncio.to_thread(self.stop_sync)
        logger.info("SSH Tunnel disconnected.")

    def is_healthy(self) -> bool:
        if not settings.USE_SSH:
            return True
        return self.tunnel is not None and self.tunnel.is_active

    def get_status(self) -> Dict[str, Any]:
        return {
            "enabled": settings.USE_SSH,
            "status": self.status,
            "host": settings.SSH_HOST if settings.USE_SSH else None,
            "remote_port": settings.SSH_PORT if settings.USE_SSH else None,
            "local_bind_port": self.local_bind_port,
            "is_active": self.is_healthy(),
            "last_error": self.last_error
        }
