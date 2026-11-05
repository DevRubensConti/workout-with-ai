import uuid
from decimal import Decimal

from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.workouts.common import TimestampMixin


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
