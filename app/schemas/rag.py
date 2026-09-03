from pydantic import BaseModel, Field


class RagRetrieveRequest(BaseModel):
    workspace_id: int | None = None
    project_id: int | None = None
    card_id: int | None = None
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


class RagRetrieveResult(BaseModel):
    chunk_id: int
    attachment_id: int
    card_id: int
    chunk_index: int
    content: str
    distance: float | None = None


class RagRetrieveResponse(BaseModel):
    query: str
    top_k: int
    results: list[RagRetrieveResult]