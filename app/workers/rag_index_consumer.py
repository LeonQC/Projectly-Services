"""
rag-index-service
→ 快任务：Card、Comment、Project 等 chunking、embedding

监听：projectly.rag.indexing.events
处理事件：
rag.source.upsert
rag.source.delete
"""
from __future__ import annotations

import json

from confluent_kafka import Consumer
from sqlalchemy import delete

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.project import RagChunk
from app.services.rag_indexing import (
    index_card,
    index_comment,
    index_epic,
    index_github_event,
    index_project,
    index_sprint,
    index_workspace,
)


SOURCE_INDEXERS = {
    "workspace": index_workspace,
    "project": index_project,
    "epic": index_epic,
    "sprint": index_sprint,
    "card": index_card,
    "comment": index_comment,
    "github_event": index_github_event,
}

# upsert
def handle_source_upsert(payload: dict) -> None:
    source_type = payload.get("source_type")
    source_id = payload.get("source_id")

    if source_type not in SOURCE_INDEXERS or source_id is None:
        raise ValueError("Invalid RAG source upsert payload")

    with SessionLocal() as db:
        SOURCE_INDEXERS[source_type](db, int(source_id))

# delete
def handle_source_delete(payload: dict) -> None:
    source_type = payload.get("source_type")
    source_id = payload.get("source_id")

    if source_type is None or source_id is None:
        raise ValueError("Invalid RAG source delete payload")

    source_id = int(source_id)

    if source_type == "workspace":
        condition = RagChunk.workspace_id == source_id
    elif source_type == "project":
        condition = RagChunk.project_id == source_id
    elif source_type == "card":
        condition = RagChunk.card_id == source_id
    else:
        condition = (
            (RagChunk.source_type == source_type)
            & (RagChunk.source_id == source_id)
        )

    with SessionLocal() as db:
        db.execute(delete(RagChunk).where(condition))
        db.commit()

# 事件分发
def handle_rag_index_event(event: dict) -> None:
    event_type = event.get("type")
    payload = event.get("payload") or {}

    if event_type == "rag.source.upsert":
        handle_source_upsert(payload)
        return

    if event_type == "rag.source.delete":
        handle_source_delete(payload)
        return

    raise ValueError(f"Unsupported RAG index event: {event_type}")

def main() -> None:
    consumer = Consumer(
        {
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "group.id": "projectly-rag-index-service",
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
    )

    consumer.subscribe([settings.rag_index_events_topic])

    print(
        f"RAG index consumer listening on "
        f"{settings.rag_index_events_topic}",
        flush=True,
    )

    try:
        while True:
            message = consumer.poll(1.0)

            if message is None:
                continue

            if message.error():
                print(f"Kafka error: {message.error()}", flush=True)
                continue

            try:
                event = json.loads(message.value().decode("utf-8"))
                print(f"Received RAG index event: {event}", flush=True)

                handle_rag_index_event(event)

                consumer.commit(
                    message=message,
                    asynchronous=False,
                )
            except Exception as exc:
                print(
                    f"Failed to process RAG index event: {exc}",
                    flush=True,
                )
                raise
    finally:
        consumer.close()


if __name__ == "__main__":
    main()