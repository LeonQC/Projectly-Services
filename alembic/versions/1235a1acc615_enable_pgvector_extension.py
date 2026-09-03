"""enable pgvector extension

Revision ID: 1235a1acc615
Revises: effba976b707
Create Date: 2026-09-03 11:04:47.997358

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1235a1acc615'
down_revision: Union[str, Sequence[str], None] = 'effba976b707'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS vector")