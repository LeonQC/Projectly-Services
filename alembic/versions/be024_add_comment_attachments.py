"""add comment attachments

Revision ID: be024commentattachments
Revises: be022sprints
Create Date: 2026-08-09 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "be024commentattachments"
down_revision: Union[str, Sequence[str], None] = "be022sprints"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("card_attachments", sa.Column("comment_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_card_attachments_comment_id_card_comments",
        "card_attachments",
        "card_comments",
        ["comment_id"],
        ["id"],
    )
    op.create_index(op.f("ix_card_attachments_comment_id"), "card_attachments", ["comment_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_card_attachments_comment_id"), table_name="card_attachments")
    op.drop_constraint("fk_card_attachments_comment_id_card_comments", "card_attachments", type_="foreignkey")
    op.drop_column("card_attachments", "comment_id")
