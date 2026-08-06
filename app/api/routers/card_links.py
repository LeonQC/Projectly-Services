from fastapi import APIRouter, status

from app.api.deps import AuthenticatedUserId, DbSession
from app.core.responses import success_response
from app.schemas.card_link import CardLinkCreate
from app.services import card_links as card_links_service


router = APIRouter(tags=["cards-detail"])


@router.get("/cards/{card_id}/links")
def list_card_links(card_id: int, db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    links = card_links_service.list_card_links(db, card_id, current_user_id)
    return success_response(data=links)


@router.post("/cards/{card_id}/links", status_code=status.HTTP_201_CREATED)
def create_card_link(
    card_id: int,
    payload: CardLinkCreate,
    db: DbSession,
    current_user_id: AuthenticatedUserId,
) -> dict:
    link = card_links_service.create_card_link(db, card_id, current_user_id, payload)
    return success_response(data=link, message="Card link created")


@router.delete("/card-links/{link_id}")
def delete_card_link(link_id: int, db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    card_links_service.delete_card_link(db, link_id, current_user_id)
    return success_response(message="Card link deleted")
