"""API Routers package."""
from app.routers.health import router as health_router
from app.routers.circulation import router as circulation_router
from app.routers.tables import router as tables_router
from app.routers.iot import router as iot_router
from app.routers.ws import router as ws_router
from app.routers.auth import router as auth_router
from app.routers.superuser import router as superuser_router

__all__ = ["health_router", "circulation_router", "tables_router", "iot_router", "ws_router", "auth_router", "superuser_router"]

