from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from src.auth.dependencies import require_permissions
from src.auth.models import User
from src.database import get_session
from src.workouts.exercises.schemas import ExerciseLocale
from src.workouts.plans import service as plan_service
from src.workouts.plans.schemas import (
    PlanStatusFilter,
    WorkoutPlanDetail,
    WorkoutPlanIn,
    WorkoutPlanSummary,
)

router = APIRouter()

def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Treino não encontrado.")


def _invalid(error: plan_service.InvalidPlanError) -> HTTPException:
    return HTTPException(status_code=422, detail=str(error))


def _conflict(error: plan_service.PlanConflictError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))


@router.get("", response_model=list[WorkoutPlanSummary])
def list_plans(
    plan_status: Annotated[PlanStatusFilter | None, Query(alias="status")] = None,
    current_user: User = Depends(require_permissions("workouts:read")),
    session: Session = Depends(get_session),
):
    return plan_service.list_plans(session, current_user.id, plan_status)


@router.post("", response_model=WorkoutPlanDetail, status_code=status.HTTP_201_CREATED)
def create_plan(
    body: WorkoutPlanIn,
    locale: Annotated[ExerciseLocale, Query()] = "pt-BR",
    current_user: User = Depends(require_permissions("workouts:write")),
    session: Session = Depends(get_session),
):
    """Cria o treino já como ativo; o treino ativo anterior é arquivado."""
    try:
        plan_id = plan_service.create_plan(session, current_user.id, body)
    except plan_service.InvalidPlanError as error:
        raise _invalid(error)
    except plan_service.PlanConflictError as error:
        raise _conflict(error)
    return plan_service.get_plan_detail(session, current_user.id, plan_id, locale)


@router.get("/{plan_id}", response_model=WorkoutPlanDetail)
def read_plan(
    plan_id: UUID,
    locale: Annotated[ExerciseLocale, Query()] = "pt-BR",
    current_user: User = Depends(require_permissions("workouts:read")),
    session: Session = Depends(get_session),
):
    plan = plan_service.get_plan_detail(session, current_user.id, plan_id, locale)
    if plan is None:
        raise _not_found()
    return plan


@router.put("/{plan_id}", response_model=WorkoutPlanDetail)
def update_plan(
    plan_id: UUID,
    body: WorkoutPlanIn,
    locale: Annotated[ExerciseLocale, Query()] = "pt-BR",
    current_user: User = Depends(require_permissions("workouts:write")),
    session: Session = Depends(get_session),
):
    """Substitui o conteúdo. Dias/exercícios com `id` são atualizados; sem `id`, criados."""
    try:
        found = plan_service.update_plan(session, current_user.id, plan_id, body)
    except plan_service.InvalidPlanError as error:
        raise _invalid(error)
    except plan_service.PlanConflictError as error:
        raise _conflict(error)
    if not found:
        raise _not_found()
    return plan_service.get_plan_detail(session, current_user.id, plan_id, locale)


@router.post("/{plan_id}/activate", response_model=WorkoutPlanDetail)
def activate_plan(
    plan_id: UUID,
    locale: Annotated[ExerciseLocale, Query()] = "pt-BR",
    current_user: User = Depends(require_permissions("workouts:write")),
    session: Session = Depends(get_session),
):
    try:
        found = plan_service.activate_plan(session, current_user.id, plan_id)
    except plan_service.PlanConflictError as error:
        raise _conflict(error)
    if not found:
        raise _not_found()
    return plan_service.get_plan_detail(session, current_user.id, plan_id, locale)


@router.post("/{plan_id}/archive", response_model=WorkoutPlanDetail)
def archive_plan(
    plan_id: UUID,
    locale: Annotated[ExerciseLocale, Query()] = "pt-BR",
    current_user: User = Depends(require_permissions("workouts:write")),
    session: Session = Depends(get_session),
):
    try:
        found = plan_service.archive_plan(session, current_user.id, plan_id)
    except plan_service.PlanConflictError as error:
        raise _conflict(error)
    if not found:
        raise _not_found()
    return plan_service.get_plan_detail(session, current_user.id, plan_id, locale)


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_plan(
    plan_id: UUID,
    current_user: User = Depends(require_permissions("workouts:write")),
    session: Session = Depends(get_session),
):
    """Apaga o treino. O histórico de sessões é mantido (sem vínculo com o plano)."""
    if not plan_service.delete_plan(session, current_user.id, plan_id):
        raise _not_found()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
