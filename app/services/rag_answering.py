# answer: merge chunks into context string & build prompt & OpenAI chat model
from fastapi import HTTPException, status
from openai import OpenAI
from sqlalchemy.orm import Session

from app.core.config import settings
from app.schemas.rag import RagAskRequest, RagAskResponse, RagAskSource
from app.services.rag_context import build_structured_rag_context
from app.services.rag_retrieval import retrieve_attachment_chunks


def build_rag_context(sources: list[RagAskSource], contents: list[str]) -> str:
    blocks: list[str] = []

    for source, content in zip(sources, contents, strict=True):
        blocks.append(
            "\n".join(
                [
                    f"[Source chunk_id={source.chunk_id}, attachment_id={source.attachment_id}, card_id={source.card_id}]",
                    content,
                ]
            )
        )

    return "\n\n---\n\n".join(blocks)


def answer_rag_question(
    db: Session,
    current_user_id: int,
    payload: RagAskRequest,
) -> RagAskResponse:
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OPENAI_API_KEY is not configured",
        )

    structured_context = build_structured_rag_context(
        db,
        current_user_id,
        card_id=payload.card_id,
        project_id=payload.project_id,
        workspace_id=payload.workspace_id,
    )
    retrieval = retrieve_attachment_chunks(db, current_user_id, payload)

    sources = [
        RagAskSource(
            chunk_id=result.chunk_id,
            attachment_id=result.attachment_id,
            card_id=result.card_id,
            chunk_index=result.chunk_index,
            distance=result.distance,
            bm25_score=result.bm25_score,
            rerank_score=result.rerank_score,
        )
        for result in retrieval.results
    ]

    contents = [result.content for result in retrieval.results]
    attachment_context = build_rag_context(sources, contents)

    if not structured_context and not attachment_context:
        return RagAskResponse(
            query=payload.query,
            answer="I don't know based on the available Projectly data.",
            sources=[],
        )

    prompt = f"""Answer the user's question using only the provided Projectly context.

Rules:
- Use the structured Projectly data first when the question asks about cards, projects, workspaces, epics, sprints, labels, comments, GitHub events, or attachment metadata.
- Use the retrieved attachment context when the question asks about PDF/file contents.
- If neither context contains the answer, say: I don't know based on the available Projectly data.
- Keep the answer concise.
- Do not use outside knowledge.

Structured Projectly data:
{structured_context or "No structured Projectly data was provided."}

Retrieved attachment context:
{attachment_context or "No relevant attachment chunks were found."}

Question:
{payload.query}
"""

    client = OpenAI(api_key=settings.openai_api_key)
    response = client.chat.completions.create(
        model=settings.chat_model,
        messages=[
            {
                "role": "system",
                "content": "You are Projectly's RAG assistant.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0,
    )

    answer = response.choices[0].message.content or ""

    return RagAskResponse(
        query=payload.query,
        answer=answer.strip(),
        sources=sources,
    )
