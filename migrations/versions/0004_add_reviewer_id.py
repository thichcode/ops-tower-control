"""Add reviewer_id to ai_reviews

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-15
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        op.add_column("ai_reviews", sa.Column("reviewer_id", sa.Integer(), nullable=True))
    else:
        op.add_column("ai_reviews", sa.Column("reviewer_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True))


def downgrade() -> None:
    op.drop_column("ai_reviews", "reviewer_id")
