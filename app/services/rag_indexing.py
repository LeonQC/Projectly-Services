"""
delete_rag_chunks_for_source
  删除某个 source 的旧 chunks

build_card_rag_text
  把 card title + status + description 拼成可 embedding 的文本

build_comment_rag_text
  把 comment body 拼成可 embedding 的文本

index_card
  card -> chunks -> embeddings -> rag_chunks

index_comment
  comment -> chunks -> embeddings -> rag_chunks
"""
from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.project import (
    AttachmentDocument,
    Card,
    CardAttachment,
    CardComment,
    Project,
    RagChunk,
)
from app.services.attachment_chunking import split_markdown_into_chunks
from app.services.embedding_client import create_embeddings


def delete_rag_chunks_for_source(
    db: Session,
    source_type: str,
    source_id: int,
) -> None:
    db.execute(
        delete(RagChunk).where(
            RagChunk.source_type == source_type,
            RagChunk.source_id == source_id,
        )
    )


def build_card_rag_text(card: Card) -> str:
    parts = [
        f"Card title: {card.title}",
        f"Card status: {card.status}",
    ]

    if card.description:
        parts.append(f"Card description:\n{card.description}")

    return "\n\n".join(parts)


def build_comment_rag_text(comment: CardComment) -> str:
    return "\n\n".join(
        [
            f"Comment author id: {comment.author_id}",
            "Comment body:",
            comment.body,
        ]
    )


def index_card(
    db: Session,
    card_id: int,
) -> list[RagChunk]:
    card = db.get(Card, card_id)
    if card is None:
        return []

    project = db.get(Project, card.project_id)
    if project is None:
        return []

    content = build_card_rag_text(card)
    chunk_texts = split_markdown_into_chunks(content)

    if not chunk_texts:
        delete_rag_chunks_for_source(db, "card", card.id)
        db.commit()
        return []

    embeddings = create_embeddings(chunk_texts)

    delete_rag_chunks_for_source(db, "card", card.id)

    chunks = [
        RagChunk(
            workspace_id=project.workspace_id,
            project_id=project.id,
            card_id=card.id,
            source_type="card",
            source_id=card.id,
            source_subtype="card_title_description",
            chunk_index=index,
            title=card.title,
            content=chunk_text,
            embedding=embedding,
            chunk_metadata={
                "status": card.status,
                "epic_id": card.epic_id,
                "sprint_id": card.sprint_id,
            },
        )
        for index, (chunk_text, embedding) in enumerate(zip(chunk_texts, embeddings, strict=True))
    ]

    db.add_all(chunks)
    db.commit()

    for chunk in chunks:
        db.refresh(chunk)

    return chunks


def index_comment(
    db: Session,
    comment_id: int,
) -> list[RagChunk]:
    comment = db.get(CardComment, comment_id)
    if comment is None:
        return []

    card = db.get(Card, comment.card_id)
    if card is None:
        return []

    project = db.get(Project, card.project_id)
    if project is None:
        return []

    content = build_comment_rag_text(comment)
    chunk_texts = split_markdown_into_chunks(content)

    if not chunk_texts:
        delete_rag_chunks_for_source(db, "comment", comment.id)
        db.commit()
        return []

    embeddings = create_embeddings(chunk_texts)

    delete_rag_chunks_for_source(db, "comment", comment.id)

    chunks = [
        RagChunk(
            workspace_id=project.workspace_id,
            project_id=project.id,
            card_id=card.id,
            source_type="comment",
            source_id=comment.id,
            source_subtype="comment_body",
            chunk_index=index,
            title=card.title,
            content=chunk_text,
            embedding=embedding,
            chunk_metadata={
                "author_id": comment.author_id,
                "card_title": card.title,
            },
        )
        for index, (chunk_text, embedding) in enumerate(zip(chunk_texts, embeddings, strict=True))
    ]

    db.add_all(chunks)
    db.commit()

    for chunk in chunks:
        db.refresh(chunk)

    return chunks

def index_attachment(
    db: Session,
    attachment_id: int,
) -> list[RagChunk]:
    attachment = db.get(CardAttachment, attachment_id)
    if attachment is None:
        return []

    document = db.query(AttachmentDocument).filter(
        AttachmentDocument.attachment_id == attachment.id
    ).one_or_none()

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Extract attachment document before indexing",
        )

    if document.extraction_status != "completed" or not document.content_markdown:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Attachment document extraction is not completed",
        )

    card = db.get(Card, attachment.card_id)
    if card is None:
        return []

    project = db.get(Project, card.project_id)
    if project is None:
        return []

    chunk_texts = split_markdown_into_chunks(document.content_markdown)

    if not chunk_texts:
        delete_rag_chunks_for_source(db, "attachment", attachment.id)
        db.commit()
        return []

    embeddings = create_embeddings(chunk_texts)

    delete_rag_chunks_for_source(db, "attachment", attachment.id)

    chunks = [
        RagChunk(
            workspace_id=project.workspace_id,
            project_id=project.id,
            card_id=card.id,
            source_type="attachment",
            source_id=attachment.id,
            source_subtype="attachment_pdf",
            chunk_index=index,
            title=attachment.file_name,
            content=chunk_text,
            embedding=embedding,
            chunk_metadata={
                "attachment_id": attachment.id,
                "file_name": attachment.file_name,
                "file_type": attachment.file_type,
                "file_size": attachment.file_size,
            },
        )
        for index, (chunk_text, embedding) in enumerate(zip(chunk_texts, embeddings, strict=True))
    ]

    db.add_all(chunks)
    db.commit()

    for chunk in chunks:
        db.refresh(chunk)

    return chunks
