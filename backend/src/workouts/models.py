"""
Models do módulo de treinos.

Hierarquia: WorkoutPlan (treino) -> WorkoutDay (A/B/C) -> WorkoutDayExercise.
Histórico: WorkoutSession (execução real) -> WorkoutSetLog (série executada).

Só tipos genéricos do SQLAlchemy, para rodar igual em PostgreSQL e SQLite (testes).
Valores "enum" são String + CheckConstraint (sem tipo nativo, migrations simples).
"""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Boolean,
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
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.auth.models import utcnow
from src.database import Base


class PlanStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class PlanSource(StrEnum):
    MANUAL = "manual"
    AI = "ai"


class TimestampMixin:
    # sort_order faz as colunas de auditoria ficarem no fim da tabela
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now(), sort_order=100
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
        sort_order=101,
    )


class Exercise(TimestampMixin, Base):
    """Catálogo. owner_user_id NULL = exercício global; preenchido = personalizado."""

    __tablename__ = "exercises"
    __table_args__ = (
        Index("ix_exercises_owner_user_id_name", "owner_user_id", "name"),
        UniqueConstraint("source", "source_id", name="uq_exercises_source_source_id"),
        CheckConstraint(
            "(source IS NULL AND source_id IS NULL) OR "
            "(source IS NOT NULL AND source_id IS NOT NULL)",
            name="ck_exercises_source_pair",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(160))
    muscle_group: Mapped[str] = mapped_column(String(60))
    equipment: Mapped[str | None] = mapped_column(String(80), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    video_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    source: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    force: Mapped[str | None] = mapped_column(String(40), nullable=True)
    level: Mapped[str | None] = mapped_column(String(40), nullable=True)
    mechanic: Mapped[str | None] = mapped_column(String(40), nullable=True)
    category: Mapped[str | None] = mapped_column(String(60), nullable=True)
    primary_muscles: Mapped[list[str] | None] = mapped_column(
        JSON(none_as_null=True), nullable=True
    )
    secondary_muscles: Mapped[list[str] | None] = mapped_column(
        JSON(none_as_null=True), nullable=True
    )
    images: Mapped[list[str] | None] = mapped_column(JSON(none_as_null=True), nullable=True)

    translations: Mapped[list["ExerciseTranslation"]] = relationship(
        back_populates="exercise",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
        order_by="ExerciseTranslation.locale",
    )
    muscle_effects: Mapped[list["ExerciseMuscleEffect"]] = relationship(
        back_populates="exercise",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )


class DisabledExercise(Base):
    """Ausência de registro significa habilitado para a IA."""

    __tablename__ = "disabled_exercises"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    exercise_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("exercises.id", ondelete="CASCADE"), primary_key=True
    )


class MuscleTarget(TimestampMixin, Base):
    """Hierarchical catalog of muscle groups, muscles, and anatomical regions."""

    __tablename__ = "muscle_targets"
    __table_args__ = (
        UniqueConstraint("code", name="uq_muscle_targets_code"),
        CheckConstraint(
            "kind IN ('group', 'muscle_group', 'muscle', 'region')",
            name="ck_muscle_targets_kind",
        ),
        CheckConstraint("parent_id IS NULL OR parent_id != id", name="ck_muscle_targets_parent"),
        CheckConstraint("sort_order >= 0", name="ck_muscle_targets_sort_order"),
        Index("ix_muscle_targets_parent_id", "parent_id"),
        Index("ix_muscle_targets_sort_order", "sort_order", "name_pt"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(80))
    name_pt: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(20))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("muscle_targets.id", ondelete="RESTRICT"), nullable=True
    )

    parent: Mapped["MuscleTarget | None"] = relationship(
        back_populates="children", remote_side="MuscleTarget.id"
    )
    children: Mapped[list["MuscleTarget"]] = relationship(back_populates="parent", lazy="selectin")
    exercise_effects: Mapped[list["ExerciseMuscleEffect"]] = relationship(
        back_populates="muscle_target", passive_deletes=True
    )


class ExerciseMuscleEffect(TimestampMixin, Base):
    """Estimated distribution of an exercise's stimulus across muscle targets."""

    __tablename__ = "exercise_muscle_effects"
    __table_args__ = (
        UniqueConstraint(
            "exercise_id", "muscle_target_id", name="uq_exercise_muscle_effects_target"
        ),
        CheckConstraint("role IN ('primary', 'auxiliary')", name="ck_exercise_muscle_effects_role"),
        CheckConstraint(
            "relative_share_pct >= 0 AND relative_share_pct <= 100",
            name="ck_exercise_muscle_effects_share_pct",
        ),
        Index("ix_exercise_muscle_effects_muscle_target_id", "muscle_target_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    exercise_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("exercises.id", ondelete="CASCADE")
    )
    muscle_target_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("muscle_targets.id", ondelete="RESTRICT")
    )
    role: Mapped[str] = mapped_column(String(20))
    relative_share_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2))

    exercise: Mapped["Exercise"] = relationship(back_populates="muscle_effects")
    muscle_target: Mapped[MuscleTarget] = relationship(back_populates="exercise_effects")


class ExerciseTranslation(TimestampMixin, Base):
    __tablename__ = "exercise_translations"
    __table_args__ = (
        UniqueConstraint("exercise_id", "locale", name="uq_exercise_translations_exercise_locale"),
        CheckConstraint("locale IN ('en', 'pt-BR')", name="ck_exercise_translations_locale"),
        CheckConstraint("length(trim(name)) > 0", name="ck_exercise_translations_name"),
        Index("ix_exercise_translations_locale_name", "locale", "name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    exercise_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("exercises.id", ondelete="CASCADE")
    )
    locale: Mapped[str] = mapped_column(String(10))
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    instructions: Mapped[list[str]] = mapped_column(JSON, default=list)

    exercise: Mapped["Exercise"] = relationship(back_populates="translations")


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
    # NO ACTION (e não RESTRICT): bloqueia apagar exercício em uso, mas permite que a
    # exclusão em cascata de um usuário leve junto seus exercícios e seus treinos.
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
    # Snapshots: sem eles, apagar o plano deixaria a sessão sem saber de qual treino foi
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
