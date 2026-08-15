import hmac
import hashlib
import time
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Header, Request, status
from app.core.config import settings
from app.services.user_service import user_service
from app.services.activity_service import activity_service

logger = logging.getLogger("routers.auth")

router = APIRouter(prefix="/api/auth", tags=["Authentication & Access Control"])

# Predefined accounts and permissions
ROLE_PERMISSIONS = {
    "superuser": {
        "role_name": "Master Super User",
        "description": "Unrestricted master control across all IoT modules, system analytics, user management, and core middleware configuration.",
        "allowed_tabs": ["dashboard", "live-tables", "whitelist", "iot-maps", "alerts", "audit", "user-management", "analytics"]
    },
    "technical": {
        "role_name": "Technical Administrator",
        "description": "Full access to all system tabs, IoT deployment, live tables, and audit logs.",
        "allowed_tabs": ["dashboard", "live-tables", "whitelist", "iot-maps", "alerts", "audit"]
    },
    "staff": {
        "role_name": "Library Staff",
        "description": "Restricted operational access to circulation Dashboard, Security Whitelist, and Alerts.",
        "allowed_tabs": ["dashboard", "whitelist", "alerts"]
    }
}

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=100)

def generate_token(username: str, role: str) -> str:
    """Generate a signed auth token with expiration."""
    exp = int(time.time()) + (86400 * 7)  # 7 days
    payload = f"{username}:{role}:{exp}"
    sig = hmac.new(settings.SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"

def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify signed auth token."""
    try:
        parts = token.split(":")
        if len(parts) != 4:
            return None
        username, role, exp_str, sig = parts
        exp = int(exp_str)
        if time.time() > exp:
            return None
        payload = f"{username}:{role}:{exp}"
        expected_sig = hmac.new(settings.SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None
        return {"username": username, "role": role, "exp": exp}
    except Exception:
        return None

@router.post("/login", summary="User Login")
async def login(req: LoginRequest, request: Request):
    """Authenticate users and return signed session token with role permissions."""
    username = req.username.strip().lower()
    password = req.password.strip()
    client_ip = request.client.host if request.client else "127.0.0.1"
    user_agent = request.headers.get("user-agent", "Browser Client")

    user_info = user_service.get_user_for_auth(username)
    if not user_info or user_info.get("password") != password:
        logger.warning(f"Failed login attempt for username: {username}")
        activity_service.log_activity(
            username=username,
            role="unknown",
            action="AUTH_LOGIN_FAILED",
            category="auth",
            details=f"Invalid login credentials attempt from IP {client_ip}",
            ip_address=client_ip,
            user_agent=user_agent,
            status="FAILED"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    if user_info.get("status") == "disabled":
        logger.warning(f"Login rejected for disabled account: {username}")
        activity_service.log_activity(
            username=username,
            role=user_info.get("role", "staff"),
            action="AUTH_LOGIN_REJECTED",
            category="auth",
            details="Account is currently disabled by administrator",
            ip_address=client_ip,
            user_agent=user_agent,
            status="WARN"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been disabled. Please contact the Super User."
        )

    role = user_info["role"]
    perms = ROLE_PERMISSIONS.get(role, ROLE_PERMISSIONS["staff"])
    token = generate_token(username, role)

    # Record login in user service & activity service
    user_service.record_login(username, client_ip, user_agent)
    activity_service.log_activity(
        username=username,
        role=role,
        action="AUTH_LOGIN_SUCCESS",
        category="auth",
        details=f"User signed in successfully ({perms['role_name']})",
        ip_address=client_ip,
        user_agent=user_agent,
        status="SUCCESS"
    )

    logger.info(f"User '{username}' ({perms['role_name']}) logged in successfully.")

    return {
        "success": True,
        "token": token,
        "user": {
            "username": username,
            "name": user_info["name"],
            "role": role,
            "role_name": perms["role_name"],
            "allowed_tabs": perms["allowed_tabs"]
        }
    }

@router.get("/me", summary="Current User Profile")
async def get_current_user(authorization: Optional[str] = Header(None)):
    """Retrieve profile and allowed tab permissions for current token."""
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authorization header missing")
    
    token = authorization.replace("Bearer ", "").strip()
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    username = payload["username"]
    user_info = user_service.get_user_details(username) or {
        "name": username.capitalize(),
        "role": payload["role"],
        "email": ""
    }
    role = payload["role"]
    perms = ROLE_PERMISSIONS.get(role, ROLE_PERMISSIONS["staff"])

    return {
        "username": username,
        "name": user_info.get("name", username),
        "role": role,
        "role_name": perms["role_name"],
        "allowed_tabs": perms["allowed_tabs"]
    }

@router.post("/logout", summary="User Logout")
async def logout(request: Request, authorization: Optional[str] = Header(None)):
    """Sign out user session and update session uptime."""
    if authorization:
        token = authorization.replace("Bearer ", "").strip()
        payload = verify_token(token)
        if payload:
            user_service.record_logout(payload["username"])
            client_ip = request.client.host if request.client else "127.0.0.1"
            activity_service.log_activity(
                username=payload["username"],
                role=payload["role"],
                action="AUTH_LOGOUT",
                category="auth",
                details="User signed out cleanly",
                ip_address=client_ip,
                status="SUCCESS"
            )
    return {"success": True, "message": "Logged out successfully"}


