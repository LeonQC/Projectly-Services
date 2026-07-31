from fastapi import FastAPI

from app.api.routers import auth, comments
from app.core.config import settings
from app.core.responses import success_response

app = FastAPI(title=settings.app_name)
app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(comments.router, prefix=settings.api_prefix)


@app.get("/health")
def health_check():
    return success_response(data={"status": "ok"})
