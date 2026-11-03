"""social

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-28 22:00:50.201906
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("username", sa.String(length=30), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("avatar_url", sa.String(length=500), nullable=True),
        sa.Column("is_private", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("nearby_enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
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
        sa.CheckConstraint(
            "username = lower(username) AND length(trim(username)) BETWEEN 3 AND 30 "
            "AND username = trim(username)",
            name="ck_user_profiles_username",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
        sa.UniqueConstraint("username"),
    )
    op.create_table(
        "user_blocks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("blocker_id", sa.Uuid(), nullable=False),
        sa.Column("blocked_id", sa.Uuid(), nullable=False),
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
        sa.CheckConstraint("blocker_id <> blocked_id", name="ck_user_blocks_not_self"),
        sa.ForeignKeyConstraint(["blocked_id"], ["user_profiles.user_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["blocker_id"], ["user_profiles.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("blocker_id", "blocked_id", name="uq_user_blocks_pair"),
    )
    op.create_index("ix_user_blocks_blocked_id", "user_blocks", ["blocked_id"], unique=False)
    op.create_table(
        "user_follows",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("follower_id", sa.Uuid(), nullable=False),
        sa.Column("following_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "(status = 'pending' AND accepted_at IS NULL) OR "
            "(status = 'accepted' AND accepted_at IS NOT NULL)",
            name="ck_user_follows_accepted_at",
        ),
        sa.CheckConstraint("status IN ('pending', 'accepted')", name="ck_user_follows_status"),
        sa.CheckConstraint("follower_id <> following_id", name="ck_user_follows_not_self"),
        sa.ForeignKeyConstraint(["follower_id"], ["user_profiles.user_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["following_id"], ["user_profiles.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("follower_id", "following_id", name="uq_user_follows_pair"),
    )
    op.create_index(
        "ix_user_follows_following_id_status",
        "user_follows",
        ["following_id", "status"],
        unique=False,
    )
    op.create_table(
        "user_locations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("latitude", sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column("longitude", sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.CheckConstraint(
            "abs(latitude * 100 - round(latitude * 100)) < 0.000001 AND "
            "abs(longitude * 100 - round(longitude * 100)) < 0.000001",
            name="ck_user_locations_approximate",
        ),
        sa.CheckConstraint("expires_at > recorded_at", name="ck_user_locations_expiration"),
        sa.CheckConstraint(
            "latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180",
            name="ck_user_locations_coordinates",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_user_locations_expires_at", "user_locations", ["expires_at"], unique=False)
    op.create_index(
        "ix_user_locations_latitude_longitude",
        "user_locations",
        ["latitude", "longitude"],
        unique=False,
    )
    if op.get_context().dialect.name == "postgresql":
        for table in ("user_profiles", "user_blocks", "user_follows", "user_locations"):
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_index("ix_user_locations_latitude_longitude", table_name="user_locations")
    op.drop_index("ix_user_locations_expires_at", table_name="user_locations")
    op.drop_table("user_locations")
    op.drop_index("ix_user_follows_following_id_status", table_name="user_follows")
    op.drop_table("user_follows")
    op.drop_index("ix_user_blocks_blocked_id", table_name="user_blocks")
    op.drop_table("user_blocks")
    op.drop_table("user_profiles")
