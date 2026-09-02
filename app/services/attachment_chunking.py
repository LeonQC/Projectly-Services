from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.project import AttachmentChunk, AttachmentDocument
from app.services.attachments import ensure_attachment_access

DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 150


def split_markdown_into_chunks(
    markdown: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    paragraphs = [p.strip() for p in markdown.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current_parts: list[str] = []

    def join_parts(parts: list[str]) -> str:
        return "\n\n".join(parts).strip()

    def overlap_parts(parts: list[str]) -> list[str]:
        selected: list[str] = []
        total_length = 0

        for part in reversed(parts):
            part_length = len(part) + (2 if selected else 0)
            if selected and total_length + part_length > overlap:
                break
            selected.insert(0, part)
            total_length += part_length

        return selected

    for paragraph in paragraphs:
        candidate_parts = [*current_parts, paragraph]
        if len(join_parts(candidate_parts)) <= chunk_size:
            current_parts = candidate_parts
            continue

        if current_parts:
            chunks.append(join_parts(current_parts))
            current_parts = [*overlap_parts(current_parts), paragraph]
        else:
            current_parts = [paragraph]

        while len(join_parts(current_parts)) > chunk_size:
            current_text = join_parts(current_parts)
            chunks.append(current_text[:chunk_size].rstrip())
            remainder = current_text[chunk_size - overlap :].lstrip()
            current_parts = [remainder] if remainder else []

    if current_parts:
        chunks.append(join_parts(current_parts))

    return chunks

def chunk_attachment_document(
    db: Session,
    attachment_id: int,
    current_user_id: int,
) -> list[AttachmentChunk]:
    attachment = ensure_attachment_access(db, current_user_id, attachment_id)

    document = db.scalar(
        select(AttachmentDocument).where(AttachmentDocument.attachment_id == attachment.id)
    )
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Extract attachment document before chunking",
        )

    chunk_texts = split_markdown_into_chunks(document.content_markdown)

    db.execute(
        delete(AttachmentChunk).where(
            AttachmentChunk.attachment_document_id == document.id
        )
    )

    chunks = [
        AttachmentChunk(
            attachment_document_id=document.id,
            attachment_id=attachment.id,
            card_id=attachment.card_id,
            chunk_index=index,
            content=content,
            token_count=None,
            page_number=None,
        )
        for index, content in enumerate(chunk_texts)
    ]

    db.add_all(chunks)
    db.commit()

    for chunk in chunks:
        db.refresh(chunk)

    return chunks


def list_attachment_chunks(
    db: Session,
    attachment_id: int,
    current_user_id: int,
) -> list[AttachmentChunk]:
    ensure_attachment_access(db, current_user_id, attachment_id)

    return list(
        db.scalars(
            select(AttachmentChunk)
            .where(AttachmentChunk.attachment_id == attachment_id)
            .order_by(AttachmentChunk.chunk_index.asc())
        ).all()
    )