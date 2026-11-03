"""exercise_translations

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-28 22:12:51.168975
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "exercise_translations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("exercise_id", sa.Uuid(), nullable=False),
        sa.Column("locale", sa.String(length=10), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("instructions", sa.JSON(), nullable=False),
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
        sa.CheckConstraint("locale IN ('en', 'pt-BR')", name="ck_exercise_translations_locale"),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_exercise_translations_name"),
        sa.ForeignKeyConstraint(["exercise_id"], ["exercises.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "exercise_id", "locale", name="uq_exercise_translations_exercise_locale"
        ),
    )
    op.create_index(
        "ix_exercise_translations_locale_name",
        "exercise_translations",
        ["locale", "name"],
        unique=False,
    )
    with op.batch_alter_table("exercises") as batch:
        for name, length in (
            ("source", 80),
            ("source_id", 160),
            ("force", 40),
            ("level", 40),
            ("mechanic", 40),
            ("category", 60),
        ):
            batch.add_column(sa.Column(name, sa.String(length), nullable=True))
        for name in ("primary_muscles", "secondary_muscles", "images"):
            batch.add_column(sa.Column(name, sa.JSON(none_as_null=True), nullable=True))
        batch.create_unique_constraint("uq_exercises_source_source_id", ["source", "source_id"])
        batch.create_check_constraint(
            "ck_exercises_source_pair",
            "(source IS NULL AND source_id IS NULL) OR "
            "(source IS NOT NULL AND source_id IS NOT NULL)",
        )
    if op.get_context().dialect.name == "postgresql":
        op.execute("ALTER TABLE exercise_translations ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_index("ix_exercise_translations_locale_name", table_name="exercise_translations")
    op.drop_table("exercise_translations")
    with op.batch_alter_table("exercises") as batch:
        batch.drop_constraint("uq_exercises_source_source_id", type_="unique")
        batch.drop_constraint("ck_exercises_source_pair", type_="check")
        for name in (
            "images",
            "secondary_muscles",
            "primary_muscles",
            "category",
            "mechanic",
            "level",
            "force",
            "source_id",
            "source",
        ):
            batch.drop_column(name)
