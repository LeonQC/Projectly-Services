from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CardCommentCreate(BaseModel):
    body: str = Field(min_length=1)


class CardCommentUpdate(BaseModel):
    body: str = Field(min_length=1)


class CardCommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    card_id: int
    author_id: int
    body: str
    archived: bool
    created_at: datetime
    updated_at: datetime
