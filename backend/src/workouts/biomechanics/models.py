import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.auth.models import utcnow
from src.database import Base


class BiomechanicalScaleVersion(Base):
    """Append-only snapshots of the regional demand assessment criteria."""

    __tablename__ = "biomechanical_scale_versions"
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_biomechanical_scale_version"),
        CheckConstraint("length(trim(change_reason)) > 0", name="ck_biomechanical_scale_reason"),
    )

    version: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    definition: Mapped[dict[str, object]] = mapped_column(JSON)
    change_reason: Mapped[str] = mapped_column(String(1000))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )


class ExerciseBiomechanicalAssessment(Base):
    __tablename__ = "exercise_biomechanical_assessments"
    __table_args__ = (
        UniqueConstraint("id", "exercise_id", name="uq_biomechanical_assessment_exercise"),
        ForeignKeyConstraint(
            ["supersedes_id", "exercise_id"],
            [
                "exercise_biomechanical_assessments.id",
                "exercise_biomechanical_assessments.exercise_id",
            ],
            ondelete="RESTRICT",
            name="fk_biomechanical_assessment_predecessor",
        ),
        CheckConstraint(
            "supersedes_id IS NULL OR supersedes_id != id",
            name="ck_biomechanical_assessment_predecessor",
        ),
        CheckConstraint(
            "assessment_method IN ('manual', 'ai', 'rule')",
            name="ck_biomechanical_assessment_method",
        ),
        CheckConstraint(
            "length(trim(assessment_source)) > 0",
            name="ck_biomechanical_assessment_source",
        ),
        CheckConstraint(
            "length(trim(execution_context)) > 0",
            name="ck_biomechanical_assessment_context",
        ),
        Index("ix_biomechanical_assessment_exercise_created", "exercise_id", "created_at"),
        Index("ix_biomechanical_assessment_scale", "scale_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    exercise_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("exercises.id", ondelete="RESTRICT")
    )
    scale_version: Mapped[int] = mapped_column(
        Integer, ForeignKey("biomechanical_scale_versions.version", ondelete="RESTRICT")
    )
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    assessment_method: Mapped[str] = mapped_column(String(10))
    assessment_source: Mapped[str] = mapped_column(String(500))
    execution_context: Mapped[str] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )

    regions: Mapped[list["ExerciseRegionDemand"]] = relationship(
        back_populates="assessment",
        lazy="selectin",
        passive_deletes=True,
        cascade="all, delete-orphan",
        order_by="ExerciseRegionDemand.region_code",
    )
    review: Mapped["BiomechanicalAssessmentReview | None"] = relationship(
        back_populates="assessment",
        lazy="selectin",
        passive_deletes=True,
    )


class ExerciseRegionDemand(Base):
    __tablename__ = "exercise_region_demands"
    __table_args__ = (
        CheckConstraint(
            "region_code IN ('shoulder', 'lumbar_spine', 'cervical_spine', 'knee', 'elbow')",
            name="ck_exercise_region_demand_region",
        ),
        CheckConstraint(
            "(assessment_status = 'assessed' AND demand_score IS NOT NULL "
            "AND demand_score BETWEEN 0 AND 5 AND demand_role IS NOT NULL "
            "AND demand_role IN ('direct', 'secondary', 'stabilizing')) OR "
            "(assessment_status = 'unassessed' AND demand_score IS NULL AND demand_role IS NULL)",
            name="ck_exercise_region_demand_result",
        ),
    )

    assessment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("exercise_biomechanical_assessments.id", ondelete="CASCADE"),
        primary_key=True,
    )
    region_code: Mapped[str] = mapped_column(String(30), primary_key=True)
    assessment_status: Mapped[str] = mapped_column(String(15))
    demand_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    demand_role: Mapped[str | None] = mapped_column(String(20), nullable=True)
    justification: Mapped[str] = mapped_column(Text)

    assessment: Mapped[ExerciseBiomechanicalAssessment] = relationship(back_populates="regions")


class BiomechanicalAssessmentReview(Base):
    __tablename__ = "biomechanical_assessment_reviews"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('reviewed', 'rejected')", name="ck_biomechanical_review_decision"
        ),
    )

    assessment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("exercise_biomechanical_assessments.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    decision: Mapped[str] = mapped_column(String(15))
    notes: Mapped[str] = mapped_column(Text)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )

    assessment: Mapped[ExerciseBiomechanicalAssessment] = relationship(back_populates="review")
