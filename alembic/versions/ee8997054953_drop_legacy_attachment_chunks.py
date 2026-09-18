"""drop legacy attachment chunks

Revision ID: ee8997054953
Revises: be062ragchunks
Create Date: 2026-09-17 17:19:19.102311

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ee8997054953'
down_revision: Union[str, Sequence[str], None] = 'be062ragchunks'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("attachment_chunks")


def downgrade() -> None:
    pass