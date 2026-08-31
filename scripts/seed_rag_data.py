from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.project import (
    Card,
    CardComment,
    CardGitHubLink,
    CardLabel,
    Epic,
    GitHubEvent,
    Project,
    Sprint,
)
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.services.search import reindex_workspace_search_documents


DEFAULT_PASSWORD = "Password123!"


def get_or_create_user(db: Session, username: str, email: str) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user is not None:
        return user

    user = User(
        username=username,
        email=email,
        hashed_password=hash_password(DEFAULT_PASSWORD),
    )
    db.add(user)
    db.flush()
    return user


def get_unique_workspace_name(db: Session, base_name: str, owner_id: int) -> str:
    existing_names = set(
        db.scalars(
            select(Workspace.name).where(
                Workspace.owner_id == owner_id,
                Workspace.name.like(f"{base_name}%"),
            )
        ).all()
    )
    if base_name not in existing_names:
        return base_name

    suffix = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{base_name} {suffix}"


def create_card(
    db: Session,
    *,
    project: Project,
    epic: Epic,
    sprint: Sprint | None,
    title: str,
    description: str,
    status: str,
    position: int,
    labels: list[tuple[str, str]],
    comments: list[tuple[User, str]],
    github_events: list[dict],
    owner: User,
) -> Card:
    card = Card(
        project_id=project.id,
        epic_id=epic.id,
        sprint_id=sprint.id if sprint is not None else None,
        title=title,
        description=description,
        status=status,
        position=position,
    )
    db.add(card)
    db.flush()

    for name, color in labels:
        db.add(CardLabel(card_id=card.id, name=name, color=color, created_by_id=owner.id))

    for author, body in comments:
        db.add(CardComment(card_id=card.id, author_id=author.id, body=body))

    for event in github_events:
        db.add(
            GitHubEvent(
                card_id=card.id,
                delivery_id=event.get("delivery_id"),
                installation_id=event.get("installation_id", 154328856),
                repo_owner=event.get("repo_owner", "uu84kera"),
                repo_name=event.get("repo_name", "Mask-Detection-ViT"),
                event_type=event["event_type"],
                action=event.get("action"),
                branch_name=event.get("branch_name"),
                pull_request_number=event.get("pull_request_number"),
                commit_sha=event.get("commit_sha"),
                title=event.get("title"),
                message=event.get("message"),
                url=event.get("url"),
                sender_login=event.get("sender_login", "uu84kera"),
                raw_payload=event,
            )
        )

    db.add(
        CardGitHubLink(
            card_id=card.id,
            repo_owner="uu84kera",
            repo_name="Mask-Detection-ViT",
            branch_name="main",
            url="https://github.com/uu84kera/Mask-Detection-ViT",
            created_by_id=owner.id,
        )
    )
    return card


def seed(db: Session, owner_email: str, workspace_name: str) -> dict[str, int | str]:
    owner = get_or_create_user(db, "test", owner_email)
    admin = get_or_create_user(db, "test12345", "test12345@email.com")
    developer = get_or_create_user(db, "john", "johnsmith@email.com")

    workspace_name = get_unique_workspace_name(db, workspace_name, owner.id)
    workspace = Workspace(name=workspace_name, owner_id=owner.id)
    db.add(workspace)
    db.flush()

    db.add_all(
        [
            WorkspaceMember(workspace_id=workspace.id, user_id=owner.id, role="owner"),
            WorkspaceMember(workspace_id=workspace.id, user_id=admin.id, role="admin"),
            WorkspaceMember(workspace_id=workspace.id, user_id=developer.id, role="member"),
        ]
    )

    projects_data = [
        (
            "RAG Knowledge Base",
            "Build retrieval augmented generation over Projectly cards, comments, labels, and GitHub events.",
            [
                (
                    "BE-046 RAG Context Retrieval API",
                    "Create an API that retrieves relevant Projectly cards, comments, labels, descriptions, and GitHub events as grounded context for AI answers.",
                    "in_progress",
                    [("rag", "#7c3aed"), ("backend", "#2563eb"), ("retrieval", "#059669")],
                    [
                        (owner, "Use Elasticsearch first, then add vector search after we verify baseline quality."),
                        (developer, "Context should include card display_id, labels, description, comments, and GitHub event evidence."),
                    ],
                    [
                        {
                            "delivery_id": "seed-rag-context-push",
                            "event_type": "push",
                            "branch_name": "main",
                            "commit_sha": "a1b2c3d4ragcontext",
                            "message": "Add RAG context retrieval service and source metadata",
                            "url": "https://github.com/uu84kera/Mask-Detection-ViT/commit/a1b2c3d4",
                        },
                    ],
                ),
                (
                    "BE-047 AI Answer API",
                    "Call the language model with retrieved Projectly context and return an answer with clickable sources.",
                    "todo",
                    [("ai", "#db2777"), ("sources", "#0891b2")],
                    [
                        (admin, "The answer response needs sources so users can verify the AI did not hallucinate."),
                    ],
                    [
                        {
                            "delivery_id": "seed-ai-answer-pr",
                            "event_type": "pull_request",
                            "action": "opened",
                            "branch_name": "feature/ai-answer-api",
                            "pull_request_number": 47,
                            "title": "Add AI answer API with source citations",
                            "url": "https://github.com/uu84kera/Mask-Detection-ViT/pull/47",
                        },
                    ],
                ),
                (
                    "FE-049 AI Ask Panel",
                    "Add a Projectly AI panel where users ask about sprint risks, blocked work, and recent GitHub activity.",
                    "backlog",
                    [("frontend", "#ea580c"), ("ux", "#16a34a")],
                    [
                        (owner, "Panel should start from project page, then support all-workspace scope later."),
                    ],
                    [],
                ),
            ],
        ),
        (
            "Search and Discovery",
            "Improve full text search for cards, descriptions, labels, comments, and GitHub webhook events.",
            [
                (
                    "FE-048 Global Search Polish",
                    "Show clearer search results with display_id, title, status, label chips, author, created time, and archived state.",
                    "done",
                    [("search", "#7c3aed"), ("frontend", "#ea580c"), ("labels", "#059669")],
                    [
                        (owner, "Searching test1234 should find comments and route to the exact comment inside card detail."),
                        (developer, "Clicking a GitHub event search result should focus the Development section."),
                    ],
                    [
                        {
                            "delivery_id": "seed-search-push",
                            "event_type": "push",
                            "branch_name": "main",
                            "commit_sha": "b2c3d4e5search",
                            "message": "Index card descriptions and labels for full text search",
                            "url": "https://github.com/uu84kera/Mask-Detection-ViT/commit/b2c3d4e5",
                        },
                    ],
                ),
                (
                    "BE-045 All Workspace Search",
                    "Support current workspace and all workspaces search while respecting workspace member and project guest access.",
                    "done",
                    [("backend", "#2563eb"), ("permissions", "#dc2626")],
                    [
                        (admin, "Archived cards should only appear when include archived is enabled."),
                    ],
                    [],
                ),
            ],
        ),
        (
            "GitHub Integration",
            "Connect GitHub App installation callbacks and webhook events to Projectly development activity.",
            [
                (
                    "BE-040 GitHub Webhook Event Storage",
                    "Store GitHub push and pull request events, match events to linked cards, and index them for search.",
                    "done",
                    [("github", "#111827"), ("webhook", "#0f766e")],
                    [
                        (owner, "ngrok must stay open when testing local GitHub webhooks."),
                        (developer, "Events should still store raw_payload for debugging delivery issues."),
                    ],
                    [
                        {
                            "delivery_id": "seed-webhook-delivery",
                            "event_type": "push",
                            "branch_name": "main",
                            "commit_sha": "c3d4e5f6webhook",
                            "message": "Persist GitHub webhook events and match them to cards",
                            "url": "https://github.com/uu84kera/Mask-Detection-ViT/commit/c3d4e5f6",
                        },
                    ],
                ),
                (
                    "FE-040 GitHub Disconnect Management",
                    "Let users connect and disconnect GitHub from User Settings.",
                    "in_progress",
                    [("github", "#111827"), ("settings", "#9333ea")],
                    [
                        (admin, "If no GitHub installation is connected, Development should show Connect GitHub instead of manual URL inputs."),
                    ],
                    [],
                ),
            ],
        ),
    ]

    project_count = 0
    epic_count = 0
    sprint_count = 0
    card_count = 0
    comment_count = 0
    label_count = 0
    event_count = 0

    for project_position, (project_name, project_description, cards) in enumerate(projects_data):
        project = Project(
            workspace_id=workspace.id,
            name=project_name,
            description=project_description,
            position=project_position,
        )
        db.add(project)
        db.flush()
        project_count += 1

        epic = Epic(
            project_id=project.id,
            title=f"{project_name} Phase 1",
            deadline=date(2026, 9, 30),
            position=0,
        )
        db.add(epic)
        db.flush()
        epic_count += 1

        sprint = Sprint(
            epic_id=epic.id,
            name=f"{project_name} Sprint 1",
            goal=f"Validate {project_name.lower()} workflow locally.",
            start_date=date(2026, 8, 21),
            end_date=date(2026, 9, 4),
            status="active",
        )
        db.add(sprint)
        db.flush()
        sprint_count += 1

        for card_position, (title, description, status, labels, comments, github_events) in enumerate(cards):
            create_card(
                db,
                project=project,
                epic=epic,
                sprint=sprint if status != "backlog" else None,
                title=title,
                description=description,
                status=status,
                position=card_position,
                labels=labels,
                comments=comments,
                github_events=github_events,
                owner=owner,
            )
            card_count += 1
            label_count += len(labels)
            comment_count += len(comments)
            event_count += len(github_events)

    db.commit()

    indexed = reindex_workspace_search_documents(db, workspace.id)

    return {
        "workspace_id": workspace.id,
        "workspace_name": workspace.name,
        "owner_email": owner.email,
        "projects": project_count,
        "epics": epic_count,
        "sprints": sprint_count,
        "cards": card_count,
        "labels": label_count,
        "comments": comment_count,
        "github_events": event_count,
        "indexed_projects": indexed["projects"],
        "indexed_cards": indexed["cards"],
        "indexed_comments": indexed["comments"],
        "indexed_github_events": indexed["github_events"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed local Projectly data for search and RAG testing.")
    parser.add_argument("--owner-email", default="test1234@email.com")
    parser.add_argument("--workspace-name", default="RAG Demo Workspace")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        result = seed(db, args.owner_email, args.workspace_name)
    finally:
        db.close()

    for key, value in result.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
