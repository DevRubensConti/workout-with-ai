from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.auth.dependencies import require_permissions
from src.auth.models import User
from src.database import get_session
from src.workouts.exercises.availability import set_availability
from src.workouts.exercises.schemas import (
    ExerciseAvailabilityIn,
    ExerciseBulkAvailabilityResponse,
    ExerciseDetail,
    ExerciseListResponse,
    ExerciseLocale,
    ExerciseQueryFilters,
)
from src.workouts.exercises.service import get_exercise, list_exercises, set_filtered_availability

router = APIRouter()


@router.get("", response_model=ExerciseListResponse)
def read_exercises(
    filters: Annotated[ExerciseQueryFilters, Depends()],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 24,
    current_user: User = Depends(require_permissions("workouts:read")),
    session: Session = Depends(get_session),
):
    return list_exercises(
        session=session,
        user_id=current_user.id,
        filters=filters,
        page=page,
        page_size=page_size,
    )


@router.put("/ai-availability", response_model=ExerciseBulkAvailabilityResponse)
def update_filtered_ai_availability(
    body: ExerciseAvailabilityIn,
    filters: Annotated[ExerciseQueryFilters, Depends()],
    current_user: User = Depends(require_permissions("workouts:write")),
    session: Session = Depends(get_session),
):
    return set_filtered_availability(session, current_user.id, filters, body.enabled)


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


@router.put("/{exercise_id}/ai-availability", status_code=status.HTTP_204_NO_CONTENT)
def update_ai_availability(
    exercise_id: UUID,
    body: ExerciseAvailabilityIn,
    current_user: User = Depends(require_permissions("workouts:write")),
    session: Session = Depends(get_session),
):
    if not set_availability(session, current_user.id, exercise_id, body.enabled):
        raise HTTPException(status_code=404, detail="Exercício não encontrado.")
