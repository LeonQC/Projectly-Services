from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.auth import UserResponse, normalize_email


class MemberInviteRequest(BaseModel):
    user_id: Optional[int] = None
    email: Optional[str] = Field(default=None, min_length=3, max_length=255)
    role: str = Field(default="member", min_length=1, max_length=20)

    @model_validator(mode="after")
    def validate_invited_user(self) -> "MemberInviteRequest":
        if self.user_id is None and self.email is None:
            raise ValueError("Either user_id or email is required")
        if self.email is not None:
            self.email = normalize_email(self.email)
        self.role = self.role.strip().lower()
        if not self.role:
            raise ValueError("Role is required")
        if self.role == "owner":
            raise ValueError("Owner role cannot be assigned through invite")
        return self


class WorkspaceMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    role: str
    user: UserResponse
    created_at: datetime
    updated_at: datetime


class ProjectMemberResponse(BaseModel):
    id: Optional[int]
    project_id: int
    membership_type: Literal["workspace", "project_guest"]
    role: Optional[str]
    user: UserResponse
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
