# answer: 
from fastapi import HTTPException, status
from openai import OpenAI
from sqlalchemy.orm import Session

from app.core.config import settings
from app.schemas.rag import RagAskRequest, RagAskResponse, RagAskSource
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

    retrieval = retrieve_attachment_chunks(db, current_user_id, payload)

    sources = [
        RagAskSource(
            chunk_id=result.chunk_id,
            attachment_id=result.attachment_id,
            card_id=result.card_id,
            chunk_index=result.chunk_index,
            distance=result.distance,
        )
        for result in retrieval.results
    ]

    contents = [result.content for result in retrieval.results]
    context = build_rag_context(sources, contents)

    if not context:
        return RagAskResponse(
            query=payload.query,
            answer="I don't know based on the available attachments.",
            sources=[],
        )

    prompt = f"""Answer the user's question using only the provided Projectly attachment context.

Rules:
- If the context does not contain the answer, say: I don't know based on the available attachments.
- Keep the answer concise.
- Do not use outside knowledge.

Context:
{context}

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