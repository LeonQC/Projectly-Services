from functools import lru_cache

from fastapi import HTTPException, status
from sentence_transformers import SentenceTransformer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.project import AttachmentChunk
from app.services.attachments import ensure_attachment_access


@lru_cache(maxsize=1)
def get_local_embedding_model() -> SentenceTransformer:
    return SentenceTransformer(settings.embedding_model)


def create_embeddings(inputs: str | list[str]) -> list[list[float]]:
    model = get_local_embedding_model()
    normalized_inputs = [inputs] if isinstance(inputs, str) else inputs
    embeddings = model.encode(
        normalized_inputs,
        normalize_embeddings=True,
    ).tolist()

    for embedding in embeddings:
        if len(embedding) != settings.embedding_dimensions:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=(
                    f"Embedding dimension mismatch: expected {settings.embedding_dimensions}, "
                    f"got {len(embedding)}"
                ),
            )

    return embeddings


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
