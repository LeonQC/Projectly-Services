"""
通用文本chunking
职责：
1. 接收已经构建好的文本。
2. 按 token 数量切分文本。
3. 保留相邻 chunks 的 overlap。
4. 尽量按照 heading、段落和句子边界切分。
5. 返回 chunk content、chunk_index、token_count 和页面 metadata。

Card
→ title + description + label + member + linked work item + status
→ 一起 chunk
→ source_type=card

GitHub Event
→ repository + event/action + PR/commit/message
→ 每条 event 独立 chunk
→ source_type=github_event

Comment 1
→ 单独 chunk
→ source_type=comment, source_id=comment_1

Comment 2
→ 单独 chunk
→ source_type=comment, source_id=comment_2

Attachment
→ Docling Markdown
→ 单独 chunk
→ source_type=attachment

Project / Sprint / Epic
→ 各自构建文本
→ 各自 chunk

Workspace
→ name + description
→ 独立 chunk
→ source_type=workspace

所有结果统一进入rag_chunks
"""

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from transformers import AutoTokenizer, PreTrainedTokenizerBase

from app.core.config import settings


DEFAULT_CHUNK_SIZE = 220
DEFAULT_CHUNK_OVERLAP = 30

# 定义切分结果
@dataclass(frozen=True, slots=True)
class RagChunkDraft:
    chunk_index: int
    content: str
    token_count: int
    page_number: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

# 加载 tokenizer
@lru_cache(maxsize=1)
def get_chunking_tokenizer() -> PreTrainedTokenizerBase:
    tokenizer = AutoTokenizer.from_pretrained(
        settings.embedding_model,
        use_fast=True,
    )

    if not tokenizer.is_fast:
        raise RuntimeError(
            "RAG chunking requires a fast tokenizer"
        )

    return tokenizer

# 计算token数量
def count_tokens(
    text: str,
    tokenizer: PreTrainedTokenizerBase | None = None,
) -> int:
    active_tokenizer = tokenizer or get_chunking_tokenizer()

    return len(
        active_tokenizer.encode(
            text,
            add_special_tokens=False,
        )
    )

# 实现基础token chunking
def chunk_text(
    text: str,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
    page_number: int | None = None,
    metadata: dict[str, Any] | None = None,
    tokenizer: PreTrainedTokenizerBase | None = None,
) -> list[RagChunkDraft]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    if overlap < 0 or overlap >= chunk_size:
        raise ValueError(
            "overlap must be non-negative and smaller than chunk_size"
        )

    normalized_text = text.strip()

    if not normalized_text:
        return []

    active_tokenizer = tokenizer or get_chunking_tokenizer()

    encoded = active_tokenizer(
    normalized_text,
    add_special_tokens=False,
    return_offsets_mapping=True,
    verbose=False,
)

    token_ids = encoded["input_ids"]
    offsets = encoded["offset_mapping"]

    chunks: list[RagChunkDraft] = []
    start = 0

    while start < len(token_ids):
        end = min(start + chunk_size, len(token_ids))

        start_character = offsets[start][0]
        end_character = offsets[end - 1][1]

        content = normalized_text[
            start_character:end_character
        ].strip()

        if content:
            chunks.append(
                RagChunkDraft(
                    chunk_index=len(chunks),
                    content=content,
                    token_count=end - start,
                    page_number=page_number,
                    metadata=dict(metadata or {}),
                )
            )

        if end >= len(token_ids):
            break

        start = end - overlap
    return chunks

# 增加Attachment按页切分
def chunk_pages(
    pages: list[tuple[int, str]],
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
    metadata: dict[str, Any] | None = None,
) -> list[RagChunkDraft]:
    tokenizer = get_chunking_tokenizer()
    chunks: list[RagChunkDraft] = []

    for page_number, page_text in pages:
        page_chunks = chunk_text(
            page_text,
            chunk_size=chunk_size,
            overlap=overlap,
            page_number=page_number,
            metadata=metadata,
            tokenizer=tokenizer,
        )

        for page_chunk in page_chunks:
            chunks.append(
                RagChunkDraft(
                    chunk_index=len(chunks),
                    content=page_chunk.content,
                    token_count=page_chunk.token_count,
                    page_number=page_chunk.page_number,
                    metadata=page_chunk.metadata,
                )
            )

    return chunks