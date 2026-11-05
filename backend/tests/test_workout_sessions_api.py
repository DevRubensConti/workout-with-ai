from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from src.auth.models import User
from src.main import app
from src.workouts.exercises.models import Exercise, ExerciseTranslation


def register(client, email="ana@example.com"):
    response = client.post(
        "/auth/register",
        json={"name": "Ana Silva", "email": email, "password": "senha-segura-123"},
    )
    assert response.status_code == 201


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
                images=["Bench_Press/0.jpg"],
                translations=[
                    ExerciseTranslation(locale="en", name="Bench Press", instructions=[]),
                    ExerciseTranslation(locale="pt-BR", name="Supino reto", instructions=[]),
                ],
            ),
            "row": Exercise(name="Row", muscle_group="lats"),
            "squat": Exercise(name="Squat", muscle_group="quadriceps"),
            "private": Exercise(name="Segredo", muscle_group="back", owner_user_id=other.id),
        }
        session.add_all(rows.values())
        session.flush()
        return {key: str(row.id) for key, row in rows.items()}


def make_plan(client, exercises):
    body = {
        "name": "Hipertrofia ABC",
        "days": [
            {
                "name": "Treino A",
                "exercises": [
                    {
                        "exercise_id": exercises["bench"],
                        "sets": 3,
                        "reps_min": 8,
                        "reps_max": 12,
                        "target_weight_kg": 40,
                        "rest_seconds": 90,
                    },
                    {"exercise_id": exercises["row"], "sets": 2, "reps_min": 10},
                ],
            },
            {
                "name": "Treino B",
                "exercises": [{"exercise_id": exercises["squat"], "sets": 1, "reps_min": 5}],
            },
        ],
    }
    response = client.post("/workouts", json=body)
    assert response.status_code == 201
    return response.json()


def flatten(detail):
    return [
        (g["exercise_id"], s["set_number"], s["reps"], s["weight_kg"], s["completed"])
        for g in detail["exercises"]
        for s in g["sets"]
    ]


def done_sets(detail, weight=50, reps=10, only_first=False):
    sets = []
    for group in detail["exercises"]:
        for item in group["sets"]:
            sets.append(
                {
                    "exercise_id": item["exercise_id"],
                    "set_number": item["set_number"],
                    "reps": reps,
                    "weight_kg": weight,
                    "completed": not only_first or item["set_number"] == 1,
                }
            )
    return sets


def test_sessions_require_login(client):
    assert client.get("/sessions").status_code == 401
    assert client.post("/sessions", json={}).status_code == 401


def test_start_prefills_sets_in_plan_order_and_resumes(client, exercises):
    register(client)
    plan = make_plan(client, exercises)
    day_a, day_b = plan["days"]

    assert client.get("/sessions/active").json() is None
    started = client.post("/sessions", json={"day_id": day_a["id"]})

    assert started.status_code == 201
    detail = started.json()
    assert detail["plan_name"] == "Hipertrofia ABC" and detail["day_name"] == "Treino A"
    assert detail["finished_at"] is None and detail["duration_seconds"] is None
    assert [group["name"] for group in detail["exercises"]] == ["Supino reto", "Row"]
    assert flatten(detail) == [
        (exercises["bench"], 1, 8, 40.0, False),
        (exercises["bench"], 2, 8, 40.0, False),
        (exercises["bench"], 3, 8, 40.0, False),
        (exercises["row"], 1, 10, None, False),
        (exercises["row"], 2, 10, None, False),
    ]
    bench = detail["exercises"][0]
    assert bench["images"] == ["Bench_Press/0.jpg"] and bench["muscle_group"] == "chest"
    assert bench["target"]["rest_seconds"] == 90 and bench["target"]["reps_max"] == 12
    assert (detail["total_sets"], detail["completed_sets"]) == (5, 0)

    again = client.post("/sessions", json={"day_id": day_a["id"]})
    assert again.status_code == 200 and again.json()["id"] == detail["id"]
    assert client.get("/sessions/active").json()["id"] == detail["id"]

    other_day = client.post("/sessions", json={"day_id": day_b["id"]})
    assert other_day.status_code == 409


def test_cannot_start_session_from_other_users_day(client, exercises):
    register(client)
    plan = make_plan(client, exercises)

    with TestClient(app) as other:
        register(other, "bruno2@example.com")
        response = other.post("/sessions", json={"day_id": plan["days"][0]["id"]})

    assert response.status_code == 404


def test_replace_sets_persists_values_and_order(client, exercises):
    register(client)
    plan = make_plan(client, exercises)
    detail = client.post("/sessions", json={"day_id": plan["days"][0]["id"]}).json()

    sets = done_sets(detail, weight=55.5, reps=9)
    sets.append(
        {
            "exercise_id": exercises["squat"],
            "set_number": 1,
            "reps": 5,
            "weight_kg": 80,
            "completed": True,
        }
    )
    saved = client.put(f"/sessions/{detail['id']}/sets", json={"sets": sets})

    assert saved.status_code == 200
    result = saved.json()
    assert [group["name"] for group in result["exercises"]] == ["Supino reto", "Row", "Squat"]
    assert flatten(result)[0] == (exercises["bench"], 1, 9, 55.5, True)
    assert result["completed_sets"] == 6 and result["volume_kg"] == 55.5 * 9 * 5 + 400
    reloaded = client.get(f"/sessions/{detail['id']}").json()
    assert flatten(reloaded) == flatten(result)


def test_replace_sets_validation(client, exercises):
    register(client)
    plan = make_plan(client, exercises)
    detail = client.post("/sessions", json={"day_id": plan["days"][0]["id"]}).json()
    url = f"/sessions/{detail['id']}/sets"
    base = {"exercise_id": exercises["bench"], "set_number": 1, "reps": 8, "completed": True}

    assert client.put(url, json={"sets": [base, base]}).status_code == 422
    unknown = {**base, "exercise_id": "00000000-0000-0000-0000-000000000000"}
    assert client.put(url, json={"sets": [unknown]}).status_code == 422
    private = {**base, "exercise_id": exercises["private"]}
    assert client.put(url, json={"sets": [private]}).status_code == 422
    assert client.put(url, json={"sets": [{**base, "reps": -1}]}).status_code == 422
    assert client.put(url, json={"sets": [{**base, "weight_kg": -5}]}).status_code == 422
    assert client.put(url, json={"sets": [{**base, "set_number": 0}]}).status_code == 422
    assert client.put(url, json={"sets": [{**base, "extra": 1}]}).status_code == 422
    # Nada foi alterado pelas tentativas inválidas
    assert client.get(url.removesuffix("/sets")).json()["total_sets"] == 5


def test_finish_requires_completed_set_and_cleans_incomplete_ones(client, exercises):
    register(client)
    plan = make_plan(client, exercises)
    detail = client.post("/sessions", json={"day_id": plan["days"][0]["id"]}).json()
    url = f"/sessions/{detail['id']}"

    assert client.post(f"{url}/finish", json={}).status_code == 422
    assert client.post(f"{url}/finish", json={"perceived_effort": 11}).status_code == 422

    client.put(f"{url}/sets", json={"sets": done_sets(detail, only_first=True)})
    finished = client.post(f"{url}/finish", json={"perceived_effort": 8, "notes": "  Bom treino  "})

    assert finished.status_code == 200
    result = finished.json()
    assert result["finished_at"] is not None and result["duration_seconds"] >= 0
    assert result["notes"] == "Bom treino" and result["perceived_effort"] == 8
    assert (result["total_sets"], result["completed_sets"]) == (2, 2)
    assert result["volume_kg"] == 2 * 10 * 50
    assert client.get("/sessions/active").json() is None

    assert client.post(f"{url}/finish", json={}).status_code == 409
    assert client.put(f"{url}/sets", json={"sets": []}).status_code == 409


def test_history_lists_only_finished_sessions_newest_first(client, exercises):
    register(client)
    plan = make_plan(client, exercises)
    day_a, day_b = plan["days"]
    ids = []
    for day, name in ((day_a, "Treino A"), (day_b, "Treino B")):
        detail = client.post("/sessions", json={"day_id": day["id"]}).json()
        client.put(f"/sessions/{detail['id']}/sets", json={"sets": done_sets(detail)})
        client.post(f"/sessions/{detail['id']}/finish", json={})
        ids.append((detail["id"], name))
    client.post("/sessions", json={"day_id": day_a["id"]})  # em andamento: fora do histórico

    history = client.get("/sessions").json()

    assert history["total"] == 2
    assert [item["day_name"] for item in history["items"]] == ["Treino B", "Treino A"]
    paged = client.get("/sessions", params={"page": 2, "page_size": 1}).json()
    assert [item["id"] for item in paged["items"]] == [ids[0][0]]
    assert paged["total_pages"] == 2

    with TestClient(app) as other:
        register(other, "bruno2@example.com")
        assert other.get("/sessions").json()["total"] == 0
        assert other.get(f"/sessions/{ids[0][0]}").status_code == 404
        assert other.delete(f"/sessions/{ids[0][0]}").status_code == 404
        assert other.put(f"/sessions/{ids[0][0]}/sets", json={"sets": []}).status_code == 404


def test_next_session_prefills_last_used_weight(client, exercises):
    register(client)
    plan = make_plan(client, exercises)
    day_a = plan["days"][0]
    first = client.post("/sessions", json={"day_id": day_a["id"]}).json()
    sets = done_sets(first, weight=60)
    sets[1]["completed"] = False  # a série 2 não foi feita e não vira referência
    client.put(f"/sessions/{first['id']}/sets", json={"sets": sets})
    client.post(f"/sessions/{first['id']}/finish", json={})

    second = client.post("/sessions", json={"day_id": day_a["id"]}).json()

    bench = [item for item in flatten(second) if item[0] == exercises["bench"]]
    weights = [(number, weight) for _, number, _, weight, _ in bench]
    assert weights == [(1, 60.0), (2, 40.0), (3, 60.0)]


def test_delete_cancels_open_session_and_allows_new_one(client, exercises):
    register(client)
    plan = make_plan(client, exercises)
    day_a, day_b = plan["days"]
    open_session = client.post("/sessions", json={"day_id": day_a["id"]}).json()

    assert client.delete(f"/sessions/{open_session['id']}").status_code == 204
    assert client.get(f"/sessions/{open_session['id']}").status_code == 404
    assert client.get("/sessions/active").json() is None
    assert client.post("/sessions", json={"day_id": day_b["id"]}).status_code == 201


def test_history_survives_plan_deletion(client, exercises):
    register(client)
    plan = make_plan(client, exercises)
    detail = client.post("/sessions", json={"day_id": plan["days"][0]["id"]}).json()
    client.put(f"/sessions/{detail['id']}/sets", json={"sets": done_sets(detail)})
    client.post(f"/sessions/{detail['id']}/finish", json={})

    assert client.delete(f"/workouts/{plan['id']}").status_code == 204

    kept = client.get(f"/sessions/{detail['id']}").json()
    assert kept["plan_id"] is None and kept["day_id"] is None
    assert kept["plan_name"] == "Hipertrofia ABC" and kept["day_name"] == "Treino A"
    assert kept["exercises"][0]["target"] is None
    assert kept["exercises"][0]["name"] == "Supino reto"
    assert UUID(kept["id"])
