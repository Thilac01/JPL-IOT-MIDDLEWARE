import json
import logging
from typing import Any, List, Optional, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

# Load environment file if present
load_dotenv()

logger = logging.getLogger("config")

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False
    )

    # --- Application Settings ---
    APP_NAME: str = "JPL Security & IoT Middleware"
    APP_VERSION: str = "2.5.0"
    ENVIRONMENT: str = "production"  # production, staging, development, test
    DEBUG: bool = False
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    SECRET_KEY: str = Field(
        default="b95f517f43f0b42c15000dcfb9165a9296f2b5bd1e5a58dfc0bc12d1e29cfbcc",
        description="Cryptographic secret key for session signing and hashing"
    )
    API_KEY: Optional[str] = Field(
        default=None,
        description="Optional API Key required for privileged and IoT control endpoints"
    )
    LOG_LEVEL: str = "INFO"
    LOG_FILE: Optional[str] = "logs/middleware.log"
    LOG_ROTATION_BYTES: int = 10 * 1024 * 1024  # 10 MB
    LOG_BACKUP_COUNT: int = 5
    CORS_ORIGINS: Union[List[str], str] = ["*"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [item.strip() for item in v.split(",") if item.strip()]
        elif isinstance(v, (list, set, tuple)):
            return list(v)
        return ["*"]


    # --- SSH Tunnel Settings ---
    USE_SSH: bool = True
    SSH_HOST: str = "137.184.15.52"
    SSH_PORT: int = 22
    SSH_USER: str = "root"
    SSH_PASSWORD: Optional[str] = None
    SSH_PKEY: Optional[str] = None
    SSH_TIMEOUT: int = 8
    SSH_KEEPALIVE: int = 30

    # --- MySQL Replica Database Settings ---
    REPLICA_HOST: str = "127.0.0.1"
    REPLICA_PORT: int = 3307
    REPLICA_USER: str = "root"
    REPLICA_PASSWORD: Optional[str] = None
    REPLICA_DB: str = "koha_library"
    SECURITY_DB: str = "jpl_security_monitor"

    # Connection Pool configuration
    DB_POOL_MIN_SIZE: int = 2
    DB_POOL_MAX_SIZE: int = 15
    DB_POOL_RECYCLE: int = 300
    DB_CONNECT_TIMEOUT: int = 10
    DB_RECONNECT_INTERVAL: int = 15

    # --- CDC / Replication Engine ---
    CDC_ENABLED: bool = True
    CDC_USER: str = "root"
    CDC_PASSWORD: Optional[str] = None
    CDC_SERVER_ID: int = 100
    CDC_RESUME_STREAM: bool = False
    CDC_LOG_FILE: Optional[str] = None
    CDC_LOG_POS: Optional[int] = None
    CDC_POLL_INTERVAL: float = 0.05
    CDC_STATE_FILE: str = ".cdc_state.json"

    # --- Koha REST API ---
    KOHA_API_BASE: str = "http://137.184.15.52:1025/api/v1"
    KOHA_API_CLIENT_ID: Optional[str] = None
    KOHA_API_CLIENT_SECRET: Optional[str] = None
    KOHA_API_TIMEOUT: int = 10

    # --- SMTP Notification Settings ---
    SMTP_ENABLED: bool = True
    SMTP_SERVER: str = "smtp-relay.brevo.com"
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_USE_TLS: bool = True
    NOTIFICATION_EMAIL: Optional[str] = None
    SMTP_RATE_LIMIT_SECONDS: int = 5

    # --- IoT Node Settings ---
    IOT_HEARTBEAT_TIMEOUT_SECONDS: int = 35
    IOT_COMMAND_TIMEOUT_SECONDS: int = 10

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

# Singleton configuration instance
settings = Settings()
