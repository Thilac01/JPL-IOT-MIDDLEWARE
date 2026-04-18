import uvicorn
from main import app
from config import settings

if __name__ == "__main__":
    print(f"Starting JPL Security Middleware on {settings.APP_HOST}:{settings.APP_PORT}")
    uvicorn.run("main:app", host=settings.APP_HOST, port=settings.APP_PORT, reload=True)
