import pytest

from tests.test_workout_generator_api import register

PROFILE = {"age": 30, "weight_kg": 75.5, "height_cm": 175}


def test_training_profile_requires_login(client):
    assert client.get("/auth/training-profile").status_code == 401
    assert client.put("/auth/training-profile", json=PROFILE).status_code == 401
    assert client.delete("/auth/training-profile").status_code == 401


def test_training_profile_is_private_updatable_and_removable(client):
    register(client)
    assert client.get("/auth/training-profile").json() is None
    saved = client.put("/auth/training-profile", json=PROFILE)
    assert saved.status_code == 200
    assert saved.json().items() >= PROFILE.items()
    assert "updated_at" in saved.json()
    assert client.get("/auth/training-profile").json() == saved.json()
    assert "weight_kg" not in client.get("/auth/me").json()

    changed = client.put("/auth/training-profile", json={**PROFILE, "weight_kg": 76.25})
    assert changed.status_code == 200
    assert changed.json()["weight_kg"] == 76.25
    client.post("/auth/logout")
    client.post(
        "/auth/register",
        json={"name": "Outro", "email": "other@example.com", "password": "senha-segura-123"},
    )
    assert client.get("/auth/training-profile").json() is None
    assert client.delete("/auth/training-profile").status_code == 204
    client.post("/auth/login", json={"email": "ana@example.com", "password": "senha-segura-123"})
    assert client.get("/auth/training-profile").json()["weight_kg"] == 76.25
    assert client.delete("/auth/training-profile").status_code == 204
    assert client.get("/auth/training-profile").json() is None


@pytest.mark.parametrize(
    "change",
    [
        {"age": 17},
        {"age": 101},
        {"age": 30.5},
        {"age": True},
        {"weight_kg": 0},
        {"weight_kg": 401},
        {"height_cm": 99},
        {"height_cm": 251},
        {"user_id": "someone-else"},
    ],
)
def test_training_profile_rejects_invalid_data(client, change):
    register(client)
    assert client.put("/auth/training-profile", json={**PROFILE, **change}).status_code == 422
