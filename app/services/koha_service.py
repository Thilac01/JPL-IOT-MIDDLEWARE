import logging
from typing import Any, Dict, List, Optional
import httpx
from app.core.config import settings

logger = logging.getLogger("services.koha")

class KohaService:
    def __init__(self):
        self.base_url = settings.KOHA_API_BASE.rstrip("/")
        self.timeout = settings.KOHA_API_TIMEOUT
        self._access_token: Optional[str] = None

    def is_configured(self) -> bool:
        return bool(settings.KOHA_API_BASE)

    async def get_client(self) -> httpx.AsyncClient:
        headers = {"Accept": "application/json"}
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        return httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout, headers=headers)

    async def fetch_biblios(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch catalog bibliographic records from Koha REST API."""
        if not self.is_configured():
            return []
        try:
            async with await self.get_client() as client:
                resp = await client.get("/biblios", params={"_per_page": limit})
                if resp.status_code == 200:
                    return resp.json()
                logger.warning(f"Koha API /biblios returned {resp.status_code}: {resp.text[:100]}")
                return []
        except Exception as e:
            logger.debug(f"Koha API fetch error: {e}")
            return []

    async def fetch_patrons(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch patron records from Koha REST API."""
        if not self.is_configured():
            return []
        try:
            async with await self.get_client() as client:
                resp = await client.get("/patrons", params={"_per_page": limit})
                if resp.status_code == 200:
                    return resp.json()
                return []
        except Exception as e:
            logger.debug(f"Koha API fetch patrons error: {e}")
            return []

koha_service = KohaService()
