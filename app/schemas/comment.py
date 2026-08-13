from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.attachment import CardAttachmentCreate, CardAttachmentResponse


class CardCommentCreate(BaseModel):
    body: str = Field(min_length=1)
    attachments: list[CardAttachmentCreate] = Field(default_factory=list)


class CardCommentUpdate(BaseModel):
    body: str = Field(min_length=1)


class CardCommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    card_id: int
    author_id: int
    body: str
    attachments: list[CardAttachmentResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
