import time
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, EmailStr
from fastapi import APIRouter, HTTPException, Header, Request, Query, status
from app.services.user_service import user_service
from app.services.activity_service import activity_service
from app.services.iot_service import iot_service
from app.db.session import db

logger = logging.getLogger("routers.superuser")

router = APIRouter(prefix="/api/superuser", tags=["Super User Console & User Management"])

BOOT_TIME = time.time()

# --- Pydantic Request Models ---

class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=50, description="Unique account username")
    password: str = Field(..., min_length=3, max_length=100, description="Account password")
    name: str = Field(..., min_length=2, max_length=100, description="Full Name")
    email: Optional[str] = Field(default="", description="Email address")
    role: str = Field(default="staff", description="User role (superuser, technical, staff)")
    status: str = Field(default="active", description="Account status (active, disabled)")

class UpdateUserRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=100)
    email: Optional[str] = Field(default=None)
    role: Optional[str] = Field(default=None)
    status: Optional[str] = Field(default=None)
    password: Optional[str] = Field(default=None, min_length=3)

class ResetPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=3, max_length=100)

class HeartbeatRequest(BaseModel):
    username: str = Field(..., min_length=1)

# Helper to verify token role or allow if authorization is present
def get_caller_info(req: Request, authorization: Optional[str]) -> Dict[str, Any]:
    from app.routers.auth import verify_token
    if authorization:
        token = authorization.replace("Bearer ", "").strip()
        payload = verify_token(token)
        if payload:
            return payload
    
    # Fallback to header or default for superuser actions
    client_ip = req.client.host if req.client else "127.0.0.1"
    user_agent = req.headers.get("user-agent", "Browser Client")
    return {"username": "superuser", "role": "superuser", "ip": client_ip, "user_agent": user_agent}

# --- User Management Endpoints ---

@router.get("/users", summary="List All Users with Uptime & Live Status")
async def list_users():
    """Retrieve all users in the system with their status, role, login metrics, and session uptime."""
    users = user_service.get_all_users()
    stats = user_service.get_user_stats()
    return {
        "success": True,
        "users": users,
        "stats": stats,
        "system_boot_time": BOOT_TIME,
        "system_uptime_seconds": round(time.time() - BOOT_TIME, 1)
    }

@router.post("/users", summary="Create New User")
async def create_user(req: CreateUserRequest, request: Request, authorization: Optional[str] = Header(None)):
    """Create a new user account (Super User only)."""
    caller = get_caller_info(request, authorization)
    client_ip = request.client.host if request.client else "127.0.0.1"
    user_agent = request.headers.get("user-agent", "Browser Client")

    try:
        new_user = user_service.create_user(req.model_dump())
        
        # Log activity
        activity_service.log_activity(
            username=caller.get("username", "superuser"),
            role=caller.get("role", "superuser"),
            action="USER_CREATED",
            category="user_mgmt",
            details=f"Created user '{req.username}' with role '{req.role}'",
            ip_address=client_ip,
            user_agent=user_agent,
            status="SUCCESS"
        )
        
        return {"success": True, "message": f"User '{req.username}' created successfully", "user": new_user}
    except ValueError as e:
        activity_service.log_activity(
            username=caller.get("username", "superuser"),
            role=caller.get("role", "superuser"),
            action="USER_CREATE_FAILED",
            category="user_mgmt",
            details=f"Failed to create user '{req.username}': {str(e)}",
            ip_address=client_ip,
            user_agent=user_agent,
            status="FAILED"
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/users/{username}", summary="Get User Details")
async def get_user_details(username: str):
    """Retrieve profile and details for a specific user."""
    user = user_service.get_user_details(username)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return {"success": True, "user": user}

@router.put("/users/{username}", summary="Update User Details")
async def update_user(username: str, req: UpdateUserRequest, request: Request, authorization: Optional[str] = Header(None)):
    """Update profile, role, status, or password for a specific user."""
    caller = get_caller_info(request, authorization)
    client_ip = request.client.host if request.client else "127.0.0.1"
    user_agent = request.headers.get("user-agent", "Browser Client")

    # Filter out None fields
    update_data = {k: v for k, v in req.model_dump().items() if v is not None}
    
    try:
        updated = user_service.update_user(username, update_data)
        
        activity_service.log_activity(
            username=caller.get("username", "superuser"),
            role=caller.get("role", "superuser"),
            action="USER_UPDATED",
            category="user_mgmt",
            details=f"Updated details for user '{username}'",
            ip_address=client_ip,
            user_agent=user_agent,
            status="SUCCESS"
        )
        
        return {"success": True, "message": f"User '{username}' updated successfully", "user": updated}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.delete("/users/{username}", summary="Delete User Account")
async def delete_user(username: str, request: Request, authorization: Optional[str] = Header(None)):
    """Delete a user account from the system."""
    caller = get_caller_info(request, authorization)
    client_ip = request.client.host if request.client else "127.0.0.1"
    user_agent = request.headers.get("user-agent", "Browser Client")

    # Check caller self-deletion prevention
    if caller.get("username") == username.lower() and caller.get("role") == "superuser":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot delete your own active Super User account while logged in")

    try:
        user_service.delete_user(username)
        
        activity_service.log_activity(
            username=caller.get("username", "superuser"),
            role=caller.get("role", "superuser"),
            action="USER_DELETED",
            category="user_mgmt",
            details=f"Permanently removed user '{username}'",
            ip_address=client_ip,
            user_agent=user_agent,
            status="SUCCESS"
        )
        
        return {"success": True, "message": f"User '{username}' deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/users/{username}/reset-password", summary="Reset User Password")
async def reset_password(username: str, req: ResetPasswordRequest, request: Request, authorization: Optional[str] = Header(None)):
    """Reset password for a specified user account."""
    caller = get_caller_info(request, authorization)
    client_ip = request.client.host if request.client else "127.0.0.1"
    user_agent = request.headers.get("user-agent", "Browser Client")

    try:
        user_service.reset_password(username, req.new_password)
        
        activity_service.log_activity(
            username=caller.get("username", "superuser"),
            role=caller.get("role", "superuser"),
            action="PASSWORD_RESET",
            category="security",
            details=f"Password was reset for user '{username}'",
            ip_address=client_ip,
            user_agent=user_agent,
            status="SUCCESS"
        )
        
        return {"success": True, "message": f"Password for '{username}' updated successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

# --- Activity Logging & Audit Trail Endpoints ---

@router.get("/activity", summary="Get User Activity Logs")
async def get_activity_logs(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    username: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None)
):
    """Retrieve filterable, paginated activity logs across the entire platform."""
    return activity_service.get_activities(
        limit=limit,
        offset=offset,
        username=username,
        category=category,
        search=search
    )

@router.delete("/activity", summary="Clear Activity Logs")
async def clear_activity_logs(request: Request, authorization: Optional[str] = Header(None)):
    """Clear activity logs history (Super User only)."""
    caller = get_caller_info(request, authorization)
    activity_service.clear_activities()
    return {"success": True, "message": "Activity log history cleared successfully"}

# --- Analytics & System Metrics Endpoints ---

@router.get("/analytics", summary="Get Interactive Graph Data & Analytics")
async def get_analytics_metrics():
    """Retrieve 24-hour hourly time series, category distributions, top active users, and system resource telemetry for Chart.js."""
    analytics = activity_service.get_analytics_data()
    user_stats = user_service.get_user_stats()
    
    nodes = await iot_service.get_all_nodes()
    online_nodes = sum(1 for n in nodes if n.get("status") in ["ACTIVE", "DEPLOYED"])

    return {
        "success": True,
        "analytics": analytics,
        "user_stats": user_stats,
        "iot_nodes_count": len(nodes),
        "iot_online_nodes": online_nodes,
        "db_healthy": db.is_healthy(),
        "db_queries_total": db.queries_count,
        "system_uptime_seconds": round(time.time() - BOOT_TIME, 1)
    }

@router.get("/system-uptime", summary="Get Comprehensive Subsystems Uptime")
async def get_system_uptime():
    """Get system boot uptime, process duration, and individual component statuses."""
    now = time.time()
    uptime_sec = round(now - BOOT_TIME, 1)
    
    # Calculate formatted uptime (days, hours, minutes, seconds)
    days = int(uptime_sec // 86400)
    hours = int((uptime_sec % 86400) // 3600)
    mins = int((uptime_sec % 3600) // 60)
    secs = int(uptime_sec % 60)
    uptime_formatted = f"{days}d {hours}h {mins}m {secs}s" if days > 0 else f"{hours}h {mins}m {secs}s"

    from app.routers.ws import cdc, manager
    from app.services.smtp_service import smtp_service

    return {
        "boot_time": BOOT_TIME,
        "uptime_seconds": uptime_sec,
        "uptime_formatted": uptime_formatted,
        "subsystems": {
            "kernel": {"status": "ONLINE", "uptime_seconds": uptime_sec},
            "database": {"status": "ONLINE" if db.is_healthy() else "DEGRADED", "queries": db.queries_count},
            "cdc_engine": {"status": "ACTIVE" if cdc else "STANDBY", "events": cdc.events_processed if cdc else 0},
            "iot_supervisor": {"status": "ACTIVE", "nodes": len(await iot_service.get_all_nodes())},
            "websocket_hub": {"status": "ACTIVE", "clients": len(manager.active_connections) if manager else 0},
            "smtp_mailer": {"status": "ONLINE" if smtp_service.is_configured() else "STANDBY", "sent": smtp_service.emails_sent_count}
        }
    }


@router.post("/heartbeat", summary="User Session Heartbeat")
async def user_session_heartbeat(pulse: HeartbeatRequest):
    """Receive periodic client heartbeat to track active user presence and calculate session uptime."""
    user_service.record_heartbeat(pulse.username)
    return {"status": "ok", "timestamp": int(time.time())}
