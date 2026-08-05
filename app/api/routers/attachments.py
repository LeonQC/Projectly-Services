from fastapi import APIRouter, status

from app.api.deps import AuthenticatedUserId, DbSession
from app.core.responses import success_response
from app.schemas.attachment import CardAttachmentCreate, CardAttachmentResponse
from app.services import attachments as attachments_service


router = APIRouter(tags=["attachments"])


@router.get("/cards/{card_id}/attachments")
def list_card_attachments(card_id: int, db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    attachments = attachments_service.list_card_attachments(db, card_id, current_user_id)
    return success_response(data=[CardAttachmentResponse.model_validate(attachment) for attachment in attachments])


@router.post("/cards/{card_id}/attachments", status_code=status.HTTP_201_CREATED)
def create_card_attachment(
    card_id: int,
    payload: CardAttachmentCreate,
    db: DbSession,
    current_user_id: AuthenticatedUserId,
) -> dict:
    attachment = attachments_service.create_card_attachment(db, card_id, current_user_id, payload)
    return success_response(data=CardAttachmentResponse.model_validate(attachment), message="Attachment created")


@router.delete("/attachments/{attachment_id}")
def delete_card_attachment(attachment_id: int, db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    attachments_service.delete_card_attachment(db, attachment_id, current_user_id)
    return success_response(message="Attachment deleted")
