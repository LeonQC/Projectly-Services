from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


CardLinkRelationship = Literal[
    "is_blocked_by",
    "blocks",
    "is_cloned_by",
    "clones",
    "is_duplicated_by",
    "duplicates",
    "relates_to",
]


class LinkedCardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    epic_id: Optional[int]
    title: str
    status: str
    archived: bool


class CardLinkCreate(BaseModel):
    target_card_id: int = Field(gt=0)
    relationship: CardLinkRelationship


class CardLinkResponse(BaseModel):
    id: int
    source_card_id: int
    target_card_id: int
    relationship: CardLinkRelationship
    created_by_id: Optional[int]
    source_card: LinkedCardResponse
    target_card: LinkedCardResponse
    created_at: datetime
    updated_at: datetime
