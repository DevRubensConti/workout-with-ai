from typing import Annotated, Literal, get_args
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.workouts.generator.rules import MUSCLE_LABELS
from src.workouts.generator.splits import SplitStyle, styles_for

TrainableMuscle = Literal[
    "chest",
    "lats",
    "middle back",
    "shoulders",
    "quadriceps",
    "hamstrings",
    "glutes",
    "biceps",
    "triceps",
    "calves",
    "abdominals",
]
# Mantido como contexto para futura avaliação por IA, sem filtro determinístico.
AvoidMuscle = Literal[
    "abdominals",
    "abductors",
    "adductors",
    "biceps",
    "calves",
    "chest",
    "forearms",
    "glutes",
    "hamstrings",
    "lats",
    "lower back",
    "middle back",
    "neck",
    "quadriceps",
    "shoulders",
    "traps",
    "triceps",
]


class GenerateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: Literal["hypertrophy", "strength", "fat_loss", "general_health"]
    level: Literal["beginner", "intermediate", "expert"]
    days_per_week: int = Field(ge=2, le=6)
    session_minutes: int = Field(ge=30, le=120)
    # "auto" escolhe pelo número de dias; os demais dependem dos dias (ver splits.SPLITS)
    split_style: SplitStyle = "auto"
    focus_muscles: Annotated[list[TrainableMuscle], Field(max_length=3)] = []
    avoid_muscles: Annotated[
        list[AvoidMuscle],
        Field(
            max_length=6,
            description=(
                "Queixas para futura avaliação por IA. Não excluem nem reduzem a prioridade "
                "de exercícios no gerador por regras."
            ),
        ),
    ] = []

    @model_validator(mode="after")
    def split_style_must_exist_for_days(self):
        if self.split_style != "auto" and self.split_style not in styles_for(self.days_per_week):
            raise ValueError(
                "Esse estilo de divisão não está disponível para "
                f"{self.days_per_week} dias por semana."
            )
        return self


class GeneratedExercise(BaseModel):
    exercise_id: UUID
    name: str
    muscle_group: str
    equipment: str | None
    images: list[str]
    role: Literal["compound", "isolation"]
    sets: int
    reps_min: int
    reps_max: int
    rest_seconds: int


class GeneratedDay(BaseModel):
    name: str
    notes: str
    estimated_minutes: int
    exercises: list[GeneratedExercise]


class WeeklyVolumeOut(BaseModel):
    muscle: str
    label: str
    sets: int
    target: int


class ReferenceOut(BaseModel):
    id: str
    text: str


class GeneratedPlan(BaseModel):
    name: str
    description: str
    goal: str
    level: str
    split: str
    days: list[GeneratedDay]
    weekly_volume: list[WeeklyVolumeOut]
    rationale: list[str]
    warnings: list[str]
    references: list[ReferenceOut]
    rules_version: str
    review_status: str


assert set(MUSCLE_LABELS) == set(get_args(TrainableMuscle))
