from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Header, HTTPException, Request, status
from fastapi.responses import RedirectResponse

from app.api.deps import AuthenticatedUserId, DbSession
from app.core.config import settings
from app.core.responses import success_response
from app.schemas.github_app import GitHubAppInstallationResponse, GitHubAppWebhookResponse
from app.services import github_app as github_app_service


router = APIRouter(prefix="/github/app", tags=["github-app"])


@router.get("/callback")
def github_app_callback(
    db: DbSession,
    installation_id: Optional[int] = None,
    setup_action: Optional[str] = None,
) -> RedirectResponse:
    query: dict[str, str] = {}

    if installation_id is None:
        query["github_app_error"] = "missing_installation_id"
    else:
        github_app_service.create_callback_installation(db, installation_id, setup_action)
        query["github_installation_id"] = str(installation_id)
        if setup_action:
            query["github_setup_action"] = setup_action

    redirect_url = f"{settings.frontend_url.rstrip('/')}/settings/integrations/github"
    if query:
        redirect_url = f"{redirect_url}?{urlencode(query)}"

    return RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)


@router.get("/installations")
def list_github_app_installations(db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    installations = github_app_service.list_user_installations(db, current_user_id)
    return success_response(
        data=[GitHubAppInstallationResponse.model_validate(installation) for installation in installations]
    )


@router.post("/installations/{installation_id}/claim")
def claim_github_app_installation(
    installation_id: int,
    db: DbSession,
    current_user_id: AuthenticatedUserId,
) -> dict:
    installation = github_app_service.claim_installation(db, installation_id, current_user_id)
    return success_response(
        data=GitHubAppInstallationResponse.model_validate(installation),
        message="GitHub App installation connected",
    )


@router.post("/webhook")
async def github_app_webhook(
    request: Request,
    db: DbSession,
    x_github_event: Optional[str] = Header(default=None, alias="X-GitHub-Event"),
    x_github_delivery: Optional[str] = Header(default=None, alias="X-GitHub-Delivery"),
    x_hub_signature_256: Optional[str] = Header(default=None, alias="X-Hub-Signature-256"),
) -> dict:
    if not x_github_event:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="GitHub event header is required")

    raw_body = await request.body()
    github_app_service.verify_github_webhook_signature(raw_body, x_hub_signature_256)
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid GitHub webhook payload")

    handled = github_app_service.handle_github_app_webhook(db, event=x_github_event, payload=payload)
    return success_response(
        data=GitHubAppWebhookResponse(
            event=x_github_event,
            delivery_id=x_github_delivery,
            handled=handled,
        ).model_dump(),
        message="GitHub webhook received",
    )
