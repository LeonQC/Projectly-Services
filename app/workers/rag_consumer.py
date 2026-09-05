from __future__ import annotations

import json
import traceback

from confluent_kafka import Consumer

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.rag_ingestion import run_rag_ingestion_job


def commit_message(consumer: Consumer, message) -> None:
    try:
        consumer.commit(message=message, asynchronous=False)
    except Exception:
        traceback.print_exc()


def handle_rag_event(event: dict) -> None:
    event_type = event.get("type")
    payload = event.get("payload") or {}

    if event_type != "attachment.uploaded":
        return

    attachment_id = payload.get("attachment_id")
    uploaded_by_id = payload.get("uploaded_by_id")
    job_id = payload.get("job_id")

    if attachment_id is None or uploaded_by_id is None:
        print(f"Skipping RAG event with missing payload fields: {event}", flush=True)
        return

    with SessionLocal() as db:
        run_rag_ingestion_job(
            db,
            int(attachment_id),
            int(uploaded_by_id),
            job_id=int(job_id) if job_id is not None else None,
        )


def main() -> None:
    consumer = Consumer(
        {
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "group.id": "projectly-rag-service",
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
    )
    consumer.subscribe([settings.rag_events_topic])

    print(f"RAG consumer listening on {settings.rag_events_topic}", flush=True)

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
                print(f"Received RAG event: {event}", flush=True)
                handle_rag_event(event)
                commit_message(consumer, message)
            except Exception as exc:
                print(f"Failed to process RAG event: {exc}", flush=True)
                traceback.print_exc()
                commit_message(consumer, message)
    finally:
        consumer.close()


if __name__ == "__main__":
    main()
