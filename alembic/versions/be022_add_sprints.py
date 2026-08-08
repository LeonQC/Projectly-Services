"""add sprints

Revision ID: be022sprints
Revises: be020cardmembers
Create Date: 2026-08-06 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "be022sprints"
down_revision: Union[str, Sequence[str], None] = "be020cardmembers"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sprints",
        sa.Column("epic_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("goal", sa.Text(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('planned', 'active', 'completed')", name="ck_sprints_status"),
        sa.ForeignKeyConstraint(["epic_id"], ["epics.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.add_column("cards", sa.Column("sprint_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_cards_sprint_id_sprints", "cards", "sprints", ["sprint_id"], ["id"])
    op.create_index(op.f("ix_cards_sprint_id"), "cards", ["sprint_id"], unique=False)
    op.create_index(op.f("ix_sprints_epic_id"), "sprints", ["epic_id"], unique=False)
    op.create_index(op.f("ix_sprints_id"), "sprints", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_sprints_id"), table_name="sprints")
    op.drop_index(op.f("ix_sprints_epic_id"), table_name="sprints")
    op.drop_index(op.f("ix_cards_sprint_id"), table_name="cards")
    op.drop_constraint("fk_cards_sprint_id_sprints", "cards", type_="foreignkey")
    op.drop_column("cards", "sprint_id")
    op.drop_table("sprints")
