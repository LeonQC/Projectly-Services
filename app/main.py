from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import (
    attachments,
    auth,
    card_labels,
    card_links,
    card_members,
    cards,
    comments,
    development,
    epics,
    github_app,
    notifications,
    projects,
    sprints,
    user_settings,
    workspaces,
)
from app.core.config import settings
from app.core.responses import success_response

app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(workspaces.router, prefix=settings.api_prefix)
app.include_router(projects.router, prefix=settings.api_prefix)
app.include_router(epics.router, prefix=settings.api_prefix)
app.include_router(sprints.router, prefix=settings.api_prefix)
app.include_router(cards.router, prefix=settings.api_prefix)
app.include_router(card_labels.router, prefix=settings.api_prefix)
app.include_router(card_links.router, prefix=settings.api_prefix)
app.include_router(card_members.router, prefix=settings.api_prefix)
app.include_router(attachments.router, prefix=settings.api_prefix)
app.include_router(comments.router, prefix=settings.api_prefix)
app.include_router(development.router, prefix=settings.api_prefix)
app.include_router(github_app.router, prefix=settings.api_prefix)
app.include_router(notifications.router, prefix=settings.api_prefix)
app.include_router(user_settings.router, prefix=settings.api_prefix)


@app.get("/health")
def health_check():
    return success_response(data={"status": "ok"})
