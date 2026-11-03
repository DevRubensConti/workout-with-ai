from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

PlanStatusFilter = Literal["active", "archived"]
PlanLevel = Literal["beginner", "intermediate", "expert"]
PlanSource = Literal["manual", "ai"]
MAX_AI_METADATA_CHARS = 20_000

Text = Annotated[str, StringConstraints(strip_whitespace=True)]


class WorkoutExerciseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID | None = None
    exercise_id: UUID
    sets: int = Field(gt=0, le=50)
    reps_min: int = Field(ge=0, le=1000)
    reps_max: int | None = Field(default=None, ge=0, le=1000)
    target_weight_kg: Decimal | None = Field(
        default=None, ge=0, le=Decimal("9999.99"), max_digits=6, decimal_places=2
    )
    rest_seconds: int | None = Field(default=None, ge=0, le=3600)
    tempo: Annotated[str, StringConstraints(strip_whitespace=True, max_length=20)] | None = None
    notes: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] | None = None

    @model_validator(mode="after")
    def reps_range_is_ordered(self):
        if self.reps_max is not None and self.reps_max < self.reps_min:
            raise ValueError("reps_max deve ser maior ou igual a reps_min.")
        return self


class WorkoutDayIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID | None = None
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    notes: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] | None = None
    exercises: list[WorkoutExerciseIn] = Field(default_factory=list, max_length=40)


class WorkoutPlanIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
    description: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None
    ) = None
    goal: Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)] | None = None
    level: PlanLevel | None = None
    # Origem do treino. Para "ai", `ai_metadata` guarda como foi gerado (regras, entradas).
    source: PlanSource = "manual"
    ai_metadata: dict[str, Any] | None = None
    days: list[WorkoutDayIn] = Field(min_length=1, max_length=14)

    @model_validator(mode="after")
    def metadata_only_for_generated_plans(self):
        if self.ai_metadata is None:
            return self
        if self.source != "ai":
            raise ValueError("ai_metadata só é aceito quando source é 'ai'.")
        if len(str(self.ai_metadata)) > MAX_AI_METADATA_CHARS:
            raise ValueError("ai_metadata é grande demais.")
        return self


class WorkoutExerciseOut(BaseModel):
    id: UUID
    exercise_id: UUID
    exercise_name: str
    muscle_group: str
    equipment: str | None
    images: list[str]
    position: int
    sets: int
    reps_min: int
    reps_max: int | None
    target_weight_kg: float | None
    rest_seconds: int | None
    tempo: str | None
    notes: str | None


class WorkoutDayOut(BaseModel):
    id: UUID
    name: str
    position: int
    notes: str | None
    exercises: list[WorkoutExerciseOut]


class WorkoutPlanSummary(BaseModel):
    id: UUID
    name: str
    description: str | None
    goal: str | None
    level: str | None
    source: str
    status: str
    started_at: datetime
    archived_at: datetime | None
    day_count: int
    exercise_count: int


class WorkoutPlanDetail(WorkoutPlanSummary):
    ai_metadata: dict[str, Any] | None = None
    days: list[WorkoutDayOut]
