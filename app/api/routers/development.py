from fastapi import APIRouter, status

from app.api.deps import AuthenticatedUserId, DbSession
from app.core.responses import success_response
from app.schemas.development import (
    CardDevelopmentResponse,
    CardGitHubLinkCreate,
    CardGitHubLinkResponse,
    CardGitHubLinkUpdate,
)
from app.services import development as development_service


router = APIRouter(tags=["development"])


@router.get("/cards/{card_id}/development")
def get_card_development(card_id: int, db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    development = development_service.get_card_development(db, card_id, current_user_id)
    return success_response(data=CardDevelopmentResponse.model_validate(development))


@router.post("/cards/{card_id}/development/github-links", status_code=status.HTTP_201_CREATED)
def create_card_github_link(
    card_id: int,
    payload: CardGitHubLinkCreate,
    db: DbSession,
    current_user_id: AuthenticatedUserId,
) -> dict:
    github_link = development_service.create_card_github_link(db, card_id, current_user_id, payload)
    return success_response(data=CardGitHubLinkResponse.model_validate(github_link), message="GitHub link created")


@router.patch("/development/github-links/{github_link_id}")
def update_card_github_link(
    github_link_id: int,
    payload: CardGitHubLinkUpdate,
    db: DbSession,
    current_user_id: AuthenticatedUserId,
) -> dict:
    github_link = development_service.update_card_github_link(db, github_link_id, current_user_id, payload)
    return success_response(data=CardGitHubLinkResponse.model_validate(github_link), message="GitHub link updated")


@router.delete("/development/github-links/{github_link_id}")
def delete_card_github_link(github_link_id: int, db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    development_service.delete_card_github_link(db, github_link_id, current_user_id)
    return success_response(message="GitHub link removed")
