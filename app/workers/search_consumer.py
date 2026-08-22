from __future__ import annotations

import json

from confluent_kafka import Consumer

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.project import CardComment, GitHubEvent
from app.services.search import (
    delete_card_search_documents,
    delete_comment_from_index,
    delete_project_search_documents,
    delete_workspace_search_documents,
    index_comment,
    index_github_event,
    reindex_card_search_documents,
    reindex_project_search_documents,
    reindex_workspace_search_documents,
)


CARD_REINDEX_EVENTS = {
    "card.created",
    "card.updated",
    "card.moved",
    "card.archived",
    "card.restored",
    "card.labels_changed",
}

PROJECT_REINDEX_EVENTS = {
    "project.created",
    "project.updated",
    "project.archived",
    "project.restored",
}

WORKSPACE_REINDEX_EVENTS = {
    "workspace.updated",
    "workspace.archived",
    "workspace.restored",
}


def handle_search_event(event: dict) -> None:
    event_type = event.get("type")
    payload = event.get("payload") or {}

    if event_type in CARD_REINDEX_EVENTS:
        card_id = payload.get("card_id")
        if card_id is None:
            return

        with SessionLocal() as db:
            reindex_card_search_documents(db, int(card_id))
        return

    if event_type in {"comment.created", "comment.updated"}:
        comment_id = payload.get("comment_id")
        if comment_id is None:
            return

        with SessionLocal() as db:
            comment = db.get(CardComment, int(comment_id))
            if comment is not None:
                index_comment(db, comment)
        return

    if event_type == "comment.deleted":
        comment_id = payload.get("comment_id")
        if comment_id is None:
            return

        delete_comment_from_index(int(comment_id))
        return

    if event_type in PROJECT_REINDEX_EVENTS:
        project_id = payload.get("project_id")
        if project_id is None:
            return

        with SessionLocal() as db:
            reindex_project_search_documents(db, int(project_id))
        return

    if event_type == "github_event.created":
        github_event_id = payload.get("github_event_id")
        if github_event_id is None:
            return

        with SessionLocal() as db:
            github_event = db.get(GitHubEvent, int(github_event_id))
            if github_event is not None:
                index_github_event(db, github_event)
        return

    if event_type == "card.deleted":
        card_id = payload.get("card_id")
        if card_id is None:
            return

        delete_card_search_documents(int(card_id))
        return

    if event_type == "project.deleted":
        project_id = payload.get("project_id")
        if project_id is None:
            return

        delete_project_search_documents(int(project_id))
        return

    if event_type in WORKSPACE_REINDEX_EVENTS:
        workspace_id = payload.get("workspace_id")
        if workspace_id is None:
            return

        with SessionLocal() as db:
            reindex_workspace_search_documents(db, int(workspace_id))
        return

    if event_type == "workspace.deleted":
        workspace_id = payload.get("workspace_id")
        if workspace_id is None:
            return

        delete_workspace_search_documents(int(workspace_id))


def main() -> None:
    consumer = Consumer(
        {
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "group.id": "projectly-search-service",
            "auto.offset.reset": "earliest",
        }
    )
    consumer.subscribe([settings.search_events_topic])

    print(f"Search consumer listening on {settings.search_events_topic}", flush=True)

    try:
        while True:
            message = consumer.poll(1.0)
            if message is None:
                continue

            if message.error():
                print(f"Kafka error: {message.error()}")
                continue

            try:
                event = json.loads(message.value().decode("utf-8"))
                print(f"Received search event: {event}", flush=True)
                handle_search_event(event)
            except Exception as exc:
                print(f"Failed to process search event: {exc}", flush=True)
    finally:
        consumer.close()


if __name__ == "__main__":
    main()
