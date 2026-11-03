from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, aliased

from src.workouts.models import Exercise, ExerciseTranslation
from src.workouts.schemas import (
    ExerciseDetail,
    ExerciseFilters,
    ExerciseListResponse,
    ExerciseLocale,
    ExerciseSummary,
)


def _visible_to_user(user_id: UUID):
    return or_(Exercise.owner_user_id.is_(None), Exercise.owner_user_id == user_id)


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


def list_exercises(
    session: Session,
    user_id: UUID,
    locale: ExerciseLocale,
    page: int,
    page_size: int,
    query: str | None = None,
    muscle_group: str | None = None,
    equipment: str | None = None,
) -> ExerciseListResponse:
    localized, english, localized_join, english_join = _translation_joins(locale)
    conditions = [_visible_to_user(user_id)]
    if muscle_group:
        conditions.append(Exercise.muscle_group == muscle_group)
    if equipment:
        conditions.append(Exercise.equipment == equipment)
    if query and query.strip():
        pattern = _search_pattern(query)
        conditions.append(
            or_(
                localized.name.ilike(pattern, escape="\\"),
                english.name.ilike(pattern, escape="\\"),
                Exercise.name.ilike(pattern, escape="\\"),
            )
        )

    total = session.scalar(
        select(func.count(Exercise.id))
        .select_from(Exercise)
        .outerjoin(localized, localized_join)
        .outerjoin(english, english_join)
        .where(*conditions)
    ) or 0
    rows = session.execute(
        select(Exercise, localized, english)
        .select_from(Exercise)
        .outerjoin(localized, localized_join)
        .outerjoin(english, english_join)
        .where(*conditions)
        .order_by(
            func.lower(func.coalesce(localized.name, english.name, Exercise.name)),
            Exercise.id,
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    muscle_groups = session.scalars(
        select(Exercise.muscle_group)
        .where(_visible_to_user(user_id))
        .distinct()
        .order_by(Exercise.muscle_group)
    ).all()
    equipment_options = session.scalars(
        select(Exercise.equipment)
        .where(_visible_to_user(user_id), Exercise.equipment.is_not(None))
        .distinct()
        .order_by(Exercise.equipment)
    ).all()
    return ExerciseListResponse(
        items=[
            _summary(exercise, localized_row, english_row)
            for exercise, localized_row, english_row in rows
        ],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=(total + page_size - 1) // page_size,
        filters=ExerciseFilters(
            muscle_groups=list(muscle_groups),
            equipment=list(equipment_options),
        ),
    )


def get_exercise(
    session: Session,
    exercise_id: UUID,
    user_id: UUID,
    locale: ExerciseLocale,
) -> ExerciseDetail | None:
    localized, english, localized_join, english_join = _translation_joins(locale)
    row = session.execute(
        select(Exercise, localized, english)
        .select_from(Exercise)
        .outerjoin(localized, localized_join)
        .outerjoin(english, english_join)
        .where(Exercise.id == exercise_id, _visible_to_user(user_id))
    ).one_or_none()
    if row is None:
        return None
    exercise, localized_row, english_row = row
    return _detail(exercise, localized_row, english_row)
