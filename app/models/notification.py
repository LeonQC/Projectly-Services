from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin


class Notification(IdMixin, Base):
    __tablename__ = "notifications"

    recipient_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    actor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    source_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class Invitation(IdMixin, Base):
    __tablename__ = "invitations"
    __table_args__ = (
        CheckConstraint(
            "target_type IN ('workspace', 'project')",
            name="ck_invitations_target_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'accepted', 'declined')",
            name="ck_invitations_status",
        ),
        UniqueConstraint("target_type", "target_id", "invitee_id", "status", name="uq_invitations_target_invitee_status"),
    )

    target_type: Mapped[str] = mapped_column(String(20), nullable=False)
    target_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    inviter_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    invitee_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
