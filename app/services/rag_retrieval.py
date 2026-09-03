from fastapi import HTTPException, status
from openai import OpenAI
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.project import AttachmentChunk, Card, Project
from app.schemas.rag import RagRetrieveRequest, RagRetrieveResponse, RagRetrieveResult


def retrieve_attachment_chunks(
    db: Session,
    current_user_id: int,
    payload: RagRetrieveRequest,
) -> RagRetrieveResponse:
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OPENAI_API_KEY is not configured",
        )

    client = OpenAI(api_key=settings.openai_api_key)
    response = client.embeddings.create(
        model=settings.embedding_model,
        input=payload.query,
    )
    query_embedding = response.data[0].embedding

    distance = AttachmentChunk.embedding.cosine_distance(query_embedding)

    statement = (
        select(
            AttachmentChunk,
            distance.label("distance"),
        )
        .join(Card, Card.id == AttachmentChunk.card_id)
        .join(Project, Project.id == Card.project_id)
        .where(AttachmentChunk.embedding.is_not(None))
        .order_by(distance.asc())
        .limit(payload.top_k)
    )

    if payload.card_id is not None:
        statement = statement.where(AttachmentChunk.card_id == payload.card_id)

    if payload.project_id is not None:
        statement = statement.where(Card.project_id == payload.project_id)

    if payload.workspace_id is not None:
        statement = statement.where(Project.workspace_id == payload.workspace_id)

    rows = db.execute(statement).all()

    return RagRetrieveResponse(
        query=payload.query,
        top_k=payload.top_k,
        results=[
            RagRetrieveResult(
                chunk_id=chunk.id,
                attachment_id=chunk.attachment_id,
                card_id=chunk.card_id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                distance=float(row_distance) if row_distance is not None else None,
            )
            for chunk, row_distance in rows
        ],
    )