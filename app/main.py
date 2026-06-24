from fastapi import FastAPI

app = FastAPI(title="Projectly API")


@app.get("/health")
def health_check():
    return {"status": "ok"}
