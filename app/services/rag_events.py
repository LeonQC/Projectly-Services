"""
RAG Kafka producer
Python 数据
→ 转成 JSON event
→ 发送到指定 Kafka topic

attachment.uploaded
rag.source.upsert
rag.source.delete
"""
from __future__ import annotations

import json
from typing import Any

from confluent_kafka import Producer

from app.core.config import settings


_producer: Producer | None = None


def get_rag_event_producer() -> Producer:
    global _producer
    if _producer is None:
        _producer = Producer({"bootstrap.servers": settings.kafka_bootstrap_servers})
    return _producer


def publish_event(
    *,
    topic: str,
    event_type: str,
    payload: dict[str, Any],
    key: str,
) -> None:
    producer = get_rag_event_producer()

    message = {
        "type": event_type,
        "payload": payload,
    }

    producer.produce(
        topic=topic,
        key=key.encode("utf-8"),
        value=json.dumps(message).encode("utf-8"),
    )

    remaining_messages = producer.flush(5)

    if remaining_messages:
        raise RuntimeError(
            f"Failed to deliver {remaining_messages} Kafka messages"
        )

# upsert
def publish_rag_source_upsert(
    source_type: str,
    source_id: int,
) -> None:
    publish_event(
        topic=settings.rag_index_events_topic,
        event_type="rag.source.upsert",
        payload={
            "source_type": source_type,
            "source_id": source_id,
        },
        key=f"{source_type}:{source_id}",
    )

# delete
def publish_rag_source_delete(
    source_type: str,
    source_id: int,
) -> None:
    publish_event(
        topic=settings.rag_index_events_topic,
        event_type="rag.source.delete",
        payload={
            "source_type": source_type,
            "source_id": source_id,
        },
        key=f"{source_type}:{source_id}",
    )

#attachment ingestion
def publish_attachment_ingestion_event(
    event_type: str,
    payload: dict[str, Any],
) -> None:
    attachment_id = payload.get("attachment_id")

    if attachment_id is None:
        raise ValueError(
            "Attachment ingestion event requires attachment_id"
        )

    publish_event(
        topic=settings.rag_ingestion_events_topic,
        event_type=event_type,
        payload=payload,
        key=f"attachment:{attachment_id}",
    )