from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.auth import UserResponse, normalize_email


MemberInviteRole = Literal["member", "admin", "guest"]


class MemberInviteRequest(BaseModel):
    user_id: Optional[int] = None
    email: Optional[str] = Field(default=None, min_length=3, max_length=255)
    role: MemberInviteRole = "member"

    @field_validator("role", mode="before")
    @classmethod
    def normalize_role(cls, value: str) -> str:
        return value.strip().lower()

    @model_validator(mode="after")
    def validate_invited_user(self) -> "MemberInviteRequest":
        if self.user_id is None and self.email is None:
            raise ValueError("Either user_id or email is required")
        if self.email is not None:
            self.email = normalize_email(self.email)
        return self


class WorkspaceMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    role: str
    user: UserResponse
    created_at: datetime
    updated_at: datetime


class WorkspaceMemberRoleUpdate(BaseModel):
    role: Literal["member", "admin"]

    @field_validator("role", mode="before")
    @classmethod
    def normalize_role(cls, value: str) -> str:
        return value.strip().lower()


class ProjectMemberResponse(BaseModel):
    id: Optional[int]
    project_id: int
    membership_type: Literal["workspace", "project_guest"]
    role: Optional[str]
    user: UserResponse
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
