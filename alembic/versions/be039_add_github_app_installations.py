"""add github app installations

Revision ID: be039githubapp
Revises: be030commentdelete
Create Date: 2026-08-17 05:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "be039githubapp"
down_revision: Union[str, Sequence[str], None] = "be030commentdelete"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "github_app_installations",
        sa.Column("installation_id", sa.BigInteger(), nullable=False),
        sa.Column("account_login", sa.String(length=120), nullable=True),
        sa.Column("account_type", sa.String(length=40), nullable=True),
        sa.Column("account_id", sa.BigInteger(), nullable=True),
        sa.Column("repository_selection", sa.String(length=40), nullable=True),
        sa.Column("setup_action", sa.String(length=40), nullable=True),
        sa.Column("sender_login", sa.String(length=120), nullable=True),
        sa.Column("installed_by_id", sa.Integer(), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["installed_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_github_app_installations_id"), "github_app_installations", ["id"], unique=False)
    op.create_index(
        op.f("ix_github_app_installations_installation_id"),
        "github_app_installations",
        ["installation_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_github_app_installations_installed_by_id"),
        "github_app_installations",
        ["installed_by_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_github_app_installations_installed_by_id"), table_name="github_app_installations")
    op.drop_index(op.f("ix_github_app_installations_installation_id"), table_name="github_app_installations")
    op.drop_index(op.f("ix_github_app_installations_id"), table_name="github_app_installations")
    op.drop_table("github_app_installations")
