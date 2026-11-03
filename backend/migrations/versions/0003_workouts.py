"""treinos: exercises, workout_plans, workout_days, workout_day_exercises, sessions e set logs

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-27 23:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Ordem de criação (pais antes dos filhos). O downgrade percorre ao contrário.
TABLES = (
    "exercises",
    "workout_plans",
    "workout_days",
    "workout_day_exercises",
    "workout_sessions",
    "workout_set_logs",
)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "exercises",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("muscle_group", sa.String(length=60), nullable=False),
        sa.Column("equipment", sa.String(length=80), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("video_url", sa.String(length=500), nullable=True),
        sa.Column("owner_user_id", sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_exercises_owner_user_id_name", "exercises", ["owner_user_id", "name"], unique=False
    )

    op.create_table(
        "workout_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("goal", sa.String(length=80), nullable=True),
        sa.Column("level", sa.String(length=40), nullable=True),
        sa.Column("source", sa.String(length=20), server_default="manual", nullable=False),
        sa.Column("ai_metadata", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("status IN ('active', 'archived')", name="ck_workout_plans_status"),
        sa.CheckConstraint("source IN ('manual', 'ai')", name="ck_workout_plans_source"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workout_plans_user_id", "workout_plans", ["user_id"], unique=False)
    # No máximo UM plano ativo por usuário
    op.create_index(
        "uq_workout_plans_one_active_per_user",
        "workout_plans",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
        sqlite_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "workout_days",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("position >= 0", name="ck_workout_days_position"),
        sa.ForeignKeyConstraint(["plan_id"], ["workout_plans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_id", "position", name="uq_workout_days_plan_id_position"),
    )

    op.create_table(
        "workout_day_exercises",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("day_id", sa.Uuid(), nullable=False),
        sa.Column("exercise_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("sets", sa.Integer(), nullable=False),
        sa.Column("reps_min", sa.Integer(), nullable=False),
        sa.Column("reps_max", sa.Integer(), nullable=True),
        sa.Column("target_weight_kg", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("rest_seconds", sa.Integer(), nullable=True),
        sa.Column("tempo", sa.String(length=20), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("position >= 0", name="ck_workout_day_exercises_position"),
        sa.CheckConstraint("sets > 0", name="ck_workout_day_exercises_sets"),
        sa.CheckConstraint("reps_min >= 0", name="ck_workout_day_exercises_reps_min"),
        sa.CheckConstraint(
            "reps_max IS NULL OR reps_max >= reps_min", name="ck_workout_day_exercises_reps_max"
        ),
        sa.CheckConstraint(
            "target_weight_kg IS NULL OR target_weight_kg >= 0",
            name="ck_workout_day_exercises_target_weight",
        ),
        sa.CheckConstraint(
            "rest_seconds IS NULL OR rest_seconds >= 0", name="ck_workout_day_exercises_rest"
        ),
        sa.ForeignKeyConstraint(["day_id"], ["workout_days.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["exercise_id"], ["exercises.id"], ondelete="NO ACTION"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("day_id", "position", name="uq_workout_day_exercises_day_id_position"),
    )
    op.create_index(
        "ix_workout_day_exercises_exercise_id",
        "workout_day_exercises",
        ["exercise_id"],
        unique=False,
    )

    op.create_table(
        "workout_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=True),
        sa.Column("day_id", sa.Uuid(), nullable=True),
        sa.Column("plan_name", sa.String(length=160), nullable=True),
        sa.Column("day_name", sa.String(length=80), nullable=True),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("perceived_effort", sa.Integer(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "perceived_effort IS NULL OR perceived_effort BETWEEN 1 AND 10",
            name="ck_workout_sessions_perceived_effort",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_id"], ["workout_plans.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["day_id"], ["workout_days.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workout_sessions_plan_id", "workout_sessions", ["plan_id"], unique=False)
    op.create_index("ix_workout_sessions_day_id", "workout_sessions", ["day_id"], unique=False)
    op.create_index(
        "ix_workout_sessions_user_id_started_at",
        "workout_sessions",
        ["user_id", sa.text("started_at DESC")],
        unique=False,
    )

    op.create_table(
        "workout_set_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("exercise_id", sa.Uuid(), nullable=False),
        sa.Column("exercise_name", sa.String(length=160), nullable=False),
        sa.Column("set_number", sa.Integer(), nullable=False),
        sa.Column("reps", sa.Integer(), nullable=False),
        sa.Column("weight_kg", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("completed", sa.Boolean(), server_default=sa.true(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("set_number > 0", name="ck_workout_set_logs_set_number"),
        sa.CheckConstraint("reps >= 0", name="ck_workout_set_logs_reps"),
        sa.CheckConstraint(
            "weight_kg IS NULL OR weight_kg >= 0", name="ck_workout_set_logs_weight"
        ),
        sa.ForeignKeyConstraint(["session_id"], ["workout_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["exercise_id"], ["exercises.id"], ondelete="NO ACTION"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_workout_set_logs_session_id", "workout_set_logs", ["session_id"], unique=False
    )
    op.create_index(
        "ix_workout_set_logs_exercise_id", "workout_set_logs", ["exercise_id"], unique=False
    )

    # RLS ligado e sem policies (padrão do projeto, ver 0002): só o backend acessa o banco.
    if op.get_context().dialect.name == "postgresql":
        for table in TABLES:
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    # Dropar a tabela remove o RLS junto; basta apagar na ordem inversa das FKs.
    op.drop_index("ix_workout_set_logs_exercise_id", table_name="workout_set_logs")
    op.drop_index("ix_workout_set_logs_session_id", table_name="workout_set_logs")
    op.drop_table("workout_set_logs")

    op.drop_index("ix_workout_sessions_user_id_started_at", table_name="workout_sessions")
    op.drop_index("ix_workout_sessions_day_id", table_name="workout_sessions")
    op.drop_index("ix_workout_sessions_plan_id", table_name="workout_sessions")
    op.drop_table("workout_sessions")

    op.drop_index("ix_workout_day_exercises_exercise_id", table_name="workout_day_exercises")
    op.drop_table("workout_day_exercises")

    op.drop_table("workout_days")

    op.drop_index(
        "uq_workout_plans_one_active_per_user",
        table_name="workout_plans",
        postgresql_where=sa.text("status = 'active'"),
        sqlite_where=sa.text("status = 'active'"),
    )
    op.drop_index("ix_workout_plans_user_id", table_name="workout_plans")
    op.drop_table("workout_plans")

    op.drop_index("ix_exercises_owner_user_id_name", table_name="exercises")
    op.drop_table("exercises")
