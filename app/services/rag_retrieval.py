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
from app.models.project import AttachmentChunk, Card, Project
from app.schemas.rag import RagRetrieveRequest, RagRetrieveResponse, RagRetrieveResult
from app.services.embedding_client import create_embeddings
from app.services.cards import ensure_card_access
from app.services.projects import ensure_project_access
from app.services.workspaces import ensure_workspace_access


WORD_PATTERN = re.compile(r"[a-zA-Z0-9_]+")


def tokenize(text: str) -> list[str]:
    return WORD_PATTERN.findall(text.lower())


def bm25_scores(query: str, chunks: list[AttachmentChunk]) -> dict[int, float]:
    tokenized_query = tokenize(query)
    if not tokenized_query or not chunks:
        return {}

    documents = [tokenize(chunk.content) for chunk in chunks]
    average_length = sum(len(document) for document in documents) / len(documents)
    document_frequency: Counter[str] = Counter()

    for document in documents:
        document_frequency.update(set(document))

    k1 = 1.5
    b = 0.75
    total_documents = len(documents)
    scores: dict[int, float] = {}

    for chunk, document in zip(chunks, documents, strict=True):
        if not document:
            scores[chunk.id] = 0.0
            continue

        term_frequency = Counter(document)
        score = 0.0
        document_length = len(document)

        for term in tokenized_query:
            if term_frequency[term] == 0:
                continue

            idf = math.log(
                1
                + (total_documents - document_frequency[term] + 0.5)
                / (document_frequency[term] + 0.5)
            )
            numerator = term_frequency[term] * (k1 + 1)
            denominator = term_frequency[term] + k1 * (
                1 - b + b * document_length / average_length
            )
            score += idf * numerator / denominator

        scores[chunk.id] = score

    return scores


@lru_cache(maxsize=1)
def get_reranker_model() -> CrossEncoder:
    return CrossEncoder(settings.reranker_model)


def apply_scope_access_check(
    db: Session,
    current_user_id: int,
    payload: RagRetrieveRequest,
) -> None:
    if payload.card_id is not None:
        ensure_card_access(db, current_user_id, payload.card_id)
        return

    if payload.project_id is not None:
        ensure_project_access(db, current_user_id, payload.project_id)
        return

    if payload.workspace_id is not None:
        ensure_workspace_access(db, current_user_id, payload.workspace_id)
        return

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Provide card_id, project_id, or workspace_id",
    )


def apply_scope_filters(
    statement: Select,
    payload: RagRetrieveRequest,
) -> Select:
    if payload.card_id is not None:
        return statement.where(AttachmentChunk.card_id == payload.card_id)

    if payload.project_id is not None:
        return statement.where(Card.project_id == payload.project_id)

    if payload.workspace_id is not None:
        return statement.where(Project.workspace_id == payload.workspace_id)

    return statement


def get_scoped_chunks(db: Session, payload: RagRetrieveRequest) -> list[AttachmentChunk]:
    statement = (
        select(AttachmentChunk)
        .join(Card, Card.id == AttachmentChunk.card_id)
        .join(Project, Project.id == Card.project_id)
        .order_by(AttachmentChunk.attachment_id.asc(), AttachmentChunk.chunk_index.asc())
    )
    statement = apply_scope_filters(statement, payload)
    return list(db.scalars(statement).all())


def get_vector_candidates(
    db: Session,
    payload: RagRetrieveRequest,
) -> dict[int, tuple[AttachmentChunk, float]]:
    query_embedding = create_embeddings(payload.query)[0]
    distance = AttachmentChunk.embedding.cosine_distance(query_embedding)

    statement = (
        select(AttachmentChunk, distance.label("distance"))
        .join(Card, Card.id == AttachmentChunk.card_id)
        .join(Project, Project.id == Card.project_id)
        .where(AttachmentChunk.embedding.is_not(None))
        .order_by(distance.asc())
        .limit(max(payload.top_k, settings.retrieval_candidate_limit))
    )
    statement = apply_scope_filters(statement, payload)

    return {
        chunk.id: (chunk, float(row_distance) if row_distance is not None else 1.0)
        for chunk, row_distance in db.execute(statement).all()
    }


def get_bm25_candidates(
    query: str,
    scoped_chunks: list[AttachmentChunk],
) -> dict[int, float]:
    scores = bm25_scores(query, scoped_chunks)
    ranked_scores = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    return {
        chunk_id: score
        for chunk_id, score in ranked_scores[: max(1, settings.bm25_candidate_limit)]
        if score > 0
    }


def rerank_candidates(
    query: str,
    candidates: list[AttachmentChunk],
) -> dict[int, float]:
    if not candidates:
        return {}

    reranker = get_reranker_model()
    scores = reranker.predict([(query, chunk.content) for chunk in candidates])
    return {
        chunk.id: float(score)
        for chunk, score in zip(candidates, scores, strict=True)
    }


def retrieve_attachment_chunks(
    db: Session,
    current_user_id: int,
    payload: RagRetrieveRequest,
) -> RagRetrieveResponse:
    apply_scope_access_check(db, current_user_id, payload)

    scoped_chunks = get_scoped_chunks(db, payload)
    chunks_by_id = {chunk.id: chunk for chunk in scoped_chunks}
    vector_candidates = get_vector_candidates(db, payload)
    bm25_candidates = get_bm25_candidates(payload.query, scoped_chunks)

    candidate_ids = list(dict.fromkeys([*vector_candidates.keys(), *bm25_candidates.keys()]))
    candidates = [chunks_by_id[chunk_id] for chunk_id in candidate_ids if chunk_id in chunks_by_id]
    reranker_scores = rerank_candidates(payload.query, candidates)

    ranked_candidates = sorted(
        candidates,
        key=lambda chunk: reranker_scores.get(chunk.id, float("-inf")),
        reverse=True,
    )[: payload.top_k]

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
                distance=vector_candidates.get(chunk.id, (chunk, None))[1],
                bm25_score=bm25_candidates.get(chunk.id),
                rerank_score=reranker_scores.get(chunk.id),
            )
            for chunk in ranked_candidates
        ],
    )
