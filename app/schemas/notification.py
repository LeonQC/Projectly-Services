from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.schemas.auth import UserResponse
from app.schemas.invitation import InvitationResponse


class CommentMentionTarget(BaseModel):
    card_id: int
    comment_id: int


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recipient_id: int
    actor_id: Optional[int]
    type: str
    title: str
    body: Optional[str]
    source_type: Optional[str]
    source_id: Optional[int]
    read_at: Optional[datetime]
    created_at: datetime
    actor: Optional[UserResponse] = None
    invitation: Optional[InvitationResponse] = None
    comment_mention: Optional[CommentMentionTarget] = None
