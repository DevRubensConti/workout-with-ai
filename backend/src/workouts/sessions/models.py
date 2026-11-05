import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
    func,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.auth.models import utcnow
from src.database import Base
from src.workouts.common import TimestampMixin

if TYPE_CHECKING:
    from src.workouts.plans.models import WorkoutDay, WorkoutPlan


class WorkoutSession(TimestampMixin, Base):
    """Execução real de um dia de treino (histórico)."""

    __tablename__ = "workout_sessions"
    __table_args__ = (
        CheckConstraint(
            "perceived_effort IS NULL OR perceived_effort BETWEEN 1 AND 10",
            name="ck_workout_sessions_perceived_effort",
        ),
        Index("ix_workout_sessions_plan_id", "plan_id"),
        Index("ix_workout_sessions_day_id", "day_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"))
    plan_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("workout_plans.id", ondelete="SET NULL"), nullable=True
    )
    day_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("workout_days.id", ondelete="SET NULL"), nullable=True
    )
    # Snapshots preservam a identificação do treino após a exclusão do plano.
    plan_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    day_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    perceived_effort: Mapped[int | None] = mapped_column(Integer, nullable=True)

    plan: Mapped["WorkoutPlan | None"] = relationship(back_populates="sessions")
    day: Mapped["WorkoutDay | None"] = relationship(back_populates="sessions")
    set_logs: Mapped[list["WorkoutSetLog"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="(WorkoutSetLog.created_at, WorkoutSetLog.set_number)",
        lazy="selectin",
    )


Index(
    "ix_workout_sessions_user_id_started_at",
    WorkoutSession.user_id,
    WorkoutSession.started_at.desc(),
)


class WorkoutSetLog(TimestampMixin, Base):
    """Série executada em uma sessão."""

    __tablename__ = "workout_set_logs"
    __table_args__ = (
        CheckConstraint("set_number > 0", name="ck_workout_set_logs_set_number"),
        CheckConstraint("reps >= 0", name="ck_workout_set_logs_reps"),
        CheckConstraint("weight_kg IS NULL OR weight_kg >= 0", name="ck_workout_set_logs_weight"),
        Index("ix_workout_set_logs_session_id", "session_id"),
        Index("ix_workout_set_logs_exercise_id", "exercise_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workout_sessions.id", ondelete="CASCADE")
    )
    exercise_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("exercises.id", ondelete="NO ACTION")
    )
    # Snapshot: o histórico mantém o nome mesmo se o exercício for renomeado
    exercise_name: Mapped[str] = mapped_column(String(160))
    set_number: Mapped[int] = mapped_column(Integer)
    reps: Mapped[int] = mapped_column(Integer)
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    completed: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())

    session: Mapped["WorkoutSession"] = relationship(back_populates="set_logs")
