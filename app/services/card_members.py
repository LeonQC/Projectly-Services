from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.project import Card, CardMember
from app.models.user import User
from app.schemas.auth import UserResponse
from app.schemas.card_member import CardMemberCreate, CardMemberResponse
from app.services.access import get_user_or_404
from app.services.activities import create_card_activity
from app.services.cards import ensure_card_access
from app.services.projects import get_project_or_404, user_can_access_project


def get_card_member_or_404(db: Session, member_id: int) -> CardMember:
    member = db.get(CardMember, member_id)
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card member not found")
    return member


def build_card_member_response(member: CardMember, user: User) -> CardMemberResponse:
    return CardMemberResponse(
        id=member.id,
        card_id=member.card_id,
        user_id=member.user_id,
        added_by_id=member.added_by_id,
        user=UserResponse.model_validate(user),
        created_at=member.created_at,
        updated_at=member.updated_at,
    )


def ensure_user_is_project_member(db: Session, card: Card, user_id: int) -> User:
    user = get_user_or_404(db, user_id)
    project = get_project_or_404(db, card.project_id)
    if not user_can_access_project(db, user_id, project):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is not a project member")
    return user


def list_card_members(db: Session, card_id: int, current_user_id: int) -> list[CardMemberResponse]:
    ensure_card_access(db, current_user_id, card_id)
    statement = (
        select(CardMember, User)
        .join(User, User.id == CardMember.user_id)
        .where(CardMember.card_id == card_id)
        .order_by(CardMember.created_at.asc(), CardMember.id.asc())
    )
    return [build_card_member_response(member, user) for member, user in db.execute(statement).all()]


def create_card_member(
    db: Session,
    card_id: int,
    current_user_id: int,
    payload: CardMemberCreate,
) -> CardMemberResponse:
    card = ensure_card_access(db, current_user_id, card_id)
    member_user = ensure_user_is_project_member(db, card, payload.user_id)
    member = CardMember(card_id=card_id, user_id=member_user.id, added_by_id=current_user_id)
    db.add(member)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Card member already exists") from exc

    create_card_activity(
        db,
        card_id=card_id,
        actor_id=current_user_id,
        action="member_added",
        metadata={"card_member_id": member.id, "user_id": member.user_id},
    )
    db.commit()
    db.refresh(member)
    return build_card_member_response(member, member_user)


def delete_card_member(db: Session, member_id: int, current_user_id: int) -> None:
    member = get_card_member_or_404(db, member_id)
    ensure_card_access(db, current_user_id, member.card_id)
    card_id = member.card_id
    user_id = member.user_id
    db.delete(member)
    create_card_activity(
        db,
        card_id=card_id,
        actor_id=current_user_id,
        action="member_removed",
        metadata={"card_member_id": member_id, "user_id": user_id},
    )
    db.commit()
