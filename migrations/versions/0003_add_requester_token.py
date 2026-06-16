"""Add requester_token column to work_items

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-15
"""

from typing import Sequence, Union
import secrets

from alembic import op
import sqlalchemy as sa


revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    op.add_column("work_items", sa.Column("requester_token", sa.Text(), nullable=True))
    for row in bind.execute(sa.text("SELECT id FROM work_items WHERE requester_token IS NULL")).fetchall():
        bind.execute(
            sa.text("UPDATE work_items SET requester_token = :token WHERE id = :id"),
            {"token": secrets.token_urlsafe(16), "id": row[0]},
        )
    op.create_index("idx_work_items_requester_token", "work_items", ["requester_token"], unique=True)


def downgrade() -> None:
    op.drop_index("idx_work_items_requester_token", table_name="work_items", if_exists=True)
    op.drop_column("work_items", "requester_token")
