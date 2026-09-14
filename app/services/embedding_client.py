from functools import lru_cache

from fastapi import HTTPException, status
from sentence_transformers import SentenceTransformer

from app.core.config import settings


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