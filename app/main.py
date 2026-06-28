from fastapi import FastAPI
from app.core.config import settings

app = FastAPI(title=settings.app_name)


@app.get("/health")
def health_check():
    return {"status": "ok"}
