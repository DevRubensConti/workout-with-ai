from uuid import UUID

from src.auth.models import User
from src.workouts.models import Exercise, ExerciseTranslation


def register(client):
    response = client.post(
        "/auth/register",
        json={
            "name": "Ana Silva",
            "email": "ana@example.com",
            "password": "senha-segura-123",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def seed_exercises(session_factory, owner_id):
    with session_factory() as session, session.begin():
        other_user = User(
            name="Bruno",
            email="bruno@example.com",
            password_hash="unused",
        )
        session.add(other_user)
        session.flush()

        bench_press = Exercise(
            name="Bench Press",
            muscle_group="chest",
            equipment="barbell",
            level="beginner",
            source="free-exercise-db",
            source_id="Bench_Press",
            primary_muscles=["chest"],
            secondary_muscles=["triceps"],
            images=["Bench_Press/0.jpg"],
            translations=[
                ExerciseTranslation(
                    locale="en",
                    name="Bench Press",
                    instructions=["Lie on the bench."],
                ),
                ExerciseTranslation(
                    locale="pt-BR",
                    name="Supino reto",
                    instructions=["Deite-se no banco."],
                ),
            ],
        )
        squat = Exercise(
            name="Squat",
            muscle_group="quadriceps",
            equipment="barbell",
            source="free-exercise-db",
            source_id="Squat",
            translations=[
                ExerciseTranslation(locale="en", name="Squat", instructions=["Stand upright."])
            ],
        )
        own_exercise = Exercise(
            name="Meu exercício",
            muscle_group="shoulders",
            owner_user_id=UUID(owner_id),
        )
        other_private_exercise = Exercise(
            name="Exercício privado",
            muscle_group="back",
            owner_user_id=other_user.id,
        )
        session.add_all([bench_press, squat, own_exercise, other_private_exercise])
        session.flush()
        return {
            "bench_press": bench_press.id,
            "squat": squat.id,
            "own": own_exercise.id,
            "other_private": other_private_exercise.id,
        }


def test_exercise_catalog_requires_login(client):
    assert client.get("/exercises").status_code == 401


def test_exercise_list_search_filters_and_pagination(client, session_factory):
    owner_id = register(client)
    seed_exercises(session_factory, owner_id)

    response = client.get(
        "/exercises",
        params={
            "locale": "pt-BR",
            "q": "SUPINO",
            "muscle_group": "chest",
            "equipment": "barbell",
            "page_size": 1,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["total_pages"] == 1
    assert body["items"][0]["name"] == "Supino reto"
    assert body["items"][0]["locale"] == "pt-BR"
    assert body["items"][0]["images"] == ["Bench_Press/0.jpg"]
    assert "Exercício privado" not in [item["name"] for item in body["items"]]
    assert "chest" in body["filters"]["muscle_groups"]
    assert "back" not in body["filters"]["muscle_groups"]

    page = client.get(
        "/exercises",
        params={"locale": "en", "equipment": "barbell", "page": 2, "page_size": 1},
    )
    assert page.status_code == 200
    assert page.json()["total"] == 2
    assert page.json()["total_pages"] == 2
    assert page.json()["items"][0]["name"] == "Squat"


def test_exercise_detail_falls_back_to_english_and_hides_other_users_private_data(
    client, session_factory
):
    owner_id = register(client)
    ids = seed_exercises(session_factory, owner_id)

    fallback = client.get(f"/exercises/{ids['squat']}", params={"locale": "pt-BR"})
    assert fallback.status_code == 200
    assert fallback.json()["name"] == "Squat"
    assert fallback.json()["locale"] == "en"
    assert fallback.json()["instructions"] == ["Stand upright."]
    assert fallback.json()["primary_muscles"] == []
    assert fallback.json()["images"] == []

    own = client.get(f"/exercises/{ids['own']}", params={"locale": "pt-BR"})
    assert own.status_code == 200
    assert own.json()["name"] == "Meu exercício"
    assert own.json()["locale"] is None

    hidden = client.get(f"/exercises/{ids['other_private']}")
    assert hidden.status_code == 404


def test_exercise_catalog_rejects_invalid_query_values(client):
    register(client)
    assert client.get("/exercises", params={"locale": "fr"}).status_code == 422
    assert client.get("/exercises", params={"page_size": 101}).status_code == 422


def test_exercise_detail_preserves_primary_and_secondary_muscles(client, session_factory):
    owner_id = register(client)
    ids = seed_exercises(session_factory, owner_id)
    response = client.get(f"/exercises/{ids['bench_press']}")
    assert response.status_code == 200
    assert response.json()["primary_muscles"] == ["chest"]
    assert response.json()["secondary_muscles"] == ["triceps"]


def test_percentage_endpoints_are_no_longer_exposed(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert "/exercises/muscle-targets" not in paths
    assert "/exercises/{exercise_id}/muscle-effects" not in paths
