from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.project import CardAttachment
from app.schemas.attachment import CardAttachmentCreate
from app.services.activities import create_card_activity
from app.services.attachment_storage import (
    delete_attachment_file,
    download_attachment_file,
    upload_attachment_file,
)
from app.services.cards import ensure_card_access


def build_attachment_storage_key(attachment_id: int, file_name: str) -> str:
    safe_name = Path(file_name or "attachment").name
    return f"card_attachments/{attachment_id}-{uuid4().hex}-{safe_name}"


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
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Use the attachment upload endpoint instead",
    )

def upload_card_attachment(
    db: Session,
    card_id: int,
    current_user_id: int,
    file: UploadFile,
) -> CardAttachment:
    ensure_card_access(db, current_user_id, card_id)

    safe_name = Path(file.filename or "attachment").name
    content = file.file.read()

    attachment = CardAttachment(
        card_id=card_id,
        comment_id=None,
        file_name=safe_name,
        file_url="",
        file_type=file.content_type,
        file_size=len(content),
        uploaded_by_id=current_user_id,
    )
    db.add(attachment)
    db.flush()

    storage_key = build_attachment_storage_key(attachment.id, safe_name)
    upload_attachment_file(storage_key, content, file.content_type)

    attachment.file_url = storage_key

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
) -> Response:
    attachment = ensure_attachment_access(db, current_user_id, attachment_id)

    if attachment.file_url.startswith("/api/attachments/"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment was uploaded before object storage migration",
        )

    content = download_attachment_file(attachment.file_url)

    return Response(
        content=content,
        media_type=attachment.file_type or "application/octet-stream",
        headers={
            "Content-Disposition": f'inline; filename="{attachment.file_name}"',
        },
    )

def delete_card_attachment(db: Session, attachment_id: int, current_user_id: int) -> None:
    attachment = ensure_attachment_access(db, current_user_id, attachment_id)
    card_id = attachment.card_id
    file_name = attachment.file_name
    storage_key = attachment.file_url

    if storage_key:
        delete_attachment_file(storage_key)

    db.delete(attachment)
    create_card_activity(
        db,
        card_id=card_id,
        actor_id=current_user_id,
        action="attachment_deleted",
        metadata={"attachment_id": attachment_id, "file_name": file_name},
    )
    db.commit()