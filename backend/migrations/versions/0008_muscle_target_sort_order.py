"""add stable catalog ordering for automatic exercise muscle shares

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-03 10:20:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "muscle_targets",
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
    )
    with op.batch_alter_table("muscle_targets") as batch:
        batch.create_check_constraint("ck_muscle_targets_sort_order", "sort_order >= 0")
    op.create_index(
        "ix_muscle_targets_sort_order",
        "muscle_targets",
        ["sort_order", "name_pt"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_muscle_targets_sort_order", table_name="muscle_targets")
    with op.batch_alter_table("muscle_targets") as batch:
        batch.drop_constraint("ck_muscle_targets_sort_order", type_="check")
        batch.drop_column("sort_order")
