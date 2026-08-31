from fastapi import APIRouter, File, UploadFile, status
from fastapi.responses import FileResponse

from app.api.deps import AuthenticatedUserId, DbSession
from app.core.responses import success_response
from app.schemas.attachment import CardAttachmentCreate, CardAttachmentResponse
from app.services import attachments as attachments_service


router = APIRouter(tags=["cards-detail"])


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


@router.post("/cards/{card_id}/attachments/upload", status_code=status.HTTP_201_CREATED)
def upload_card_attachment(
    card_id: int,
    db: DbSession,
    current_user_id: AuthenticatedUserId,
    file: UploadFile = File(...),
) -> dict:
    attachment = attachments_service.upload_card_attachment(db, card_id, current_user_id, file)
    return success_response(
        data=CardAttachmentResponse.model_validate(attachment),
        message="Attachment uploaded",
    )


@router.get("/attachments/{attachment_id}/download")
def download_card_attachment(
    attachment_id: int,
    db: DbSession,
    current_user_id: AuthenticatedUserId,
) -> FileResponse:
    return attachments_service.get_attachment_download_response(
        db,
        attachment_id,
        current_user_id,
    )
