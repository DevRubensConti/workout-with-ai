import importlib.util
import io
import json
import re
from copy import deepcopy
from pathlib import Path
from uuid import UUID

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, select

from src.auth.models import User
from src.workouts.biomechanics.models import BiomechanicalScaleVersion
from src.workouts.biomechanics.schemas import ScaleDefinition


@pytest.fixture()
def migration():
    path = Path(__file__).parents[1] / "migrations" / "versions" / "0012_biomechanical_scales.py"
    spec = importlib.util.spec_from_file_location("biomechanical_migration", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def initial(session_factory, migration):
    with session_factory() as session, session.begin():
        session.add(
            BiomechanicalScaleVersion(
                version=1,
                definition=deepcopy(migration.INITIAL_DEFINITION),
                change_reason="Inicialização",
            )
        )
    return deepcopy(migration.INITIAL_DEFINITION)


def register(client, session_factory, *, admin=False):
    response = client.post(
        "/auth/register",
        json={"name": "Teste Admin", "email": "scale@example.com", "password": "senha-segura-123"},
    )
    assert response.status_code == 201
    user_id = UUID(response.json()["id"])
    if admin:
        with session_factory() as session, session.begin():
            user = session.get(User, user_id)
            user.role = "admin"
    return user_id


def changed(initial, base_version=1):
    definition = deepcopy(initial)
    definition["scores"][3]["description"] = "Critério revisado para demanda relevante."
    return {
        "base_version": base_version,
        "change_reason": "Revisão dos critérios de estabilização.",
        "definition": definition,
    }


def test_authentication_and_admin_permissions(client, session_factory, initial):
    assert client.get("/biomechanical-scales/current").status_code == 401
    assert client.get("/biomechanical-scales").status_code == 401
    assert client.get("/biomechanical-scales/1").status_code == 401
    assert client.post("/biomechanical-scales", json=changed(initial)).status_code == 401
    register(client, session_factory)
    assert client.get("/biomechanical-scales/current").status_code == 200
    assert client.get("/biomechanical-scales").status_code == 403
    assert client.get("/biomechanical-scales/1").status_code == 403
    assert client.post("/biomechanical-scales", json=changed(initial)).status_code == 403


def test_new_version_preserves_history_and_audit(client, session_factory, initial):
    user_id = register(client, session_factory, admin=True)
    body = changed(initial)
    response = client.post("/biomechanical-scales", json=body)
    assert response.status_code == 201, response.text
    saved = response.json()
    assert saved["version"] == 2
    assert saved["created_by"] == str(user_id)
    assert saved["change_reason"] == body["change_reason"]
    assert saved["created_at"]
    assert saved["definition"] == body["definition"]
    assert client.get("/biomechanical-scales/current").json() == saved
    assert client.get("/biomechanical-scales/1").json()["definition"] == initial
    history = client.get("/biomechanical-scales?page_size=1").json()
    assert history["total"] == 2
    assert [item["version"] for item in history["items"]] == [2]
    assert "definition" not in history["items"][0]
    assert client.get("/biomechanical-scales?page_size=1&page=2").json()["items"][0]["version"] == 1
    assert client.get("/biomechanical-scales/999").status_code == 404
    assert client.get("/biomechanical-scales/0").status_code == 422
    assert client.get("/biomechanical-scales?page=0").status_code == 422
    assert client.get("/biomechanical-scales?page_size=101").status_code == 422
    assert client.put("/biomechanical-scales/1", json=body).status_code == 405
    assert client.delete("/biomechanical-scales/1").status_code == 405


@pytest.mark.parametrize(
    "invalid",
    [
        "empty_title",
        "blank_reason",
        "score_range",
        "duplicate_score",
        "missing_region",
        "duplicate_region",
        "unknown_region",
        "duplicate_role",
        "blank_description",
        "unknown_field",
        "boolean_score",
        "boolean_version",
        "too_long",
    ],
)
def test_invalid_criteria_are_not_saved(client, session_factory, initial, invalid):
    register(client, session_factory, admin=True)
    body = changed(initial)
    definition = body["definition"]
    if invalid == "empty_title":
        definition["title"] = "   "
    elif invalid == "blank_reason":
        body["change_reason"] = "   "
    elif invalid == "score_range":
        definition["scores"][0]["score"] = 6
    elif invalid == "duplicate_score":
        definition["scores"][0]["score"] = 1
    elif invalid == "missing_region":
        definition["regions"].pop()
    elif invalid == "duplicate_region":
        definition["regions"][0]["code"] = definition["regions"][1]["code"]
    elif invalid == "unknown_region":
        definition["regions"][0]["code"] = "unknown"
    elif invalid == "duplicate_role":
        definition["roles"][0]["code"] = definition["roles"][1]["code"]
    elif invalid == "blank_description":
        definition["regions"][0]["description"] = " "
    elif invalid == "unknown_field":
        definition["risk_percentage"] = 90
    elif invalid == "boolean_score":
        definition["scores"][0]["score"] = False
    elif invalid == "boolean_version":
        body["base_version"] = True
    elif invalid == "too_long":
        definition["evaluation_criteria"] = "a" * 4001
    assert client.post("/biomechanical-scales", json=body).status_code == 422
    assert client.get("/biomechanical-scales/current").json()["version"] == 1


def test_unchanged_criteria_are_rejected(client, session_factory, initial):
    register(client, session_factory, admin=True)
    response = client.post(
        "/biomechanical-scales",
        json={"base_version": 1, "change_reason": "Sem alteração", "definition": initial},
    )
    assert response.status_code == 422


def test_stale_and_concurrent_save_conflict(client, session_factory, initial, monkeypatch):
    from src.workouts.biomechanics import service

    register(client, session_factory, admin=True)
    body = changed(initial)
    assert client.post("/biomechanical-scales", json=body).status_code == 201
    assert client.post("/biomechanical-scales", json=body).status_code == 409

    # Simulate another transaction winning after our current-version read.
    monkeypatch.setattr(
        service,
        "current_version",
        lambda session: session.get(BiomechanicalScaleVersion, 1),
    )
    assert client.post("/biomechanical-scales", json=body).status_code == 409
    with session_factory() as session:
        assert len(session.scalars(select(BiomechanicalScaleVersion)).all()) == 2


def test_uninitialized_scale_reports_migration_needed(client, session_factory):
    register(client, session_factory, admin=True)
    response = client.get("/biomechanical-scales/current")
    assert response.status_code == 503
    assert "migrações" in response.json()["detail"]


def test_migration_seeds_valid_scale_and_preserves_existing_data(migration, monkeypatch):
    engine = create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE TABLE users (id UUID PRIMARY KEY)")
            connection.exec_driver_sql("INSERT INTO users VALUES ('existing')")
            monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
            migration.upgrade()
            row = connection.execute(select(BiomechanicalScaleVersion.__table__)).mappings().one()
            assert row["version"] == 1
            assert row["created_by"] is None
            assert row["created_at"] is not None
            definition = ScaleDefinition.model_validate(row["definition"])
            assert {item.score for item in definition.scores} == set(range(6))
            assert len(definition.regions) == 5
            assert (
                len(inspect(connection).get_check_constraints("biomechanical_scale_versions")) == 2
            )
            assert connection.exec_driver_sql("SELECT id FROM users").scalar() == "existing"
            migration.downgrade()
            assert "biomechanical_scale_versions" not in inspect(connection).get_table_names()
            assert connection.exec_driver_sql("SELECT id FROM users").scalar() == "existing"
    finally:
        engine.dispose()


def test_migration_generates_offline_postgresql_sql(migration, monkeypatch):
    output = io.StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output}
    )
    monkeypatch.setattr(migration, "op", Operations(context))
    migration.upgrade()
    sql = output.getvalue()
    assert "CREATE TABLE biomechanical_scale_versions" in sql
    assert "INSERT INTO biomechanical_scale_versions" in sql
    assert "Escala de Demanda Biomecânica Regional" in sql
    assert "ALTER TABLE biomechanical_scale_versions ENABLE ROW LEVEL SECURITY" in sql


def test_sql_snapshot_matches_migration_definition(migration):
    sql = (Path(__file__).parents[1] / "schema.sql").read_text(encoding="utf-8")
    insert = next(
        line
        for line in sql.splitlines()
        if line.startswith("INSERT INTO biomechanical_scale_versions")
    )
    match = re.search(r"VALUES \(1, '((?:[^']|'')*)',", insert)
    assert match is not None
    assert json.loads(match.group(1).replace("''", "'")) == migration.INITIAL_DEFINITION


def test_deleting_author_preserves_scale_history(client, session_factory, initial):
    user_id = register(client, session_factory, admin=True)
    assert client.post("/biomechanical-scales", json=changed(initial)).status_code == 201
    with session_factory() as session, session.begin():
        user = session.get(User, user_id)
        assert user is not None
        session.delete(user)
    with session_factory() as session:
        version = session.get(BiomechanicalScaleVersion, 2)
        assert version is not None
        assert version.created_by is None
        assert version.definition == changed(initial)["definition"]
        assert session.get(BiomechanicalScaleVersion, 1) is not None
