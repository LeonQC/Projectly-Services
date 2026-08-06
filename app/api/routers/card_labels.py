from fastapi import APIRouter, status

from app.api.deps import AuthenticatedUserId, DbSession
from app.core.responses import success_response
from app.schemas.card_label import CardLabelCreate, CardLabelResponse, CardLabelUpdate
from app.services import card_labels as card_labels_service


router = APIRouter(tags=["cards-detail"])


@router.get("/cards/{card_id}/labels")
def list_card_labels(card_id: int, db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    labels = card_labels_service.list_card_labels(db, card_id, current_user_id)
    return success_response(data=[CardLabelResponse.model_validate(label) for label in labels])


@router.post("/cards/{card_id}/labels", status_code=status.HTTP_201_CREATED)
def create_card_label(
    card_id: int,
    payload: CardLabelCreate,
    db: DbSession,
    current_user_id: AuthenticatedUserId,
) -> dict:
    label = card_labels_service.create_card_label(db, card_id, current_user_id, payload)
    return success_response(data=CardLabelResponse.model_validate(label), message="Card label created")


@router.patch("/card-labels/{label_id}")
def update_card_label(
    label_id: int,
    payload: CardLabelUpdate,
    db: DbSession,
    current_user_id: AuthenticatedUserId,
) -> dict:
    label = card_labels_service.update_card_label(db, label_id, current_user_id, payload)
    return success_response(data=CardLabelResponse.model_validate(label), message="Card label updated")


@router.delete("/card-labels/{label_id}")
def delete_card_label(label_id: int, db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    card_labels_service.delete_card_label(db, label_id, current_user_id)
    return success_response(message="Card label deleted")
