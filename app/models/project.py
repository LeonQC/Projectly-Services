from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
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


class CardAttachment(IdMixin, TimestampMixin, Base):
    __tablename__ = "card_attachments"

    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id"), index=True, nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_url: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    uploaded_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)


class CardComment(IdMixin, TimestampMixin, Base):
    __tablename__ = "card_comments"

    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id"), index=True, nullable=False)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


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
