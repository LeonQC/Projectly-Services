"""add invitations

Revision ID: be025invitations
Revises: be024commentattachments
Create Date: 2026-08-09 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "be025invitations"
down_revision: Union[str, Sequence[str], None] = "be024commentattachments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "invitations",
        sa.Column("target_type", sa.String(length=20), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("inviter_id", sa.Integer(), nullable=False),
        sa.Column("invitee_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("target_type IN ('workspace', 'project')", name="ck_invitations_target_type"),
        sa.CheckConstraint("status IN ('pending', 'accepted', 'declined')", name="ck_invitations_status"),
        sa.ForeignKeyConstraint(["invitee_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["inviter_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("target_type", "target_id", "invitee_id", "status", name="uq_invitations_target_invitee_status"),
    )
    op.create_index(op.f("ix_invitations_id"), "invitations", ["id"], unique=False)
    op.create_index(op.f("ix_invitations_invitee_id"), "invitations", ["invitee_id"], unique=False)
    op.create_index(op.f("ix_invitations_inviter_id"), "invitations", ["inviter_id"], unique=False)
    op.create_index(op.f("ix_invitations_target_id"), "invitations", ["target_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_invitations_target_id"), table_name="invitations")
    op.drop_index(op.f("ix_invitations_inviter_id"), table_name="invitations")
    op.drop_index(op.f("ix_invitations_invitee_id"), table_name="invitations")
    op.drop_index(op.f("ix_invitations_id"), table_name="invitations")
    op.drop_table("invitations")
