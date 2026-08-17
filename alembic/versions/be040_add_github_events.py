"""add github events

Revision ID: be040githubevents
Revises: be039githubapp
Create Date: 2026-08-17 06:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "be040githubevents"
down_revision: Union[str, Sequence[str], None] = "be039githubapp"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "github_events",
        sa.Column("delivery_id", sa.String(length=80), nullable=True),
        sa.Column("installation_id", sa.BigInteger(), nullable=True),
        sa.Column("repo_owner", sa.String(length=120), nullable=True),
        sa.Column("repo_name", sa.String(length=120), nullable=True),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=True),
        sa.Column("branch_name", sa.String(length=255), nullable=True),
        sa.Column("pull_request_number", sa.Integer(), nullable=True),
        sa.Column("commit_sha", sa.String(length=80), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("url", sa.String(length=500), nullable=True),
        sa.Column("sender_login", sa.String(length=120), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_github_events_branch_name"), "github_events", ["branch_name"], unique=False)
    op.create_index(op.f("ix_github_events_commit_sha"), "github_events", ["commit_sha"], unique=False)
    op.create_index(op.f("ix_github_events_delivery_id"), "github_events", ["delivery_id"], unique=False)
    op.create_index(op.f("ix_github_events_event_type"), "github_events", ["event_type"], unique=False)
    op.create_index(op.f("ix_github_events_id"), "github_events", ["id"], unique=False)
    op.create_index(op.f("ix_github_events_installation_id"), "github_events", ["installation_id"], unique=False)
    op.create_index(op.f("ix_github_events_pull_request_number"), "github_events", ["pull_request_number"], unique=False)
    op.create_index(op.f("ix_github_events_repo_name"), "github_events", ["repo_name"], unique=False)
    op.create_index(op.f("ix_github_events_repo_owner"), "github_events", ["repo_owner"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_github_events_repo_owner"), table_name="github_events")
    op.drop_index(op.f("ix_github_events_repo_name"), table_name="github_events")
    op.drop_index(op.f("ix_github_events_pull_request_number"), table_name="github_events")
    op.drop_index(op.f("ix_github_events_installation_id"), table_name="github_events")
    op.drop_index(op.f("ix_github_events_id"), table_name="github_events")
    op.drop_index(op.f("ix_github_events_event_type"), table_name="github_events")
    op.drop_index(op.f("ix_github_events_delivery_id"), table_name="github_events")
    op.drop_index(op.f("ix_github_events_commit_sha"), table_name="github_events")
    op.drop_index(op.f("ix_github_events_branch_name"), table_name="github_events")
    op.drop_table("github_events")
