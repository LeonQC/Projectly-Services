import json
from tempfile import NamedTemporaryFile

from docling.document_converter import DocumentConverter
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.project import AttachmentDocument
from app.services.attachments import ensure_attachment_access
from app.services.attachment_storage import download_attachment_file


def extract_attachment_document(
    db: Session,
    attachment_id: int,
    current_user_id: int,
) -> AttachmentDocument:
    attachment = ensure_attachment_access(db, current_user_id, attachment_id)

    existing = db.scalar(
        select(AttachmentDocument).where(AttachmentDocument.attachment_id == attachment.id)
    )
    if existing is not None:
        return existing

    if attachment.file_type != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF attachments can be extracted",
        )

    content = download_attachment_file(attachment.file_url)

    with NamedTemporaryFile(suffix=".pdf", delete=True) as temp_file:
        temp_file.write(content)
        temp_file.flush()

        converter = DocumentConverter()
        result = converter.convert(temp_file.name)
        doc = result.document

    content_json = json.loads(doc.model_dump_json())
    content_markdown = doc.export_to_markdown()

    document = AttachmentDocument(
        attachment_id=attachment.id,
        card_id=attachment.card_id,
        file_name=attachment.file_name,
        content_json=content_json,
        content_markdown=content_markdown,
        extraction_status="completed",
        error_message=None,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def get_attachment_document(
    db: Session,
    attachment_id: int,
    current_user_id: int,
) -> AttachmentDocument:
    ensure_attachment_access(db, current_user_id, attachment_id)

    document = db.scalar(
        select(AttachmentDocument).where(AttachmentDocument.attachment_id == attachment_id)
    )
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment document not found",
        )
    return document
