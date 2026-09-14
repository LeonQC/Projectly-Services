from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.project import AttachmentChunk
from app.services.attachments import ensure_attachment_access
from app.services.embedding_client import create_embeddings


def embed_attachment_chunks(
    db: Session,
    attachment_id: int,
    current_user_id: int,
) -> dict[str, int]:
    ensure_attachment_access(db, current_user_id, attachment_id)

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

    embeddings = create_embeddings([chunk.content for chunk in chunks_to_embed])

    for chunk, embedding in zip(chunks_to_embed, embeddings, strict=True):
        chunk.embedding = embedding

    db.commit()

    return {
        "total_chunks": len(chunks),
        "embedded_chunks": len(chunks_to_embed),
        "skipped_chunks": len(chunks) - len(chunks_to_embed),
    }
