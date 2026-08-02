from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: Optional[str] = None
    position: int = 0

    @field_validator("name")
    @classmethod
    def validate_name(cls, name: str) -> str:
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("Project name is required")
        return normalized_name

    @field_validator("description")
    @classmethod
    def validate_description(cls, description: Optional[str]) -> Optional[str]:
        if description is None:
            return description
        normalized_description = description.strip()
        return normalized_description or None


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    description: Optional[str] = None
    position: Optional[int] = None
    archived: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, name: Optional[str]) -> Optional[str]:
        if name is None:
            return name
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("Project name is required")
        return normalized_name

    @field_validator("description")
    @classmethod
    def validate_description(cls, description: Optional[str]) -> Optional[str]:
        if description is None:
            return description
        normalized_description = description.strip()
        return normalized_description or None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    name: str
    description: Optional[str]
    position: int
    archived: bool
    created_at: datetime
    updated_at: datetime
