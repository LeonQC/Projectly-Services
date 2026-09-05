"""add rag ingestion jobs

Revision ID: be061ragjobs
Revises: d8b0a831f42b
Create Date: 2026-09-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "be061ragjobs"
down_revision: Union[str, Sequence[str], None] = "d8b0a831f42b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "attachment_documents",
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.alter_column("attachment_documents", "content_json", existing_type=sa.JSON(), nullable=True)
    op.alter_column("attachment_documents", "content_markdown", existing_type=sa.Text(), nullable=True)
    op.create_check_constraint(
        "ck_attachment_documents_extraction_status",
        "attachment_documents",
        "extraction_status IN ('pending', 'processing', 'completed', 'failed')",
    )

    op.create_table(
        "rag_ingestion_jobs",
        sa.Column("attachment_id", sa.Integer(), nullable=False),
        sa.Column("card_id", sa.Integer(), nullable=False),
        sa.Column("requested_by_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["attachment_id"], ["card_attachments.id"]),
        sa.ForeignKeyConstraint(["card_id"], ["cards.id"]),
        sa.ForeignKeyConstraint(["requested_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name="ck_rag_ingestion_jobs_status",
        ),
    )
    op.create_index(op.f("ix_rag_ingestion_jobs_id"), "rag_ingestion_jobs", ["id"], unique=False)
    op.create_index(op.f("ix_rag_ingestion_jobs_attachment_id"), "rag_ingestion_jobs", ["attachment_id"], unique=False)
    op.create_index(op.f("ix_rag_ingestion_jobs_card_id"), "rag_ingestion_jobs", ["card_id"], unique=False)
    op.create_index(op.f("ix_rag_ingestion_jobs_requested_by_id"), "rag_ingestion_jobs", ["requested_by_id"], unique=False)
    op.create_index(op.f("ix_rag_ingestion_jobs_status"), "rag_ingestion_jobs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_rag_ingestion_jobs_status"), table_name="rag_ingestion_jobs")
    op.drop_index(op.f("ix_rag_ingestion_jobs_requested_by_id"), table_name="rag_ingestion_jobs")
    op.drop_index(op.f("ix_rag_ingestion_jobs_card_id"), table_name="rag_ingestion_jobs")
    op.drop_index(op.f("ix_rag_ingestion_jobs_attachment_id"), table_name="rag_ingestion_jobs")
    op.drop_index(op.f("ix_rag_ingestion_jobs_id"), table_name="rag_ingestion_jobs")
    op.drop_table("rag_ingestion_jobs")

    op.drop_constraint(
        "ck_attachment_documents_extraction_status",
        "attachment_documents",
        type_="check",
    )
    op.alter_column("attachment_documents", "content_markdown", existing_type=sa.Text(), nullable=False)
    op.alter_column("attachment_documents", "content_json", existing_type=sa.JSON(), nullable=False)
    op.drop_column("attachment_documents", "retry_count")
