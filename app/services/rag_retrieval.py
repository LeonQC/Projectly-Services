"""
PGVector + Python BM25 → RRF → CrossEncoder
"""

from __future__ import annotations

import math
import re
from collections import Counter
from functools import lru_cache

from fastapi import HTTPException, status
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
from app.services.workspaces import ensure_workspace_access


WORD_PATTERN = re.compile(
    r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]"
)
RRF_K = 60


def tokenize(text: str) -> list[str]:
    return WORD_PATTERN.findall(text.lower())

# scope and permission
def check_scope_access(
    db: Session,
    user_id: int,
    payload: RagRetrieveRequest,
) -> None:
    if payload.card_id is not None:
        ensure_card_access(db, user_id, payload.card_id)
    elif payload.project_id is not None:
        ensure_project_access(db, user_id, payload.project_id)
    elif payload.workspace_id is not None:
        ensure_workspace_access(db, user_id, payload.workspace_id)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide card_id, project_id, or workspace_id",
        )


def apply_scope(
    statement: Select,
    payload: RagRetrieveRequest,
) -> Select:
    if payload.card_id is not None:
        return statement.where(RagChunk.card_id == payload.card_id)
    if payload.project_id is not None:
        return statement.where(RagChunk.project_id == payload.project_id)
    if payload.workspace_id is not None:
        return statement.where(
            RagChunk.workspace_id == payload.workspace_id
        )
    return statement

# BM25
def calculate_bm25(
    query: str,
    chunks: list[RagChunk],
) -> dict[int, float]:
    query_tokens = tokenize(query)
    documents = [tokenize(chunk.content) for chunk in chunks]

    if not query_tokens or not documents:
        return {}

    average_length = (
        sum(len(document) for document in documents)
        / len(documents)
    )
    document_frequency: Counter[str] = Counter()

    for document in documents:
        document_frequency.update(set(document))

    scores: dict[int, float] = {}
    total_documents = len(documents)
    k1 = 1.5
    b = 0.75

    for chunk, document in zip(chunks, documents, strict=True):
        frequencies = Counter(document)
        score = 0.0

        for term in query_tokens:
            frequency = frequencies[term]
            if frequency == 0:
                continue

            df = document_frequency[term]
            idf = math.log(
                1 + (total_documents - df + 0.5) / (df + 0.5)
            )
            denominator = frequency + k1 * (
                1 - b + b * len(document) / average_length
            )
            score += idf * frequency * (k1 + 1) / denominator

        scores[chunk.id] = score

    return scores

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
    check_scope_access(db, current_user_id, payload)

    scoped_statement = apply_scope(select(RagChunk), payload)
    scoped_chunks = list(db.scalars(scoped_statement).all())
    chunks_by_id = {chunk.id: chunk for chunk in scoped_chunks}

    query_vector = create_embeddings(payload.query)[0]
    distance = RagChunk.embedding.cosine_distance(query_vector)

    vector_statement = apply_scope(
        select(RagChunk, distance.label("distance"))
        .where(RagChunk.embedding.is_not(None))
        .order_by(distance.asc())
        .limit(settings.retrieval_candidate_limit),
        payload,
    )
    vector_rows = db.execute(vector_statement).all()
    vector_ids = [chunk.id for chunk, _ in vector_rows]
    distances = {
        chunk.id: float(value)
        for chunk, value in vector_rows
    }

    bm25_scores = calculate_bm25(payload.query, scoped_chunks)
    bm25_ids = [
        chunk_id
        for chunk_id, score in sorted(
            bm25_scores.items(),
            key=lambda item: item[1],
            reverse=True,
        )
        if score > 0
    ][:settings.bm25_candidate_limit]

    rrf_scores = reciprocal_rank_fusion(vector_ids, bm25_ids)
    candidate_ids = sorted(
        rrf_scores,
        key=rrf_scores.get,
        reverse=True,
    )[:settings.retrieval_candidate_limit]

    candidates = [
        chunks_by_id[chunk_id]
        for chunk_id in candidate_ids
        if chunk_id in chunks_by_id
    ]

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
