"""add github event card matching

Revision ID: be042githubmatching
Revises: be040githubevents
Create Date: 2026-08-17 19:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "be042githubmatching"
down_revision: Union[str, Sequence[str], None] = "be040githubevents"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("github_events", sa.Column("card_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_github_events_card_id"), "github_events", ["card_id"], unique=False)
    op.create_foreign_key("fk_github_events_card_id_cards", "github_events", "cards", ["card_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_github_events_card_id_cards", "github_events", type_="foreignkey")
    op.drop_index(op.f("ix_github_events_card_id"), table_name="github_events")
    op.drop_column("github_events", "card_id")
