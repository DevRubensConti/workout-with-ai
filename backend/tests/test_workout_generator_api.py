import pytest

from src.workouts.exercises.models import Exercise, ExerciseTranslation
from src.workouts.generator.service import CATALOG_SOURCE
from tests.test_workout_generator import build_catalog

BODY = {
    "goal": "hypertrophy",
    "level": "intermediate",
    "days_per_week": 4,
    "session_minutes": 90,
}


def register(client):
    response = client.post(
        "/auth/register",
        json={"name": "Ana Silva", "email": "ana@example.com", "password": "senha-segura-123"},
    )
    assert response.status_code == 201


@pytest.fixture()
def seeded(session_factory):
    with session_factory() as session, session.begin():
        for info in build_catalog().values():
            session.add(
                Exercise(
                    id=info.id,
                    name=info.name,
                    muscle_group=info.muscle_group,
                    equipment=info.equipment,
                    level=info.level,
                    source=CATALOG_SOURCE,
                    source_id=info.source_id,
                    primary_muscles=[info.muscle_group],
                    secondary_muscles=["shoulders", "triceps"]
                    if info.muscle_group == "chest"
                    else [],
                    images=list(info.images),
                    translations=[
                        ExerciseTranslation(
                            locale="pt-BR", name=f"PT {info.name}", instructions=[]
                        )
                    ],
                )
            )


def test_generate_requires_login(client):
    assert client.post("/workouts/generate", json=BODY).status_code == 401


def test_generate_returns_reviewable_draft_without_saving(client, seeded):
    register(client)

    response = client.post("/workouts/generate", json=BODY)

    assert response.status_code == 200
    plan = response.json()
    assert plan["name"].startswith("Hipertrofia")
    assert plan["goal"] == "Hipertrofia" and plan["level"] == "intermediate"
    assert len(plan["days"]) == 4
    first = plan["days"][0]["exercises"][0]
    assert first["name"].startswith("PT ")
    assert first["sets"] >= 2 and first["reps_min"] <= first["reps_max"]
    assert plan["weekly_volume"] and plan["rationale"] and plan["references"]
    assert plan["rules_version"] and plan["review_status"]
    assert {ref["id"] for ref in plan["references"]} >= {"R1"}
    assert client.get("/workouts").json() == []


@pytest.mark.parametrize(
    "change",
    [
        {"days_per_week": 7},
        {"days_per_week": 1},
        {"session_minutes": 10},
        {"goal": "bulking"},
        {"level": "pro"},
        {"focus_muscles": ["chest", "lats", "shoulders", "biceps"]},
        {"focus_muscles": ["neck"]},
        {"avoid_muscles": ["tail"]},
        {"extra": 1},
    ],
)
def test_generate_validates_input(client, seeded, change):
    register(client)

    assert client.post("/workouts/generate", json={**BODY, **change}).status_code == 422


def test_generate_without_loaded_catalog_is_unavailable(client):
    register(client)

    assert client.post("/workouts/generate", json=BODY).status_code == 503


def test_complaints_do_not_change_generated_exercises_or_volume(client, seeded):
    register(client)
    baseline = client.post("/workouts/generate", json=BODY)
    response = client.post(
        "/workouts/generate",
        json={**BODY, "avoid_muscles": ["shoulders", "lower back", "chest"]},
    )

    assert baseline.status_code == response.status_code == 200
    plan = response.json()
    assert plan["days"] == baseline.json()["days"]
    assert plan["weekly_volume"] == baseline.json()["weekly_volume"]
    assert any("não alteraram" in warning for warning in plan["warnings"])


def test_generated_draft_can_be_saved_as_ai_plan_with_metadata(client, seeded):
    register(client)
    draft = client.post("/workouts/generate", json=BODY).json()
    body = {
        "name": draft["name"],
        "description": draft["description"],
        "goal": draft["goal"],
        "level": draft["level"],
        "source": "ai",
        "ai_metadata": {
            "generator": "rules",
            "rules_version": draft["rules_version"],
            "rationale": draft["rationale"],
        },
        "days": [
            {
                "name": day["name"],
                "notes": day["notes"],
                "exercises": [
                    {
                        "exercise_id": e["exercise_id"],
                        "sets": e["sets"],
                        "reps_min": e["reps_min"],
                        "reps_max": e["reps_max"],
                        "rest_seconds": e["rest_seconds"],
                    }
                    for e in day["exercises"]
                ],
            }
            for day in draft["days"]
        ],
    }

    saved = client.post("/workouts", json=body)

    assert saved.status_code == 201
    detail = saved.json()
    assert detail["source"] == "ai" and detail["status"] == "active"
    assert detail["ai_metadata"]["rules_version"] == draft["rules_version"]
    assert client.get("/workouts").json()[0]["source"] == "ai"


def test_ai_metadata_is_only_accepted_for_ai_plans_and_is_bounded(client, seeded):
    register(client)
    draft = client.post("/workouts/generate", json=BODY).json()
    day = draft["days"][0]
    base = {
        "name": "X",
        "days": [
            {
                "name": "A",
                "exercises": [
                    {"exercise_id": day["exercises"][0]["exercise_id"], "sets": 3, "reps_min": 8}
                ],
            }
        ],
    }

    assert client.post("/workouts", json={**base, "ai_metadata": {"a": 1}}).status_code == 422
    huge = {"text": "x" * 25_000}
    assert (
        client.post("/workouts", json={**base, "source": "ai", "ai_metadata": huge}).status_code
        == 422
    )
    assert client.post("/workouts", json={**base, "source": "ai"}).status_code == 201


def test_generate_accepts_a_split_style_available_for_the_days(client, seeded):
    register(client)

    response = client.post(
        "/workouts/generate", json={**BODY, "days_per_week": 4, "split_style": "body_part"}
    )

    assert response.status_code == 200
    plan = response.json()
    assert plan["split"] == "Por grupos musculares"
    assert [day["name"] for day in plan["days"]][0] == "Peito e tríceps"
    assert any("convenção" in line for line in plan["rationale"])


@pytest.mark.parametrize(
    ("days", "style"),
    [(2, "body_part"), (4, "push_pull_legs"), (5, "upper_lower"), (6, "full_body"), (4, "x")],
)
def test_generate_rejects_a_style_unavailable_for_the_days(client, seeded, days, style):
    register(client)

    response = client.post(
        "/workouts/generate", json={**BODY, "days_per_week": days, "split_style": style}
    )

    assert response.status_code == 422
