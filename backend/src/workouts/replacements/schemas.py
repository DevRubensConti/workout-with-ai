from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from src.workouts.exercises.schemas import ExerciseSummary
from src.workouts.plans.schemas import WorkoutPlanDetail, WorkoutPlanIn
from src.workouts.sessions.schemas import SessionDetail


class DraftContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["draft"]
    workout: WorkoutPlanIn
    day_index: int = Field(ge=0)
    exercise_index: int = Field(ge=0)


class PlanContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["plan"]
    plan_id: UUID
    day_id: UUID
    row_id: UUID


class SessionContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["session"]
    session_id: UUID
    exercise_id: UUID


ReplacementContext = Annotated[
    DraftContext | PlanContext | SessionContext, Field(discriminator="mode")
]
SavedContext = Annotated[PlanContext | SessionContext, Field(discriminator="mode")]


class SuggestIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context: ReplacementContext
    ai_consent: Literal[True]


ComparisonText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
]


class AiComparison(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_index: int = Field(strict=True, ge=0, le=2)
    pro: ComparisonText
    con: ComparisonText


class AiComparisons(BaseModel):
    model_config = ConfigDict(extra="forbid")

    comparisons: list[AiComparison] = Field(min_length=1, max_length=3)


class ReplacementOption(BaseModel):
    exercise: ExerciseSummary
    pro: str
    con: str


class SuggestionsOut(BaseModel):
    options: list[ReplacementOption]
    revision: str
    message: str | None = None


class ApplyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context: SavedContext
    replacement_id: UUID
    revision: str = Field(pattern=r"^[a-f0-9]{64}$")


class AppliedOut(BaseModel):
    plan: WorkoutPlanDetail | None = None
    session: SessionDetail | None = None
