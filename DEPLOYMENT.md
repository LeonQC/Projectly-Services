# Projectly Services Deployment

## Render

Use `render.yaml` to create:

- `projectly-api` FastAPI web service
- `projectly-postgres` PostgreSQL database

Set these secret environment variables in Render:

```text
AUTH_SECRET_KEY=<strong-random-secret>
GOOGLE_CLIENT_ID=<google-oauth-client-id>
CORS_ORIGINS=https://<projectly-ui-domain>,http://localhost:5173,http://127.0.0.1:5173
```

The service start command runs migrations before starting FastAPI:

```text
alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

After deploy, verify:

```text
https://<projectly-api-domain>/health
https://<projectly-api-domain>/docs
```
