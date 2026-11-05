from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.auth.dependencies import require_permissions
from src.auth.models import User
from src.database import get_session
from src.workouts.generator.ai_service import AiInvalidResponseError, AiUnavailableError
from src.workouts.replacements import service
from src.workouts.replacements.schemas import AppliedOut, ApplyIn, SuggestIn, SuggestionsOut

router = APIRouter()


@router.post("/suggest", response_model=SuggestionsOut)
def suggest_replacements(
    body: SuggestIn,
    user: User = Depends(require_permissions("workouts:write")),
    db: Session = Depends(get_session),
):
    try:
        return service.suggest(db, user.id, body.context)
    except service.ReplacementError as error:
        raise HTTPException(error.status_code, str(error)) from None
    except AiUnavailableError as error:
        raise HTTPException(503, str(error)) from None
    except AiInvalidResponseError as error:
        raise HTTPException(502, str(error)) from None


@router.post("/apply", response_model=AppliedOut)
def apply_replacement(
    body: ApplyIn,
    user: User = Depends(require_permissions("workouts:write")),
    db: Session = Depends(get_session),
):
    try:
        return service.apply(db, user.id, body)
    except service.ReplacementError as error:
        raise HTTPException(error.status_code, str(error)) from None
