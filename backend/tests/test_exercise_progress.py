import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select

from src.main import app
from src.workouts.sessions.models import WorkoutSession, WorkoutSetLog
from tests.test_workout_sessions_api import exercises, register  # noqa: F401


def seed_history(session_factory, user_id, exercise_id):
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with session_factory() as db, db.begin():
        for index, values in enumerate(
            [
                [(20, 10, True), (30, 8, True), (999, 10, False)],
                [(40, 5, True), (500, 0, True)],
                [(40, 6, True)],
                [(None, 10, True)],
                [(0, 10, True)],
            ]
        ):
            db.add(
                WorkoutSession(
                    user_id=user_id,
                    started_at=base + timedelta(days=index),
                    finished_at=base + timedelta(days=index, minutes=30),
                    set_logs=[
                        WorkoutSetLog(
                            exercise_id=exercise_id,
                            exercise_name="Supino",
                            set_number=number,
                            weight_kg=weight,
                            reps=reps,
                            completed=completed,
                        )
                        for number, (weight, reps, completed) in enumerate(values, 1)
                    ],
                )
            )
        db.add(
            WorkoutSession(
                user_id=user_id,
                started_at=base + timedelta(days=10),
                set_logs=[
                    WorkoutSetLog(
                        exercise_id=exercise_id,
                        exercise_name="Supino",
                        set_number=1,
                        weight_kg=900,
                        reps=10,
                        completed=True,
                    )
                ],
            )
        )


def test_progress_dates_records_pagination_and_exclusions(client, session_factory, exercises):  # noqa: F811
    register(client)
    user_id = UUID(client.get("/auth/me").json()["id"])
    seed_history(session_factory, user_id, UUID(exercises["bench"]))
    path = f"/sessions/progress/exercises/{exercises['bench']}"
    response = client.get(path, params={"page_size": 2})
    assert response.status_code == 200
    data = response.json()
    assert data["personal_record_kg"] == 40
    assert data["personal_record_at"].startswith("2026-01-02")
    assert data["completed_sessions"] == 5
    assert data["total_pages"] == 3
    assert [point["max_weight_kg"] for point in data["points"]] == [0, None]
    assert data["points"][0]["performed_at"].startswith("2026-01-05")
    older = client.get(path, params={"page": 3, "page_size": 2}).json()
    assert older["points"][0]["max_weight_kg"] == 30
    assert older["points"][0]["volume_kg"] == 440
    assert [item["weight_kg"] for item in older["points"][0]["sets"]] == [20, 30]
    assert client.get(path, params={"page": 99}).json()["points"] == []
    assert client.get(path, params={"page_size": 51}).status_code == 422
    assert (
        client.get(f"/sessions/progress/exercises/{exercises['row']}").json()["completed_sessions"]
        == 0
    )

    consistency = client.get("/sessions/progress/consistency").json()
    assert consistency["completed_sessions"] == 5
    assert [
        item["sessions_required"] for item in consistency["achievements"] if item["unlocked"]
    ] == [1, 5]
    with session_factory() as db:
        record_session = db.scalar(
            select(WorkoutSession).where(
                WorkoutSession.user_id == user_id, WorkoutSession.started_at == datetime(2026, 1, 3)
            )
        )
    assert client.delete(f"/sessions/{record_session.id}").status_code == 204
    assert client.get("/sessions/progress/consistency").json()["completed_sessions"] == 4
    assert client.get(path).json()["personal_record_kg"] == 40
    with TestClient(app) as other:
        register(other, "other-progress@example.com")
        private = other.get(path).json()
        assert private["completed_sessions"] == 0 and private["personal_record_kg"] is None
        assert private["points"] == []
        assert other.get("/sessions/progress/consistency").json()["completed_sessions"] == 0


def test_progress_endpoints_require_login(client):
    assert client.get("/sessions/progress/consistency").status_code == 401
    assert (
        client.get("/sessions/progress/exercises/00000000-0000-0000-0000-000000000001").status_code
        == 401
    )


def test_rest_preference_default_persistence_isolation_and_strict_input(client):
    assert client.get("/auth/workout-preferences").status_code == 401
    register(client)
    path = "/auth/workout-preferences"
    assert client.get(path).json() == {"rest_timer_enabled": False}
    assert client.put(path, json={"rest_timer_enabled": True}).json() == {
        "rest_timer_enabled": True
    }
    assert client.get(path).json()["rest_timer_enabled"]
    for body in [
        {"rest_timer_enabled": "true"},
        {"rest_timer_enabled": 1},
        {},
        {"rest_timer_enabled": False, "user_id": "other"},
    ]:
        assert client.put(path, json=body).status_code == 422
    with TestClient(app) as other:
        register(other, "preferences@example.com")
        assert other.get(path).json() == {"rest_timer_enabled": False}
    assert client.get(path).json()["rest_timer_enabled"]
    assert client.put(path, json={"rest_timer_enabled": False}).status_code == 200


def test_rest_preference_migration_preserves_existing_users(tmp_path, monkeypatch):
    path = Path(__file__).parents[1] / "migrations" / "versions" / "0011_rest_timer_preference.py"
    spec = importlib.util.spec_from_file_location("rest_preference_migration", path)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine(f"sqlite:///{tmp_path / 'preferences.db'}")
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE TABLE users(id INTEGER PRIMARY KEY, name TEXT)")
            connection.exec_driver_sql("INSERT INTO users VALUES(1, 'Example')")
            monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
            migration.upgrade()
            assert connection.exec_driver_sql("SELECT rest_timer_enabled FROM users").scalar() == 0
            connection.exec_driver_sql("UPDATE users SET rest_timer_enabled=1")
            migration.downgrade()
            assert connection.exec_driver_sql("SELECT name FROM users").scalar() == "Example"
    finally:
        engine.dispose()
