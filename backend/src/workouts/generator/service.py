from sqlalchemy import select
from sqlalchemy.orm import Session

from src.workouts.exercises.models import Exercise
from src.workouts.generator import rules
from src.workouts.generator.engine import (
    ExerciseInfo,
    GenerationInput,
    GenerationResult,
    generate,
)
from src.workouts.generator.schemas import (
    GeneratedDay,
    GeneratedExercise,
    GeneratedPlan,
    GenerateIn,
    ReferenceOut,
    WeeklyVolumeOut,
)
from src.workouts.generator.staples import all_source_ids
from src.workouts.plans.service import localized_name

CATALOG_SOURCE = "free-exercise-db"
NAME_LOCALE = "pt-BR"


class EmptyPlanError(ValueError):
    """Nenhum exercício pôde ser escolhido com as opções informadas."""


class CatalogUnavailableError(RuntimeError):
    """O catálogo de exercícios não está carregado no banco."""


def load_catalog(db: Session) -> dict[str, ExerciseInfo]:
    """Carrega só os exercícios-base curados (globais), com nomes em português."""
    rows = db.scalars(
        select(Exercise).where(
            Exercise.source == CATALOG_SOURCE,
            Exercise.owner_user_id.is_(None),
            Exercise.source_id.in_(all_source_ids()),
        )
    ).all()
    return {
        row.source_id: ExerciseInfo(
            id=row.id,
            source_id=row.source_id,
            name=localized_name(row, NAME_LOCALE),
            muscle_group=row.muscle_group,
            equipment=row.equipment,
            level=row.level or "beginner",
            images=tuple(row.images or ()),
        )
        for row in rows
        if row.source_id
    }


def generate_plan(db: Session, data: GenerateIn) -> GeneratedPlan:
    catalog = load_catalog(db)
    if not catalog:
        raise CatalogUnavailableError("O catálogo de exercícios ainda não foi carregado.")

    result = generate(
        GenerationInput(
            goal=data.goal,
            level=data.level,
            days_per_week=data.days_per_week,
            session_minutes=data.session_minutes,
            focus_muscles=tuple(data.focus_muscles),
            avoid_muscles=tuple(data.avoid_muscles),
            split_style=data.split_style,
        ),
        catalog,
    )
    if not result.name:
        raise EmptyPlanError(
            "Não foi possível montar um treino com essas opções e os exercícios disponíveis."
        )
    return _to_schema(result, data)


def _to_schema(result: GenerationResult, data: GenerateIn) -> GeneratedPlan:
    return GeneratedPlan(
        name=result.name,
        description=result.description,
        goal=rules.GOALS[data.goal].label,
        level=data.level,
        split=result.split_name,
        days=[
            GeneratedDay(
                name=day.name,
                notes=f"{rules.WARMUP_NOTE} Duração estimada: cerca de {day.minutes} min.",
                estimated_minutes=day.minutes,
                exercises=[
                    GeneratedExercise(
                        exercise_id=e.info.id,
                        name=e.info.name,
                        muscle_group=e.info.muscle_group,
                        equipment=e.info.equipment,
                        images=list(e.info.images),
                        role=e.role,  # type: ignore[arg-type]
                        sets=e.sets,
                        reps_min=e.reps_min,
                        reps_max=e.reps_max,
                        rest_seconds=e.rest_seconds,
                    )
                    for e in day.exercises
                ],
            )
            for day in result.days
        ],
        weekly_volume=[
            WeeklyVolumeOut(
                muscle=entry.muscle,
                label=rules.MUSCLE_LABELS[entry.muscle],
                sets=entry.achieved,
                target=entry.target,
            )
            for entry in result.weekly
        ],
        rationale=result.rationale,
        warnings=result.warnings,
        references=[
            ReferenceOut(id=ref, text=rules.REFERENCES[ref]) for ref in result.reference_ids
        ],
        rules_version=rules.RULES_VERSION,
        review_status=rules.REVIEW_STATUS,
    )
