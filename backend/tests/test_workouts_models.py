from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from src.auth.models import User
from src.auth.permissions import ROLE_ADMIN, ROLE_USER, permissions_for_role
from src.workouts.exercises.models import (
    Exercise,
    ExerciseMuscleEffect,
    MuscleTarget,
)
from src.workouts.plans.models import (
    WorkoutDay,
    WorkoutDayExercise,
    WorkoutPlan,
)
from src.workouts.sessions.models import WorkoutSession, WorkoutSetLog


@pytest.fixture()
def db(session_factory):
    with session_factory() as session:
        yield session


def make_user(db, email="ana@example.com"):
    user = User(name="Ana", email=email, password_hash="hash")
    db.add(user)
    db.commit()
    return user


def make_exercise(db, name="Supino reto", owner=None):
    exercise = Exercise(name=name, muscle_group="peito", owner_user_id=owner.id if owner else None)
    db.add(exercise)
    db.commit()
    return exercise


def make_plan(db, user, name="Plano", **kwargs):
    plan = WorkoutPlan(user_id=user.id, name=name, **kwargs)
    db.add(plan)
    db.commit()
    return plan


def make_day(db, plan, position=0, name="Treino A"):
    day = WorkoutDay(plan_id=plan.id, name=name, position=position)
    db.add(day)
    db.commit()
    return day


def make_day_exercise(db, day, exercise, position=0, **kwargs):
    values = {"sets": 3, "reps_min": 8, **kwargs}
    item = WorkoutDayExercise(day_id=day.id, exercise_id=exercise.id, position=position, **values)
    db.add(item)
    db.commit()
    return item


def make_session(db, user, plan=None, day=None, **kwargs):
    session = WorkoutSession(
        user_id=user.id,
        plan_id=plan.id if plan else None,
        day_id=day.id if day else None,
        plan_name=plan.name if plan else None,
        day_name=day.name if day else None,
        **kwargs,
    )
    db.add(session)
    db.commit()
    return session


def make_set_log(db, session, exercise, set_number=1, **kwargs):
    values = {"reps": 10, "weight_kg": Decimal("40"), **kwargs}
    log = WorkoutSetLog(
        session_id=session.id,
        exercise_id=exercise.id,
        exercise_name=exercise.name,
        set_number=set_number,
        **values,
    )
    db.add(log)
    db.commit()
    return log


def count(db, model):
    return db.scalar(select(func.count()).select_from(model))


def test_plan_with_days_and_exercises_is_read_back_in_order(db, session_factory):
    user = make_user(db)
    supino = make_exercise(db, "Supino reto")
    agachamento = make_exercise(db, "Agachamento")
    remada = make_exercise(db, "Remada curvada")

    plan = make_plan(db, user, name="ABC", goal="hipertrofia", source="ai", ai_metadata={"m": 1})
    # Inseridos fora de ordem de propósito
    day_b = make_day(db, plan, position=1, name="Treino B")
    day_a = make_day(db, plan, position=0, name="Treino A")
    make_day_exercise(db, day_a, remada, position=1, reps_max=12, target_weight_kg=Decimal("30.5"))
    make_day_exercise(db, day_a, supino, position=0, rest_seconds=90, tempo="2-0-1-0")
    make_day_exercise(db, day_b, agachamento, position=0)

    with session_factory() as fresh:
        loaded = fresh.scalar(select(WorkoutPlan).where(WorkoutPlan.id == plan.id))
        assert loaded.status == "active"
        assert loaded.source == "ai"
        assert loaded.ai_metadata == {"m": 1}
        assert [d.name for d in loaded.days] == ["Treino A", "Treino B"]
        first = loaded.days[0].exercises
        assert [e.exercise.name for e in first] == ["Supino reto", "Remada curvada"]
        assert first[0].rest_seconds == 90
        assert first[1].reps_max == 12
        assert first[1].target_weight_kg == Decimal("30.50")


def test_exercise_muscle_effects_store_hierarchical_targets_and_shares(db, session_factory):
    exercise = make_exercise(db)
    chest = MuscleTarget(code="chest", name_pt="Peito", kind="group")
    pectoralis = MuscleTarget(
        code="pectoralis_major",
        name_pt="Peitoral Maior",
        kind="muscle",
        parent=chest,
    )
    clavicular = MuscleTarget(
        code="pectoralis_major_clavicular",
        name_pt="Peitoral Maior - Porção Superior (Clavicular)",
        kind="region",
        parent=pectoralis,
    )
    triceps = MuscleTarget(code="triceps", name_pt="Tríceps", kind="muscle")
    db.add_all(
        [
            chest,
            pectoralis,
            clavicular,
            triceps,
            ExerciseMuscleEffect(
                exercise=exercise,
                muscle_target=clavicular,
                role="primary",
                relative_share_pct=Decimal("70.00"),
            ),
            ExerciseMuscleEffect(
                exercise=exercise,
                muscle_target=triceps,
                role="auxiliary",
                relative_share_pct=Decimal("30.00"),
            ),
        ]
    )
    db.commit()

    with session_factory() as fresh:
        loaded = fresh.scalar(select(Exercise).where(Exercise.id == exercise.id))
        loaded_effects = {
            effect.muscle_target.code: effect.relative_share_pct
            for effect in loaded.muscle_effects
        }
        assert loaded_effects == {
            "pectoralis_major_clavicular": Decimal("70.00"),
            "triceps": Decimal("30.00"),
        }
        chest_effect = next(
            effect for effect in loaded.muscle_effects
            if effect.muscle_target.code == "pectoralis_major_clavicular"
        )
        assert chest_effect.muscle_target.parent.parent.code == "chest"


def test_exercise_muscle_effects_reject_invalid_role_and_share(db):
    exercise = make_exercise(db)
    target = MuscleTarget(code="chest", name_pt="Peito", kind="group")
    db.add(target)
    db.commit()

    db.add(
        ExerciseMuscleEffect(
            exercise=exercise,
            muscle_target=target,
            role="tertiary",
            relative_share_pct=Decimal("101.00"),
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()


def test_plan_defaults(db):
    plan = make_plan(db, make_user(db))
    assert plan.status == "active"
    assert plan.source == "manual"
    assert plan.ai_metadata is None
    assert plan.started_at is not None and plan.created_at is not None


def test_only_one_active_plan_per_user(db):
    user = make_user(db)
    first = make_plan(db, user, name="Primeiro")

    with pytest.raises(IntegrityError):
        make_plan(db, user, name="Segundo")
    db.rollback()

    first.status = "archived"
    db.commit()
    second = make_plan(db, user, name="Segundo")
    assert second.status == "active"

    # Vários arquivados são permitidos
    second.status = "archived"
    db.commit()
    make_plan(db, user, name="Terceiro")
    assert count(db, WorkoutPlan) == 3


def test_two_users_can_each_have_an_active_plan(db):
    make_plan(db, make_user(db, "a@example.com"))
    make_plan(db, make_user(db, "b@example.com"))
    assert count(db, WorkoutPlan) == 2


def test_duplicate_positions_are_rejected(db):
    user = make_user(db)
    plan = make_plan(db, user)
    day = make_day(db, plan, position=0)
    exercise = make_exercise(db)
    make_day_exercise(db, day, exercise, position=0)

    with pytest.raises(IntegrityError):
        make_day(db, plan, position=0, name="Outro")
    db.rollback()
    with pytest.raises(IntegrityError):
        make_day_exercise(db, day, exercise, position=0)


def test_deleting_plan_removes_days_and_day_exercises_but_not_catalog(db):
    user = make_user(db)
    exercise = make_exercise(db)
    plan = make_plan(db, user)
    day = make_day(db, plan)
    make_day_exercise(db, day, exercise)

    db.delete(plan)
    db.commit()

    assert count(db, WorkoutPlan) == 0
    assert count(db, WorkoutDay) == 0
    assert count(db, WorkoutDayExercise) == 0
    assert count(db, Exercise) == 1


def test_deleting_user_removes_everything_of_theirs(db):
    ana = make_user(db, "ana@example.com")
    bia = make_user(db, "bia@example.com")
    global_ex = make_exercise(db, "Supino reto")
    custom_ex = make_exercise(db, "Meu exercício", owner=ana)

    plan = make_plan(db, ana)
    day = make_day(db, plan)
    make_day_exercise(db, day, global_ex, position=0)
    make_day_exercise(db, day, custom_ex, position=1)
    session = make_session(db, ana, plan, day)
    make_set_log(db, session, custom_ex)

    bia_plan = make_plan(db, bia)
    make_day(db, bia_plan)

    db.delete(ana)
    db.commit()

    assert count(db, User) == 1
    assert count(db, WorkoutPlan) == 1
    assert count(db, WorkoutDay) == 1
    assert count(db, WorkoutDayExercise) == 0
    assert count(db, WorkoutSession) == 0
    assert count(db, WorkoutSetLog) == 0
    # Só o exercício personalizado do usuário some; o global permanece
    assert [e.name for e in db.scalars(select(Exercise))] == ["Supino reto"]


def test_deleting_exercise_used_in_a_plan_is_blocked(db):
    user = make_user(db)
    exercise = make_exercise(db)
    day = make_day(db, make_plan(db, user))
    make_day_exercise(db, day, exercise)

    db.delete(exercise)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    assert count(db, Exercise) == 1


def test_deleting_exercise_used_in_history_is_blocked(db):
    user = make_user(db)
    exercise = make_exercise(db)
    make_set_log(db, make_session(db, user), exercise)

    db.delete(exercise)
    with pytest.raises(IntegrityError):
        db.commit()


def test_unused_exercise_can_be_deleted(db):
    exercise = make_exercise(db)
    db.delete(exercise)
    db.commit()
    assert count(db, Exercise) == 0


@pytest.mark.parametrize(
    "overrides",
    [
        {"sets": 0},
        {"sets": -1},
        {"reps_min": -1},
        {"reps_min": 10, "reps_max": 8},
        {"target_weight_kg": Decimal("-1")},
        {"rest_seconds": -1},
        {"position": -1},
    ],
)
def test_day_exercise_rejects_invalid_values(db, overrides):
    day = make_day(db, make_plan(db, make_user(db)))
    with pytest.raises(IntegrityError):
        make_day_exercise(db, day, make_exercise(db), **overrides)


def test_day_exercise_accepts_boundary_values(db):
    day = make_day(db, make_plan(db, make_user(db)))
    item = make_day_exercise(
        db,
        day,
        make_exercise(db),
        sets=1,
        reps_min=0,
        reps_max=0,
        target_weight_kg=Decimal("0"),
        rest_seconds=0,
    )
    assert item.sets == 1


@pytest.mark.parametrize("overrides", [{"status": "paused"}, {"source": "robot"}])
def test_plan_rejects_invalid_enum_values(db, overrides):
    with pytest.raises(IntegrityError):
        make_plan(db, make_user(db), **overrides)


def test_day_rejects_negative_position(db):
    plan = make_plan(db, make_user(db))
    with pytest.raises(IntegrityError):
        make_day(db, plan, position=-1)


@pytest.mark.parametrize("effort", [0, 11, -3])
def test_session_rejects_invalid_perceived_effort(db, effort):
    with pytest.raises(IntegrityError):
        make_session(db, make_user(db), perceived_effort=effort)


@pytest.mark.parametrize("effort", [None, 1, 10])
def test_session_accepts_valid_perceived_effort(db, effort):
    assert make_session(db, make_user(db), perceived_effort=effort).id


@pytest.mark.parametrize(
    "overrides",
    [{"set_number": 0}, {"reps": -1}, {"weight_kg": Decimal("-0.5")}],
)
def test_set_log_rejects_invalid_values(db, overrides):
    session = make_session(db, make_user(db))
    with pytest.raises(IntegrityError):
        make_set_log(db, session, make_exercise(db), **overrides)


def test_set_log_accepts_zero_reps_and_no_weight(db):
    session = make_session(db, make_user(db))
    log = make_set_log(db, session, make_exercise(db), reps=0, weight_kg=None, completed=False)
    assert log.completed is False


def test_session_with_set_logs_survives_plan_deletion(db):
    user = make_user(db)
    exercise = make_exercise(db)
    plan = make_plan(db, user, name="Meu plano")
    day = make_day(db, plan, name="Treino A")
    make_day_exercise(db, day, exercise)

    session = make_session(db, user, plan, day, perceived_effort=7)
    make_set_log(db, session, exercise, set_number=1, reps=10, weight_kg=Decimal("60"))
    make_set_log(db, session, exercise, set_number=2, reps=8, weight_kg=Decimal("62.5"))

    db.delete(plan)
    db.commit()
    db.expire_all()

    kept = db.scalar(select(WorkoutSession))
    assert kept.plan_id is None
    assert kept.day_id is None
    # Os snapshots preservam de qual treino foi a sessão
    assert kept.plan_name == "Meu plano"
    assert kept.day_name == "Treino A"
    assert [(s.set_number, s.reps, s.weight_kg) for s in kept.set_logs] == [
        (1, 10, Decimal("60.00")),
        (2, 8, Decimal("62.50")),
    ]
    assert kept.set_logs[0].exercise_name == "Supino reto"


def test_deleting_session_removes_its_set_logs(db):
    session = make_session(db, make_user(db))
    make_set_log(db, session, make_exercise(db))

    db.delete(session)
    db.commit()
    assert count(db, WorkoutSetLog) == 0


def test_workout_permissions_by_role():
    user_perms = permissions_for_role(ROLE_USER)
    admin_perms = permissions_for_role(ROLE_ADMIN)

    assert {"workouts:read", "workouts:write"} <= set(user_perms)
    assert "exercises:manage" not in user_perms
    assert {"workouts:read", "workouts:write", "exercises:manage"} <= set(admin_perms)
