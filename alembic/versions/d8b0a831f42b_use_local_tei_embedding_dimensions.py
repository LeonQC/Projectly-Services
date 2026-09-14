"""use local tei embedding dimensions

Revision ID: d8b0a831f42b
Revises: c31d5ed58bf1
Create Date: 2026-09-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = "d8b0a831f42b"
down_revision: Union[str, Sequence[str], None] = "c31d5ed58bf1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_attachment_chunks_embedding_hnsw")
    op.execute("UPDATE attachment_chunks SET embedding = NULL")
    op.alter_column(
        "attachment_chunks",
        "embedding",
        existing_type=Vector(1536),
        type_=Vector(384),
        existing_nullable=True,
        postgresql_using="NULL::vector(384)",
    )
    op.execute(
        "CREATE INDEX ix_attachment_chunks_embedding_hnsw "
        "ON attachment_chunks USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_attachment_chunks_embedding_hnsw")
    op.execute("UPDATE attachment_chunks SET embedding = NULL")
    op.alter_column(
        "attachment_chunks",
        "embedding",
        existing_type=Vector(384),
        type_=Vector(1536),
        existing_nullable=True,
        postgresql_using="NULL::vector(1536)",
    )
    op.execute(
        "CREATE INDEX ix_attachment_chunks_embedding_hnsw "
        "ON attachment_chunks USING hnsw (embedding vector_cosine_ops)"
    )
