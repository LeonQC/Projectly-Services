from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision = "be062ragchunks"
down_revision: Union[str, Sequence[str], None] = "be061ragjobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rag_chunks",
        sa.Column("workspace_id", sa.Integer(), nullable=True),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("card_id", sa.Integer(), nullable=True),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("source_subtype", sa.String(length=80), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(384), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "source_type IN ('attachment', 'card', 'comment', 'project', 'workspace', 'epic', 'sprint', 'github_event')",
            name="ck_rag_chunks_source_type",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["card_id"], ["cards.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_type",
            "source_id",
            "chunk_index",
            name="uq_rag_chunks_source_chunk",
        ),
    )
    op.create_index(op.f("ix_rag_chunks_id"), "rag_chunks", ["id"], unique=False)
    op.create_index(op.f("ix_rag_chunks_workspace_id"), "rag_chunks", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_rag_chunks_project_id"), "rag_chunks", ["project_id"], unique=False)
    op.create_index(op.f("ix_rag_chunks_card_id"), "rag_chunks", ["card_id"], unique=False)
    op.create_index(op.f("ix_rag_chunks_source_type"), "rag_chunks", ["source_type"], unique=False)
    op.create_index(op.f("ix_rag_chunks_source_id"), "rag_chunks", ["source_id"], unique=False)
    op.create_index(op.f("ix_rag_chunks_source_subtype"), "rag_chunks", ["source_subtype"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_rag_chunks_source_subtype"), table_name="rag_chunks")
    op.drop_index(op.f("ix_rag_chunks_source_id"), table_name="rag_chunks")
    op.drop_index(op.f("ix_rag_chunks_source_type"), table_name="rag_chunks")
    op.drop_index(op.f("ix_rag_chunks_card_id"), table_name="rag_chunks")
    op.drop_index(op.f("ix_rag_chunks_project_id"), table_name="rag_chunks")
    op.drop_index(op.f("ix_rag_chunks_workspace_id"), table_name="rag_chunks")
    op.drop_index(op.f("ix_rag_chunks_id"), table_name="rag_chunks")
    op.drop_table("rag_chunks")
