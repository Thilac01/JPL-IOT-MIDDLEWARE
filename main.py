import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging
from app.db.session import db
from app.services.iot_service import iot_service
from app.routers.ws import manager, cdc, router as ws_router
from app.routers.health import router as health_router
from app.routers.circulation import router as circulation_router
from app.routers.tables import router as tables_router
from app.routers.iot import router as iot_router
from app.routers.auth import router as auth_router
from app.routers.superuser import router as superuser_router
from app.middleware.correlation import CorrelationIdMiddleware
from app.middleware.security import SecurityHeadersMiddleware
from app.middleware.error_handler import register_error_handlers

# Initialize structured enterprise logging
setup_logging()
logger = logging.getLogger("main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup Lifecycle ---
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION} [{settings.ENVIRONMENT.upper()}]...")
    
    # 1. Initialize Database and Resilience Worker
    try:
        await db.initialize()
    except Exception as e:
        logger.error(f"Database initialization error: {e}")

    # 2. Initialize IoT Node Supervisor
    try:
        await iot_service.initialize()
    except Exception as e:
        logger.error(f"IoT service initialization error: {e}")

    # 3. Start CDC Engine / Simulation Fallback
    try:
        await cdc.start()
        logger.info("CDC Replication / Fallback Engine started.")
    except Exception as e:
        logger.error(f"CDC startup error: {e}")

    logger.info("JPL Middleware fully online and ready for traffic.")
    yield

    # --- Shutdown Lifecycle ---
    logger.info("Initiating graceful shutdown of JPL Middleware...")
    try:
        cdc.stop()
    except Exception as e:
        logger.error(f"Error stopping CDC engine: {e}")

    try:
        await iot_service.stop()
    except Exception as e:
        logger.error(f"Error stopping IoT service: {e}")

    try:
        await db.disconnect()
    except Exception as e:
        logger.error(f"Error disconnecting database: {e}")

    logger.info("JPL Middleware shut down cleanly.")

# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Industrial IoT and Change Data Capture Middleware for Library Automation & Physical Security Gates",
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production or settings.DEBUG else "/api/docs",
    redoc_url="/redoc" if not settings.is_production or settings.DEBUG else None
)

# 1. Correlation ID Middleware (First in stack)
app.add_middleware(CorrelationIdMiddleware)

# 2. Security Headers Middleware
app.add_middleware(SecurityHeadersMiddleware)

# 3. CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS if isinstance(settings.CORS_ORIGINS, list) else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 4. Standardized JSON Error Handlers
register_error_handlers(app)

# 5. Attach Routers
app.include_router(health_router)
app.include_router(circulation_router)
app.include_router(tables_router)
app.include_router(iot_router)
app.include_router(ws_router)
app.include_router(auth_router)
app.include_router(superuser_router)


# 6. Mount Static Frontend if directory exists
if os.path.isdir("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.DEBUG or not settings.is_production,
        log_level=settings.LOG_LEVEL.lower()
    )
