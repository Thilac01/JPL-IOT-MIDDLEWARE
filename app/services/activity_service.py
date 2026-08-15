import os
import json
import time
import uuid
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
import psutil

logger = logging.getLogger("services.activity")

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
ACTIVITY_FILE = os.path.join(DATA_DIR, "user_activity.json")
MAX_LOG_ENTRIES = 3000

class ActivityService:
    def __init__(self):
        self.activities: List[Dict[str, Any]] = []
        self._ensure_storage()
        self.load_activities()

    def _ensure_storage(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        if not os.path.exists(ACTIVITY_FILE):
            # Seed with initial system startup activity
            initial = [
                {
                    "id": str(uuid.uuid4())[:8],
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "epoch": int(time.time()),
                    "username": "system",
                    "role": "system",
                    "action": "SYSTEM_STARTUP",
                    "category": "system",
                    "details": "JPL Middleware Kernel initialized with Super User subsystem.",
                    "ip_address": "127.0.0.1",
                    "user_agent": "System Daemon",
                    "status": "SUCCESS"
                }
            ]
            try:
                with open(ACTIVITY_FILE, "w", encoding="utf-8") as f:
                    json.dump(initial, f, indent=2)
            except Exception as e:
                logger.error(f"Failed to create activity file: {e}")

    def load_activities(self):
        if os.path.exists(ACTIVITY_FILE):
            try:
                with open(ACTIVITY_FILE, "r", encoding="utf-8") as f:
                    self.activities = json.load(f)
                logger.info(f"Loaded {len(self.activities)} activity log entries.")
                return
            except Exception as e:
                logger.error(f"Error loading activities from file: {e}")
        self.activities = []

    def _save_activities(self):
        try:
            with open(ACTIVITY_FILE, "w", encoding="utf-8") as f:
                json.dump(self.activities, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save activities to file: {e}")

    def log_activity(
        self,
        username: str,
        role: str,
        action: str,
        category: str = "system",
        details: str = "",
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        status: str = "SUCCESS"
    ) -> Dict[str, Any]:
        """Record an activity event."""
        now_epoch = int(time.time())
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        entry = {
            "id": str(uuid.uuid4())[:8],
            "timestamp": now_str,
            "epoch": now_epoch,
            "username": username or "anonymous",
            "role": role or "staff",
            "action": action,
            "category": category,
            "details": details,
            "ip_address": ip_address or "127.0.0.1",
            "user_agent": (user_agent[:80] + "...") if user_agent and len(user_agent) > 80 else (user_agent or "Web Client"),
            "status": status
        }

        # Prepend so newest is first
        self.activities.insert(0, entry)

        # Cap log length to prevent unbounded growth
        if len(self.activities) > MAX_LOG_ENTRIES:
            self.activities = self.activities[:MAX_LOG_ENTRIES]

        self._save_activities()
        logger.debug(f"Activity logged: [{category.upper()}] {username} -> {action}: {details}")
        return entry

    def get_activities(
        self,
        limit: int = 50,
        offset: int = 0,
        username: Optional[str] = None,
        category: Optional[str] = None,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """Filter, search, and paginate user activities."""
        filtered = self.activities

        if username:
            u_clean = username.strip().lower()
            filtered = [a for a in filtered if a.get("username", "").lower() == u_clean]

        if category and category.lower() != "all":
            c_clean = category.strip().lower()
            filtered = [a for a in filtered if a.get("category", "").lower() == c_clean]

        if search:
            s_clean = search.strip().lower()
            filtered = [
                a for a in filtered
                if s_clean in a.get("username", "").lower()
                or s_clean in a.get("action", "").lower()
                or s_clean in a.get("details", "").lower()
                or s_clean in a.get("ip_address", "").lower()
            ]

        total = len(filtered)
        paginated = filtered[offset:offset + limit]

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "activities": paginated
        }

    def clear_activities(self) -> bool:
        """Clear log history (superuser only) keeping a single reset entry."""
        self.activities = [
            {
                "id": str(uuid.uuid4())[:8],
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "epoch": int(time.time()),
                "username": "superuser",
                "role": "superuser",
                "action": "LOGS_CLEARED",
                "category": "system",
                "details": "Activity log history was cleared by Super User.",
                "ip_address": "127.0.0.1",
                "user_agent": "Web Console",
                "status": "SUCCESS"
            }
        ]
        self._save_activities()
        return True

    def get_analytics_data(self) -> Dict[str, Any]:
        """Generate aggregated time series, category breakdowns, and performance metrics for Chart.js."""
        now = time.time()
        
        # 1. Hourly activity timeline (last 24 hours)
        hours_labels = []
        hourly_logins = []
        hourly_actions = []
        hourly_errors = []

        for i in range(23, -1, -1):
            h_time = now - (i * 3600)
            h_dt = datetime.fromtimestamp(h_time)
            h_label = h_dt.strftime("%H:00")
            hours_labels.append(h_label)
            
            # Match logs in this hour bucket
            bucket_start = int(h_dt.replace(minute=0, second=0, microsecond=0).timestamp())
            bucket_end = bucket_start + 3600

            in_bucket = [
                a for a in self.activities
                if bucket_start <= a.get("epoch", 0) < bucket_end
            ]

            logins = sum(1 for a in in_bucket if "LOGIN" in a.get("action", "").upper())
            actions = sum(1 for a in in_bucket if "LOGIN" not in a.get("action", "").upper() and a.get("status") == "SUCCESS")
            errors = sum(1 for a in in_bucket if a.get("status") in ["FAILED", "WARN", "ERROR"])

            hourly_logins.append(logins)
            hourly_actions.append(actions)
            hourly_errors.append(errors)

        # 2. Activity Category Breakdown
        categories = {}
        for a in self.activities:
            cat = a.get("category", "other").capitalize()
            categories[cat] = categories.get(cat, 0) + 1

        # 3. Real Top Active Users
        from app.services.user_service import user_service
        users_list = user_service.get_all_users()
        
        # Calculate real combined score (logins + logged activities)
        user_scores = {}
        for u in users_list:
            uname = u.get("username", "")
            user_scores[uname] = u.get("total_logins", 0)

        for a in self.activities:
            uname = a.get("username", "")
            if uname and uname != "system":
                user_scores[uname] = user_scores.get(uname, 0) + 1

        top_users_sorted = sorted(user_scores.items(), key=lambda x: x[1], reverse=True)[:8]

        # 4. Live System Performance Telemetry from OS
        try:
            mem = psutil.virtual_memory()
            cpu = psutil.cpu_percent(interval=None)
            mem_used_mb = round(mem.used / (1024 * 1024), 1)
            mem_total_mb = round(mem.total / (1024 * 1024), 1)
            mem_pct = mem.percent
        except Exception:
            cpu = 0.0
            mem_used_mb = 0.0
            mem_total_mb = 0.0
            mem_pct = 0.0

        return {
            "timeline": {
                "labels": hours_labels,
                "logins": hourly_logins,
                "actions": hourly_actions,
                "errors": hourly_errors
            },
            "category_distribution": categories,
            "top_users": {
                "labels": [u[0] for u in top_users_sorted],
                "data": [u[1] for u in top_users_sorted]
            },
            "system_telemetry": {
                "cpu_percent": cpu,
                "memory_used_mb": mem_used_mb,
                "memory_total_mb": mem_total_mb,
                "memory_percent": mem_pct
            }
        }

activity_service = ActivityService()

