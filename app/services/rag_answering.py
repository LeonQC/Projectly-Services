# answer: merge chunks into context string & build prompt & OpenAI chat model
from fastapi import HTTPException, status
from openai import OpenAI
from sqlalchemy.orm import Session

from app.core.config import settings
from app.schemas.rag import RagAskRequest, RagAskResponse, RagAskSource
from app.services.rag_context import build_structured_rag_context
from app.services.rag_retrieval import retrieve_rag_chunks

def build_rag_context(
    sources: list[RagAskSource],
    contents: list[str],
) -> str:
    blocks: list[str] = []

    for source, content in zip(sources, contents, strict=True):
        blocks.append(
            "\n".join(
                [
                    (
                        f"[Source type={source.source_type}, "
                        f"source_id={source.source_id}, "
                        f"subtype={source.source_subtype}, "
                        f"card_id={source.card_id}, "
                        f"title={source.title}]"
                    ),
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
    retrieval = retrieve_rag_chunks(db, current_user_id, payload)

    sources = [
        RagAskSource(
            chunk_id=result.chunk_id,
            source_type=result.source_type,
            source_id=result.source_id,
            source_subtype=result.source_subtype,
            title=result.title,
            workspace_id=result.workspace_id,
            project_id=result.project_id,
            card_id=result.card_id,
            attachment_id=result.attachment_id,
            chunk_index=result.chunk_index,
            distance=result.distance,
            bm25_score=result.bm25_score,
            rerank_score=result.rerank_score,
     )
        for result in retrieval.results
    ]

    contents = [result.content for result in retrieval.results]
    retrieved_context = build_rag_context(sources, contents)

    if not structured_context and not retrieved_context:
        return RagAskResponse(
            query=payload.query,
            answer="I don't know based on the available Projectly data.",
            sources=[],
        )

    prompt = f"""Answer the user's question using only the provided Projectly context.

    Rules:
    - The retrieved context may come from attachments, cards, comments, projects, or workspaces.
    - Use structured Projectly data and retrieved RAG context together.
    - If the context does not contain the answer, say: I don't know based on the available Projectly data.
    - Keep the answer concise.
    - Do not use outside knowledge.

    Structured Projectly data:
    {structured_context or "No structured Projectly data was provided."}

    Retrieved RAG context:
    {retrieved_context or "No relevant RAG chunks were found."}

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
