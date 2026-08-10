from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.project import CardAttachment, CardComment
from app.schemas.attachment import CardAttachmentResponse
from app.schemas.comment import CardCommentCreate, CardCommentUpdate
from app.schemas.comment import CardCommentResponse
from app.services.access import ensure_card_access, ensure_comment_access
from app.services.activities import create_card_activity


def build_comment_response(comment: CardComment, attachments: list[CardAttachment]) -> CardCommentResponse:
    return CardCommentResponse(
        id=comment.id,
        card_id=comment.card_id,
        author_id=comment.author_id,
        body=comment.body,
        archived=comment.archived,
        attachments=[CardAttachmentResponse.model_validate(attachment) for attachment in attachments],
        created_at=comment.created_at,
        updated_at=comment.updated_at,
    )


def get_comment_attachments(db: Session, comment_ids: list[int]) -> dict[int, list[CardAttachment]]:
    if not comment_ids:
        return {}

    statement = (
        select(CardAttachment)
        .where(CardAttachment.comment_id.in_(comment_ids))
        .order_by(CardAttachment.created_at.asc(), CardAttachment.id.asc())
    )
    attachments_by_comment: dict[int, list[CardAttachment]] = {}
    for attachment in db.scalars(statement).all():
        if attachment.comment_id is None:
            continue
        attachments_by_comment.setdefault(attachment.comment_id, []).append(attachment)
    return attachments_by_comment


def list_card_comments(db: Session, card_id: int, current_user_id: int) -> list[CardCommentResponse]:
    ensure_card_access(db, current_user_id, card_id)
    statement = (
        select(CardComment)
        .where(CardComment.card_id == card_id, CardComment.archived.is_(False))
        .order_by(CardComment.created_at.asc(), CardComment.id.asc())
    )
    comments = list(db.scalars(statement).all())
    attachments_by_comment = get_comment_attachments(db, [comment.id for comment in comments])
    return [
        build_comment_response(comment, attachments_by_comment.get(comment.id, []))
        for comment in comments
    ]


def create_card_comment(
    db: Session,
    card_id: int,
    author_id: int,
    payload: CardCommentCreate,
) -> CardCommentResponse:
    ensure_card_access(db, author_id, card_id)
    body = payload.body.strip()
    if not body:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Comment body is required")

    comment = CardComment(card_id=card_id, author_id=author_id, body=body)
    db.add(comment)
    db.flush()

    attachments: list[CardAttachment] = []
    for attachment_payload in payload.attachments:
        attachment = CardAttachment(
            card_id=card_id,
            comment_id=comment.id,
            file_name=attachment_payload.file_name,
            file_url=attachment_payload.file_url,
            file_type=attachment_payload.file_type,
            file_size=attachment_payload.file_size,
            uploaded_by_id=author_id,
        )
        db.add(attachment)
        attachments.append(attachment)

    create_card_activity(
        db,
        card_id=card_id,
        actor_id=author_id,
        action="comment_added",
        metadata={"comment_id": comment.id, "attachment_count": len(attachments)},
    )
    from app.services.notifications import create_comment_mention_notifications

    create_comment_mention_notifications(
        db,
        card_id=card_id,
        comment_id=comment.id,
        author_id=author_id,
        body=body,
    )
    db.commit()
    db.refresh(comment)
    for attachment in attachments:
        db.refresh(attachment)
    return build_comment_response(comment, attachments)


def update_card_comment(
    db: Session,
    comment_id: int,
    current_user_id: int,
    payload: CardCommentUpdate,
) -> CardCommentResponse:
    comment = ensure_comment_access(db, current_user_id, comment_id)
    body = payload.body.strip()
    if not body:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Comment body is required")

    comment.body = body
    create_card_activity(
        db,
        card_id=comment.card_id,
        actor_id=current_user_id,
        action="comment_updated",
        metadata={"comment_id": comment.id},
    )
    db.commit()
    db.refresh(comment)
    attachments = get_comment_attachments(db, [comment.id]).get(comment.id, [])
    return build_comment_response(comment, attachments)


def archive_card_comment(db: Session, comment_id: int, current_user_id: int) -> None:
    comment = ensure_comment_access(db, current_user_id, comment_id)
    comment.archived = True
    create_card_activity(
        db,
        card_id=comment.card_id,
        actor_id=current_user_id,
        action="comment_deleted",
        metadata={"comment_id": comment.id},
    )
    db.commit()
