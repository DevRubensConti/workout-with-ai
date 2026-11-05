import copy
import json
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select

from src.auth.models import User
from src.config import get_settings
from src.main import app
from src.workouts.exercises.models import DisabledExercise, Exercise, ExerciseTranslation
from src.workouts.generator import ai_service
from src.workouts.replacements import service
from src.workouts.sessions.models import WorkoutSetLog


@pytest.fixture
def ready(client, session_factory, monkeypatch):
    assert (
        client.post(
            "/auth/register",
            json={
                "name": "Teste",
                "email": "replacement@example.com",
                "password": "senha-segura-123",
            },
        ).status_code
        == 201
    )
    with session_factory() as db, db.begin():
        user = db.scalar(select(User).where(User.email == "replacement@example.com"))
        other = User(name="Outro", email="private@example.com", password_hash="unused")
        db.add(other)
        db.flush()
        common = {
            "muscle_group": "chest",
            "primary_muscles": ["chest", "triceps"],
            "secondary_muscles": ["shoulders"],
            "equipment": "dumbbell",
            "level": "beginner",
            "mechanic": "compound",
            "force": "push",
            "category": "strength",
        }
        rows = {
            key: Exercise(name=key, **common)
            for key in ["original", "first", "second", "third", "duplicate", "disabled"]
        }
        rows["first"].translations = [
            ExerciseTranslation(locale="pt-BR", name="Alternativa traduzida", instructions=[])
        ]
        rows["first"].primary_muscles = ["triceps", "chest"]
        for key, changes in {
            "wrong_muscles": {"primary_muscles": ["chest"]},
            "wrong_equipment": {"equipment": "barbell"},
            "wrong_level": {"level": "expert"},
            "private": {"owner_user_id": other.id},
        }.items():
            rows[key] = Exercise(name=key, **{**common, **changes})
        db.add_all(rows.values())
        db.flush()
        db.add(DisabledExercise(user_id=user.id, exercise_id=rows["disabled"].id))
        ids = {key: str(row.id) for key, row in rows.items()}
        owner_id = user.id
    body = {
        "name": "Nome livre não enviar",
        "description": "Descrição privada",
        "goal": "Objetivo livre",
        "days": [
            {
                "name": "Dia A",
                "notes": "Notas privadas do dia",
                "exercises": [
                    {
                        "exercise_id": ids["original"],
                        "sets": 3,
                        "reps_min": 8,
                        "reps_max": 12,
                        "target_weight_kg": 40,
                        "rest_seconds": 90,
                        "tempo": "3010",
                        "notes": "Orientações específicas",
                    },
                    {
                        "exercise_id": ids["duplicate"],
                        "sets": 2,
                        "reps_min": 10,
                    },
                ],
            }
        ],
    }
    plan_response = client.post("/workouts", json=body)
    assert plan_response.status_code == 201, plan_response.text
    plan = plan_response.json()
    context = {
        "mode": "plan",
        "plan_id": plan["id"],
        "day_id": plan["days"][0]["id"],
        "row_id": plan["days"][0]["exercises"][0]["id"],
    }
    captured = []

    def compare(instruction, wire, schema):
        captured.append(wire)
        return {
            "comparisons": [
                {
                    "candidate_index": index,
                    "pro": f"Vantagem {index}",
                    "con": f"Limitação {index}",
                }
                for index in range(len(wire["candidates"]))
            ]
        }

    monkeypatch.setattr(service, "request_gemini_json", compare)
    return {
        "ids": ids,
        "plan": plan,
        "context": context,
        "body": body,
        "captured": captured,
        "user_id": owner_id,
        "compare": compare,
    }


def suggest(client, context):
    response = client.post(
        "/workouts/replacements/suggest",
        json={
            "context": context,
            "ai_consent": True,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def apply(client, context, suggestions, candidate=None):
    return client.post(
        "/workouts/replacements/apply",
        json={
            "context": context,
            "revision": suggestions["revision"],
            "replacement_id": candidate or suggestions["options"][0]["exercise"]["id"],
        },
    )


def start(client, ready):
    response = client.post("/sessions", json={"day_id": ready["context"]["day_id"]})
    assert response.status_code == 201, response.text
    return response.json()


def session_context(detail, ready):
    return {
        "mode": "session",
        "session_id": detail["id"],
        "exercise_id": ready["ids"]["original"],
    }


def test_exact_candidates_and_private_context(client, ready):
    result = suggest(client, ready["context"])
    assert len(result["options"]) == 3
    assert {entry["exercise"]["id"] for entry in result["options"]} == {
        ready["ids"][key] for key in ["first", "second", "third"]
    }
    assert all(entry["pro"] and entry["con"] for entry in result["options"])
    assert "Alternativa traduzida" in {entry["exercise"]["name"] for entry in result["options"]}
    wire = ready["captured"][0]
    assert len(wire["workout"]["days"][0]["exercises"]) == 2
    assert wire["original"]["name"] == "original"
    text = json.dumps(wire)
    for private in [
        "Nome livre",
        "Descrição privada",
        "Objetivo livre",
        "Notas privadas",
        "Orientações específicas",
        "replacement@example.com",
        "target_weight_kg",
    ]:
        assert private not in text
    assert (
        client.get(f"/workouts/{ready['plan']['id']}").json()["days"][0]["exercises"][0][
            "exercise_id"
        ]
        == ready["ids"]["original"]
    )


def test_draft_does_not_save_and_validates_other_exercises(client, ready):
    context = {
        "mode": "draft",
        "workout": ready["body"],
        "day_index": 0,
        "exercise_index": 0,
    }
    assert len(suggest(client, context)["options"]) == 3
    assert len(client.get("/workouts").json()) == 1
    context["workout"] = copy.deepcopy(ready["body"])
    context["workout"]["days"][0]["exercises"][1]["exercise_id"] = ready["ids"]["private"]
    assert (
        client.post(
            "/workouts/replacements/suggest",
            json={
                "context": context,
                "ai_consent": True,
            },
        ).status_code
        == 404
    )


def test_fewer_candidates_and_none_skip_gemini(client, ready, session_factory):
    with session_factory() as db, db.begin():
        for key in ["first", "second"]:
            db.add(DisabledExercise(user_id=ready["user_id"], exercise_id=UUID(ready["ids"][key])))
    result = suggest(client, ready["context"])
    assert len(result["options"]) == 1 and "1 de 3" in result["message"]
    with session_factory() as db, db.begin():
        db.add(DisabledExercise(user_id=ready["user_id"], exercise_id=UUID(ready["ids"]["third"])))
    assert suggest(client, ready["context"])["options"] == []
    assert len(ready["captured"]) == 1


def test_missing_primary_muscles_does_not_relax_criteria(client, ready, session_factory):
    with session_factory() as db, db.begin():
        db.get(Exercise, UUID(ready["ids"]["original"])).primary_muscles = None
    assert suggest(client, ready["context"])["options"] == []
    assert not ready["captured"]


@pytest.mark.parametrize(
    "output",
    [
        {"comparisons": []},
        {"comparisons": [{"candidate_index": 0, "pro": "Bom", "con": "Ruim"}] * 3},
        {"comparisons": [{"candidate_index": 3, "pro": "Bom", "con": "Ruim"}]},
        {"comparisons": [{"candidate_index": True, "pro": "Bom", "con": "Ruim"}]},
        {"comparisons": [{"candidate_index": 0, "pro": "", "con": "Ruim"}]},
        {"comparisons": [{"candidate_index": 0, "pro": "Bom", "con": "Ruim", "extra": 1}]},
        None,
    ],
)
def test_rejects_invalid_gemini_output(client, ready, monkeypatch, output):
    monkeypatch.setattr(service, "request_gemini_json", lambda *args: output)
    response = client.post(
        "/workouts/replacements/suggest",
        json={
            "context": ready["context"],
            "ai_consent": True,
        },
    )
    assert response.status_code == 502
    assert "Nenhuma troca" in response.json()["detail"]


def test_plan_swap_persists_prescription_but_resets_specifics(client, ready):
    suggestions = suggest(client, ready["context"])
    result = apply(client, ready["context"], suggestions)
    assert result.status_code == 200, result.text
    changed = result.json()["plan"]["days"][0]["exercises"][0]
    assert changed["exercise_id"] == suggestions["options"][0]["exercise"]["id"]
    assert (changed["sets"], changed["reps_min"], changed["reps_max"], changed["rest_seconds"]) == (
        3,
        8,
        12,
        90,
    )
    assert changed["target_weight_kg"] is None and changed["notes"] is None
    assert changed["tempo"] is None
    detail = start(client, ready)
    assert detail["exercises"][0]["exercise_id"] == changed["exercise_id"]


def test_session_swap_preserves_completed_logs_and_updates_next_session(
    client,
    ready,
    session_factory,
):
    detail = start(client, ready)
    completed_log = None
    with session_factory() as db, db.begin():
        logs = db.scalars(
            select(WorkoutSetLog)
            .where(
                WorkoutSetLog.session_id == UUID(detail["id"]),
                WorkoutSetLog.exercise_id == UUID(ready["ids"]["original"]),
            )
            .order_by(WorkoutSetLog.set_number)
        ).all()
        logs[0].completed = True
        logs[0].weight_kg = 42
        completed_log = logs[0].id
    context = session_context(detail, ready)
    suggestions = suggest(client, context)
    response = apply(client, context, suggestions)
    assert response.status_code == 200, response.text
    result = response.json()["session"]
    original, replacement, duplicate = result["exercises"]
    assert original["exercise_id"] == ready["ids"]["original"]
    assert original["sets"] == [
        {
            "exercise_id": ready["ids"]["original"],
            "set_number": 1,
            "reps": 8,
            "weight_kg": 42,
            "completed": True,
        }
    ]
    assert replacement["exercise_id"] == suggestions["options"][0]["exercise"]["id"]
    assert [entry["set_number"] for entry in replacement["sets"]] == [1, 2]
    assert all(
        entry["weight_kg"] is None and not entry["completed"] for entry in replacement["sets"]
    )
    assert (result["total_sets"], result["completed_sets"], result["volume_kg"]) == (5, 1, 336)
    assert duplicate["exercise_id"] == ready["ids"]["duplicate"]
    with session_factory() as db:
        assert db.get(WorkoutSetLog, completed_log).exercise_id == UUID(ready["ids"]["original"])
    reloaded = client.get(f"/sessions/{detail['id']}").json()
    assert reloaded["exercises"] == result["exercises"]
    assert client.post(f"/sessions/{detail['id']}/finish", json={}).status_code == 200
    next_session = start(client, ready)
    assert next_session["exercises"][0]["exercise_id"] == replacement["exercise_id"]
    assert len(next_session["exercises"][0]["sets"]) == 3
    history = client.get(f"/sessions/{detail['id']}").json()
    assert [entry["exercise_id"] for entry in history["exercises"]] == [ready["ids"]["original"]]


def test_swap_before_any_completed_series_replaces_entire_exercise(client, ready):
    detail = start(client, ready)
    context = session_context(detail, ready)
    suggestions = suggest(client, context)
    response = apply(client, context, suggestions)
    assert response.status_code == 200, response.text
    exercises = response.json()["session"]["exercises"]
    assert len(exercises) == 2
    assert len(exercises[0]["sets"]) == 3
    assert exercises[0]["exercise_id"] != ready["ids"]["original"]


def test_saved_plan_swap_blocked_when_day_running(client, ready):
    start(client, ready)
    response = client.post(
        "/workouts/replacements/suggest",
        json={
            "context": ready["context"],
            "ai_consent": True,
        },
    )
    assert response.status_code == 409
    assert not ready["captured"]


def test_all_completed_and_finished_sessions_block_swaps(client, ready, session_factory):
    detail = start(client, ready)
    with session_factory() as db, db.begin():
        logs = db.scalars(
            select(WorkoutSetLog).where(WorkoutSetLog.session_id == UUID(detail["id"]))
        )
        for log in logs:
            log.completed = True
    context = session_context(detail, ready)
    assert (
        client.post(
            "/workouts/replacements/suggest",
            json={
                "context": context,
                "ai_consent": True,
            },
        ).status_code
        == 409
    )
    assert client.post(f"/sessions/{detail['id']}/finish", json={}).status_code == 200
    assert (
        client.post(
            "/workouts/replacements/suggest",
            json={
                "context": context,
                "ai_consent": True,
            },
        ).status_code
        == 409
    )


def test_apply_revalidates_eligibility_and_revision(client, ready, session_factory):
    suggestions = suggest(client, ready["context"])
    assert (
        apply(client, ready["context"], suggestions, ready["ids"]["wrong_muscles"]).status_code
        == 409
    )
    candidate_id = suggestions["options"][0]["exercise"]["id"]
    with session_factory() as db, db.begin():
        db.add(DisabledExercise(user_id=ready["user_id"], exercise_id=UUID(candidate_id)))
    assert apply(client, ready["context"], suggestions).status_code == 409
    with session_factory() as db, db.begin():
        plan = db.get(service.WorkoutPlan, UUID(ready["plan"]["id"]))
        plan.days[0].exercises[0].sets = 4
    assert apply(client, ready["context"], suggestions).status_code == 409


def test_completed_series_changed_since_suggest_is_conflict(client, ready, session_factory):
    detail = start(client, ready)
    context = session_context(detail, ready)
    suggestions = suggest(client, context)
    with session_factory() as db, db.begin():
        log = db.scalar(select(WorkoutSetLog).where(WorkoutSetLog.session_id == UUID(detail["id"])))
        log.completed = True
    response = apply(client, context, suggestions)
    assert response.status_code == 409


def test_swapped_session_can_autosave_and_swap_again(client, ready):
    detail = start(client, ready)
    sets = [
        {**entry, "completed": entry["set_number"] == 1}
        for group in detail["exercises"]
        for entry in group["sets"]
    ]
    assert client.put(f"/sessions/{detail['id']}/sets", json={"sets": sets}).status_code == 200
    context = session_context(detail, ready)
    suggestions = suggest(client, context)
    first = apply(client, context, suggestions).json()["session"]
    saved = client.put(
        f"/sessions/{detail['id']}/sets",
        json={
            "sets": [entry for group in first["exercises"] for entry in group["sets"]],
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["exercises"] == first["exercises"]
    replacement_id = suggestions["options"][0]["exercise"]["id"]
    next_context = {**context, "exercise_id": replacement_id}
    alternatives = suggest(client, next_context)
    assert ready["ids"]["original"] not in {
        option["exercise"]["id"] for option in alternatives["options"]
    }
    second = apply(client, next_context, alternatives)
    assert second.status_code == 200, second.text
    groups = second.json()["session"]["exercises"]
    assert groups[0]["exercise_id"] == ready["ids"]["original"]
    assert groups[0]["sets"][0]["completed"]


def test_session_without_original_plan_cannot_make_permanent_swap(client, ready):
    detail = start(client, ready)
    assert client.delete(f"/workouts/{ready['plan']['id']}").status_code == 204
    response = client.post(
        "/workouts/replacements/suggest",
        json={
            "context": session_context(detail, ready),
            "ai_consent": True,
        },
    )
    assert response.status_code == 409
    assert not ready["captured"]


def test_ai_not_configured_returns_explicit_error(client, ready, monkeypatch):
    monkeypatch.setattr(service, "request_gemini_json", ai_service.request_gemini_json)
    response = client.post(
        "/workouts/replacements/suggest",
        json={
            "context": ready["context"],
            "ai_consent": True,
        },
    )
    assert response.status_code == 503
    assert "configurada" in response.json()["detail"]


def test_auth_consent_and_ownership(client, ready):
    assert (
        client.post(
            "/workouts/replacements/suggest",
            json={
                "context": ready["context"],
                "ai_consent": False,
            },
        ).status_code
        == 422
    )
    with TestClient(app) as other:
        assert other.post("/workouts/replacements/suggest", json={}).status_code == 401
        other.post(
            "/auth/register",
            json={
                "name": "Outro",
                "email": "other2@example.com",
                "password": "senha-segura-123",
            },
        )
        assert (
            other.post(
                "/workouts/replacements/suggest",
                json={
                    "context": ready["context"],
                    "ai_consent": True,
                },
            ).status_code
            == 404
        )


def test_session_and_apply_are_owner_scoped(client, ready):
    detail = start(client, ready)
    context = session_context(detail, ready)
    suggestions = suggest(client, context)
    with TestClient(app) as other:
        other.post(
            "/auth/register",
            json={
                "name": "Outro",
                "email": "other3@example.com",
                "password": "senha-segura-123",
            },
        )
        assert (
            other.post(
                "/workouts/replacements/suggest",
                json={
                    "context": context,
                    "ai_consent": True,
                },
            ).status_code
            == 404
        )
        assert apply(other, context, suggestions).status_code == 404


@pytest.mark.parametrize("status,finish", [(200, "STOP"), (429, "STOP"), (200, "MAX_TOKENS")])
def test_real_transport_offline(client, ready, monkeypatch, status, finish):
    settings = get_settings().model_copy(
        update={
            "GEMINI_API_KEY": SecretStr("fake-offline-key"),
            "GEMINI_PERSONAL_DATA_ENABLED": True,
        }
    )
    monkeypatch.setattr(ai_service, "get_settings", lambda: settings)
    monkeypatch.setattr(service, "request_gemini_json", ai_service.request_gemini_json)
    real_client = httpx.Client
    captured = []

    def handle(request):
        body = json.loads(request.content)
        captured.append(body)
        context = json.loads(body["contents"][0]["parts"][0]["text"])
        output = ready["compare"]("", context, {})
        return httpx.Response(
            status,
            json={
                "candidates": [
                    {
                        "finishReason": finish,
                        "content": {"parts": [{"text": json.dumps(output)}]},
                    }
                ],
            },
        )

    monkeypatch.setattr(
        ai_service.httpx,
        "Client",
        lambda **kwargs: real_client(
            transport=httpx.MockTransport(handle),
            **kwargs,
        ),
    )
    response = client.post(
        "/workouts/replacements/suggest",
        json={
            "context": ready["context"],
            "ai_consent": True,
        },
    )
    assert response.status_code == (503 if status == 429 else 502 if finish != "STOP" else 200)
    assert captured[0]["generationConfig"]["responseMimeType"] == "application/json"
