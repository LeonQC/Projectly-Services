from pydantic import BaseModel, Field, field_validator

from app.schemas.auth import normalize_email


class UsernameUpdate(BaseModel):
    username: str = Field(min_length=1, max_length=80)

    @field_validator("username")
    @classmethod
    def validate_username(cls, username: str) -> str:
        normalized_username = username.strip()
        if not normalized_username:
            raise ValueError("Username is required")
        return normalized_username


class EmailUpdate(BaseModel):
    email: str = Field(min_length=3, max_length=255)

    @field_validator("email")
    @classmethod
    def validate_email(cls, email: str) -> str:
        return normalize_email(email)


class ThemeUpdate(BaseModel):
    theme: str = Field(min_length=1, max_length=20)

    @field_validator("theme")
    @classmethod
    def validate_theme(cls, theme: str) -> str:
        normalized_theme = theme.strip().lower()
        if normalized_theme not in {"system", "light", "dark"}:
            raise ValueError("Theme must be system, light, or dark")
        return normalized_theme
