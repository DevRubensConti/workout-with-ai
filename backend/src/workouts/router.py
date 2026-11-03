from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.auth.dependencies import require_permissions
from src.auth.models import User
from src.database import get_session
from src.workouts.schemas import (
    ExerciseDetail,
    ExerciseListResponse,
    ExerciseLocale,
)
from src.workouts.service import get_exercise, list_exercises

router = APIRouter()


@router.get("", response_model=ExerciseListResponse)
def read_exercises(
    locale: Annotated[ExerciseLocale, Query()] = "pt-BR",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 24,
    query: Annotated[str | None, Query(alias="q", min_length=1, max_length=120)] = None,
    muscle_group: Annotated[str | None, Query(min_length=1, max_length=60)] = None,
    equipment: Annotated[str | None, Query(min_length=1, max_length=80)] = None,
    current_user: User = Depends(require_permissions("workouts:read")),
    session: Session = Depends(get_session),
):
    return list_exercises(
        session=session,
        user_id=current_user.id,
        locale=locale,
        page=page,
        page_size=page_size,
        query=query,
        muscle_group=muscle_group,
        equipment=equipment,
    )


@router.get("/{exercise_id}", response_model=ExerciseDetail)
def read_exercise(
    exercise_id: UUID,
    locale: Annotated[ExerciseLocale, Query()] = "pt-BR",
    current_user: User = Depends(require_permissions("workouts:read")),
    session: Session = Depends(get_session),
):
    exercise = get_exercise(session, exercise_id, current_user.id, locale)
    if exercise is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exercício não encontrado.",
        )
    return exercise
