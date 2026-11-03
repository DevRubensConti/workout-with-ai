from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from src.auth.dependencies import require_permissions
from src.auth.models import User
from src.database import get_session
from src.workouts import session_service
from src.workouts.session_schemas import (
    ConsistencyProgress,
    ExerciseProgress,
    SessionDetail,
    SessionFinishIn,
    SessionListResponse,
    SessionSetsIn,
    SessionStartIn,
)

router = APIRouter()


@router.get("/progress/consistency", response_model=ConsistencyProgress)
def read_consistency(
    current_user: User = Depends(require_permissions("workouts:read")),
    session: Session = Depends(get_session),
):
    return session_service.consistency_progress(session, current_user.id)


@router.get("/progress/exercises/{exercise_id}", response_model=ExerciseProgress)
def read_exercise_progress(
    exercise_id: UUID,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 20,
    current_user: User = Depends(require_permissions("workouts:read")),
    session: Session = Depends(get_session),
):
    return session_service.exercise_progress(session, current_user.id, exercise_id, page, page_size)


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Treino não encontrado.")


def _invalid(error: ValueError) -> HTTPException:
    return HTTPException(status_code=422, detail=str(error))


def _conflict(error: RuntimeError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))


@router.get("", response_model=SessionListResponse)
def list_sessions(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 20,
    current_user: User = Depends(require_permissions("workouts:read")),
    session: Session = Depends(get_session),
):
    """Histórico: apenas treinos finalizados, do mais recente para o mais antigo."""
    return session_service.list_sessions(session, current_user.id, page, page_size)


@router.get("/active", response_model=SessionDetail | None)
def read_active_session(
    current_user: User = Depends(require_permissions("workouts:read")),
    session: Session = Depends(get_session),
):
    return session_service.get_open_session_detail(session, current_user.id)


@router.post("", response_model=SessionDetail, status_code=status.HTTP_201_CREATED)
def start_session(
    body: SessionStartIn,
    response: Response,
    current_user: User = Depends(require_permissions("workouts:write")),
    session: Session = Depends(get_session),
):
    """Inicia o treino de um dia. Se este dia já está em andamento, retoma (200)."""
    try:
        started = session_service.start_session(session, current_user.id, body.day_id)
    except session_service.OpenSessionError as error:
        raise _conflict(error)
    except session_service.SessionStateError as error:
        raise _conflict(error)
    if started is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dia não encontrado.")
    workout, created = started
    if not created:
        response.status_code = status.HTTP_200_OK
    return session_service.get_session_detail(session, current_user.id, workout.id)


@router.get("/{session_id}", response_model=SessionDetail)
def read_session(
    session_id: UUID,
    current_user: User = Depends(require_permissions("workouts:read")),
    session: Session = Depends(get_session),
):
    detail = session_service.get_session_detail(session, current_user.id, session_id)
    if detail is None:
        raise _not_found()
    return detail


@router.put("/{session_id}/sets", response_model=SessionDetail)
def replace_sets(
    session_id: UUID,
    body: SessionSetsIn,
    current_user: User = Depends(require_permissions("workouts:write")),
    session: Session = Depends(get_session),
):
    """Salva o estado atual das séries de um treino em andamento (substitui todas)."""
    try:
        found = session_service.replace_sets(session, current_user.id, session_id, body.sets)
    except session_service.InvalidSessionError as error:
        raise _invalid(error)
    except session_service.SessionStateError as error:
        raise _conflict(error)
    if not found:
        raise _not_found()
    return session_service.get_session_detail(session, current_user.id, session_id)


@router.post("/{session_id}/finish", response_model=SessionDetail)
def finish_session(
    session_id: UUID,
    body: SessionFinishIn,
    current_user: User = Depends(require_permissions("workouts:write")),
    session: Session = Depends(get_session),
):
    try:
        found = session_service.finish_session(session, current_user.id, session_id, body)
    except session_service.InvalidSessionError as error:
        raise _invalid(error)
    except session_service.SessionStateError as error:
        raise _conflict(error)
    if not found:
        raise _not_found()
    return session_service.get_session_detail(session, current_user.id, session_id)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: UUID,
    current_user: User = Depends(require_permissions("workouts:write")),
    session: Session = Depends(get_session),
):
    """Cancela um treino em andamento ou apaga um registro do histórico."""
    if not session_service.delete_session(session, current_user.id, session_id):
        raise _not_found()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
