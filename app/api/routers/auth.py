from fastapi import APIRouter, status

from app.api.deps import DbSession
from app.core.responses import success_response
from app.schemas.auth import LoginRequest, RegisterRequest
from app.services import auth as auth_service


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: DbSession) -> dict:
    auth_response = auth_service.register_user(db, payload)
    return success_response(data=auth_response, message="User registered")


@router.post("/login")
def login(payload: LoginRequest, db: DbSession) -> dict:
    auth_response = auth_service.login_user(db, payload)
    return success_response(data=auth_response, message="Login successful")
