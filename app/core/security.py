from typing import Optional
from fastapi import Header, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from app.core.config import settings

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def verify_api_key(api_key: Optional[str] = Security(api_key_header)) -> Optional[str]:
    """
    Validate incoming API Key if configured in settings.
    If settings.API_KEY is None, access is permitted (open dev/intranet mode).
    If settings.API_KEY is configured, requests must supply a matching X-API-Key header.
    """
    if not settings.API_KEY:
        return None  # Open access mode

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key required in 'X-API-Key' header",
            headers={"WWW-Authenticate": "ApiKey"}
        )

    if api_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API Key"
        )

    return api_key
