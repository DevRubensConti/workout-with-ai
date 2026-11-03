from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool

ExerciseLocale = Literal["en", "pt-BR"]


class ExerciseSummary(BaseModel):
    id: UUID
    source_id: str | None
    name: str
    muscle_group: str
    equipment: str | None
    level: str | None
    locale: ExerciseLocale | None
    images: list[str]
    enabled_for_ai: bool = True


class ExerciseDetail(ExerciseSummary):
    description: str | None
    force: str | None
    mechanic: str | None
    category: str | None
    primary_muscles: list[str]
    secondary_muscles: list[str]
    instructions: list[str]


class ExerciseFilters(BaseModel):
    muscle_groups: list[str]
    equipment: list[str]
    levels: list[str]
    categories: list[str]
    mechanics: list[str]
    forces: list[str]


class ExerciseQueryFilters(BaseModel):
    locale: ExerciseLocale = "pt-BR"
    q: str | None = Field(default=None, min_length=1, max_length=120)
    muscle_group: str | None = Field(default=None, min_length=1, max_length=60)
    equipment: str | None = Field(default=None, min_length=1, max_length=80)
    level: str | None = Field(default=None, min_length=1, max_length=40)
    category: str | None = Field(default=None, min_length=1, max_length=60)
    mechanic: str | None = Field(default=None, min_length=1, max_length=40)
    force: str | None = Field(default=None, min_length=1, max_length=40)
    enabled_for_ai: bool | None = None


class ExerciseListResponse(BaseModel):
    items: list[ExerciseSummary]
    page: int
    page_size: int
    total: int
    total_pages: int
    filters: ExerciseFilters


class ExerciseAvailabilityIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: StrictBool


class ExerciseBulkAvailabilityResponse(BaseModel):
    matched: int
    updated: int
