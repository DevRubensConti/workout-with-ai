from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.auth.router import router as auth_router
from src.config import get_settings
from src.logging import setup_logging
from src.workouts.biomechanics.router import assessment_router
from src.workouts.biomechanics.router import router as biomechanical_router
from src.workouts.exercises.router import router as exercises_router
from src.workouts.generator.router import router as generator_router
from src.workouts.plans.router import router as plans_router
from src.workouts.replacements.router import router as replacements_router
from src.workouts.sessions.router import router as sessions_router

setup_logging()

settings = get_settings()

is_production = settings.ENVIRONMENT == "production"

app = FastAPI(
    title=settings.APP_NAME,
    # Sem Swagger/ReDoc públicos em produção
    docs_url=None if is_production else "/docs",
    redoc_url=None if is_production else "/redoc",
    openapi_url=None if is_production else "/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    max_age=3600,
)

app.include_router(auth_router, prefix="/auth", tags=["Autenticação"])
app.include_router(exercises_router, prefix="/exercises", tags=["Exercícios"])
app.include_router(
    biomechanical_router, prefix="/biomechanical-scales", tags=["Demanda biomecânica"]
)
app.include_router(
    assessment_router, prefix="/biomechanical-assessments", tags=["Avaliações biomecânicas"]
)
app.include_router(generator_router, prefix="/workouts", tags=["Treinos"])
app.include_router(replacements_router, prefix="/workouts/replacements", tags=["Treinos"])
app.include_router(plans_router, prefix="/workouts", tags=["Treinos"])
app.include_router(sessions_router, prefix="/sessions", tags=["Histórico de treinos"])


@app.get("/health", tags=["Infra"])
def health():
    return {"status": "ok"}
