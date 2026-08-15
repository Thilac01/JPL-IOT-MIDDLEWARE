import os
import json
import time
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("services.user")

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
USERS_FILE = os.path.join(DATA_DIR, "users.json")

DEFAULT_USERS: Dict[str, Dict[str, Any]] = {
    "superuser": {
        "username": "superuser",
        "password": "superuser123",
        "role": "superuser",
        "name": "Chief Systems Architect / Super User",
        "email": "superuser@library.jpl.gov",
        "status": "active",
        "created_at": 1704067200,
        "last_login": None,
        "last_ip": None,
        "last_user_agent": None,
        "total_logins": 0,
        "session_uptime_seconds": 0,
        "last_heartbeat": 0,
        "current_session_start": None
    },
    "mwdep": {
        "username": "mwdep",
        "password": "Jaf@@mw1291",
        "role": "superuser",
        "name": "DevOps Administrator / Super User",
        "email": "mwdep@library.jpl.gov",
        "status": "active",
        "created_at": 1704067200,
        "last_login": None,
        "last_ip": None,
        "last_user_agent": None,
        "total_logins": 0,
        "session_uptime_seconds": 0,
        "last_heartbeat": 0,
        "current_session_start": None
    },
    "admin": {
        "username": "admin",
        "password": "admin123",
        "role": "technical",
        "name": "Technical Administrator",
        "email": "admin@library.jpl.gov",
        "status": "active",
        "created_at": 1704067200,
        "last_login": None,
        "last_ip": None,
        "last_user_agent": None,
        "total_logins": 0,
        "session_uptime_seconds": 0,
        "last_heartbeat": 0,
        "current_session_start": None
    },
    "tech": {
        "username": "tech",
        "password": "tech123",
        "role": "technical",
        "name": "IoT Systems Engineer",
        "email": "engineer@library.jpl.gov",
        "status": "active",
        "created_at": 1704067200,
        "last_login": None,
        "last_ip": None,
        "last_user_agent": None,
        "total_logins": 0,
        "session_uptime_seconds": 0,
        "last_heartbeat": 0,
        "current_session_start": None
    },
    "staff": {
        "username": "staff",
        "password": "staff123",
        "role": "staff",
        "name": "Circulation Desk Staff",
        "email": "staff@library.jpl.gov",
        "status": "active",
        "created_at": 1704067200,
        "last_login": None,
        "last_ip": None,
        "last_user_agent": None,
        "total_logins": 0,
        "session_uptime_seconds": 0,
        "last_heartbeat": 0,
        "current_session_start": None
    },
    "librarian": {
        "username": "librarian",
        "password": "staff123",
        "role": "staff",
        "name": "Branch Librarian",
        "email": "librarian@library.jpl.gov",
        "status": "active",
        "created_at": 1704067200,
        "last_login": None,
        "last_ip": None,
        "last_user_agent": None,
        "total_logins": 0,
        "session_uptime_seconds": 0,
        "last_heartbeat": 0,
        "current_session_start": None
    },
    "library": {
        "username": "library",
        "password": "library123",
        "role": "staff",
        "name": "Library Assistant",
        "email": "assistant@library.jpl.gov",
        "status": "active",
        "created_at": 1704067200,
        "last_login": None,
        "last_ip": None,
        "last_user_agent": None,
        "total_logins": 0,
        "session_uptime_seconds": 0,
        "last_heartbeat": 0,
        "current_session_start": None
    }
}

class UserService:
    def __init__(self):
        self.users: Dict[str, Dict[str, Any]] = {}
        self._ensure_storage()
        self.load_users()

    def _ensure_storage(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        if not os.path.exists(USERS_FILE):
            try:
                with open(USERS_FILE, "w", encoding="utf-8") as f:
                    json.dump(DEFAULT_USERS, f, indent=2)
                logger.info(f"Initialized default users database at {USERS_FILE}")
            except Exception as e:
                logger.error(f"Failed to create users file: {e}")

    def load_users(self):
        if os.path.exists(USERS_FILE):
            try:
                with open(USERS_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    # Merge with default users so superuser & mwdep are guaranteed
                    self.users = {**DEFAULT_USERS, **loaded}
                logger.info(f"Loaded {len(self.users)} users from storage.")
                return
            except Exception as e:
                logger.error(f"Error loading users from file, using in-memory defaults: {e}")
        self.users = {k: dict(v) for k, v in DEFAULT_USERS.items()}

    def _save_users(self):
        try:
            with open(USERS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.users, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save users to file: {e}")

    def get_all_users(self) -> List[Dict[str, Any]]:
        """Return list of public user profiles with uptime and live status."""
        now = time.time()
        result = []
        for u in self.users.values():
            user_copy = dict(u)
            # Calculate online status (heartbeat within last 45 seconds)
            last_hb = user_copy.get("last_heartbeat") or 0
            is_online = (now - last_hb) < 45 if last_hb > 0 else False
            user_copy["is_online"] = is_online
            
            # Dynamic current session uptime calculation
            session_start = user_copy.get("current_session_start")
            current_uptime = user_copy.get("session_uptime_seconds", 0)
            if is_online and session_start:
                current_uptime += int(now - session_start)
            user_copy["session_uptime_seconds"] = current_uptime
            
            # Strip password from public listing
            user_copy.pop("password", None)
            result.append(user_copy)
        return result

    def get_user_for_auth(self, username: str) -> Optional[Dict[str, Any]]:
        """Fetch user record including password for authentication."""
        clean_user = username.strip().lower()
        return self.users.get(clean_user)

    def get_user_details(self, username: str) -> Optional[Dict[str, Any]]:
        """Get single user profile without password."""
        clean_user = username.strip().lower()
        u = self.users.get(clean_user)
        if not u:
            return None
        user_copy = dict(u)
        user_copy.pop("password", None)
        now = time.time()
        last_hb = user_copy.get("last_heartbeat") or 0
        user_copy["is_online"] = (now - last_hb) < 45 if last_hb > 0 else False
        return user_copy

    def create_user(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new user account."""
        username = data.get("username", "").strip().lower()
        if not username:
            raise ValueError("Username is required")
        if username in self.users:
            raise ValueError(f"User '{username}' already exists")
        
        password = data.get("password", "").strip()
        if not password:
            raise ValueError("Password is required")

        role = data.get("role", "staff").strip().lower()
        if role not in ["superuser", "technical", "staff"]:
            role = "staff"

        new_user = {
            "username": username,
            "password": password,
            "role": role,
            "name": data.get("name", username.capitalize()).strip(),
            "email": data.get("email", f"{username}@library.jpl.gov").strip(),
            "status": data.get("status", "active"),
            "created_at": int(time.time()),
            "last_login": None,
            "last_ip": None,
            "last_user_agent": None,
            "total_logins": 0,
            "session_uptime_seconds": 0,
            "last_heartbeat": 0,
            "current_session_start": None
        }

        self.users[username] = new_user
        self._save_users()
        logger.info(f"Created new user '{username}' with role '{role}'")
        
        resp = dict(new_user)
        resp.pop("password", None)
        return resp

    def update_user(self, username: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update existing user profile, role, or status."""
        clean_user = username.strip().lower()
        if clean_user not in self.users:
            raise ValueError(f"User '{clean_user}' not found")
        
        user = self.users[clean_user]
        
        if "name" in data and data["name"]:
            user["name"] = data["name"].strip()
        if "email" in data and data["email"]:
            user["email"] = data["email"].strip()
        if "role" in data and data["role"] in ["superuser", "technical", "staff"]:
            # Prevent demoting the last superuser
            if user["role"] == "superuser" and data["role"] != "superuser":
                super_count = sum(1 for u in self.users.values() if u.get("role") == "superuser" and u.get("status") == "active")
                if super_count <= 1:
                    raise ValueError("Cannot demote the only remaining active Super User")
            user["role"] = data["role"]
        if "status" in data and data["status"] in ["active", "disabled"]:
            if user["role"] == "superuser" and data["status"] == "disabled":
                super_count = sum(1 for u in self.users.values() if u.get("role") == "superuser" and u.get("status") == "active")
                if super_count <= 1:
                    raise ValueError("Cannot disable the only remaining active Super User")
            user["status"] = data["status"]
        if "password" in data and data["password"]:
            user["password"] = data["password"].strip()

        self._save_users()
        logger.info(f"Updated user '{clean_user}'")
        resp = dict(user)
        resp.pop("password", None)
        return resp

    def delete_user(self, username: str) -> bool:
        """Delete user account with safety checks."""
        clean_user = username.strip().lower()
        if clean_user not in self.users:
            raise ValueError(f"User '{clean_user}' not found")
        
        # Safeguard: Never delete the last active superuser
        user = self.users[clean_user]
        if user.get("role") == "superuser":
            super_count = sum(1 for u in self.users.values() if u.get("role") == "superuser")
            if super_count <= 1:
                raise ValueError("Cannot delete the only Super User in the system")

        del self.users[clean_user]
        self._save_users()
        logger.info(f"Deleted user '{clean_user}'")
        return True

    def reset_password(self, username: str, new_pass: str) -> bool:
        """Reset a user's password."""
        clean_user = username.strip().lower()
        if clean_user not in self.users:
            raise ValueError(f"User '{clean_user}' not found")
        if not new_pass or len(new_pass.strip()) < 3:
            raise ValueError("Password must be at least 3 characters")
        
        self.users[clean_user]["password"] = new_pass.strip()
        self._save_users()
        logger.info(f"Password reset for user '{clean_user}'")
        return True

    def record_login(self, username: str, ip: Optional[str] = None, user_agent: Optional[str] = None):
        """Update login timestamp, login count, and start session timer."""
        clean_user = username.strip().lower()
        if clean_user in self.users:
            now = int(time.time())
            u = self.users[clean_user]
            u["last_login"] = now
            u["last_ip"] = ip or "127.0.0.1"
            u["last_user_agent"] = user_agent or "Unknown"
            u["total_logins"] = (u.get("total_logins") or 0) + 1
            u["current_session_start"] = now
            u["last_heartbeat"] = now
            self._save_users()

    def record_logout(self, username: str):
        """Update session uptime upon logout."""
        clean_user = username.strip().lower()
        if clean_user in self.users:
            now = int(time.time())
            u = self.users[clean_user]
            start = u.get("current_session_start")
            if start:
                elapsed = now - start
                u["session_uptime_seconds"] = (u.get("session_uptime_seconds") or 0) + max(0, elapsed)
            u["current_session_start"] = None
            u["last_heartbeat"] = 0
            self._save_users()

    def record_heartbeat(self, username: str):
        """Periodic heartbeat from client to track live presence and uptime."""
        clean_user = username.strip().lower()
        if clean_user in self.users:
            now = int(time.time())
            u = self.users[clean_user]
            if not u.get("current_session_start"):
                u["current_session_start"] = now
            u["last_heartbeat"] = now

    def get_user_stats(self) -> Dict[str, Any]:
        """Aggregate user counts, role breakdown, and online metrics."""
        all_users = self.get_all_users()
        now = time.time()
        
        total = len(all_users)
        online = sum(1 for u in all_users if u.get("is_online"))
        superusers = sum(1 for u in all_users if u.get("role") == "superuser")
        technical = sum(1 for u in all_users if u.get("role") == "technical")
        staff = sum(1 for u in all_users if u.get("role") == "staff")
        active = sum(1 for u in all_users if u.get("status") == "active")
        disabled = sum(1 for u in all_users if u.get("status") == "disabled")
        
        total_logins = sum(u.get("total_logins", 0) for u in all_users)
        total_uptime_seconds = sum(u.get("session_uptime_seconds", 0) for u in all_users)

        return {
            "total_users": total,
            "online_users": online,
            "active_users": active,
            "disabled_users": disabled,
            "role_distribution": {
                "superuser": superusers,
                "technical": technical,
                "staff": staff
            },
            "total_logins_all_time": total_logins,
            "total_user_uptime_seconds": total_uptime_seconds
        }

user_service = UserService()
