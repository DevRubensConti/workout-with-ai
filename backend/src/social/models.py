import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    false,
    func,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.auth.models import utcnow
from src.database import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, server_default=func.now()
    )


class UserProfile(TimestampMixin, Base):
    __tablename__ = "user_profiles"
    __table_args__ = (
        CheckConstraint(
            "username = lower(username) AND length(trim(username)) BETWEEN 3 AND 30 "
            "AND username = trim(username)",
            name="ck_user_profiles_username",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    username: Mapped[str] = mapped_column(String(30), unique=True)
    display_name: Mapped[str] = mapped_column(String(120))
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_private: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())

    # Consentimento separado da visibilidade do perfil.
    nearby_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    location: Mapped["UserLocation | None"] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
        uselist=False,
    )


class UserFollow(TimestampMixin, Base):
    __tablename__ = "user_follows"
    __table_args__ = (
        UniqueConstraint("follower_id", "following_id", name="uq_user_follows_pair"),
        CheckConstraint("follower_id <> following_id", name="ck_user_follows_not_self"),
        CheckConstraint("status IN ('pending', 'accepted')", name="ck_user_follows_status"),
        CheckConstraint(
            "(status = 'pending' AND accepted_at IS NULL) OR "
            "(status = 'accepted' AND accepted_at IS NOT NULL)",
            name="ck_user_follows_accepted_at",
        ),
        Index("ix_user_follows_following_id_status", "following_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    follower_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("user_profiles.user_id", ondelete="CASCADE")
    )
    following_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("user_profiles.user_id", ondelete="CASCADE")
    )
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending")
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UserBlock(TimestampMixin, Base):
    __tablename__ = "user_blocks"
    __table_args__ = (
        UniqueConstraint("blocker_id", "blocked_id", name="uq_user_blocks_pair"),
        CheckConstraint("blocker_id <> blocked_id", name="ck_user_blocks_not_self"),
        Index("ix_user_blocks_blocked_id", "blocked_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    blocker_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("user_profiles.user_id", ondelete="CASCADE")
    )
    blocked_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("user_profiles.user_id", ondelete="CASCADE")
    )


class UserLocation(TimestampMixin, Base):
    """Uma unica celula aproximada por usuario, nunca coordenadas brutas ou trajetos."""

    __tablename__ = "user_locations"
    __table_args__ = (
        CheckConstraint(
            "latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180",
            name="ck_user_locations_coordinates",
        ),
        # A grade de 0.01 grau impede armazenar precisao maior, inclusive no SQLite.
        CheckConstraint(
            "abs(latitude * 100 - round(latitude * 100)) < 0.000001 AND "
            "abs(longitude * 100 - round(longitude * 100)) < 0.000001",
            name="ck_user_locations_approximate",
        ),
        CheckConstraint("expires_at > recorded_at", name="ck_user_locations_expiration"),
        Index("ix_user_locations_latitude_longitude", "latitude", "longitude"),
        Index("ix_user_locations_expires_at", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("user_profiles.user_id", ondelete="CASCADE"), unique=True
    )
    latitude: Mapped[Decimal] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal] = mapped_column(Numeric(9, 6))
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    profile: Mapped["UserProfile"] = relationship(back_populates="location")
