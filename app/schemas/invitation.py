from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.auth import UserResponse, normalize_email


InvitationTargetType = Literal["workspace", "project"]
InvitationStatus = Literal["pending", "accepted", "declined"]


class InvitationCreate(BaseModel):
    user_id: Optional[int] = None
    email: Optional[str] = Field(default=None, min_length=3, max_length=255)
    role: str = Field(default="member", min_length=1, max_length=20)

    @model_validator(mode="after")
    def validate_invitee(self) -> "InvitationCreate":
        if self.user_id is None and self.email is None:
            raise ValueError("Either user_id or email is required")
        if self.email is not None:
            self.email = normalize_email(self.email)
        self.role = self.role.strip().lower()
        if not self.role or self.role == "owner":
            raise ValueError("Invalid invitation role")
        return self


class InvitationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    target_type: InvitationTargetType
    target_id: int
    inviter_id: int
    invitee_id: int
    role: str
    status: InvitationStatus
    inviter: UserResponse
    invitee: UserResponse
    created_at: datetime
    updated_at: datetime
