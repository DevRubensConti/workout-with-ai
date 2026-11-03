"""exercise muscle targets and effects

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-03 09:20:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "muscle_targets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name_pt", sa.String(length=120), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("kind IN ('group', 'muscle', 'region')", name="ck_muscle_targets_kind"),
        sa.CheckConstraint(
            "parent_id IS NULL OR parent_id != id", name="ck_muscle_targets_parent"
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"], ["muscle_targets.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_muscle_targets_code"),
    )
    op.create_index("ix_muscle_targets_parent_id", "muscle_targets", ["parent_id"], unique=False)

    op.create_table(
        "exercise_muscle_effects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("exercise_id", sa.Uuid(), nullable=False),
        sa.Column("muscle_target_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("relative_share_pct", sa.Numeric(precision=5, scale=2), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "role IN ('primary', 'auxiliary')", name="ck_exercise_muscle_effects_role"
        ),
        sa.CheckConstraint(
            "relative_share_pct >= 0 AND relative_share_pct <= 100",
            name="ck_exercise_muscle_effects_share_pct",
        ),
        sa.ForeignKeyConstraint(["exercise_id"], ["exercises.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["muscle_target_id"], ["muscle_targets.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "exercise_id", "muscle_target_id", name="uq_exercise_muscle_effects_target"
        ),
    )
    op.create_index(
        "ix_exercise_muscle_effects_muscle_target_id",
        "exercise_muscle_effects",
        ["muscle_target_id"],
        unique=False,
    )

    if op.get_context().dialect.name == "postgresql":
        op.execute("ALTER TABLE muscle_targets ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE exercise_muscle_effects ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_index(
        "ix_exercise_muscle_effects_muscle_target_id", table_name="exercise_muscle_effects"
    )
    op.drop_table("exercise_muscle_effects")
    op.drop_index("ix_muscle_targets_parent_id", table_name="muscle_targets")
    op.drop_table("muscle_targets")
