import json
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import AuthResponse, GoogleOAuthRequest, LoginRequest, RegisterRequest, UserResponse


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    statement = select(User).where(func.lower(User.email) == email.lower())
    return db.scalar(statement)


def get_user_by_google_sub(db: Session, google_sub: str) -> Optional[User]:
    statement = select(User).where(User.google_sub == google_sub)
    return db.scalar(statement)


def build_auth_response(user: User) -> AuthResponse:
    return AuthResponse(
        access_token=create_access_token(user.id),
        user=UserResponse.model_validate(user),
    )


def get_current_user(db: Session, user_id: int) -> UserResponse:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")

    return UserResponse.model_validate(user)


def register_user(db: Session, payload: RegisterRequest) -> AuthResponse:
    existing_user = get_user_by_email(db, payload.email)
    if existing_user is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        username=payload.username.strip(),
        email=payload.email,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered") from exc

    db.refresh(user)
    return build_auth_response(user)


def login_user(db: Session, payload: LoginRequest) -> AuthResponse:
    user = get_user_by_email(db, payload.email)
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")

    return build_auth_response(user)


def verify_google_id_token(id_token: str) -> dict[str, Any]:
    if not settings.google_client_id:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Google OAuth is not configured")

    tokeninfo_url = "https://oauth2.googleapis.com/tokeninfo?" + urlencode({"id_token": id_token})
    try:
        with urlopen(tokeninfo_url, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Google token") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Google token verification failed") from exc

    if payload.get("aud") != settings.google_client_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Google token audience")

    if payload.get("iss") not in {"accounts.google.com", "https://accounts.google.com"}:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Google token issuer")

    if payload.get("email_verified") not in {True, "true", "True"}:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google email is not verified")

    if not payload.get("sub") or not payload.get("email"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Google token payload")

    return payload


def google_login(db: Session, payload: GoogleOAuthRequest) -> AuthResponse:
    google_payload = verify_google_id_token(payload.id_token)
    google_sub = str(google_payload["sub"])
    email = str(google_payload["email"]).strip().lower()
    username = str(google_payload.get("name") or email.split("@", 1)[0]).strip()
    avatar_url = google_payload.get("picture")

    user = get_user_by_google_sub(db, google_sub)
    if user is None:
        user = get_user_by_email(db, email)
        if user is not None and user.google_sub not in {None, google_sub}:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is linked to another Google account")

    if user is None:
        user = User(
            username=username or email,
            email=email,
            hashed_password=None,
            google_sub=google_sub,
            avatar_url=avatar_url,
        )
        db.add(user)
    else:
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")
        user.google_sub = google_sub
        if avatar_url:
            user.avatar_url = str(avatar_url)
        if username and user.username != username:
            user.username = username

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Google account already registered") from exc

    db.refresh(user)
    return build_auth_response(user)
