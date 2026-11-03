from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.auth.dependencies import require_permissions
from src.auth.models import User
from src.database import get_session
from src.workouts.generator import service
from src.workouts.generator.ai_service import (
    AiInvalidResponseError,
    AiReviewRequiredError,
    AiUnavailableError,
    generate_ai_plan,
)
from src.workouts.generator.schemas import AiGenerateIn, GeneratedPlan, GenerateIn

router = APIRouter()


@router.post("/generate", response_model=GeneratedPlan)
def generate_workout(
    body: GenerateIn,
    _: User = Depends(require_permissions("workouts:write")),
    session: Session = Depends(get_session),
):
    """Gera um treino-rascunho por regras. Nada é gravado: o usuário revisa e salva."""
    try:
        return service.generate_plan(session, body)
    except service.CatalogUnavailableError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error))
    except service.EmptyPlanError as error:
        raise HTTPException(status_code=422, detail=str(error))


@router.post("/generate-ai", response_model=GeneratedPlan)
def generate_workout_with_ai(
    body: AiGenerateIn,
    current_user: User = Depends(require_permissions("workouts:write")),
    session: Session = Depends(get_session),
):
    """Entrega o plano personalizado para revisão, sem salvar um treino."""
    try:
        return generate_ai_plan(session, current_user, body)
    except (AiUnavailableError, service.CatalogUnavailableError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from None
    except AiInvalidResponseError as error:
        raise HTTPException(status_code=502, detail=str(error)) from None
    except (AiReviewRequiredError, service.EmptyPlanError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
