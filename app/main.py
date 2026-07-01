from fastapi import FastAPI
from app.core.config import settings
from app.core.responses import success_response

app = FastAPI(title=settings.app_name)


@app.get("/health")
def health_check():
    return success_response(data={"status": "ok"})
