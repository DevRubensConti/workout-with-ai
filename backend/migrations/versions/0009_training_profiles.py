"""add private training profiles for AI personalization

Revision ID: 0009
Revises: 0008
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "training_profiles",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("age", sa.Integer(), nullable=False),
        sa.Column("weight_kg", sa.Numeric(5, 2), nullable=False),
        sa.Column("height_cm", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("user_id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.CheckConstraint("age BETWEEN 18 AND 100", name="ck_training_profiles_age"),
        sa.CheckConstraint("weight_kg BETWEEN 20 AND 400", name="ck_training_profiles_weight"),
        sa.CheckConstraint("height_cm BETWEEN 100 AND 250", name="ck_training_profiles_height"),
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE training_profiles ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("training_profiles")
