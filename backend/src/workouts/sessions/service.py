"""Registro de treinos realizados: sessões e séries executadas."""

from datetime import timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.auth.models import utcnow
from src.workouts.exercises.models import Exercise
from src.workouts.plans.models import (
    WorkoutDay,
    WorkoutDayExercise,
    WorkoutPlan,
)
from src.workouts.plans.service import localized_name
from src.workouts.sessions.models import WorkoutSession, WorkoutSetLog
from src.workouts.sessions.schemas import (
    ConsistencyAchievement,
    ConsistencyProgress,
    ExerciseProgress,
    ExerciseProgressPoint,
    SessionDetail,
    SessionExerciseOut,
    SessionFinishIn,
    SessionListResponse,
    SessionSummary,
    SessionTarget,
    SetLogIn,
    SetLogOut,
)

SNAPSHOT_LOCALE = "pt-BR"
PREVIOUS_LOOKUP_LIMIT = 2000


def exercise_progress(
    db: Session, user_id: UUID, exercise_id: UUID, page: int, page_size: int
) -> ExerciseProgress:
    conditions = (
        WorkoutSession.user_id == user_id,
        WorkoutSession.finished_at.is_not(None),
        WorkoutSetLog.exercise_id == exercise_id,
        WorkoutSetLog.completed.is_(True),
        WorkoutSetLog.reps > 0,
    )
    grouped = (
        select(
            WorkoutSession.id.label("session_id"),
            WorkoutSession.started_at.label("performed_at"),
            func.max(WorkoutSetLog.weight_kg).label("max_weight"),
        )
        .join(WorkoutSetLog, WorkoutSetLog.session_id == WorkoutSession.id)
        .where(*conditions)
        .group_by(WorkoutSession.id, WorkoutSession.started_at)
    )
    total = db.scalar(select(func.count()).select_from(grouped.subquery())) or 0
    record = db.execute(
        grouped.having(func.max(WorkoutSetLog.weight_kg).is_not(None))
        .order_by(
            func.max(WorkoutSetLog.weight_kg).desc(), WorkoutSession.started_at, WorkoutSession.id
        )
        .limit(1)
    ).first()
    entries = db.execute(
        grouped.order_by(WorkoutSession.started_at.desc(), WorkoutSession.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    logs_by_session: dict[UUID, list[SetLogOut]] = {entry.session_id: [] for entry in entries}
    if entries:
        logs = db.scalars(
            select(WorkoutSetLog)
            .join(WorkoutSession, WorkoutSetLog.session_id == WorkoutSession.id)
            .where(*conditions, WorkoutSession.id.in_(logs_by_session))
            .order_by(WorkoutSetLog.set_number)
        ).all()
        for log in logs:
            logs_by_session[log.session_id].append(
                SetLogOut(
                    exercise_id=exercise_id,
                    set_number=log.set_number,
                    reps=log.reps,
                    weight_kg=float(log.weight_kg) if log.weight_kg is not None else None,
                    completed=True,
                )
            )
    return ExerciseProgress(
        exercise_id=exercise_id,
        personal_record_kg=float(record.max_weight) if record else None,
        personal_record_at=record.performed_at if record else None,
        completed_sessions=total,
        page=page,
        total_pages=(total + page_size - 1) // page_size,
        points=[
            ExerciseProgressPoint(
                session_id=entry.session_id,
                performed_at=entry.performed_at,
                max_weight_kg=float(entry.max_weight) if entry.max_weight is not None else None,
                volume_kg=sum(
                    (item.weight_kg or 0) * item.reps for item in logs_by_session[entry.session_id]
                ),
                sets=logs_by_session[entry.session_id],
            )
            for entry in entries
        ],
    )


def consistency_progress(db: Session, user_id: UUID) -> ConsistencyProgress:
    completed = (
        select(WorkoutSetLog.id)
        .where(
            WorkoutSetLog.session_id == WorkoutSession.id,
            WorkoutSetLog.completed.is_(True),
            WorkoutSetLog.reps > 0,
        )
        .exists()
    )
    total = (
        db.scalar(
            select(func.count(WorkoutSession.id)).where(
                WorkoutSession.user_id == user_id,
                WorkoutSession.finished_at.is_not(None),
                completed,
            )
        )
        or 0
    )
    milestones = [
        (1, "Primeiro passo"),
        (5, "Criando rotina"),
        (10, "Consistência"),
        (25, "Dedicação"),
        (50, "Hábito consolidado"),
        (100, "Jornada de 100 treinos"),
    ]
    return ConsistencyProgress(
        completed_sessions=total,
        achievements=[
            ConsistencyAchievement(sessions_required=count, label=label, unlocked=total >= count)
            for count, label in milestones
        ],
    )


class InvalidSessionError(ValueError):
    """Conteúdo inválido (exercício inexistente, série duplicada, nada concluído...)."""


class SessionStateError(RuntimeError):
    """A operação não vale para o estado atual (ex.: treino já finalizado)."""


class OpenSessionError(RuntimeError):
    """Já existe outro treino em andamento."""


def _owned(db: Session, user_id: UUID, session_id: UUID) -> WorkoutSession | None:
    return db.scalar(
        select(WorkoutSession)
        .where(WorkoutSession.id == session_id, WorkoutSession.user_id == user_id)
        .execution_options(populate_existing=True)
    )


def _open_session(db: Session, user_id: UUID) -> WorkoutSession | None:
    return db.scalar(
        select(WorkoutSession)
        .where(WorkoutSession.user_id == user_id, WorkoutSession.finished_at.is_(None))
        .order_by(WorkoutSession.started_at.desc())
        .limit(1)
        .execution_options(populate_existing=True)
    )


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise SessionStateError("Não foi possível salvar o treino. Tente novamente.") from error


def _previous_weights(
    db: Session, user_id: UUID, exercise_ids: set[UUID]
) -> dict[tuple[UUID, int], Decimal]:
    """Última carga usada em cada série (por exercício e número), para pré-preencher."""
    if not exercise_ids:
        return {}
    rows = db.execute(
        select(WorkoutSetLog.exercise_id, WorkoutSetLog.set_number, WorkoutSetLog.weight_kg)
        .join(WorkoutSession, WorkoutSession.id == WorkoutSetLog.session_id)
        .where(
            WorkoutSession.user_id == user_id,
            WorkoutSession.finished_at.is_not(None),
            WorkoutSetLog.completed.is_(True),
            WorkoutSetLog.weight_kg.is_not(None),
            WorkoutSetLog.exercise_id.in_(exercise_ids),
        )
        .order_by(WorkoutSession.started_at.desc())
        .limit(PREVIOUS_LOOKUP_LIMIT)
    ).all()
    latest: dict[tuple[UUID, int], Decimal] = {}
    for exercise_id, set_number, weight in rows:
        latest.setdefault((exercise_id, set_number), weight)
    return latest


def start_session(db: Session, user_id: UUID, day_id: UUID) -> tuple[WorkoutSession, bool] | None:
    """Inicia (ou retoma) o treino de um dia. Retorna (sessão, criada_agora)."""
    day = db.scalar(
        select(WorkoutDay)
        .join(WorkoutPlan, WorkoutPlan.id == WorkoutDay.plan_id)
        .where(WorkoutDay.id == day_id, WorkoutPlan.user_id == user_id)
        .execution_options(populate_existing=True)
    )
    if day is None:
        return None

    existing = _open_session(db, user_id)
    if existing is not None:
        if existing.day_id == day.id:
            return existing, False
        raise OpenSessionError(
            "Você já tem um treino em andamento. Finalize ou cancele antes de iniciar outro."
        )

    rows = sorted(day.exercises, key=lambda row: row.position)
    previous = _previous_weights(db, user_id, {row.exercise_id for row in rows})
    base = utcnow()
    logs: list[WorkoutSetLog] = []
    for row in rows:
        name = localized_name(row.exercise, SNAPSHOT_LOCALE)
        for number in range(1, row.sets + 1):
            weight = previous.get((row.exercise_id, number), row.target_weight_kg)
            logs.append(
                WorkoutSetLog(
                    exercise_id=row.exercise_id,
                    exercise_name=name,
                    set_number=number,
                    reps=row.reps_min,
                    weight_kg=weight,
                    completed=False,
                    # created_at distinto preserva a ordem de exibição dos exercícios
                    created_at=base + timedelta(microseconds=len(logs)),
                )
            )
    workout = WorkoutSession(
        user_id=user_id,
        plan_id=day.plan_id,
        day_id=day.id,
        plan_name=day.plan.name,
        day_name=day.name,
        started_at=base,
        set_logs=logs,
    )
    db.add(workout)
    _commit(db)
    return workout, True


def replace_sets(db: Session, user_id: UUID, session_id: UUID, sets: list[SetLogIn]) -> bool:
    workout = _owned(db, user_id, session_id)
    if workout is None:
        return False
    if workout.finished_at is not None:
        raise SessionStateError("Este treino já foi finalizado.")

    keys = [(item.exercise_id, item.set_number) for item in sets]
    if len(keys) != len(set(keys)):
        raise InvalidSessionError("Há séries repetidas para o mesmo exercício.")
    ids = {item.exercise_id for item in sets}
    exercises = {}
    if ids:
        found = db.scalars(
            select(Exercise).where(
                Exercise.id.in_(ids),
                or_(Exercise.owner_user_id.is_(None), Exercise.owner_user_id == user_id),
            )
        ).all()
        exercises = {exercise.id: exercise for exercise in found}
        if ids - exercises.keys():
            raise InvalidSessionError("Um ou mais exercícios não existem ou não estão disponíveis.")

    names = {key: localized_name(value, SNAPSHOT_LOCALE) for key, value in exercises.items()}
    base = utcnow()
    workout.set_logs.clear()
    db.flush()
    for index, item in enumerate(sets):
        workout.set_logs.append(
            WorkoutSetLog(
                exercise_id=item.exercise_id,
                exercise_name=names[item.exercise_id],
                set_number=item.set_number,
                reps=item.reps,
                weight_kg=item.weight_kg,
                completed=item.completed,
                created_at=base + timedelta(microseconds=index),
            )
        )
    _commit(db)
    return True


def finish_session(db: Session, user_id: UUID, session_id: UUID, data: SessionFinishIn) -> bool:
    workout = _owned(db, user_id, session_id)
    if workout is None:
        return False
    if workout.finished_at is not None:
        raise SessionStateError("Este treino já foi finalizado.")
    if not any(log.completed for log in workout.set_logs):
        raise InvalidSessionError("Conclua ao menos uma série antes de finalizar.")

    # Séries não realizadas não fazem parte do histórico.
    for log in [log for log in workout.set_logs if not log.completed]:
        workout.set_logs.remove(log)
    workout.finished_at = utcnow()
    workout.notes = data.notes or None
    workout.perceived_effort = data.perceived_effort
    _commit(db)
    return True


def delete_session(db: Session, user_id: UUID, session_id: UUID) -> bool:
    workout = _owned(db, user_id, session_id)
    if workout is None:
        return False
    db.delete(workout)
    db.commit()
    return True


def _summary(workout: WorkoutSession) -> SessionSummary:
    logs = workout.set_logs
    completed = [log for log in logs if log.completed]
    volume = sum(
        (Decimal(log.reps) * log.weight_kg for log in completed if log.weight_kg is not None),
        Decimal(0),
    )
    duration = None
    if workout.finished_at is not None:
        duration = max(0, int((workout.finished_at - workout.started_at).total_seconds()))
    return SessionSummary(
        id=workout.id,
        plan_id=workout.plan_id,
        plan_name=workout.plan_name,
        day_id=workout.day_id,
        day_name=workout.day_name,
        started_at=workout.started_at,
        finished_at=workout.finished_at,
        notes=workout.notes,
        perceived_effort=workout.perceived_effort,
        total_sets=len(logs),
        completed_sets=len(completed),
        volume_kg=float(volume),
        duration_seconds=duration,
    )


def _target(row: WorkoutDayExercise) -> SessionTarget:
    return SessionTarget(
        sets=row.sets,
        reps_min=row.reps_min,
        reps_max=row.reps_max,
        target_weight_kg=float(row.target_weight_kg) if row.target_weight_kg is not None else None,
        rest_seconds=row.rest_seconds,
        notes=row.notes,
    )


def _exercise_out(
    exercise_id: UUID,
    logs: list[WorkoutSetLog],
    exercises: dict[UUID, Exercise],
    targets: dict[UUID, WorkoutDayExercise],
) -> SessionExerciseOut:
    catalog = exercises.get(exercise_id)
    target = targets.get(exercise_id)
    return SessionExerciseOut(
        exercise_id=exercise_id,
        name=logs[0].exercise_name,
        muscle_group=catalog.muscle_group if catalog else None,
        images=(catalog.images or []) if catalog else [],
        target=_target(target) if target else None,
        sets=[
            SetLogOut(
                exercise_id=log.exercise_id,
                set_number=log.set_number,
                reps=log.reps,
                weight_kg=float(log.weight_kg) if log.weight_kg is not None else None,
                completed=log.completed,
            )
            for log in logs
        ],
    )


def _detail(db: Session, workout: WorkoutSession) -> SessionDetail:
    groups: dict[UUID, list[WorkoutSetLog]] = {}
    for log in workout.set_logs:
        groups.setdefault(log.exercise_id, []).append(log)

    exercises = {}
    if groups:
        exercises = {
            exercise.id: exercise
            for exercise in db.scalars(select(Exercise).where(Exercise.id.in_(groups.keys())))
        }
    targets: dict[UUID, WorkoutDayExercise] = {}
    if workout.day_id is not None:
        for row in db.scalars(
            select(WorkoutDayExercise)
            .where(WorkoutDayExercise.day_id == workout.day_id)
            .order_by(WorkoutDayExercise.position)
        ):
            targets.setdefault(row.exercise_id, row)

    return SessionDetail(
        **_summary(workout).model_dump(),
        exercises=[
            _exercise_out(exercise_id, logs, exercises, targets)
            for exercise_id, logs in groups.items()
        ],
    )


def get_session_detail(db: Session, user_id: UUID, session_id: UUID) -> SessionDetail | None:
    workout = _owned(db, user_id, session_id)
    return _detail(db, workout) if workout else None


def get_open_session_detail(db: Session, user_id: UUID) -> SessionDetail | None:
    workout = _open_session(db, user_id)
    return _detail(db, workout) if workout else None


def list_sessions(db: Session, user_id: UUID, page: int, page_size: int) -> SessionListResponse:
    finished = (WorkoutSession.user_id == user_id, WorkoutSession.finished_at.is_not(None))
    total = db.scalar(select(func.count(WorkoutSession.id)).where(*finished)) or 0
    rows = db.scalars(
        select(WorkoutSession)
        .where(*finished)
        .order_by(WorkoutSession.started_at.desc(), WorkoutSession.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return SessionListResponse(
        items=[_summary(workout) for workout in rows],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=(total + page_size - 1) // page_size,
    )
