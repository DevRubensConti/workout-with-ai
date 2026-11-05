from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from src.auth.dependencies import require_permissions
from src.auth.models import User
from src.database import get_session
from src.workouts.biomechanics import service
from src.workouts.biomechanics.models import BiomechanicalScaleVersion
from src.workouts.biomechanics.schemas import (
    AssessmentCorrectionIn,
    AssessmentDetail,
    AssessmentList,
    AssessmentReviewIn,
    ReviewStatus,
    ScaleCreate,
    ScaleHistory,
    ScaleVersion,
)

router = APIRouter()
assessment_router = APIRouter()


@assessment_router.post(
    "/{assessment_id}/corrections", response_model=AssessmentDetail, status_code=201
)
def correct_assessment(
    assessment_id: UUID,
    body: AssessmentCorrectionIn,
    user: User = Depends(require_permissions("exercises:manage")),
    session: Session = Depends(get_session),
):
    try:
        return service.correct_assessment(session, assessment_id, body, user.id)
    except service.AssessmentNotFoundError as error:
        raise HTTPException(404, str(error)) from error
    except service.ScaleConflictError as error:
        raise HTTPException(409, str(error)) from error
    except service.InvalidAssessmentError as error:
        raise HTTPException(422, str(error)) from error
    except service.ScaleUnavailableError as error:
        raise HTTPException(503, str(error)) from error


@assessment_router.get("", response_model=AssessmentList)
def read_assessments(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    q: Annotated[str | None, Query(min_length=1, max_length=160)] = None,
    review_status: ReviewStatus | None = None,
    exercise_id: UUID | None = None,
    category: Annotated[str | None, Query(min_length=1, max_length=50)] = None,
    muscle_group: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    user: User = Depends(require_permissions("exercises:manage")),
    session: Session = Depends(get_session),
):
    try:
        return service.list_assessments(
            session, page, page_size, q, review_status, exercise_id, category, muscle_group
        )
    except service.ScaleUnavailableError as error:
        raise HTTPException(503, str(error)) from error


@assessment_router.get("/{assessment_id}", response_model=AssessmentDetail)
def read_assessment(
    assessment_id: UUID,
    user: User = Depends(require_permissions("exercises:manage")),
    session: Session = Depends(get_session),
):
    try:
        return service.assessment_detail(session, assessment_id)
    except service.AssessmentNotFoundError as error:
        raise HTTPException(404, str(error)) from error
    except service.ScaleUnavailableError as error:
        raise HTTPException(503, str(error)) from error


@assessment_router.post("/{assessment_id}/review", response_model=AssessmentDetail)
def submit_assessment_review(
    assessment_id: UUID,
    body: AssessmentReviewIn,
    user: User = Depends(require_permissions("exercises:manage")),
    session: Session = Depends(get_session),
):
    try:
        return service.review_assessment(session, assessment_id, body, user.id)
    except service.AssessmentNotFoundError as error:
        raise HTTPException(404, str(error)) from error
    except service.ScaleConflictError as error:
        raise HTTPException(409, str(error)) from error
    except service.InvalidAssessmentError as error:
        raise HTTPException(422, str(error)) from error
    except service.ScaleUnavailableError as error:
        raise HTTPException(503, str(error)) from error


@router.get("/current", response_model=ScaleVersion)
def read_current(
    user: User = Depends(require_permissions("workouts:read")),
    session: Session = Depends(get_session),
):
    try:
        return service.current_version(session)
    except service.ScaleUnavailableError as error:
        raise HTTPException(503, str(error)) from error


@router.get("", response_model=ScaleHistory)
def read_history(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    user: User = Depends(require_permissions("exercises:manage")),
    session: Session = Depends(get_session),
):
    return service.list_versions(session, page, page_size)


@router.get("/{version}", response_model=ScaleVersion)
def read_version(
    version: Annotated[int, Path(ge=1)],
    user: User = Depends(require_permissions("exercises:manage")),
    session: Session = Depends(get_session),
):
    scale = session.get(BiomechanicalScaleVersion, version)
    if scale is None:
        raise HTTPException(404, "Versão da escala não encontrada.")
    return scale


@router.post("", response_model=ScaleVersion, status_code=201)
def create_version(
    body: ScaleCreate,
    user: User = Depends(require_permissions("exercises:manage")),
    session: Session = Depends(get_session),
):
    try:
        return service.create_version(session, body, user.id)
    except service.ScaleUnavailableError as error:
        raise HTTPException(503, str(error)) from error
    except service.ScaleConflictError as error:
        raise HTTPException(409, str(error)) from error
    except service.UnchangedScaleError as error:
        raise HTTPException(422, str(error)) from error
