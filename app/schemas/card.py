from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.attachment import CardAttachmentResponse
from app.schemas.card_label import CardLabelResponse
from app.schemas.card_link import CardLinkResponse
from app.schemas.card_member import CardMemberResponse
from app.schemas.comment import CardCommentResponse


CardStatus = Literal["backlog", "todo", "in_progress", "done"]


class CardCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    epic_id: Optional[int] = None
    status: CardStatus = "backlog"
    position: int = 0

    @field_validator("title")
    @classmethod
    def validate_title(cls, title: str) -> str:
        normalized_title = title.strip()
        if not normalized_title:
            raise ValueError("Card title is required")
        return normalized_title

    @field_validator("description")
    @classmethod
    def validate_description(cls, description: Optional[str]) -> Optional[str]:
        if description is None:
            return description
        normalized_description = description.strip()
        return normalized_description or None


class CardUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    epic_id: Optional[int] = None
    status: Optional[CardStatus] = None
    position: Optional[int] = None
    archived: Optional[bool] = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, title: Optional[str]) -> Optional[str]:
        if title is None:
            return title
        normalized_title = title.strip()
        if not normalized_title:
            raise ValueError("Card title is required")
        return normalized_title

    @field_validator("description")
    @classmethod
    def validate_description(cls, description: Optional[str]) -> Optional[str]:
        if description is None:
            return description
        normalized_description = description.strip()
        return normalized_description or None


class CardMove(BaseModel):
    status: Optional[CardStatus] = None
    position: Optional[int] = None
    sprint_id: Optional[int] = None


class CardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    epic_id: Optional[int]
    sprint_id: Optional[int]
    title: str
    description: Optional[str]
    status: str
    position: int
    archived: bool
    created_at: datetime
    updated_at: datetime


class CardDetailResponse(BaseModel):
    card: CardResponse
    labels: list[CardLabelResponse]
    members: list[CardMemberResponse]
    attachments: list[CardAttachmentResponse]
    comments: list[CardCommentResponse]
    links: list[CardLinkResponse]
