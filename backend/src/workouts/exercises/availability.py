from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from src.workouts.exercises.models import DisabledExercise, Exercise


def visible_exercises(user_id: UUID):
    return or_(Exercise.owner_user_id.is_(None), Exercise.owner_user_id == user_id)


def enabled_exercises(user_id: UUID):
    return (
        ~select(DisabledExercise.exercise_id)
        .where(
            DisabledExercise.user_id == user_id,
            DisabledExercise.exercise_id == Exercise.id,
        )
        .exists()
    )


def set_availability(session: Session, user_id: UUID, exercise_id: UUID, enabled: bool) -> bool:
    exercise = session.scalar(
        select(Exercise.id)
        .where(Exercise.id == exercise_id, visible_exercises(user_id))
        .with_for_update()
    )
    if exercise is None:
        return False
    record = session.get(DisabledExercise, (user_id, exercise_id))
    if enabled and record is not None:
        session.delete(record)
    elif not enabled and record is None:
        session.add(DisabledExercise(user_id=user_id, exercise_id=exercise_id))
    session.commit()
    return True
