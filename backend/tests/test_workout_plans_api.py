from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from src.auth.models import User
from src.main import app
from src.workouts.exercises.models import Exercise, ExerciseTranslation
from src.workouts.sessions.models import WorkoutSession


def register(client, email="ana@example.com"):
    response = client.post(
        "/auth/register",
        json={"name": "Ana Silva", "email": email, "password": "senha-segura-123"},
    )
    assert response.status_code == 201
    return UUID(response.json()["id"])


@pytest.fixture()
def exercises(session_factory):
    with session_factory() as session, session.begin():
        other = User(name="Bruno", email="bruno@example.com", password_hash="unused")
        session.add(other)
        session.flush()
        rows = {
            "bench": Exercise(
                name="Bench Press",
                muscle_group="chest",
                equipment="barbell",
                images=["Bench_Press/0.jpg"],
                translations=[
                    ExerciseTranslation(locale="en", name="Bench Press", instructions=[]),
                    ExerciseTranslation(locale="pt-BR", name="Supino reto", instructions=[]),
                ],
            ),
            "squat": Exercise(
                name="Squat",
                muscle_group="quadriceps",
                translations=[ExerciseTranslation(locale="en", name="Squat", instructions=[])],
            ),
            "row": Exercise(name="Row", muscle_group="lats"),
            "private": Exercise(name="Segredo", muscle_group="back", owner_user_id=other.id),
        }
        session.add_all(rows.values())
        session.flush()
        return {key: str(row.id) for key, row in rows.items()}


def exercise_item(exercise_id, **overrides):
    return {"exercise_id": exercise_id, "sets": 3, "reps_min": 8, "reps_max": 12, **overrides}


def plan_body(exercises, **overrides):
    body = {
        "name": "Hipertrofia ABC",
        "goal": "Hipertrofia",
        "level": "intermediate",
        "days": [
            {
                "name": "Treino A",
                "exercises": [
                    exercise_item(exercises["bench"], target_weight_kg=60.5, rest_seconds=90),
                    exercise_item(exercises["row"]),
                ],
            },
            {"name": "Treino B", "exercises": [exercise_item(exercises["squat"])]},
        ],
    }
    return {**body, **overrides}


def test_workouts_require_login(client):
    assert client.get("/workouts").status_code == 401
    assert client.post("/workouts", json={}).status_code == 401


def test_create_plan_returns_ordered_localized_detail(client, exercises):
    register(client)

    response = client.post("/workouts", json=plan_body(exercises))

    assert response.status_code == 201
    plan = response.json()
    assert plan["status"] == "active" and plan["source"] == "manual"
    assert (plan["day_count"], plan["exercise_count"]) == (2, 3)
    assert [day["name"] for day in plan["days"]] == ["Treino A", "Treino B"]
    first = plan["days"][0]["exercises"]
    assert [item["position"] for item in first] == [0, 1]
    assert first[0]["exercise_name"] == "Supino reto"
    assert first[0]["target_weight_kg"] == 60.5
    assert first[0]["images"] == ["Bench_Press/0.jpg"]
    assert first[1]["exercise_name"] == "Row"

    english = client.get(f"/workouts/{plan['id']}", params={"locale": "en"}).json()
    assert english["days"][0]["exercises"][0]["exercise_name"] == "Bench Press"
    fallback = client.get(f"/workouts/{plan['id']}", params={"locale": "pt-BR"}).json()
    assert fallback["days"][1]["exercises"][0]["exercise_name"] == "Squat"


def test_new_plan_archives_previous_active_plan(client, exercises):
    register(client)
    first = client.post("/workouts", json=plan_body(exercises, name="Primeiro")).json()
    second = client.post("/workouts", json=plan_body(exercises, name="Segundo")).json()

    plans = client.get("/workouts").json()
    assert [plan["name"] for plan in plans] == ["Segundo", "Primeiro"]
    assert [plan["status"] for plan in plans] == ["active", "archived"]
    assert plans[1]["archived_at"] is not None
    assert [p["id"] for p in client.get("/workouts", params={"status": "active"}).json()] == [
        second["id"]
    ]
    assert [p["id"] for p in client.get("/workouts", params={"status": "archived"}).json()] == [
        first["id"]
    ]


def test_activate_and_archive(client, exercises):
    register(client)
    first = client.post("/workouts", json=plan_body(exercises, name="Primeiro")).json()
    second = client.post("/workouts", json=plan_body(exercises, name="Segundo")).json()

    activated = client.post(f"/workouts/{first['id']}/activate")
    assert activated.status_code == 200
    assert activated.json()["status"] == "active"
    statuses = {p["name"]: p["status"] for p in client.get("/workouts").json()}
    assert statuses == {"Primeiro": "active", "Segundo": "archived"}

    archived = client.post(f"/workouts/{first['id']}/archive")
    assert archived.json()["status"] == "archived"
    assert client.post(f"/workouts/{first['id']}/archive").status_code == 200
    assert {p["status"] for p in client.get("/workouts").json()} == {"archived"}
    assert second["id"]


def test_update_preserves_ids_and_reorders_without_unique_conflicts(client, exercises):
    register(client)
    plan = client.post("/workouts", json=plan_body(exercises)).json()
    day_a, day_b = plan["days"]
    bench, row = day_a["exercises"]

    body = {
        "name": "Renomeado",
        "level": None,
        "days": [
            {
                "id": day_b["id"],
                "name": "Pernas",
                "exercises": [
                    exercise_item(
                        exercises["squat"], id=day_b["exercises"][0]["id"], sets=5, reps_max=None
                    )
                ],
            },
            {
                "id": day_a["id"],
                "name": "Peito e costas",
                "exercises": [
                    exercise_item(exercises["row"], id=row["id"]),
                    exercise_item(exercises["bench"], id=bench["id"], target_weight_kg=70),
                    exercise_item(exercises["squat"]),
                ],
            },
            {"name": "Novo dia", "exercises": []},
        ],
    }
    response = client.put(f"/workouts/{plan['id']}", json=body)

    assert response.status_code == 200
    updated = response.json()
    assert updated["name"] == "Renomeado" and updated["level"] is None
    assert [day["name"] for day in updated["days"]] == ["Pernas", "Peito e costas", "Novo dia"]
    assert [day["position"] for day in updated["days"]] == [0, 1, 2]
    assert updated["days"][0]["id"] == day_b["id"]
    assert updated["days"][1]["id"] == day_a["id"]
    moved = updated["days"][1]["exercises"]
    assert [item["id"] for item in moved[:2]] == [row["id"], bench["id"]]
    assert [item["position"] for item in moved] == [0, 1, 2]
    assert moved[1]["target_weight_kg"] == 70
    assert updated["days"][0]["exercises"][0]["sets"] == 5
    assert updated["days"][0]["exercises"][0]["reps_max"] is None
    assert (updated["day_count"], updated["exercise_count"]) == (3, 4)


def test_update_removes_missing_days_and_exercises(client, exercises):
    register(client)
    plan = client.post("/workouts", json=plan_body(exercises)).json()
    day_a = plan["days"][0]

    body = plan_body(exercises)
    body["days"] = [
        {
            "id": day_a["id"],
            "name": "Treino A",
            "exercises": [exercise_item(exercises["bench"], id=day_a["exercises"][0]["id"])],
        }
    ]
    updated = client.put(f"/workouts/{plan['id']}", json=body).json()

    assert (updated["day_count"], updated["exercise_count"]) == (1, 1)
    assert updated["days"][0]["exercises"][0]["id"] == day_a["exercises"][0]["id"]


def test_update_rejects_foreign_ids_and_keeps_plan_unchanged(client, exercises):
    register(client)
    plan = client.post("/workouts", json=plan_body(exercises)).json()
    other = client.post("/workouts", json=plan_body(exercises, name="Outro")).json()

    body = plan_body(exercises, name="Alterado")
    body["days"][0]["id"] = other["days"][0]["id"]
    response = client.put(f"/workouts/{plan['id']}", json=body)

    assert response.status_code == 422
    unchanged = client.get(f"/workouts/{plan['id']}").json()
    assert unchanged["name"] == "Hipertrofia ABC"
    assert unchanged["exercise_count"] == 3


def test_users_cannot_access_each_others_plans(client, exercises):
    register(client)
    plan = client.post("/workouts", json=plan_body(exercises)).json()

    with TestClient(app) as other:
        register(other, "bruno2@example.com")
        assert other.get("/workouts").json() == []
        for method, path in (
            ("get", f"/workouts/{plan['id']}"),
            ("put", f"/workouts/{plan['id']}"),
            ("post", f"/workouts/{plan['id']}/activate"),
            ("post", f"/workouts/{plan['id']}/archive"),
            ("delete", f"/workouts/{plan['id']}"),
        ):
            kwargs = {"json": plan_body(exercises)} if method == "put" else {}
            assert getattr(other, method)(path, **kwargs).status_code == 404

        mine = other.post("/workouts", json=plan_body(exercises)).json()
        assert mine["status"] == "active"

    assert client.get(f"/workouts/{plan['id']}").json()["status"] == "active"


def test_each_user_keeps_their_own_active_plan(client, exercises):
    register(client)
    client.post("/workouts", json=plan_body(exercises))
    with TestClient(app) as other:
        register(other, "bruno2@example.com")
        other.post("/workouts", json=plan_body(exercises))

    assert [p["status"] for p in client.get("/workouts").json()] == ["active"]


def test_rejects_unknown_and_other_users_private_exercises(client, exercises):
    register(client)
    unknown = plan_body(exercises)
    unknown["days"][0]["exercises"][0]["exercise_id"] = "00000000-0000-0000-0000-000000000000"
    private = plan_body(exercises)
    private["days"][0]["exercises"][0]["exercise_id"] = exercises["private"]

    assert client.post("/workouts", json=unknown).status_code == 422
    assert client.post("/workouts", json=private).status_code == 422
    assert client.get("/workouts").json() == []


@pytest.mark.parametrize(
    "change",
    [
        {"sets": 0},
        {"reps_min": -1},
        {"reps_min": 10, "reps_max": 8},
        {"target_weight_kg": -5},
        {"rest_seconds": -1},
        {"unknown": 1},
    ],
)
def test_rejects_invalid_exercise_prescription(client, exercises, change):
    register(client)
    body = plan_body(exercises)
    body["days"][0]["exercises"][0].update(change)

    assert client.post("/workouts", json=body).status_code == 422


@pytest.mark.parametrize(
    "change",
    [{"name": "  "}, {"days": []}, {"days": [{"name": ""}]}, {"level": "godlike"}],
)
def test_rejects_invalid_plan(client, exercises, change):
    register(client)

    assert client.post("/workouts", json=plan_body(exercises, **change)).status_code == 422


def test_delete_plan_keeps_session_history(client, session_factory, exercises):
    user_id = register(client)
    plan = client.post("/workouts", json=plan_body(exercises)).json()
    with session_factory() as session, session.begin():
        session.add(
            WorkoutSession(
                user_id=user_id,
                plan_id=UUID(plan["id"]),
                day_id=UUID(plan["days"][0]["id"]),
                plan_name=plan["name"],
                day_name="Treino A",
            )
        )

    assert client.delete(f"/workouts/{plan['id']}").status_code == 204
    assert client.get(f"/workouts/{plan['id']}").status_code == 404
    assert client.delete(f"/workouts/{plan['id']}").status_code == 404

    with session_factory() as session:
        history = session.scalars(select(WorkoutSession)).all()
        assert len(history) == 1
        assert history[0].plan_id is None and history[0].plan_name == "Hipertrofia ABC"
