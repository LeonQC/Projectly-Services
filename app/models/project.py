from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class Project(IdMixin, TimestampMixin, Base):
    __tablename__ = "projects"

    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class ProjectGuest(IdMixin, TimestampMixin, Base):
    __tablename__ = "project_guests"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_guests_project_user"),
    )

    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)


class Epic(IdMixin, TimestampMixin, Base):
    __tablename__ = "epics"

    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    deadline: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Sprint(IdMixin, TimestampMixin, Base):
    __tablename__ = "sprints"
    __table_args__ = (
        CheckConstraint(
            "status IN ('planned', 'active', 'completed')",
            name="ck_sprints_status",
        ),
    )

    epic_id: Mapped[int] = mapped_column(ForeignKey("epics.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    goal: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="planned", nullable=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Card(IdMixin, TimestampMixin, Base):
    __tablename__ = "cards"
    __table_args__ = (
        CheckConstraint(
            "status IN ('backlog', 'todo', 'in_progress', 'done')",
            name="ck_cards_status",
        ),
    )

    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True, nullable=False)
    epic_id: Mapped[Optional[int]] = mapped_column(ForeignKey("epics.id"), index=True, nullable=True)
    sprint_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sprints.id"), index=True, nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="backlog", nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class CardLink(IdMixin, TimestampMixin, Base):
    __tablename__ = "card_links"
    __table_args__ = (
        CheckConstraint(
            "relationship IN ("
            "'is_blocked_by', "
            "'blocks', "
            "'is_cloned_by', "
            "'clones', "
            "'is_duplicated_by', "
            "'duplicates', "
            "'relates_to'"
            ")",
            name="ck_card_links_relationship",
        ),
        UniqueConstraint(
            "source_card_id",
            "target_card_id",
            "relationship",
            name="uq_card_links_source_target_relationship",
        ),
    )

    source_card_id: Mapped[int] = mapped_column(ForeignKey("cards.id"), index=True, nullable=False)
    target_card_id: Mapped[int] = mapped_column(ForeignKey("cards.id"), index=True, nullable=False)
    relationship: Mapped[str] = mapped_column(String(30), nullable=False)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)


class CardGitHubLink(IdMixin, TimestampMixin, Base):
    __tablename__ = "card_github_links"
    __table_args__ = (
        UniqueConstraint(
            "card_id",
            "repo_owner",
            "repo_name",
            "branch_name",
            "pull_request_number",
            "commit_sha",
            name="uq_card_github_links_target",
        ),
    )

    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id"), index=True, nullable=False)
    repo_owner: Mapped[str] = mapped_column(String(120), nullable=False)
    repo_name: Mapped[str] = mapped_column(String(120), nullable=False)
    branch_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    pull_request_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    commit_sha: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)


class GitHubAppInstallation(IdMixin, TimestampMixin, Base):
    __tablename__ = "github_app_installations"

    installation_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    account_login: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    account_type: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    account_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    repository_selection: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    setup_action: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    sender_login: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    installed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    raw_payload: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)


class GitHubEvent(IdMixin, TimestampMixin, Base):
    __tablename__ = "github_events"

    delivery_id: Mapped[Optional[str]] = mapped_column(String(80), index=True, nullable=True)
    installation_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True, nullable=True)
    repo_owner: Mapped[Optional[str]] = mapped_column(String(120), index=True, nullable=True)
    repo_name: Mapped[Optional[str]] = mapped_column(String(120), index=True, nullable=True)
    event_type: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    action: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    branch_name: Mapped[Optional[str]] = mapped_column(String(255), index=True, nullable=True)
    pull_request_number: Mapped[Optional[int]] = mapped_column(Integer, index=True, nullable=True)
    commit_sha: Mapped[Optional[str]] = mapped_column(String(80), index=True, nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    sender_login: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    raw_payload: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)


class CardAttachment(IdMixin, TimestampMixin, Base):
    __tablename__ = "card_attachments"

    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id"), index=True, nullable=False)
    comment_id: Mapped[Optional[int]] = mapped_column(ForeignKey("card_comments.id"), index=True, nullable=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_url: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    uploaded_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)


class CardLabel(IdMixin, TimestampMixin, Base):
    __tablename__ = "card_labels"
    __table_args__ = (
        UniqueConstraint("card_id", "name", name="uq_card_labels_card_name"),
    )

    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    color: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)


class CardMember(IdMixin, TimestampMixin, Base):
    __tablename__ = "card_members"
    __table_args__ = (
        UniqueConstraint("card_id", "user_id", name="uq_card_members_card_user"),
    )

    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id"), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    added_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)


class CardComment(IdMixin, TimestampMixin, Base):
    __tablename__ = "card_comments"

    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id"), index=True, nullable=False)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)


class CardActivity(IdMixin, Base):
    __tablename__ = "card_activities"

    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id"), index=True, nullable=False)
    actor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    activity_metadata: Mapped[Optional[dict[str, Any]]] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
