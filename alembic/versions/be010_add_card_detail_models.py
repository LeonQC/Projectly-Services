"""add card detail models

Revision ID: be010carddetail
Revises: af8989b7753c
Create Date: 2026-07-14 04:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "be010carddetail"
down_revision: Union[str, Sequence[str], None] = "af8989b7753c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "card_attachments",
        sa.Column("card_id", sa.Integer(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_url", sa.String(length=500), nullable=False),
        sa.Column("file_type", sa.String(length=120), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("uploaded_by_id", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["card_id"], ["cards.id"]),
        sa.ForeignKeyConstraint(["uploaded_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_card_attachments_card_id"), "card_attachments", ["card_id"], unique=False)
    op.create_index(op.f("ix_card_attachments_id"), "card_attachments", ["id"], unique=False)
    op.create_index(op.f("ix_card_attachments_uploaded_by_id"), "card_attachments", ["uploaded_by_id"], unique=False)

    op.create_table(
        "card_comments",
        sa.Column("card_id", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["card_id"], ["cards.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_card_comments_author_id"), "card_comments", ["author_id"], unique=False)
    op.create_index(op.f("ix_card_comments_card_id"), "card_comments", ["card_id"], unique=False)
    op.create_index(op.f("ix_card_comments_id"), "card_comments", ["id"], unique=False)

    op.create_table(
        "card_activities",
        sa.Column("card_id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["card_id"], ["cards.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_card_activities_actor_id"), "card_activities", ["actor_id"], unique=False)
    op.create_index(op.f("ix_card_activities_card_id"), "card_activities", ["card_id"], unique=False)
    op.create_index(op.f("ix_card_activities_id"), "card_activities", ["id"], unique=False)

    op.create_table(
        "notifications",
        sa.Column("recipient_id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(length=50), nullable=True),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["recipient_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_notifications_actor_id"), "notifications", ["actor_id"], unique=False)
    op.create_index(op.f("ix_notifications_id"), "notifications", ["id"], unique=False)
    op.create_index(op.f("ix_notifications_recipient_id"), "notifications", ["recipient_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_notifications_recipient_id"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_id"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_actor_id"), table_name="notifications")
    op.drop_table("notifications")

    op.drop_index(op.f("ix_card_activities_id"), table_name="card_activities")
    op.drop_index(op.f("ix_card_activities_card_id"), table_name="card_activities")
    op.drop_index(op.f("ix_card_activities_actor_id"), table_name="card_activities")
    op.drop_table("card_activities")

    op.drop_index(op.f("ix_card_comments_id"), table_name="card_comments")
    op.drop_index(op.f("ix_card_comments_card_id"), table_name="card_comments")
    op.drop_index(op.f("ix_card_comments_author_id"), table_name="card_comments")
    op.drop_table("card_comments")

    op.drop_index(op.f("ix_card_attachments_uploaded_by_id"), table_name="card_attachments")
    op.drop_index(op.f("ix_card_attachments_id"), table_name="card_attachments")
    op.drop_index(op.f("ix_card_attachments_card_id"), table_name="card_attachments")
    op.drop_table("card_attachments")
