from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.project import CardComment
from app.schemas.comment import CardCommentCreate, CardCommentUpdate
from app.services.access import ensure_card_access, ensure_comment_access
from app.services.activities import create_card_activity


def list_card_comments(db: Session, card_id: int, current_user_id: int) -> list[CardComment]:
    ensure_card_access(db, current_user_id, card_id)
    statement = (
        select(CardComment)
        .where(CardComment.card_id == card_id, CardComment.archived.is_(False))
        .order_by(CardComment.created_at.asc(), CardComment.id.asc())
    )
    return list(db.scalars(statement).all())


def create_card_comment(
    db: Session,
    card_id: int,
    author_id: int,
    payload: CardCommentCreate,
) -> CardComment:
    ensure_card_access(db, author_id, card_id)
    body = payload.body.strip()
    if not body:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Comment body is required")

    comment = CardComment(card_id=card_id, author_id=author_id, body=body)
    db.add(comment)
    db.flush()
    create_card_activity(
        db,
        card_id=card_id,
        actor_id=author_id,
        action="comment_added",
        metadata={"comment_id": comment.id},
    )
    db.commit()
    db.refresh(comment)
    return comment


def update_card_comment(
    db: Session,
    comment_id: int,
    current_user_id: int,
    payload: CardCommentUpdate,
) -> CardComment:
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
    return comment


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
