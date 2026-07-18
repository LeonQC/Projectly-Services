from fastapi import APIRouter, status

from app.api.deps import CurrentUserId, DbSession
from app.core.responses import success_response
from app.schemas.comment import CardCommentCreate, CardCommentResponse, CardCommentUpdate
from app.services import comments as comments_service


router = APIRouter(tags=["comments"])


@router.get("/cards/{card_id}/comments")
def list_card_comments(card_id: int, db: DbSession, current_user_id: CurrentUserId) -> dict:
    comments = comments_service.list_card_comments(db, card_id, current_user_id)
    return success_response(
        data=[CardCommentResponse.model_validate(comment) for comment in comments]
    )


@router.post("/cards/{card_id}/comments", status_code=status.HTTP_201_CREATED)
def create_card_comment(
    card_id: int,
    payload: CardCommentCreate,
    db: DbSession,
    current_user_id: CurrentUserId,
) -> dict:
    comment = comments_service.create_card_comment(db, card_id, current_user_id, payload)
    return success_response(data=CardCommentResponse.model_validate(comment), message="Comment created")


@router.patch("/comments/{comment_id}")
def update_card_comment(
    comment_id: int,
    payload: CardCommentUpdate,
    db: DbSession,
    current_user_id: CurrentUserId,
) -> dict:
    comment = comments_service.update_card_comment(db, comment_id, current_user_id, payload)
    return success_response(data=CardCommentResponse.model_validate(comment), message="Comment updated")


@router.delete("/comments/{comment_id}")
def delete_card_comment(comment_id: int, db: DbSession, current_user_id: CurrentUserId) -> dict:
    comments_service.archive_card_comment(db, comment_id, current_user_id)
    return success_response(message="Comment deleted")
