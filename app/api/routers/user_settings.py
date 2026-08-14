from fastapi import APIRouter

from app.api.deps import AuthenticatedUserId, DbSession
from app.core.responses import success_response
from app.schemas.auth import UserResponse
from app.schemas.user_settings import EmailUpdate, ThemeUpdate, UsernameUpdate
from app.services import user_settings as user_settings_service


router = APIRouter(prefix="/user-settings", tags=["user-settings"])


@router.get("")
def get_user_settings(db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    user = user_settings_service.get_user_settings(db, current_user_id)
    return success_response(data=UserResponse.model_validate(user))


@router.patch("/username")
def update_username(payload: UsernameUpdate, db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    user = user_settings_service.update_username(db, current_user_id, payload)
    return success_response(data=UserResponse.model_validate(user), message="Username updated")


@router.patch("/email")
def update_email(payload: EmailUpdate, db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    user = user_settings_service.update_email(db, current_user_id, payload)
    return success_response(data=UserResponse.model_validate(user), message="Email updated")


@router.patch("/theme")
def update_theme(payload: ThemeUpdate, db: DbSession, current_user_id: AuthenticatedUserId) -> dict:
    user = user_settings_service.update_theme(db, current_user_id, payload)
    return success_response(data=UserResponse.model_validate(user), message="Theme updated")
