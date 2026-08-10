"""add card github links

Revision ID: be026githublinks
Revises: be025invitations
Create Date: 2026-08-10 00:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "be026githublinks"
down_revision: Union[str, Sequence[str], None] = "be025invitations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "card_github_links",
        sa.Column("card_id", sa.Integer(), nullable=False),
        sa.Column("repo_owner", sa.String(length=120), nullable=False),
        sa.Column("repo_name", sa.String(length=120), nullable=False),
        sa.Column("branch_name", sa.String(length=255), nullable=True),
        sa.Column("pull_request_number", sa.Integer(), nullable=True),
        sa.Column("commit_sha", sa.String(length=80), nullable=True),
        sa.Column("url", sa.String(length=500), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["card_id"], ["cards.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "card_id",
            "repo_owner",
            "repo_name",
            "branch_name",
            "pull_request_number",
            "commit_sha",
            name="uq_card_github_links_target",
        ),
    )
    op.create_index(op.f("ix_card_github_links_card_id"), "card_github_links", ["card_id"], unique=False)
    op.create_index(op.f("ix_card_github_links_created_by_id"), "card_github_links", ["created_by_id"], unique=False)
    op.create_index(op.f("ix_card_github_links_id"), "card_github_links", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_card_github_links_id"), table_name="card_github_links")
    op.drop_index(op.f("ix_card_github_links_created_by_id"), table_name="card_github_links")
    op.drop_index(op.f("ix_card_github_links_card_id"), table_name="card_github_links")
    op.drop_table("card_github_links")
