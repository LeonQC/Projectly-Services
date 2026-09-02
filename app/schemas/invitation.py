from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.auth import UserResponse, normalize_email


InvitationTargetType = Literal["workspace", "project"]
InvitationStatus = Literal["pending", "accepted", "declined"]
InvitationRole = Literal["member", "admin", "guest"]


class InvitationCreate(BaseModel):
    user_id: Optional[int] = None
    email: Optional[str] = Field(default=None, min_length=3, max_length=255)
    role: InvitationRole = "member"

    @field_validator("role", mode="before")
    @classmethod
    def normalize_role(cls, value: str) -> str:
        return value.strip().lower()

    @model_validator(mode="after")
    def validate_invitee(self) -> "InvitationCreate":
        if self.user_id is None and self.email is None:
            raise ValueError("Either user_id or email is required")
        if self.email is not None:
            self.email = normalize_email(self.email)
        return self


class InvitationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    target_type: InvitationTargetType
    target_id: int
    target_name: str
    inviter_id: int
    invitee_id: int
    role: str
    status: InvitationStatus
    inviter: UserResponse
    invitee: UserResponse
    created_at: datetime
    updated_at: datetime
