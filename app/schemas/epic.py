from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EpicCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    deadline: Optional[date] = None
    position: int = 0

    @field_validator("title")
    @classmethod
    def validate_title(cls, title: str) -> str:
        normalized_title = title.strip()
        if not normalized_title:
            raise ValueError("Epic title is required")
        return normalized_title


class EpicUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=160)
    deadline: Optional[date] = None
    position: Optional[int] = None
    archived: Optional[bool] = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, title: Optional[str]) -> Optional[str]:
        if title is None:
            return title
        normalized_title = title.strip()
        if not normalized_title:
            raise ValueError("Epic title is required")
        return normalized_title


class EpicResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    title: str
    deadline: Optional[date]
    position: int
    archived: bool
    created_at: datetime
    updated_at: datetime
