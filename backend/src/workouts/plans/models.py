import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.auth.models import utcnow
from src.database import Base
from src.workouts.common import TimestampMixin

if TYPE_CHECKING:
    from src.workouts.exercises.models import Exercise
    from src.workouts.sessions.models import WorkoutSession


class PlanStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class PlanSource(StrEnum):
    MANUAL = "manual"
    AI = "ai"


class WorkoutPlan(TimestampMixin, Base):
    __tablename__ = "workout_plans"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'archived')", name="ck_workout_plans_status"),
        CheckConstraint("source IN ('manual', 'ai')", name="ck_workout_plans_source"),
        # No máximo UM plano ativo por usuário (índice parcial: PostgreSQL e SQLite)
        Index(
            "uq_workout_plans_one_active_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
            sqlite_where=text("status = 'active'"),
        ),
        Index("ix_workout_plans_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    goal: Mapped[str | None] = mapped_column(String(80), nullable=True)
    level: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source: Mapped[str] = mapped_column(
        String(20), default=PlanSource.MANUAL.value, server_default=PlanSource.MANUAL.value
    )
    # Prompt/modelo usados quando source = "ai"
    ai_metadata: Mapped[dict | None] = mapped_column(JSON(none_as_null=True), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default=PlanStatus.ACTIVE.value, server_default=PlanStatus.ACTIVE.value
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    days: Mapped[list["WorkoutDay"]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="WorkoutDay.position",
        lazy="selectin",
    )
    # Sem cascade: apagar o plano preserva as sessões (plan_id vira NULL no banco)
    sessions: Mapped[list["WorkoutSession"]] = relationship(
        back_populates="plan", passive_deletes=True, lazy="select"
    )


class WorkoutDay(TimestampMixin, Base):
    __tablename__ = "workout_days"
    __table_args__ = (
        UniqueConstraint("plan_id", "position", name="uq_workout_days_plan_id_position"),
        CheckConstraint("position >= 0", name="ck_workout_days_position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    plan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workout_plans.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(80))
    position: Mapped[int] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    plan: Mapped["WorkoutPlan"] = relationship(back_populates="days")
    exercises: Mapped[list["WorkoutDayExercise"]] = relationship(
        back_populates="day",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="WorkoutDayExercise.position",
        lazy="selectin",
    )
    sessions: Mapped[list["WorkoutSession"]] = relationship(
        back_populates="day", passive_deletes=True, lazy="select"
    )


class WorkoutDayExercise(TimestampMixin, Base):
    """Exercício dentro de um dia do treino, com a prescrição própria."""

    __tablename__ = "workout_day_exercises"
    __table_args__ = (
        UniqueConstraint("day_id", "position", name="uq_workout_day_exercises_day_id_position"),
        CheckConstraint("position >= 0", name="ck_workout_day_exercises_position"),
        CheckConstraint("sets > 0", name="ck_workout_day_exercises_sets"),
        CheckConstraint("reps_min >= 0", name="ck_workout_day_exercises_reps_min"),
        CheckConstraint(
            "reps_max IS NULL OR reps_max >= reps_min", name="ck_workout_day_exercises_reps_max"
        ),
        CheckConstraint(
            "target_weight_kg IS NULL OR target_weight_kg >= 0",
            name="ck_workout_day_exercises_target_weight",
        ),
        CheckConstraint(
            "rest_seconds IS NULL OR rest_seconds >= 0", name="ck_workout_day_exercises_rest"
        ),
        Index("ix_workout_day_exercises_exercise_id", "exercise_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    day_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workout_days.id", ondelete="CASCADE")
    )
    # NO ACTION permite a exclusão em cascata de exercícios e treinos do mesmo usuário.
    exercise_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("exercises.id", ondelete="NO ACTION")
    )
    position: Mapped[int] = mapped_column(Integer)
    sets: Mapped[int] = mapped_column(Integer)
    reps_min: Mapped[int] = mapped_column(Integer)
    reps_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    rest_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tempo: Mapped[str | None] = mapped_column(String(20), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    day: Mapped["WorkoutDay"] = relationship(back_populates="exercises")
    exercise: Mapped["Exercise"] = relationship(lazy="selectin")
