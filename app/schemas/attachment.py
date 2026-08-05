from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CardAttachmentCreate(BaseModel):
    file_name: str = Field(min_length=1, max_length=255)
    file_url: str = Field(min_length=1, max_length=500)
    file_type: Optional[str] = Field(default=None, max_length=120)
    file_size: Optional[int] = Field(default=None, ge=0)

    @field_validator("file_name", "file_url")
    @classmethod
    def validate_required_string(cls, value: str) -> str:
        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Value is required")
        return normalized_value

    @field_validator("file_type")
    @classmethod
    def validate_file_type(cls, file_type: Optional[str]) -> Optional[str]:
        if file_type is None:
            return file_type
        normalized_file_type = file_type.strip()
        return normalized_file_type or None


class CardAttachmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    card_id: int
    file_name: str
    file_url: str
    file_type: Optional[str]
    file_size: Optional[int]
    uploaded_by_id: Optional[int]
    created_at: datetime
    updated_at: datetime
