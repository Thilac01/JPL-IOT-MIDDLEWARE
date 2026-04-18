from pydantic_settings import BaseSettings
import os
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    # --- SSH Tunnel Settings (Optional) ---
    SSH_HOST: str = "137.184.15.52"  # Guessed from API IP
    SSH_PORT: int = 22
    SSH_USER: str = "root"
    SSH_PASSWORD: str = "JPL@#lib260219a"  # Guessed same as DB
    USE_SSH: bool = False  # Set to True if tunnel isn't handled externally

    REPLICA_HOST: str = "127.0.0.1"
    REPLICA_PORT: int = 3307
    REPLICA_USER: str = "root"
    REPLICA_PASSWORD: str = "JPL@#lib260219a"
    REPLICA_DB: str = "koha_jpl"
    
    SECURITY_DB: str = "jpl_security_monitor"
    
    CDC_USER: str = "root"
    CDC_PASSWORD: str = "JPL@#lib260219a"
    CDC_SERVER_ID: int = 2024  # More unique ID
    
    KOHA_API_BASE: str = "http://137.184.15.52:1025/api/v1"
    KOHA_API_CLIENT_ID: str = ""
    KOHA_API_CLIENT_SECRET: str = ""
    
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    SECRET_KEY: str = "secret"
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"

settings = Settings()
