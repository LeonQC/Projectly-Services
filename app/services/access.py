from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.project import Card, CardComment
from app.models.user import User


def get_user_or_404(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def get_card_or_404(db: Session, card_id: int) -> Card:
    card = db.get(Card, card_id)
    if card is None or card.archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")
    return card


def get_comment_or_404(db: Session, comment_id: int) -> CardComment:
    comment = db.get(CardComment, comment_id)
    if comment is None or comment.archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    return comment


def ensure_card_access(db: Session, user_id: int, card_id: int) -> Card:
    get_user_or_404(db, user_id)
    return get_card_or_404(db, card_id)


def ensure_comment_access(db: Session, user_id: int, comment_id: int) -> CardComment:
    get_user_or_404(db, user_id)
    comment = get_comment_or_404(db, comment_id)
    get_card_or_404(db, comment.card_id)
    return comment
