"""add card labels

Revision ID: be018cardlabels
Revises: be010carddetail
Create Date: 2026-08-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "be018cardlabels"
down_revision: Union[str, Sequence[str], None] = "be010carddetail"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "card_labels",
        sa.Column("card_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("color", sa.String(length=20), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["card_id"], ["cards.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("card_id", "name", name="uq_card_labels_card_name"),
    )
    op.create_index(op.f("ix_card_labels_card_id"), "card_labels", ["card_id"], unique=False)
    op.create_index(op.f("ix_card_labels_created_by_id"), "card_labels", ["created_by_id"], unique=False)
    op.create_index(op.f("ix_card_labels_id"), "card_labels", ["id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_card_labels_id"), table_name="card_labels")
    op.drop_index(op.f("ix_card_labels_created_by_id"), table_name="card_labels")
    op.drop_index(op.f("ix_card_labels_card_id"), table_name="card_labels")
    op.drop_table("card_labels")
