import os
import time
import psutil
from fastapi import APIRouter, Response, status
from app.core.config import settings
from app.db.session import db
from app.services.smtp_service import smtp_service
from app.services.iot_service import iot_service

router = APIRouter(tags=["Health & Diagnostics"])

START_TIME = time.time()

@router.get("/healthz", summary="Liveness Probe")
async def liveness_probe():
    """Kubernetes / Docker lightweight liveness probe."""
    return {"status": "ok", "uptime_seconds": round(time.time() - START_TIME, 2)}

@router.get("/ready", summary="Readiness Probe")
async def readiness_probe(response: Response):
    """Readiness probe indicating if the service is ready to accept traffic."""
    is_ready = db.is_healthy()
    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unavailable", "reason": "Database connection not ready"}
    return {"status": "ready"}

@router.get("/api/health", summary="Detailed Diagnostic Health")
async def full_health_diagnostic():
    """Comprehensive health and diagnostic status of all subsystems."""
    try:
        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()
        mem_mb = round(mem_info.rss / (1024 * 1024), 2)
        cpu_percent = process.cpu_percent(interval=None)
    except Exception:
        mem_mb = -1
        cpu_percent = -1

    nodes = await iot_service.get_all_nodes()

    # Read CDC health if active
    cdc_health = {}
    from app.routers.ws import cdc
    if cdc:
        cdc_health = cdc.get_health()

    return {
        "status": "HEALTHY" if db.is_healthy() else "DEGRADED",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "uptime_seconds": round(time.time() - START_TIME, 2),
        "database": db.get_health(),
        "cdc": cdc_health,
        "smtp": smtp_service.get_health(),
        "iot": {
            "total_nodes": len(nodes),
            "online_nodes": sum(1 for n in nodes if n.get("status") in ["ACTIVE", "DEPLOYED"]),
        },
        "system": {
            "memory_rss_mb": mem_mb,
            "cpu_percent": cpu_percent
        }
    }

@router.get("/api/metrics", summary="Operational Metrics")
async def operational_metrics():
    """Aggregated operational metrics for Prometheus/monitoring scrapers."""
    from app.routers.ws import manager, cdc
    return {
        "app_uptime_seconds": round(time.time() - START_TIME, 2),
        "db_queries_total": db.queries_count,
        "db_queries_failed_total": db.failed_queries_count,
        "db_pool_size": db.pool.size if db.pool else 0,
        "db_pool_free": db.pool.freesize if db.pool else 0,
        "cdc_events_processed_total": cdc.events_processed if cdc else 0,
        "ws_active_connections": len(manager.active_connections) if manager else 0,
        "smtp_emails_sent_total": smtp_service.emails_sent_count,
        "smtp_emails_failed_total": smtp_service.failed_emails_count
    }
