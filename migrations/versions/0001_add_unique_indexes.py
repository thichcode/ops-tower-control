"""Add unique indexes for source_id, source_message_id, capacity(user_id, month)

Revision ID: 0001
Revises: 0000
Create Date: 2026-06-15
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "0001"
down_revision: Union[str, None] = "0000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _dedup_keep_first(table: str, id_col: str, unique_col: str) -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        keep = sa.text(
            f"SELECT MIN({id_col}) FROM {table} WHERE {unique_col} IS NOT NULL "
            f"GROUP BY {unique_col} HAVING COUNT(*) > 1"
        )
        dup_ids = [row[0] for row in bind.execute(keep).fetchall()]
        if dup_ids:
            op.execute(
                sa.text(
                    f"DELETE FROM {table} WHERE {unique_col} IS NOT NULL "
                    f"AND {id_col} NOT IN (SELECT MIN({id_col}) FROM {table} "
                    f"WHERE {unique_col} IS NOT NULL GROUP BY {unique_col})"
                )
            )
    else:
        for_cols = sa.text(
            f"SELECT MIN({id_col}) as keep_id FROM {table} "
            f"WHERE {unique_col} IS NOT NULL "
            f"GROUP BY {unique_col} HAVING COUNT(*) > 1"
        )
        for row in bind.execute(for_cols).fetchall():
            op.execute(
                sa.text(
                    f"DELETE FROM {table} WHERE {unique_col} IS NOT NULL "
                    f"AND {unique_col} = (SELECT {unique_col} FROM {table} WHERE {id_col} = :keep_id) "
                    f"AND {id_col} != :keep_id"
                ).bindparams(keep_id=row[0])
            )


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    _dedup_keep_first("work_items", "id", "source_id")
    _dedup_keep_first("work_item_evidence", "id", "source_message_id")

    op.execute(
        "DELETE FROM capacity WHERE rowid NOT IN "
        "(SELECT MIN(rowid) FROM capacity GROUP BY user_id, month)"
    ) if dialect == "sqlite" else op.execute(
        "DELETE FROM capacity WHERE ctid NOT IN "
        "(SELECT MIN(ctid) FROM capacity GROUP BY user_id, month)"
    )

    op.create_index("idx_work_items_source_id", "work_items", ["source_id"], unique=True)
    op.create_index("idx_evidence_source_message_id", "work_item_evidence", ["source_message_id"], unique=True)
    op.create_index("idx_capacity_user_month", "capacity", ["user_id", "month"], unique=True)


def downgrade() -> None:
    op.drop_index("idx_work_items_source_id", table_name="work_items", if_exists=True)
    op.drop_index("idx_evidence_source_message_id", table_name="work_item_evidence", if_exists=True)
    op.drop_index("idx_capacity_user_month", table_name="capacity", if_exists=True)
