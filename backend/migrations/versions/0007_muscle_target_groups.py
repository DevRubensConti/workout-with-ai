"""allow intermediate muscle groups in muscle target hierarchy

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-03 09:35:00
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("muscle_targets") as batch:
        batch.drop_constraint("ck_muscle_targets_kind", type_="check")
        batch.create_check_constraint(
            "ck_muscle_targets_kind",
            "kind IN ('group', 'muscle_group', 'muscle', 'region')",
        )


def downgrade() -> None:
    op.execute(
        "UPDATE muscle_targets SET kind = 'group' WHERE kind = 'muscle_group'"
    )
    with op.batch_alter_table("muscle_targets") as batch:
        batch.drop_constraint("ck_muscle_targets_kind", type_="check")
        batch.create_check_constraint(
            "ck_muscle_targets_kind", "kind IN ('group', 'muscle', 'region')"
        )
