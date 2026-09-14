from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class RagChunkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int | None
    project_id: int | None
    card_id: int | None
    source_type: str
    source_id: int
    source_subtype: str | None
    chunk_index: int
    title: str | None
    content: str
    chunk_metadata: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime