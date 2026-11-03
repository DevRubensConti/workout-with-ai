import importlib.util
from pathlib import Path
from uuid import UUID

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, select

from src.auth.permissions import ROLE_PERMISSIONS
from src.workouts.models import DisabledExercise, Exercise
from tests.test_exercises_api import register, seed_exercises


def test_availability_is_enabled_by_default_private_persistent_and_filterable(
    client, session_factory
):
    user_id = register(client)
    ids = seed_exercises(session_factory, user_id)
    exercise_id = ids["bench_press"]
    path = f"/exercises/{exercise_id}/ai-availability"
    assert all(item["enabled_for_ai"] for item in client.get("/exercises").json()["items"])
    assert client.put(path, json={"enabled": False}).status_code == 204
    assert client.put(path, json={"enabled": False}).status_code == 204
    assert not client.get(f"/exercises/{exercise_id}").json()["enabled_for_ai"]
    disabled = client.get("/exercises", params={"enabled_for_ai": False}).json()
    assert [item["id"] for item in disabled["items"]] == [str(exercise_id)]
    enabled = client.get("/exercises", params={"enabled_for_ai": True, "muscle_group": "chest"})
    assert enabled.json()["total"] == 0
    # Desabilitar nao esconde da consulta geral nem da inclusao manual.
    assert client.get("/exercises").json()["total"] == 3
    with session_factory() as session:
        assert len(session.scalars(select(DisabledExercise)).all()) == 1
        assert session.get(DisabledExercise, (UUID(user_id), exercise_id)) is not None
    client.post("/auth/logout")
    client.post(
        "/auth/register",
        json={
            "name": "Outro",
            "email": "other@example.com",
            "password": "senha-segura-123",
        },
    )
    assert client.get(f"/exercises/{exercise_id}").json()["enabled_for_ai"]
    client.post("/auth/login", json={"email": "ana@example.com", "password": "senha-segura-123"})
    assert not client.get(f"/exercises/{exercise_id}").json()["enabled_for_ai"]
    assert client.put(path, json={"enabled": True}).status_code == 204
    assert client.put(path, json={"enabled": True}).status_code == 204
    assert client.get(f"/exercises/{exercise_id}").json()["enabled_for_ai"]


def test_availability_rejects_other_users_exercises_and_invalid_input(client, session_factory):
    user_id = register(client)
    ids = seed_exercises(session_factory, user_id)
    assert (
        client.put(
            f"/exercises/{ids['other_private']}/ai-availability", json={"enabled": False}
        ).status_code
        == 404
    )
    assert (
        client.put(f"/exercises/{ids['own']}/ai-availability", json={"enabled": False}).status_code
        == 204
    )
    for body in [{"enabled": "false"}, {"enabled": 0}, {}, {"enabled": True, "user_id": user_id}]:
        assert (
            client.put(f"/exercises/{ids['bench_press']}/ai-availability", json=body).status_code
            == 422
        )
    client.post("/auth/logout")
    assert (
        client.put(
            f"/exercises/{ids['bench_press']}/ai-availability", json={"enabled": False}
        ).status_code
        == 401
    )


@pytest.mark.parametrize(
    ("field", "value", "options"),
    [
        ("level", "beginner", "levels"),
        ("category", "strength", "categories"),
        ("mechanic", "compound", "mechanics"),
        ("force", "push", "forces"),
    ],
)
def test_column_filters_and_bulk_update_match_the_same_catalog(
    client, session_factory, field, value, options
):
    user_id = register(client)
    ids = seed_exercises(session_factory, user_id)
    with session_factory() as session, session.begin():
        bench = session.get(Exercise, ids["bench_press"])
        setattr(bench, field, value)
        private = session.get(Exercise, ids["other_private"])
        setattr(private, field, "private-value")

    params = {field: value, "equipment": "barbell", "q": "SUPINO", "locale": "pt-BR"}
    catalog = client.get("/exercises", params=params)
    assert catalog.status_code == 200
    assert catalog.json()["total"] == 1
    assert value in catalog.json()["filters"][options]
    assert "private-value" not in catalog.json()["filters"][options]
    bulk = client.put("/exercises/ai-availability", params=params, json={"enabled": False})
    assert bulk.status_code == 200
    assert bulk.json() == {"matched": 1, "updated": 1}
    assert not client.get(f"/exercises/{ids['bench_press']}").json()["enabled_for_ai"]
    assert client.get(f"/exercises/{ids['squat']}").json()["enabled_for_ai"]
    assert client.get("/exercises", params={field: "no-match"}).json()["total"] == 0


def test_bulk_availability_spans_all_pages_is_personal_and_idempotent(client, session_factory):
    user_id = register(client)
    ids = seed_exercises(session_factory, user_id)
    with session_factory() as session, session.begin():
        session.add_all(
            Exercise(name=f"Extra {index}", muscle_group="chest") for index in range(105)
        )
    first_page = client.get("/exercises", params={"page_size": 24}).json()
    assert len(first_page["items"]) == 24
    assert first_page["total"] == 108
    path = "/exercises/ai-availability"
    assert client.put(path, json={"enabled": False}).json() == {"matched": 108, "updated": 108}
    assert client.put(path, json={"enabled": False}).json() == {"matched": 108, "updated": 0}
    assert client.get("/exercises", params={"enabled_for_ai": False}).json()["total"] == 108
    with session_factory() as session:
        assert session.get(DisabledExercise, (UUID(user_id), ids["own"])) is not None
        assert session.get(DisabledExercise, (UUID(user_id), ids["other_private"])) is None

    filtered = {"enabled_for_ai": False, "muscle_group": "chest"}
    assert client.put(path, params=filtered, json={"enabled": True}).json() == {
        "matched": 106,
        "updated": 106,
    }
    assert client.get("/exercises", params=filtered).json()["total"] == 0
    assert client.get("/exercises", params={"enabled_for_ai": False}).json()["total"] == 2
    assert client.put(path, json={"enabled": True}).json() == {"matched": 108, "updated": 2}
    assert client.put(path, json={"enabled": True}).json() == {"matched": 108, "updated": 0}
    assert client.put(path, json={"enabled": False}).json()["updated"] == 108

    client.post("/auth/logout")
    # A separate authenticated user still has default availability.
    client.post(
        "/auth/register",
        json={"name": "Outro", "email": "bulk@example.com", "password": "senha-segura-123"},
    )
    assert client.get("/exercises", params={"enabled_for_ai": False}).json()["total"] == 0
    assert client.put(path, json={"enabled": True}).json() == {"matched": 107, "updated": 0}
    with session_factory() as session:
        assert (
            len(
                session.scalars(
                    select(DisabledExercise).where(DisabledExercise.user_id == UUID(user_id))
                ).all()
            )
            == 108
        )


def test_bulk_validates_input_authentication_and_empty_matches(
    client, session_factory, monkeypatch
):
    path = "/exercises/ai-availability"
    assert client.put(path, json={"enabled": False}).status_code == 401
    user_id = register(client)
    seed_exercises(session_factory, user_id)
    for body in [{"enabled": "false"}, {"enabled": 0}, {}, {"enabled": True, "user_id": user_id}]:
        assert client.put(path, json=body).status_code == 422
    for params in [{"level": ""}, {"force": "x" * 41}, {"locale": "fr"}]:
        assert client.get("/exercises", params=params).status_code == 422
        assert client.put(path, params=params, json={"enabled": False}).status_code == 422
    assert client.put(path, params={"q": "no matches"}, json={"enabled": False}).json() == {
        "matched": 0,
        "updated": 0,
    }
    assert client.get("/exercises", params={"enabled_for_ai": True}).json()["total"] == 3
    monkeypatch.setitem(ROLE_PERMISSIONS, "user", frozenset({"profile:read", "workouts:read"}))
    assert client.put(path, json={"enabled": False}).status_code == 403
    assert client.get("/exercises", params={"enabled_for_ai": True}).json()["total"] == 3


def test_bulk_search_treats_wildcards_as_literals(client, session_factory):
    user_id = register(client)
    seed_exercises(session_factory, user_id)
    with session_factory() as session, session.begin():
        session.add(Exercise(name="Movement 100%_custom", muscle_group="chest"))
    params = {"q": "%_"}
    assert client.get("/exercises", params=params).json()["total"] == 1
    assert client.put(
        "/exercises/ai-availability", params=params, json={"enabled": False}
    ).json() == {"matched": 1, "updated": 1}
    disabled = client.get("/exercises", params={"enabled_for_ai": False}).json()
    assert [exercise["name"] for exercise in disabled["items"]] == ["Movement 100%_custom"]


def test_availability_migration_preserves_catalog_and_has_cascading_keys(tmp_path, monkeypatch):
    path = Path(__file__).parents[1] / "migrations" / "versions" / "0010_disabled_exercises.py"
    spec = importlib.util.spec_from_file_location("availability_migration", path)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine(f"sqlite:///{tmp_path / 'availability.db'}")
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            connection.exec_driver_sql("CREATE TABLE users (id UUID PRIMARY KEY)")
            connection.exec_driver_sql("CREATE TABLE exercises (id UUID PRIMARY KEY)")
            connection.exec_driver_sql("INSERT INTO users VALUES ('u1')")
            connection.exec_driver_sql("INSERT INTO exercises VALUES ('e1')")
            monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
            migration.upgrade()
            keys = inspect(connection).get_foreign_keys("disabled_exercises")
            assert len(keys) == 2 and all(key["options"]["ondelete"] == "CASCADE" for key in keys)
            connection.exec_driver_sql("INSERT INTO disabled_exercises VALUES ('u1', 'e1')")
            connection.exec_driver_sql("DELETE FROM exercises WHERE id = 'e1'")
            assert (
                connection.exec_driver_sql("SELECT count(*) FROM disabled_exercises").scalar() == 0
            )
            migration.downgrade()
            assert "disabled_exercises" not in inspect(connection).get_table_names()
            assert connection.exec_driver_sql("SELECT id FROM users").scalar() == "u1"
    finally:
        engine.dispose()
