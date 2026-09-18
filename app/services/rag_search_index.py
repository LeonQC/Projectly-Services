"""
Elasticsearch BM25 index for unified RAG chunks.

PostgreSQL rag_chunks:
- 保存 chunk 文本
- 保存 embedding
- 是数据源

Elasticsearch rag_chunks:
- 保存可搜索的 chunk 文本副本
- 使用 BM25 做关键词检索
- ES document ID 使用 PostgreSQL RagChunk.id
"""
from app.core.elasticsearch import es
from app.models.project import RagChunk
from collections.abc import Iterable
from elasticsearch.helpers import bulk
from elasticsearch import NotFoundError
from sqlalchemy import select
from sqlalchemy.orm import Session

RAG_CHUNK_INDEX = "rag_chunks"

RAG_CHUNK_INDEX_MAPPING = {
    "dynamic": "strict",
    "properties": {
        "chunk_id": {
            "type": "integer",
        },
        "workspace_id": {
            "type": "integer",
        },
        "project_id": {
            "type": "integer",
        },
        "card_id": {
            "type": "integer",
        },
        "source_type": {
            "type": "keyword",
        },
        "source_id": {
            "type": "integer",
        },
        "source_subtype": {
            "type": "keyword",
        },
        "chunk_index": {
            "type": "integer",
        },
        "title": {
            "type": "text",
        },
        "content": {
            "type": "text",
        },
        "metadata": {
            "type": "object",
            "enabled": False,
        },
        "created_at": {
            "type": "date",
        },
        "updated_at": {
            "type": "date",
        },
    },
}


def create_rag_chunk_index() -> None:
    if es.indices.exists(index=RAG_CHUNK_INDEX):
        es.indices.put_mapping(
            index=RAG_CHUNK_INDEX,
            properties=RAG_CHUNK_INDEX_MAPPING["properties"],
        )
        return

    es.indices.create(
        index=RAG_CHUNK_INDEX,
        mappings=RAG_CHUNK_INDEX_MAPPING,
    )

def build_rag_chunk_document(chunk: RagChunk) -> dict:
    return {
        "chunk_id": chunk.id,
        "workspace_id": chunk.workspace_id,
        "project_id": chunk.project_id,
        "card_id": chunk.card_id,
        "source_type": chunk.source_type,
        "source_id": chunk.source_id,
        "source_subtype": chunk.source_subtype,
        "chunk_index": chunk.chunk_index,
        "title": chunk.title,
        "content": chunk.content,
        "metadata": chunk.chunk_metadata,
        "created_at": chunk.created_at,
        "updated_at": chunk.updated_at,
    }

def index_rag_chunks(
    chunks: Iterable[RagChunk],
    *,
    refresh: bool = False,
) -> int:
    chunk_list = list(chunks)

    if not chunk_list:
        return 0

    create_rag_chunk_index()

    actions = [
        {
            "_op_type": "index",
            "_index": RAG_CHUNK_INDEX,
            "_id": str(chunk.id),
            "_source": build_rag_chunk_document(chunk),
        }
        for chunk in chunk_list
    ]

    bulk(
        es,
        actions,
        refresh=refresh,
    )

    return len(chunk_list)

def delete_by_query(
    query: dict,
    *,
    refresh: bool = False,
) -> int:
    try:
        response = es.delete_by_query(
            index=RAG_CHUNK_INDEX,
            query=query,
            conflicts="proceed",
            refresh=refresh,
        )
    except NotFoundError:
        return 0

    return int(response.get("deleted", 0))

def delete_rag_source_documents(
    source_type: str,
    source_id: int,
    *,
    refresh: bool = False,
) -> int:
    return delete_by_query(
        {
            "bool": {
                "filter": [
                    {
                        "term": {
                            "source_type": source_type,
                        }
                    },
                    {
                        "term": {
                            "source_id": source_id,
                        }
                    },
                ]
            }
        },
        refresh=refresh,
    )

def replace_rag_source_documents(
    source_type: str,
    source_id: int,
    chunks: Iterable[RagChunk],
    *,
    refresh: bool = False,
) -> int:
    chunk_list = list(chunks)

    delete_rag_source_documents(
        source_type,
        source_id,
        refresh=False,
    )

    return index_rag_chunks(
        chunk_list,
        refresh=refresh,
    )

def delete_rag_scope_documents(
    source_type: str,
    source_id: int,
    *,
    refresh: bool = False,
) -> int:
    scope_fields = {
        "workspace": "workspace_id",
        "project": "project_id",
        "card": "card_id",
    }

    scope_field = scope_fields.get(source_type)

    if scope_field is None:
        return delete_rag_source_documents(
            source_type,
            source_id,
            refresh=refresh,
        )

    return delete_by_query(
        {
            "term": {
                scope_field: source_id,
            }
        },
        refresh=refresh,
    )

def search_rag_chunks_bm25(
    query: str,
    *,
    limit: int,
    workspace_id: int | None = None,
    project_id: int | None = None,
    card_id: int | None = None,
    workspace_ids: list[int] | None = None,
) -> dict[int, float]:
    filters: list[dict] = []
    if workspace_ids == []:
        return {}

    if card_id is not None:
        filters.append(
            {
                "term": {
                    "card_id": card_id,
                }
            }
        )
    elif project_id is not None:
        filters.append(
            {
                "term": {
                    "project_id": project_id,
                }
            }
        )
    elif workspace_id is not None:
        filters.append(
            {
                "term": {
                    "workspace_id": workspace_id,
                }
            }
        )
    elif workspace_ids is not None:
        filters.append(
            {
                "terms": {
                    "workspace_id": workspace_ids,
                }
            }
        )
    try:
        response = es.search(
            index=RAG_CHUNK_INDEX,
            size=limit,
            source=False,
            query={
                "bool": {
                    "must": [
                        {
                            "multi_match": {
                                "query": query,
                                "fields": [
                                    "title^2",
                                    "content",
                                ],
                            }
                        }
                    ],
                    "filter": filters,
                }
            },
        )
    except NotFoundError:
        return {}

    return {
        int(hit["_id"]): float(hit["_score"])
        for hit in response["hits"]["hits"]
    }

def backfill_rag_chunk_index(
    db: Session,
    *,
    batch_size: int = 500,
    refresh: bool = True,
) -> int:
    create_rag_chunk_index()

    result = db.scalars(
        select(RagChunk).order_by(RagChunk.id.asc())
    )

    indexed_count = 0

    for chunks in result.partitions(batch_size):
        indexed_count += index_rag_chunks(
            chunks,
            refresh=False,
        )

    if refresh:
        es.indices.refresh(index=RAG_CHUNK_INDEX)

    return indexed_count