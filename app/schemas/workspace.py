from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def validate_name(cls, name: str) -> str:
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("Workspace name is required")
        return normalized_name


class WorkspaceUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    archived: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, name: Optional[str]) -> Optional[str]:
        if name is None:
            return name
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("Workspace name is required")
        return normalized_name


class WorkspaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    owner_id: int
    archived: bool
    created_at: datetime
    updated_at: datetime
