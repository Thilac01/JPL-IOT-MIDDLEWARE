# ==============================================================================
# Gunicorn Multi-Worker Production ASGI Configuration
# ==============================================================================
import multiprocessing
import os

bind = f"{os.getenv('APP_HOST', '0.0.0.0')}:{os.getenv('APP_PORT', '8000')}"
workers = int(os.getenv("GUNICORN_WORKERS", "2"))
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
timeout = 60
keepalive = 5
max_requests = 2000
max_requests_jitter = 200
graceful_timeout = 30
preload_app = False
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info").lower()
