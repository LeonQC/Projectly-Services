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


def publish_rag_event(event_type: str, payload: dict[str, Any]) -> None:
    try:
        producer = get_rag_event_producer()
        message = {
            "type": event_type,
            "payload": payload,
        }
        producer.produce(
            settings.rag_events_topic,
            json.dumps(message).encode("utf-8"),
        )
        producer.flush(5)
    except Exception as exc:
        print(f"Failed to publish RAG event {event_type}: {exc}", flush=True)