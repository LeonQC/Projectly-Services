"""add card members

Revision ID: be020cardmembers
Revises: be018cardlabels
Create Date: 2026-08-06 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "be020cardmembers"
down_revision: Union[str, Sequence[str], None] = "be018cardlabels"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "card_members",
        sa.Column("card_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("added_by_id", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["added_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["card_id"], ["cards.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("card_id", "user_id", name="uq_card_members_card_user"),
    )
    op.create_index(op.f("ix_card_members_added_by_id"), "card_members", ["added_by_id"], unique=False)
    op.create_index(op.f("ix_card_members_card_id"), "card_members", ["card_id"], unique=False)
    op.create_index(op.f("ix_card_members_id"), "card_members", ["id"], unique=False)
    op.create_index(op.f("ix_card_members_user_id"), "card_members", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_card_members_user_id"), table_name="card_members")
    op.drop_index(op.f("ix_card_members_id"), table_name="card_members")
    op.drop_index(op.f("ix_card_members_card_id"), table_name="card_members")
    op.drop_index(op.f("ix_card_members_added_by_id"), table_name="card_members")
    op.drop_table("card_members")
