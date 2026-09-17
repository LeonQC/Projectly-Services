from pydantic import BaseModel, Field


class RagRetrieveRequest(BaseModel):
    workspace_id: int | None = None
    project_id: int | None = None
    card_id: int | None = None
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)

class RagRetrieveResult(BaseModel):
    chunk_id: int

    source_type: str
    source_id: int
    source_subtype: str | None = None
    title: str | None = None

    workspace_id: int | None = None
    project_id: int | None = None
    card_id: int | None = None

    # 临时保留，兼容当前前端
    attachment_id: int | None = None

    chunk_index: int
    content: str

    distance: float | None = None
    bm25_score: float | None = None
    rerank_score: float | None = None

class RagRetrieveResponse(BaseModel):
    query: str
    top_k: int
    results: list[RagRetrieveResult]

class RagAskRequest(RagRetrieveRequest):
    pass


class RagAskSource(BaseModel):
    chunk_id: int

    source_type: str
    source_id: int
    source_subtype: str | None = None
    title: str | None = None

    workspace_id: int | None = None
    project_id: int | None = None
    card_id: int | None = None

    # 临时保留，兼容当前前端
    attachment_id: int | None = None

    chunk_index: int
    distance: float | None = None
    bm25_score: float | None = None
    rerank_score: float | None = None


class RagAskResponse(BaseModel):
    query: str
    answer: str
    sources: list[RagAskSource]
