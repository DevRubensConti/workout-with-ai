from uuid import UUID

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.orm import Session, aliased

from src.workouts.availability import enabled_exercises, visible_exercises
from src.workouts.models import DisabledExercise, Exercise, ExerciseTranslation
from src.workouts.schemas import (
    ExerciseBulkAvailabilityResponse,
    ExerciseDetail,
    ExerciseFilters,
    ExerciseListResponse,
    ExerciseLocale,
    ExerciseQueryFilters,
    ExerciseSummary,
)


def _translation_joins(locale: ExerciseLocale):
    localized = aliased(ExerciseTranslation, name="localized_translation")
    english = aliased(ExerciseTranslation, name="english_translation")
    localized_condition = and_(
        localized.exercise_id == Exercise.id,
        localized.locale == locale,
    )
    english_condition = and_(
        english.exercise_id == Exercise.id,
        english.locale == "en",
    )
    return localized, english, localized_condition, english_condition


def _summary(
    exercise: Exercise,
    localized: ExerciseTranslation | None,
    english: ExerciseTranslation | None,
) -> ExerciseSummary:
    translation = localized or english
    return ExerciseSummary(
        id=exercise.id,
        source_id=exercise.source_id,
        name=translation.name if translation else exercise.name,
        muscle_group=exercise.muscle_group,
        equipment=exercise.equipment,
        level=exercise.level,
        locale=translation.locale if translation else None,
        images=exercise.images or [],
    )


def _detail(
    exercise: Exercise,
    localized: ExerciseTranslation | None,
    english: ExerciseTranslation | None,
) -> ExerciseDetail:
    summary = _summary(exercise, localized, english)
    translation = localized or english
    description = (
        localized.description
        if localized and localized.description is not None
        else english.description
        if english and english.description is not None
        else exercise.description
    )
    return ExerciseDetail(
        **summary.model_dump(),
        description=description,
        force=exercise.force,
        mechanic=exercise.mechanic,
        category=exercise.category,
        primary_muscles=exercise.primary_muscles or [],
        secondary_muscles=exercise.secondary_muscles or [],
        instructions=translation.instructions if translation else [],
    )


def _search_pattern(query: str) -> str:
    escaped = query.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _filtered_catalog(user_id: UUID, filters: ExerciseQueryFilters):
    localized, english, localized_join, english_join = _translation_joins(filters.locale)
    conditions = [visible_exercises(user_id)]
    if filters.enabled_for_ai is not None:
        condition = enabled_exercises(user_id)
        conditions.append(condition if filters.enabled_for_ai else ~condition)
    for column, value in (
        (Exercise.muscle_group, filters.muscle_group),
        (Exercise.equipment, filters.equipment),
        (Exercise.level, filters.level),
        (Exercise.category, filters.category),
        (Exercise.mechanic, filters.mechanic),
        (Exercise.force, filters.force),
    ):
        if value:
            conditions.append(column == value)
    if filters.q and filters.q.strip():
        pattern = _search_pattern(filters.q)
        conditions.append(
            or_(
                localized.name.ilike(pattern, escape="\\"),
                english.name.ilike(pattern, escape="\\"),
                Exercise.name.ilike(pattern, escape="\\"),
            )
        )

    statement = (
        select(Exercise.id)
        .select_from(Exercise)
        .outerjoin(localized, localized_join)
        .outerjoin(english, english_join)
        .where(*conditions)
    )
    return statement, localized, english


def list_exercises(
    session: Session,
    user_id: UUID,
    filters: ExerciseQueryFilters,
    page: int,
    page_size: int,
) -> ExerciseListResponse:
    statement, localized, english = _filtered_catalog(user_id, filters)
    total = session.scalar(select(func.count()).select_from(statement.subquery())) or 0
    rows = session.execute(
        statement.with_only_columns(Exercise, localized, english, enabled_exercises(user_id))
        .order_by(
            func.lower(func.coalesce(localized.name, english.name, Exercise.name)),
            Exercise.id,
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    options = {
        key: list(
            session.scalars(
                select(column)
                .where(visible_exercises(user_id), column.is_not(None), column != "")
                .distinct()
                .order_by(column)
            ).all()
        )
        for key, column in (
            ("muscle_groups", Exercise.muscle_group),
            ("equipment", Exercise.equipment),
            ("levels", Exercise.level),
            ("categories", Exercise.category),
            ("mechanics", Exercise.mechanic),
            ("forces", Exercise.force),
        )
    }
    return ExerciseListResponse(
        items=[
            _summary(exercise, localized_row, english_row).model_copy(
                update={"enabled_for_ai": enabled}
            )
            for exercise, localized_row, english_row, enabled in rows
        ],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=(total + page_size - 1) // page_size,
        filters=ExerciseFilters(**options),
    )


def set_filtered_availability(
    session: Session,
    user_id: UUID,
    filters: ExerciseQueryFilters,
    enabled: bool,
) -> ExerciseBulkAvailabilityResponse:
    statement, _, _ = _filtered_catalog(user_id, filters)
    # A ordem dos locks evita conflitos com outras escolhas em lote ou individuais.
    ids = list(session.scalars(statement.order_by(Exercise.id).with_for_update(of=Exercise)).all())
    disabled_ids = set(
        session.scalars(
            select(DisabledExercise.exercise_id).where(
                DisabledExercise.user_id == user_id,
                DisabledExercise.exercise_id.in_(ids),
            )
        ).all()
    )
    if enabled:
        session.execute(
            delete(DisabledExercise).where(
                DisabledExercise.user_id == user_id,
                DisabledExercise.exercise_id.in_(ids),
            )
        )
        updated = len(disabled_ids)
    else:
        session.add_all(
            DisabledExercise(user_id=user_id, exercise_id=exercise_id)
            for exercise_id in ids
            if exercise_id not in disabled_ids
        )
        updated = len(ids) - len(disabled_ids)
    session.commit()
    return ExerciseBulkAvailabilityResponse(matched=len(ids), updated=updated)


def get_exercise(
    session: Session,
    exercise_id: UUID,
    user_id: UUID,
    locale: ExerciseLocale,
) -> ExerciseDetail | None:
    localized, english, localized_join, english_join = _translation_joins(locale)
    row = session.execute(
        select(Exercise, localized, english, enabled_exercises(user_id))
        .select_from(Exercise)
        .outerjoin(localized, localized_join)
        .outerjoin(english, english_join)
        .where(Exercise.id == exercise_id, visible_exercises(user_id))
    ).one_or_none()
    if row is None:
        return None
    exercise, localized_row, english_row, enabled = row
    return _detail(exercise, localized_row, english_row).model_copy(
        update={"enabled_for_ai": enabled}
    )
