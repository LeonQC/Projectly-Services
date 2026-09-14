# parsing: pdf -> docling -> attachment_documents, PDF 文件变成 Markdown / JSON
"""
输入：attachment_id
做：
1. 查 card_attachments
2. 检查用户权限
3. 从 Supabase Storage 下载 PDF
4. 临时写成本地 PDF 文件
5. 用 Docling 解析 PDF
6. 保存到 attachment_documents

输出：
content_json
content_markdown
"""

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
    *,
    force: bool = False,
) -> AttachmentDocument:
    attachment = ensure_attachment_access(db, current_user_id, attachment_id)

    existing = db.scalar(
        select(AttachmentDocument).where(AttachmentDocument.attachment_id == attachment.id)
    )
    if existing is not None and existing.extraction_status == "completed" and not force:
        return existing

    if attachment.file_type != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF attachments can be extracted",
        )

    document = existing
    if document is None:
        document = AttachmentDocument(
            attachment_id=attachment.id,
            card_id=attachment.card_id,
            file_name=attachment.file_name,
            content_json=None,
            content_markdown=None,
            extraction_status="pending",
            error_message=None,
        )
        db.add(document)
        db.flush()

    document.extraction_status = "processing"
    document.error_message = None
    document.file_name = attachment.file_name
    db.commit()

    try:
        content = download_attachment_file(attachment.file_url)

        with NamedTemporaryFile(suffix=".pdf", delete=True) as temp_file:
            temp_file.write(content)
            temp_file.flush()

            converter = DocumentConverter()
            result = converter.convert(temp_file.name)
            doc = result.document

        document.content_json = json.loads(doc.model_dump_json())
        document.content_markdown = doc.export_to_markdown()
        document.extraction_status = "completed"
        document.error_message = None
        db.commit()
        db.refresh(document)
        return document
    except Exception as exc:
        db.rollback()
        document = db.scalar(
            select(AttachmentDocument).where(AttachmentDocument.attachment_id == attachment.id)
        )
        if document is not None:
            document.extraction_status = "failed"
            document.error_message = str(exc)
            document.retry_count += 1
            db.commit()
        raise


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
