"""add attachment chunk embeddings

Revision ID: c31d5ed58bf1
Revises: 1235a1acc615
Create Date: 2026-09-03 11:12:13.953748

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = 'c31d5ed58bf1'
down_revision: Union[str, Sequence[str], None] = '1235a1acc615'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "attachment_chunks",
        sa.Column("embedding", Vector(1536), nullable=True),
    )
    op.execute(
        "CREATE INDEX ix_attachment_chunks_embedding_hnsw "
        "ON attachment_chunks USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS ix_attachment_chunks_embedding_hnsw")
    op.drop_column("attachment_chunks", "embedding")
