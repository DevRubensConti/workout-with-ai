from typing import Literal
from uuid import UUID

from pydantic import BaseModel

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


class ExerciseListResponse(BaseModel):
    items: list[ExerciseSummary]
    page: int
    page_size: int
    total: int
    total_pages: int
    filters: ExerciseFilters
