from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AttachmentChunkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    attachment_document_id: int
    attachment_id: int
    card_id: int
    chunk_index: int
    content: str
    token_count: int | None
    page_number: int | None
    created_at: datetime
    updated_at: datetime