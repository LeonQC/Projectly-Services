from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


def normalize_email(email: str) -> str:
    normalized_email = email.strip().lower()
    if "@" not in normalized_email:
        raise ValueError("Invalid email address")
    return normalized_email


class RegisterRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def validate_username(cls, username: str) -> str:
        normalized_username = username.strip()
        if not normalized_username:
            raise ValueError("Username is required")
        return normalized_username

    @field_validator("email")
    @classmethod
    def validate_email(cls, email: str) -> str:
        return normalize_email(email)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, email: str) -> str:
        return normalize_email(email)


class GoogleOAuthRequest(BaseModel):
    id_token: str = Field(min_length=1)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    avatar_url: Optional[str]
    theme: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
