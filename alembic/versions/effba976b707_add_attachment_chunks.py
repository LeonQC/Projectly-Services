"""add attachment chunks

Revision ID: effba976b707
Revises: 4f968d38c737
Create Date: 2026-09-02 14:08:07.189742

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'effba976b707'
down_revision: Union[str, Sequence[str], None] = '4f968d38c737'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "attachment_chunks",
        sa.Column("attachment_document_id", sa.Integer(), nullable=False),
        sa.Column("attachment_id", sa.Integer(), nullable=False),
        sa.Column("card_id", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["attachment_document_id"], ["attachment_documents.id"]),
        sa.ForeignKeyConstraint(["attachment_id"], ["card_attachments.id"]),
        sa.ForeignKeyConstraint(["card_id"], ["cards.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("attachment_document_id", "chunk_index", name="uq_attachment_chunks_document_chunk_index"),
    )
    op.create_index(op.f("ix_attachment_chunks_id"), "attachment_chunks", ["id"], unique=False)
    op.create_index(op.f("ix_attachment_chunks_attachment_document_id"), "attachment_chunks", ["attachment_document_id"], unique=False)
    op.create_index(op.f("ix_attachment_chunks_attachment_id"), "attachment_chunks", ["attachment_id"], unique=False)
    op.create_index(op.f("ix_attachment_chunks_card_id"), "attachment_chunks", ["card_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_attachment_chunks_card_id"), table_name="attachment_chunks")
    op.drop_index(op.f("ix_attachment_chunks_attachment_id"), table_name="attachment_chunks")
    op.drop_index(op.f("ix_attachment_chunks_attachment_document_id"), table_name="attachment_chunks")
    op.drop_index(op.f("ix_attachment_chunks_id"), table_name="attachment_chunks")
    op.drop_table("attachment_chunks")

