from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CardLabelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    color: Optional[str] = Field(default=None, max_length=20)

    @field_validator("name")
    @classmethod
    def validate_name(cls, name: str) -> str:
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("Label name is required")
        return normalized_name

    @field_validator("color")
    @classmethod
    def validate_color(cls, color: Optional[str]) -> Optional[str]:
        if color is None:
            return color
        normalized_color = color.strip()
        return normalized_color or None


class CardLabelUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=60)
    color: Optional[str] = Field(default=None, max_length=20)

    @field_validator("name")
    @classmethod
    def validate_name(cls, name: Optional[str]) -> Optional[str]:
        if name is None:
            return name
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("Label name is required")
        return normalized_name

    @field_validator("color")
    @classmethod
    def validate_color(cls, color: Optional[str]) -> Optional[str]:
        if color is None:
            return color
        normalized_color = color.strip()
        return normalized_color or None


class CardLabelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    card_id: int
    name: str
    color: Optional[str]
    created_by_id: Optional[int]
    created_at: datetime
    updated_at: datetime
