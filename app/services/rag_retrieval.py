"""
PGVector + Elasticsearch BM25 → RRF → CrossEncoder
"""

from __future__ import annotations
from functools import lru_cache

from sentence_transformers import CrossEncoder
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.project import RagChunk
from app.schemas.rag import (
    RagRetrieveRequest,
    RagRetrieveResponse,
    RagRetrieveResult,
)
from app.services.cards import ensure_card_access
from app.services.projects import ensure_project_access
from app.services.rag_embedding import create_embeddings
from app.services.workspaces import (
    ensure_workspace_access,
    get_accessible_workspace_ids,
)
from app.services.rag_search_index import search_rag_chunks_bm25


RRF_K = 60

# scope and permission
def resolve_accessible_workspace_ids(
    db: Session,
    user_id: int,
    payload: RagRetrieveRequest,
) -> list[int] | None:
    if payload.card_id is not None:
        ensure_card_access(db, user_id, payload.card_id)
        return None

    if payload.project_id is not None:
        ensure_project_access(db, user_id, payload.project_id)
        return None

    if payload.workspace_id is not None:
        ensure_workspace_access(
            db,
            user_id,
            payload.workspace_id,
        )
        return None

    return get_accessible_workspace_ids(
        db,
        user_id,
    )


def apply_scope(
    statement: Select,
    payload: RagRetrieveRequest,
    workspace_ids: list[int] | None = None,
) -> Select:
    if payload.card_id is not None:
        return statement.where(
            RagChunk.card_id == payload.card_id
        )

    if payload.project_id is not None:
        return statement.where(
            RagChunk.project_id == payload.project_id
        )

    if payload.workspace_id is not None:
        return statement.where(
            RagChunk.workspace_id == payload.workspace_id
        )

    if workspace_ids is not None:
        return statement.where(
            RagChunk.workspace_id.in_(workspace_ids)
        )

    return statement


# vector, RRF, Reranker
@lru_cache(maxsize=1)
def get_reranker() -> CrossEncoder:
    return CrossEncoder(settings.reranker_model)


def reciprocal_rank_fusion(
    vector_ids: list[int],
    bm25_ids: list[int],
) -> dict[int, float]:
    scores: dict[int, float] = {}

    for ranked_ids in (vector_ids, bm25_ids):
        for rank, chunk_id in enumerate(ranked_ids, start=1):
            scores[chunk_id] = (
                scores.get(chunk_id, 0.0)
                + 1 / (RRF_K + rank)
            )

    return scores

# retrieval
def retrieve_rag_chunks(
    db: Session,
    current_user_id: int,
    payload: RagRetrieveRequest,
) -> RagRetrieveResponse:
    accessible_workspace_ids = (
        resolve_accessible_workspace_ids(
            db,
            current_user_id,
            payload,
        )
    )

    query_vector = create_embeddings(payload.query)[0]
    distance = RagChunk.embedding.cosine_distance(query_vector)

    vector_statement = apply_scope(
        select(RagChunk, distance.label("distance"))
        .where(RagChunk.embedding.is_not(None))
        .order_by(distance.asc())
        .limit(settings.retrieval_candidate_limit),
        payload,
        accessible_workspace_ids,
    )
    vector_rows = db.execute(vector_statement).all()
    vector_ids = [chunk.id for chunk, _ in vector_rows]
    distances = {
        chunk.id: float(value)
        for chunk, value in vector_rows
    }

    bm25_scores = search_rag_chunks_bm25(
        payload.query,
        limit=settings.bm25_candidate_limit,
        workspace_id=payload.workspace_id,
        project_id=payload.project_id,
        card_id=payload.card_id,
        workspace_ids=accessible_workspace_ids,
    )
    bm25_ids = list(bm25_scores)

    rrf_scores = reciprocal_rank_fusion(vector_ids, bm25_ids)
    candidate_ids = sorted(
        rrf_scores,
        key=rrf_scores.get,
        reverse=True,
    )[:settings.retrieval_candidate_limit]

    candidate_statement = apply_scope(
        select(RagChunk).where(
            RagChunk.id.in_(candidate_ids)
        ),
        payload,
        accessible_workspace_ids,
    )
    candidate_chunks = list(
        db.scalars(candidate_statement).all()
    )
    chunks_by_id = {
        chunk.id: chunk
        for chunk in candidate_chunks
    }

    candidates = [
        chunks_by_id[chunk_id]
        for chunk_id in candidate_ids
        if chunk_id in chunks_by_id
    ]

    if not candidates:
        return RagRetrieveResponse(
            query=payload.query,
            top_k=payload.top_k,
            results=[],
        )

    rerank_values = get_reranker().predict(
        [(payload.query, chunk.content) for chunk in candidates]
    )
    rerank_scores = {
        chunk.id: float(score)
        for chunk, score in zip(
            candidates,
            rerank_values,
            strict=True,
        )
    }

    ranked = sorted(
        candidates,
        key=lambda chunk: rerank_scores[chunk.id],
        reverse=True,
    )[:payload.top_k]

    return RagRetrieveResponse(
        query=payload.query,
        top_k=payload.top_k,
        results=[
            RagRetrieveResult(
                chunk_id=chunk.id,
                source_type=chunk.source_type,
                source_id=chunk.source_id,
                source_subtype=chunk.source_subtype,
                title=chunk.title,
                workspace_id=chunk.workspace_id,
                project_id=chunk.project_id,
                card_id=chunk.card_id,
                attachment_id=(
                    chunk.source_id
                    if chunk.source_type == "attachment"
                    else None
                ),
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                distance=distances.get(chunk.id),
                bm25_score=bm25_scores.get(chunk.id),
                rerank_score=rerank_scores.get(chunk.id),
            )
            for chunk in ranked
        ],
    )
