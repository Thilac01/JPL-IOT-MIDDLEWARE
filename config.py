from pydantic_settings import BaseSettings
import os
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    # --- SSH Tunnel Settings (Optional) ---
    SSH_HOST: str = "137.184.15.52"
    SSH_PORT: int = 22
    SSH_USER: str = "root"
    SSH_PASSWORD: str = "JPL@#lib260219a"
    USE_SSH: bool = True  # Set to True by default as per .env

    REPLICA_HOST: str = "127.0.0.1"
    REPLICA_PORT: int = 3307
    REPLICA_USER: str = "root"
    REPLICA_PASSWORD: str = "JPL@#lib260219a"
    REPLICA_DB: str = "koha_library"
    
    SECURITY_DB: str = "jpl_security_monitor"
    
    CDC_USER: str = "root"
    CDC_PASSWORD: str = "JPL@#lib260219a"
    CDC_SERVER_ID: int = 100
    
    KOHA_API_BASE: str = "http://137.184.15.52:1025/api/v1"
    KOHA_API_CLIENT_ID: str = ""
    KOHA_API_CLIENT_SECRET: str = ""
    
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    SECRET_KEY: str = "b95f517f43f0b42c15000dcfb9165a9296f2b5bd1e5a58dfc0bc12d1e29cfbcc"
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"

settings = Settings()
