from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SprintStatus = Literal["planned", "active", "completed"]


class SprintCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    goal: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: SprintStatus = "planned"

    @field_validator("name")
    @classmethod
    def validate_name(cls, name: str) -> str:
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("Sprint name is required")
        return normalized_name

    @field_validator("goal")
    @classmethod
    def validate_goal(cls, goal: Optional[str]) -> Optional[str]:
        if goal is None:
            return goal
        normalized_goal = goal.strip()
        return normalized_goal or None

    @model_validator(mode="after")
    def validate_dates(self) -> "SprintCreate":
        if self.start_date is not None and self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("Sprint end date cannot be before start date")
        return self


class SprintUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    goal: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[SprintStatus] = None
    archived: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, name: Optional[str]) -> Optional[str]:
        if name is None:
            return name
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("Sprint name is required")
        return normalized_name

    @field_validator("goal")
    @classmethod
    def validate_goal(cls, goal: Optional[str]) -> Optional[str]:
        if goal is None:
            return goal
        normalized_goal = goal.strip()
        return normalized_goal or None

    @model_validator(mode="after")
    def validate_dates(self) -> "SprintUpdate":
        if self.start_date is not None and self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("Sprint end date cannot be before start date")
        return self


class SprintResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    epic_id: int
    name: str
    goal: Optional[str]
    start_date: Optional[date]
    end_date: Optional[date]
    status: SprintStatus
    archived: bool
    created_at: datetime
    updated_at: datetime


class CardSprintUpdate(BaseModel):
    sprint_id: Optional[int] = Field(default=None, gt=0)
