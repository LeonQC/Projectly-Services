"""
rag-attachment-service
→ 慢任务：Supabase、Docling、chunking、embedding

监听：projectly.rag.ingestion.events
处理事件：
attachment.uploaded
attachment.reprocess
调用流程：
run_rag_ingestion_job()
    ↓
attachment_extraction.py
    ↓
rag_indexing.index_attachment()
    ├── rag_chunking.py
    └── rag_embedding.py
    ↓
rag_chunks
"""

from __future__ import annotations

import json

from confluent_kafka import Consumer

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.rag_ingestion import run_rag_ingestion_job

# 事件处理函数
SUPPORTED_EVENTS = {
    "attachment.uploaded",
    "attachment.reprocess",
}


def handle_attachment_event(event: dict) -> None:
    event_type = event.get("type")
    payload = event.get("payload") or {}

    if event_type not in SUPPORTED_EVENTS:
        raise ValueError(
            f"Unsupported attachment RAG event: {event_type}"
        )

    job_id = payload.get("job_id")
    attachment_id = payload.get("attachment_id")
    uploaded_by_id = payload.get("uploaded_by_id")

    if (
        job_id is None
        or attachment_id is None
        or uploaded_by_id is None
    ):
        raise ValueError(
            "Attachment event requires job_id, "
            "attachment_id and uploaded_by_id"
        )

    with SessionLocal() as db:
        run_rag_ingestion_job(
            db,
            attachment_id=int(attachment_id),
            current_user_id=int(uploaded_by_id),
            job_id=int(job_id),
            force=event_type == "attachment.reprocess",
        )

# Kafka consumer主循环
def main() -> None:
    consumer = Consumer(
        {
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "group.id": "projectly-rag-attachment-service",
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,

            # Docling/OCR 可能需要几分钟。
            "max.poll.interval.ms": 900_000,
        }
    )

    consumer.subscribe([
        settings.rag_ingestion_events_topic,
    ])

    print(
        "RAG attachment consumer listening on "
        f"{settings.rag_ingestion_events_topic}",
        flush=True,
    )

    try:
        while True:
            message = consumer.poll(1.0)

            if message is None:
                continue

            if message.error():
                print(
                    f"Kafka error: {message.error()}",
                    flush=True,
                )
                continue

            try:
                event = json.loads(
                    message.value().decode("utf-8")
                )

                print(
                    f"Received attachment RAG event: {event}",
                    flush=True,
                )

                handle_attachment_event(event)

                consumer.commit(
                    message=message,
                    asynchronous=False,
                )

                print(
                    "Attachment RAG event completed",
                    flush=True,
                )

            except Exception as exc:
                print(
                    f"Failed to process attachment RAG event: {exc}",
                    flush=True,
                )

                # 不提交 offset，让容器重启后重新处理。
                raise

    finally:
        consumer.close()


if __name__ == "__main__":
    main()