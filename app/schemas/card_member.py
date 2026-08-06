from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.auth import UserResponse


class CardMemberCreate(BaseModel):
    user_id: int = Field(gt=0)


class CardMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    card_id: int
    user_id: int
    added_by_id: Optional[int]
    user: UserResponse
    created_at: datetime
    updated_at: datetime
