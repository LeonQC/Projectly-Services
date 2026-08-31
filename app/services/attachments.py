from pathlib import Path
from shutil import copyfileobj
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.project import CardAttachment
from app.schemas.attachment import CardAttachmentCreate
from app.services.activities import create_card_activity
from app.services.cards import ensure_card_access


UPLOAD_DIR = Path("uploads/card_attachments")


def _find_attachment_storage_path(attachment_id: int) -> Path | None:
    matches = list(UPLOAD_DIR.glob(f"{attachment_id}-*"))
    return matches[0] if matches else None


def upload_card_attachment(
    db: Session,
    card_id: int,
    current_user_id: int,
    file: UploadFile,
) -> CardAttachment:
    ensure_card_access(db, current_user_id, card_id)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    safe_name = Path(file.filename or "attachment").name

    attachment = CardAttachment(
        card_id=card_id,
        comment_id=None,
        file_name=safe_name,
        file_url="",
        file_type=file.content_type,
        file_size=0,
        uploaded_by_id=current_user_id,
    )
    db.add(attachment)
    db.flush()

    storage_name = f"{attachment.id}-{uuid4().hex}-{safe_name}"
    storage_path = UPLOAD_DIR / storage_name

    with storage_path.open("wb") as buffer:
        copyfileobj(file.file, buffer)

    attachment.file_size = storage_path.stat().st_size
    attachment.file_url = f"/api/attachments/{attachment.id}/download"

    create_card_activity(
        db,
        card_id=card_id,
        actor_id=current_user_id,
        action="attachment_added",
        metadata={"attachment_id": attachment.id, "file_name": attachment.file_name},
    )

    db.commit()
    db.refresh(attachment)
    return attachment

def get_attachment_download_response(
    db: Session,
    attachment_id: int,
    current_user_id: int,
) -> FileResponse:
    attachment = ensure_attachment_access(db, current_user_id, attachment_id)

    storage_path = _find_attachment_storage_path(attachment.id)
    if storage_path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment file not found",
        )

    return FileResponse(
        path=storage_path,
        media_type=attachment.file_type or "application/octet-stream",
        filename=attachment.file_name,
    )


def get_attachment_or_404(db: Session, attachment_id: int) -> CardAttachment:
    attachment = db.get(CardAttachment, attachment_id)
    if attachment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")
    return attachment


def ensure_attachment_access(db: Session, user_id: int, attachment_id: int) -> CardAttachment:
    attachment = get_attachment_or_404(db, attachment_id)
    ensure_card_access(db, user_id, attachment.card_id)
    return attachment


def list_card_attachments(db: Session, card_id: int, current_user_id: int) -> list[CardAttachment]:
    ensure_card_access(db, current_user_id, card_id)
    statement = (
        select(CardAttachment)
        .where(CardAttachment.card_id == card_id, CardAttachment.comment_id.is_(None))
        .order_by(CardAttachment.created_at.asc(), CardAttachment.id.asc())
    )
    return list(db.scalars(statement).all())


def create_card_attachment(
    db: Session,
    card_id: int,
    current_user_id: int,
    payload: CardAttachmentCreate,
) -> CardAttachment:
    ensure_card_access(db, current_user_id, card_id)
    attachment = CardAttachment(
        card_id=card_id,
        comment_id=None,
        file_name=payload.file_name,
        file_url=payload.file_url,
        file_type=payload.file_type,
        file_size=payload.file_size,
        uploaded_by_id=current_user_id,
    )
    db.add(attachment)
    db.flush()
    create_card_activity(
        db,
        card_id=card_id,
        actor_id=current_user_id,
        action="attachment_added",
        metadata={"attachment_id": attachment.id, "file_name": attachment.file_name},
    )
    db.commit()
    db.refresh(attachment)
    return attachment


def delete_card_attachment(db: Session, attachment_id: int, current_user_id: int) -> None:
    attachment = ensure_attachment_access(db, current_user_id, attachment_id)
    card_id = attachment.card_id
    file_name = attachment.file_name
    storage_path = _find_attachment_storage_path(attachment.id)
    db.delete(attachment)
    create_card_activity(
        db,
        card_id=card_id,
        actor_id=current_user_id,
        action="attachment_deleted",
        metadata={"attachment_id": attachment_id, "file_name": file_name},
    )
    db.commit()
    if storage_path is not None:
        storage_path.unlink(missing_ok=True)
