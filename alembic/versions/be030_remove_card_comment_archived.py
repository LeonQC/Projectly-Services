"""remove card comment archived column

Revision ID: be030commentdelete
Revises: be026githublinks
Create Date: 2026-08-13 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "be030commentdelete"
down_revision: Union[str, Sequence[str], None] = "be026githublinks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("card_comments", "archived")


def downgrade() -> None:
    op.add_column(
        "card_comments",
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("card_comments", "archived", server_default=None)
