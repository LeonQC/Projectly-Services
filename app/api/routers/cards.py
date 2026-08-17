from fastapi import APIRouter, status

from app.api.deps import AuthenticatedUserId, DbSession
from app.core.responses import success_response
from app.schemas.card import CardCreate, CardDetailResponse, CardMove, CardUpdate
from app.services import cards as cards_service


router = APIRouter(tags=["cards"])


@router.get("/projects/{project_id}/cards")
def list_project_cards(project_id: int, db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    cards = cards_service.list_project_cards(db, project_id, current_user_id)
    return success_response(data=cards_service.build_card_responses(db, cards))


@router.get("/projects/{project_id}/cards/archived")
def list_archived_project_cards(project_id: int, db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    cards = cards_service.list_archived_project_cards(db, project_id, current_user_id)
    return success_response(data=cards_service.build_card_responses(db, cards))


@router.post("/projects/{project_id}/cards", status_code=status.HTTP_201_CREATED)
def create_project_card(
    project_id: int,
    payload: CardCreate,
    db: DbSession,
    current_user_id: AuthenticatedUserId,
) -> dict:
    card = cards_service.create_card(db, project_id, current_user_id, payload)
    return success_response(data=cards_service.build_card_response(db, card), message="Card created")


@router.get("/cards/{card_id}")
def get_card(card_id: int, db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    card = cards_service.get_card(db, card_id, current_user_id)
    return success_response(data=cards_service.build_card_response(db, card))


@router.get("/cards/{card_id}/detail")
def get_card_detail(card_id: int, db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    detail = cards_service.get_card_detail(db, card_id, current_user_id)
    return success_response(data=CardDetailResponse.model_validate(detail))


@router.patch("/cards/{card_id}")
def update_card(
    card_id: int,
    payload: CardUpdate,
    db: DbSession,
    current_user_id: AuthenticatedUserId,
) -> dict:
    card = cards_service.update_card(db, card_id, current_user_id, payload)
    return success_response(data=cards_service.build_card_response(db, card), message="Card updated")


@router.patch("/cards/{card_id}/move")
def move_card(
    card_id: int,
    payload: CardMove,
    db: DbSession,
    current_user_id: AuthenticatedUserId,
) -> dict:
    card = cards_service.move_card(db, card_id, current_user_id, payload)
    return success_response(data=cards_service.build_card_response(db, card), message="Card moved")


@router.delete("/cards/{card_id}")
def delete_card(card_id: int, db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    cards_service.archive_card(db, card_id, current_user_id)
    return success_response(message="Card deleted")


@router.patch("/cards/{card_id}/restore")
def restore_card(card_id: int, db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    card = cards_service.restore_card(db, card_id, current_user_id)
    return success_response(data=cards_service.build_card_response(db, card), message="Card restored")


@router.delete("/cards/{card_id}/permanent")
def permanently_delete_card(card_id: int, db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    cards_service.permanently_delete_card(db, card_id, current_user_id)
    return success_response(message="Card permanently deleted")
