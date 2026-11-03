"""persist personal exercise availability for AI generation"""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "disabled_exercises",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("exercise_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "exercise_id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["exercise_id"], ["exercises.id"], ondelete="CASCADE"),
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE disabled_exercises ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("disabled_exercises")
