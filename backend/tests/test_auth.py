import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from src.auth import router as auth_router
from src.auth.dependencies import require_permissions
from src.auth.models import User
from src.database import get_session

USER = {"name": "Ana Silva", "email": "ana@example.com", "password": "senha-segura-123"}


def register(client, **overrides):
    return client.post("/auth/register", json={**USER, **overrides})


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_register_logs_user_in_and_me_works(client):
    response = register(client)
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == USER["email"]
    assert body["role"] == "user"
    assert "profile:read" in body["permissions"]
    assert "password" not in body and "password_hash" not in body

    assert "httponly" in response.headers["set-cookie"].lower()

    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == USER["email"]


def test_register_duplicate_email_is_case_insensitive(client):
    assert register(client).status_code == 201
    assert register(client, email="ANA@example.com").status_code == 409


@pytest.mark.parametrize(
    "overrides",
    [{"password": "curta"}, {"email": "nao-e-email"}, {"name": ""}],
)
def test_register_validates_input(client, overrides):
    assert register(client, **overrides).status_code == 422


def test_me_requires_login(client):
    assert client.get("/auth/me").status_code == 401


def test_me_rejects_garbage_token(client):
    client.cookies.set("access_token", "not-a-jwt")
    assert client.get("/auth/me").status_code == 401


def test_login_and_logout(client):
    register(client)
    client.cookies.clear()

    bad = client.post("/auth/login", json={"email": USER["email"], "password": "errada-123"})
    assert bad.status_code == 401
    unknown = client.post(
        "/auth/login", json={"email": "x@example.com", "password": "qualquer-123"}
    )
    assert unknown.status_code == 401
    assert bad.json() == unknown.json()

    ok = client.post("/auth/login", json={"email": "Ana@Example.com", "password": USER["password"]})
    assert ok.status_code == 200
    assert client.get("/auth/me").status_code == 200

    assert client.post("/auth/logout").status_code == 200
    assert client.get("/auth/me").status_code == 401


def test_inactive_user_loses_access(client, session_factory):
    register(client)
    with session_factory() as session:
        user = session.query(User).one()
        user.is_active = False
        session.commit()

    assert client.get("/auth/me").status_code == 401
    client.cookies.clear()
    login = client.post("/auth/login", json={"email": USER["email"], "password": USER["password"]})
    assert login.status_code == 401


def test_change_password(client):
    register(client)

    wrong = client.patch(
        "/auth/change-password",
        json={"current_password": "errada-123", "new_password": "nova-senha-456"},
    )
    assert wrong.status_code == 400

    ok = client.patch(
        "/auth/change-password",
        json={"current_password": USER["password"], "new_password": "nova-senha-456"},
    )
    assert ok.status_code == 200

    client.cookies.clear()
    old = client.post("/auth/login", json={"email": USER["email"], "password": USER["password"]})
    new = client.post("/auth/login", json={"email": USER["email"], "password": "nova-senha-456"})
    assert old.status_code == 401
    assert new.status_code == 200


def test_forgot_and_reset_password(client, monkeypatch):
    sent: list[tuple[str, str]] = []

    async def fake_send(email: str, token: str):
        sent.append((email, token))

    monkeypatch.setattr(auth_router, "send_password_reset_email", fake_send)
    register(client)
    client.cookies.clear()

    unknown = client.post("/auth/forgot-password", json={"email": "ninguem@example.com"})
    known = client.post("/auth/forgot-password", json={"email": USER["email"]})
    assert unknown.status_code == known.status_code == 200
    assert unknown.json() == known.json()
    assert len(sent) == 1

    _, token = sent[0]
    reset = client.post(
        "/auth/reset-password", json={"token": token, "new_password": "reset-456-ok"}
    )
    assert reset.status_code == 200

    # Token é de uso único
    again = client.post(
        "/auth/reset-password", json={"token": token, "new_password": "outra-789-ok"}
    )
    assert again.status_code == 400

    login = client.post("/auth/login", json={"email": USER["email"], "password": "reset-456-ok"})
    assert login.status_code == 200


def test_reset_password_rejects_invalid_token(client):
    response = client.post(
        "/auth/reset-password", json={"token": "inventado", "new_password": "reset-456-ok"}
    )
    assert response.status_code == 400


def test_permissions_are_enforced(client, session_factory):
    probe = FastAPI()

    @probe.get("/admin-only")
    def admin_only(user: User = Depends(require_permissions("user:read"))):
        return {"ok": True}

    def override_get_session():
        with session_factory() as session:
            yield session

    probe.dependency_overrides[get_session] = override_get_session

    register(client)
    probe_client = TestClient(probe, cookies=client.cookies)
    assert probe_client.get("/admin-only").status_code == 403

    with session_factory() as session:
        user = session.query(User).one()
        user.role = "admin"
        session.commit()

    assert probe_client.get("/admin-only").status_code == 200
