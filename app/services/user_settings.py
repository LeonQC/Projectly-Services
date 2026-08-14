from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.auth import UserResponse
from app.schemas.user_settings import EmailUpdate, ThemeUpdate, UsernameUpdate
from app.services.auth import get_user_by_email


def get_settings_user(db: Session, current_user_id: int) -> User:
    user = db.get(User, current_user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")

    return user


def get_user_settings(db: Session, current_user_id: int) -> UserResponse:
    user = get_settings_user(db, current_user_id)
    return UserResponse.model_validate(user)


def update_username(db: Session, current_user_id: int, payload: UsernameUpdate) -> UserResponse:
    user = get_settings_user(db, current_user_id)
    user.username = payload.username
    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)


def update_email(db: Session, current_user_id: int, payload: EmailUpdate) -> UserResponse:
    user = get_settings_user(db, current_user_id)
    existing_user = get_user_by_email(db, payload.email)
    if existing_user is not None and existing_user.id != user.id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user.email = payload.email

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered") from exc

    db.refresh(user)
    return UserResponse.model_validate(user)


def update_theme(db: Session, current_user_id: int, payload: ThemeUpdate) -> UserResponse:
    user = get_settings_user(db, current_user_id)
    user.theme = payload.theme
    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)
