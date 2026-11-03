from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class SessionStartIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day_id: UUID


class SetLogIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exercise_id: UUID
    set_number: int = Field(gt=0, le=100)
    reps: int = Field(ge=0, le=1000)
    weight_kg: Decimal | None = Field(
        default=None, ge=0, le=Decimal("9999.99"), max_digits=6, decimal_places=2
    )
    completed: bool = False


class SessionSetsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sets: list[SetLogIn] = Field(max_length=500)


class SessionFinishIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    notes: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None = None
    perceived_effort: int | None = Field(default=None, ge=1, le=10)


class SetLogOut(BaseModel):
    exercise_id: UUID
    set_number: int
    reps: int
    weight_kg: float | None
    completed: bool


class SessionTarget(BaseModel):
    """Prescrição atual do dia (se o dia ainda existir), para exibir a meta."""

    sets: int
    reps_min: int
    reps_max: int | None
    target_weight_kg: float | None
    rest_seconds: int | None
    notes: str | None


class SessionExerciseOut(BaseModel):
    exercise_id: UUID
    name: str
    muscle_group: str | None
    images: list[str]
    target: SessionTarget | None
    sets: list[SetLogOut]


class SessionSummary(BaseModel):
    id: UUID
    plan_id: UUID | None
    plan_name: str | None
    day_id: UUID | None
    day_name: str | None
    started_at: datetime
    finished_at: datetime | None
    notes: str | None
    perceived_effort: int | None
    total_sets: int
    completed_sets: int
    volume_kg: float
    duration_seconds: int | None


class SessionDetail(SessionSummary):
    exercises: list[SessionExerciseOut]


class SessionListResponse(BaseModel):
    items: list[SessionSummary]
    page: int
    page_size: int
    total: int
    total_pages: int


class ExerciseProgressPoint(BaseModel):
    session_id: UUID
    performed_at: datetime
    max_weight_kg: float | None
    volume_kg: float
    sets: list[SetLogOut]


class ExerciseProgress(BaseModel):
    exercise_id: UUID
    personal_record_kg: float | None
    personal_record_at: datetime | None
    completed_sessions: int
    points: list[ExerciseProgressPoint]
    page: int
    total_pages: int


class ConsistencyAchievement(BaseModel):
    sessions_required: int
    label: str
    unlocked: bool


class ConsistencyProgress(BaseModel):
    completed_sessions: int
    achievements: list[ConsistencyAchievement]
