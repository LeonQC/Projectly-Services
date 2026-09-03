from fastapi import HTTPException, status
from openai import OpenAI
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.project import AttachmentChunk
from app.services.attachments import ensure_attachment_access


def embed_attachment_chunks(
    db: Session,
    attachment_id: int,
    current_user_id: int,
) -> dict[str, int]:
    ensure_attachment_access(db, current_user_id, attachment_id)

    if not settings.openai_api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OPENAI_API_KEY is not configured",
        )

    chunks = list(
        db.scalars(
            select(AttachmentChunk)
            .where(AttachmentChunk.attachment_id == attachment_id)
            .order_by(AttachmentChunk.chunk_index.asc())
        ).all()
    )
    if not chunks:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chunk attachment before embedding",
        )

    chunks_to_embed = [chunk for chunk in chunks if chunk.embedding is None]
    if not chunks_to_embed:
        return {
            "total_chunks": len(chunks),
            "embedded_chunks": 0,
            "skipped_chunks": len(chunks),
        }

    client = OpenAI(api_key=settings.openai_api_key)
    response = client.embeddings.create(
        model=settings.embedding_model,
        input=[chunk.content for chunk in chunks_to_embed],
    )

    for chunk, embedding_data in zip(chunks_to_embed, response.data, strict=True):
        chunk.embedding = embedding_data.embedding

    db.commit()

    return {
        "total_chunks": len(chunks),
        "embedded_chunks": len(chunks_to_embed),
        "skipped_chunks": len(chunks) - len(chunks_to_embed),
    }
