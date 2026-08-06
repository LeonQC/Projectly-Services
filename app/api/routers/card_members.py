from fastapi import APIRouter, status

from app.api.deps import AuthenticatedUserId, DbSession
from app.core.responses import success_response
from app.schemas.card_member import CardMemberCreate
from app.services import card_members as card_members_service


router = APIRouter(tags=["cards-detail"])


@router.get("/cards/{card_id}/members")
def list_card_members(card_id: int, db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    members = card_members_service.list_card_members(db, card_id, current_user_id)
    return success_response(data=members)


@router.post("/cards/{card_id}/members", status_code=status.HTTP_201_CREATED)
def create_card_member(
    card_id: int,
    payload: CardMemberCreate,
    db: DbSession,
    current_user_id: AuthenticatedUserId,
) -> dict:
    member = card_members_service.create_card_member(db, card_id, current_user_id, payload)
    return success_response(data=member, message="Card member created")


@router.delete("/card-members/{member_id}")
def delete_card_member(member_id: int, db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    card_members_service.delete_card_member(db, member_id, current_user_id)
    return success_response(message="Card member deleted")
