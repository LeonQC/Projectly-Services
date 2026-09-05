from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class AttachmentDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    attachment_id: int
    card_id: int
    file_name: str
    content_json: dict[str, Any] | None
    content_markdown: str | None
    extraction_status: str
    error_message: Optional[str]
    retry_count: int
    created_at: datetime
    updated_at: datetime
