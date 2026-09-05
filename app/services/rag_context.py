from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.project import (
    Card,
    CardAttachment,
    CardComment,
    CardGitHubLink,
    CardLabel,
    Epic,
    GitHubEvent,
    Project,
    Sprint,
)
from app.models.workspace import Workspace
from app.services.cards import ensure_card_access
from app.services.projects import ensure_project_access
from app.services.workspaces import ensure_workspace_access


MAX_CARDS = 80
MAX_COMMENTS = 80
MAX_GITHUB_EVENTS = 50


def format_value(value: object) -> str:
    if value is None or value == "":
        return "None"
    return str(value)


def join_lines(lines: list[str]) -> str:
    return "\n".join(line for line in lines if line)


def format_card(card: Card) -> str:
    return join_lines(
        [
            f"Card #{card.id}",
            f"- Title: {format_value(card.title)}",
            f"- Description: {format_value(card.description)}",
            f"- Status: {format_value(card.status)}",
            f"- Epic ID: {format_value(card.epic_id)}",
            f"- Sprint ID: {format_value(card.sprint_id)}",
            f"- Archived: {card.archived}",
        ]
    )


def format_epic(epic: Epic) -> str:
    return (
        f"- Epic #{epic.id}: {epic.title}; "
        f"deadline={format_value(epic.deadline)}; archived={epic.archived}"
    )


def format_sprint(sprint: Sprint) -> str:
    return (
        f"- Sprint #{sprint.id}: {sprint.name}; status={sprint.status}; "
        f"goal={format_value(sprint.goal)}; start={format_value(sprint.start_date)}; "
        f"end={format_value(sprint.end_date)}; archived={sprint.archived}"
    )


def get_card_ids_for_project(db: Session, project_id: int) -> list[int]:
    return list(
        db.scalars(
            select(Card.id)
            .where(Card.project_id == project_id)
            .order_by(Card.position.asc(), Card.created_at.asc(), Card.id.asc())
            .limit(MAX_CARDS)
        ).all()
    )


def get_card_ids_for_workspace(db: Session, workspace_id: int) -> list[int]:
    return list(
        db.scalars(
            select(Card.id)
            .join(Project, Project.id == Card.project_id)
            .where(Project.workspace_id == workspace_id)
            .order_by(Project.position.asc(), Card.position.asc(), Card.created_at.asc(), Card.id.asc())
            .limit(MAX_CARDS)
        ).all()
    )


def build_card_related_context(db: Session, card_ids: list[int]) -> str:
    if not card_ids:
        return ""

    labels = list(
        db.scalars(
            select(CardLabel)
            .where(CardLabel.card_id.in_(card_ids))
            .order_by(CardLabel.card_id.asc(), CardLabel.created_at.asc(), CardLabel.id.asc())
        ).all()
    )
    comments = list(
        db.scalars(
            select(CardComment)
            .where(CardComment.card_id.in_(card_ids))
            .order_by(CardComment.created_at.desc(), CardComment.id.desc())
            .limit(MAX_COMMENTS)
        ).all()
    )
    attachments = list(
        db.scalars(
            select(CardAttachment)
            .where(CardAttachment.card_id.in_(card_ids))
            .order_by(CardAttachment.card_id.asc(), CardAttachment.created_at.asc(), CardAttachment.id.asc())
        ).all()
    )
    github_links = list(
        db.scalars(
            select(CardGitHubLink)
            .where(CardGitHubLink.card_id.in_(card_ids))
            .order_by(CardGitHubLink.card_id.asc(), CardGitHubLink.created_at.asc(), CardGitHubLink.id.asc())
        ).all()
    )
    github_events = list(
        db.scalars(
            select(GitHubEvent)
            .where(GitHubEvent.card_id.in_(card_ids))
            .order_by(GitHubEvent.created_at.desc(), GitHubEvent.id.desc())
            .limit(MAX_GITHUB_EVENTS)
        ).all()
    )

    blocks: list[str] = []

    if labels:
        blocks.append(
            "Labels:\n"
            + "\n".join(
                f"- Card #{label.card_id}: {label.name}; color={format_value(label.color)}"
                for label in labels
            )
        )

    if comments:
        blocks.append(
            "Recent comments:\n"
            + "\n".join(
                f"- Card #{comment.card_id}, comment #{comment.id}: {comment.body}"
                for comment in comments
            )
        )

    if attachments:
        blocks.append(
            "Attachments:\n"
            + "\n".join(
                f"- Card #{attachment.card_id}, attachment #{attachment.id}: "
                f"{attachment.file_name}; type={format_value(attachment.file_type)}; "
                f"size={format_value(attachment.file_size)}"
                for attachment in attachments
            )
        )

    if github_links:
        blocks.append(
            "GitHub links:\n"
            + "\n".join(
                f"- Card #{link.card_id}: {link.repo_owner}/{link.repo_name}; "
                f"branch={format_value(link.branch_name)}; pr={format_value(link.pull_request_number)}; "
                f"commit={format_value(link.commit_sha)}"
                for link in github_links
            )
        )

    if github_events:
        blocks.append(
            "Recent GitHub events:\n"
            + "\n".join(
                f"- Card #{event.card_id}, {event.event_type} {format_value(event.action)}: "
                f"{format_value(event.title or event.message)}; repo={format_value(event.repo_owner)}/{format_value(event.repo_name)}; "
                f"branch={format_value(event.branch_name)}; pr={format_value(event.pull_request_number)}; "
                f"commit={format_value(event.commit_sha)}"
                for event in github_events
            )
        )

    return "\n\n".join(blocks)


def build_card_structured_context(db: Session, current_user_id: int, card_id: int) -> str:
    card = ensure_card_access(db, current_user_id, card_id)
    project = db.get(Project, card.project_id)
    workspace = db.get(Workspace, project.workspace_id) if project is not None else None
    epic = db.get(Epic, card.epic_id) if card.epic_id is not None else None
    sprint = db.get(Sprint, card.sprint_id) if card.sprint_id is not None else None

    blocks = [
        "Scope: Card",
        f"Workspace: {format_value(workspace.name if workspace else None)}",
        f"Project: {format_value(project.name if project else None)}",
        format_card(card),
    ]

    if epic is not None:
        blocks.append(f"Epic: {format_epic(epic)}")

    if sprint is not None:
        blocks.append(f"Sprint: {format_sprint(sprint)}")

    related_context = build_card_related_context(db, [card.id])
    if related_context:
        blocks.append(related_context)

    return "\n\n".join(blocks)


def build_project_structured_context(db: Session, current_user_id: int, project_id: int) -> str:
    project = ensure_project_access(db, current_user_id, project_id)
    workspace = db.get(Workspace, project.workspace_id)
    epics = list(
        db.scalars(
            select(Epic)
            .where(Epic.project_id == project.id)
            .order_by(Epic.position.asc(), Epic.created_at.asc(), Epic.id.asc())
        ).all()
    )
    sprints = list(
        db.scalars(
            select(Sprint)
            .join(Epic, Epic.id == Sprint.epic_id)
            .where(Epic.project_id == project.id)
            .order_by(Sprint.created_at.asc(), Sprint.id.asc())
        ).all()
    )
    cards = list(
        db.scalars(
            select(Card)
            .where(Card.project_id == project.id)
            .order_by(Card.position.asc(), Card.created_at.asc(), Card.id.asc())
            .limit(MAX_CARDS)
        ).all()
    )
    card_ids = [card.id for card in cards]

    blocks = [
        "Scope: Project",
        f"Workspace: {format_value(workspace.name if workspace else None)}",
        join_lines(
            [
                f"Project #{project.id}",
                f"- Name: {format_value(project.name)}",
                f"- Description: {format_value(project.description)}",
                f"- Archived: {project.archived}",
            ]
        ),
    ]

    if epics:
        blocks.append("Epics:\n" + "\n".join(format_epic(epic) for epic in epics))

    if sprints:
        blocks.append("Sprints:\n" + "\n".join(format_sprint(sprint) for sprint in sprints))

    if cards:
        blocks.append("Cards:\n" + "\n\n".join(format_card(card) for card in cards))

    related_context = build_card_related_context(db, card_ids)
    if related_context:
        blocks.append(related_context)

    return "\n\n".join(blocks)


def build_workspace_structured_context(db: Session, current_user_id: int, workspace_id: int) -> str:
    workspace = ensure_workspace_access(db, current_user_id, workspace_id)
    projects = list(
        db.scalars(
            select(Project)
            .where(Project.workspace_id == workspace.id)
            .order_by(Project.position.asc(), Project.created_at.asc(), Project.id.asc())
        ).all()
    )
    project_ids = [project.id for project in projects]
    epics = list(
        db.scalars(
            select(Epic)
            .where(Epic.project_id.in_(project_ids) if project_ids else False)
            .order_by(Epic.project_id.asc(), Epic.position.asc(), Epic.created_at.asc(), Epic.id.asc())
        ).all()
    )
    sprints = list(
        db.scalars(
            select(Sprint)
            .join(Epic, Epic.id == Sprint.epic_id)
            .where(Epic.project_id.in_(project_ids) if project_ids else False)
            .order_by(Epic.project_id.asc(), Sprint.created_at.asc(), Sprint.id.asc())
        ).all()
    )
    cards = list(
        db.scalars(
            select(Card)
            .where(Card.project_id.in_(project_ids) if project_ids else False)
            .order_by(Card.project_id.asc(), Card.position.asc(), Card.created_at.asc(), Card.id.asc())
            .limit(MAX_CARDS)
        ).all()
    )
    card_ids = [card.id for card in cards]

    blocks = [
        "Scope: Workspace",
        join_lines(
            [
                f"Workspace #{workspace.id}",
                f"- Name: {format_value(workspace.name)}",
                f"- Archived: {workspace.archived}",
            ]
        ),
    ]

    if projects:
        blocks.append(
            "Projects:\n"
            + "\n".join(
                f"- Project #{project.id}: {project.name}; "
                f"description={format_value(project.description)}; archived={project.archived}"
                for project in projects
            )
        )

    if epics:
        blocks.append("Epics:\n" + "\n".join(format_epic(epic) for epic in epics))

    if sprints:
        blocks.append("Sprints:\n" + "\n".join(format_sprint(sprint) for sprint in sprints))

    if cards:
        blocks.append("Cards:\n" + "\n\n".join(format_card(card) for card in cards))

    related_context = build_card_related_context(db, card_ids)
    if related_context:
        blocks.append(related_context)

    return "\n\n".join(blocks)


def build_structured_rag_context(
    db: Session,
    current_user_id: int,
    *,
    card_id: int | None = None,
    project_id: int | None = None,
    workspace_id: int | None = None,
) -> str:
    if card_id is not None:
        return build_card_structured_context(db, current_user_id, card_id)

    if project_id is not None:
        return build_project_structured_context(db, current_user_id, project_id)

    if workspace_id is not None:
        return build_workspace_structured_context(db, current_user_id, workspace_id)

    return ""
