"""Casos de uso dos planos de treino. Toda consulta é filtrada pelo dono (user_id)."""

from collections.abc import Callable
from typing import Any
from uuid import UUID

from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, lazyload

from src.auth.models import utcnow
from src.workouts.models import (
    Exercise,
    PlanStatus,
    WorkoutDay,
    WorkoutDayExercise,
    WorkoutPlan,
)
from src.workouts.plan_schemas import (
    PlanStatusFilter,
    WorkoutDayIn,
    WorkoutDayOut,
    WorkoutExerciseIn,
    WorkoutExerciseOut,
    WorkoutPlanDetail,
    WorkoutPlanIn,
    WorkoutPlanSummary,
)
from src.workouts.schemas import ExerciseLocale

# Posições são únicas por (plano, dia) e (dia, posição). Para reordenar sem violar a
# restrição no meio da atualização, as linhas mantidas vão primeiro para esta faixa.
POSITION_STAGE = 10_000


class InvalidPlanError(ValueError):
    """Conteúdo do treino inválido (exercício inexistente, id de outro treino...)."""


class PlanConflictError(RuntimeError):
    """Conflito de concorrência ao gravar (ex.: dois planos ativos ao mesmo tempo)."""


def _load_exercises(session: Session, user_id: UUID, data: WorkoutPlanIn) -> dict[UUID, Exercise]:
    ids = {item.exercise_id for day in data.days for item in day.exercises}
    if not ids:
        return {}
    found = session.scalars(
        select(Exercise).where(
            Exercise.id.in_(ids),
            or_(Exercise.owner_user_id.is_(None), Exercise.owner_user_id == user_id),
        )
    ).all()
    exercises = {exercise.id: exercise for exercise in found}
    if ids - exercises.keys():
        raise InvalidPlanError("Um ou mais exercícios não existem ou não estão disponíveis.")
    return exercises


def _owned_plan(session: Session, user_id: UUID, plan_id: UUID) -> WorkoutPlan | None:
    # populate_existing garante dias/exercícios atualizados após uma gravação.
    return session.scalar(
        select(WorkoutPlan)
        .where(WorkoutPlan.id == plan_id, WorkoutPlan.user_id == user_id)
        .execution_options(populate_existing=True)
    )


def _archive_active(session: Session, user_id: UUID) -> None:
    now = utcnow()
    active = session.scalars(
        select(WorkoutPlan)
        .options(lazyload(WorkoutPlan.days))
        .where(WorkoutPlan.user_id == user_id, WorkoutPlan.status == PlanStatus.ACTIVE.value)
    ).all()
    for plan in active:
        plan.status = PlanStatus.ARCHIVED.value
        plan.archived_at = now
    # O índice único parcial exige o arquivamento antes de ativar outro plano.
    session.flush()


def _commit(session: Session) -> None:
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise PlanConflictError("Não foi possível salvar o treino. Tente novamente.") from error


def _apply_exercise(
    row: WorkoutDayExercise,
    item: WorkoutExerciseIn,
    position: int,
    exercises: dict[UUID, Exercise],
) -> None:
    row.exercise = exercises[item.exercise_id]
    row.position = position
    row.sets = item.sets
    row.reps_min = item.reps_min
    row.reps_max = item.reps_max
    row.target_weight_kg = item.target_weight_kg
    row.rest_seconds = item.rest_seconds
    row.tempo = item.tempo or None
    row.notes = item.notes or None


def _build_exercise(
    item: WorkoutExerciseIn, position: int, exercises: dict[UUID, Exercise]
) -> WorkoutDayExercise:
    row = WorkoutDayExercise()
    _apply_exercise(row, item, position, exercises)
    return row


def _build_day(item: WorkoutDayIn, position: int, exercises: dict[UUID, Exercise]) -> WorkoutDay:
    return WorkoutDay(
        name=item.name,
        position=position,
        notes=item.notes or None,
        exercises=[
            _build_exercise(entry, index, exercises) for index, entry in enumerate(item.exercises)
        ],
    )


def _sync_collection(
    session: Session,
    collection: list[Any],
    payload: list[Any],
    create: Callable[[Any, int], Any],
    update: Callable[[Any, Any, int], None],
    label: str,
) -> None:
    """Reconcilia por id: atualiza o que veio, cria o que é novo e remove o que sumiu."""
    existing = {row.id: row for row in collection}
    requested: set[UUID] = set()
    for item in payload:
        if item.id is None:
            continue
        if item.id not in existing or item.id in requested:
            raise InvalidPlanError(f"{label} inválido para este treino.")
        requested.add(item.id)

    for row in [row for row in collection if row.id not in requested]:
        collection.remove(row)
    session.flush()

    for offset, row in enumerate(collection):
        row.position = POSITION_STAGE + offset
    session.flush()

    for position, item in enumerate(payload):
        if item.id is None:
            collection.append(create(item, position))
        else:
            update(existing[item.id], item, position)
    session.flush()


def create_plan(session: Session, user_id: UUID, data: WorkoutPlanIn) -> UUID:
    exercises = _load_exercises(session, user_id, data)
    _archive_active(session, user_id)
    plan = WorkoutPlan(
        user_id=user_id,
        name=data.name,
        description=data.description or None,
        goal=data.goal or None,
        level=data.level,
        source=data.source,
        ai_metadata=data.ai_metadata,
        status=PlanStatus.ACTIVE.value,
        started_at=utcnow(),
        days=[_build_day(day, index, exercises) for index, day in enumerate(data.days)],
    )
    session.add(plan)
    _commit(session)
    return plan.id


def update_plan(
    session: Session, user_id: UUID, plan_id: UUID, data: WorkoutPlanIn
) -> bool:
    plan = _owned_plan(session, user_id, plan_id)
    if plan is None:
        return False
    exercises = _load_exercises(session, user_id, data)

    plan.name = data.name
    plan.description = data.description or None
    plan.goal = data.goal or None
    plan.level = data.level

    def update_day(row: WorkoutDay, item: WorkoutDayIn, position: int) -> None:
        row.name = item.name
        row.notes = item.notes or None
        row.position = position
        _sync_collection(
            session,
            row.exercises,
            item.exercises,
            create=lambda entry, index: _build_exercise(entry, index, exercises),
            update=lambda target, entry, index: _apply_exercise(
                target, entry, index, exercises
            ),
            label="Exercício do treino",
        )

    try:
        _sync_collection(
            session,
            plan.days,
            data.days,
            create=lambda item, index: _build_day(item, index, exercises),
            update=update_day,
            label="Dia do treino",
        )
    except InvalidPlanError:
        session.rollback()
        raise
    _commit(session)
    return True


def activate_plan(session: Session, user_id: UUID, plan_id: UUID) -> bool:
    plan = _owned_plan(session, user_id, plan_id)
    if plan is None:
        return False
    if plan.status != PlanStatus.ACTIVE.value:
        _archive_active(session, user_id)
        plan.status = PlanStatus.ACTIVE.value
        plan.archived_at = None
        plan.started_at = utcnow()
        _commit(session)
    return True


def archive_plan(session: Session, user_id: UUID, plan_id: UUID) -> bool:
    plan = _owned_plan(session, user_id, plan_id)
    if plan is None:
        return False
    if plan.status != PlanStatus.ARCHIVED.value:
        plan.status = PlanStatus.ARCHIVED.value
        plan.archived_at = utcnow()
        _commit(session)
    return True


def delete_plan(session: Session, user_id: UUID, plan_id: UUID) -> bool:
    plan = _owned_plan(session, user_id, plan_id)
    if plan is None:
        return False
    session.delete(plan)
    session.commit()
    return True


def list_plans(
    session: Session, user_id: UUID, status: PlanStatusFilter | None = None
) -> list[WorkoutPlanSummary]:
    day_count = (
        select(func.count(WorkoutDay.id))
        .where(WorkoutDay.plan_id == WorkoutPlan.id)
        .scalar_subquery()
    )
    exercise_count = (
        select(func.count(WorkoutDayExercise.id))
        .join(WorkoutDay, WorkoutDay.id == WorkoutDayExercise.day_id)
        .where(WorkoutDay.plan_id == WorkoutPlan.id)
        .scalar_subquery()
    )
    query = (
        select(WorkoutPlan, day_count, exercise_count)
        .options(lazyload(WorkoutPlan.days))
        .where(WorkoutPlan.user_id == user_id)
        .order_by(
            case((WorkoutPlan.status == PlanStatus.ACTIVE.value, 0), else_=1),
            WorkoutPlan.started_at.desc(),
        )
    )
    if status:
        query = query.where(WorkoutPlan.status == status)
    return [
        _summary(plan, days, exercises) for plan, days, exercises in session.execute(query).all()
    ]


def get_plan_detail(
    session: Session, user_id: UUID, plan_id: UUID, locale: ExerciseLocale
) -> WorkoutPlanDetail | None:
    plan = _owned_plan(session, user_id, plan_id)
    if plan is None:
        return None
    days = sorted(plan.days, key=lambda day: day.position)
    summary = _summary(plan, len(days), sum(len(day.exercises) for day in days))
    return WorkoutPlanDetail(
        **summary.model_dump(),
        ai_metadata=plan.ai_metadata,
        days=[
            WorkoutDayOut(
                id=day.id,
                name=day.name,
                position=day.position,
                notes=day.notes,
                exercises=[
                    _exercise_out(row, locale)
                    for row in sorted(day.exercises, key=lambda row: row.position)
                ],
            )
            for day in days
        ],
    )


def _summary(plan: WorkoutPlan, day_count: int, exercise_count: int) -> WorkoutPlanSummary:
    return WorkoutPlanSummary(
        id=plan.id,
        name=plan.name,
        description=plan.description,
        goal=plan.goal,
        level=plan.level,
        source=plan.source,
        status=plan.status,
        started_at=plan.started_at,
        archived_at=plan.archived_at,
        day_count=day_count,
        exercise_count=exercise_count,
    )


def localized_name(exercise: Exercise, locale: ExerciseLocale) -> str:
    by_locale = {item.locale: item.name for item in exercise.translations}
    return by_locale.get(locale) or by_locale.get("en") or exercise.name


def _exercise_out(row: WorkoutDayExercise, locale: ExerciseLocale) -> WorkoutExerciseOut:
    exercise = row.exercise
    return WorkoutExerciseOut(
        id=row.id,
        exercise_id=row.exercise_id,
        exercise_name=localized_name(exercise, locale),
        muscle_group=exercise.muscle_group,
        equipment=exercise.equipment,
        images=exercise.images or [],
        position=row.position,
        sets=row.sets,
        reps_min=row.reps_min,
        reps_max=row.reps_max,
        target_weight_kg=float(row.target_weight_kg) if row.target_weight_kg is not None else None,
        rest_seconds=row.rest_seconds,
        tempo=row.tempo,
        notes=row.notes,
    )
