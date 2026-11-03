from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.auth.dependencies import require_permissions
from src.auth.models import User
from src.database import get_session
from src.workouts.generator import service
from src.workouts.generator.schemas import GeneratedPlan, GenerateIn

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
