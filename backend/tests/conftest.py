import os

# Precisa vir antes de qualquer import de `src` (as settings são lidas no import).
os.environ.update(
    {
        "ENVIRONMENT": "testing",
        "DATABASE_URL": "sqlite://",
        "SECRET_KEY": "test-secret-key-test-secret-key-0123456789",
        "PEPPER": "test-pepper-0123456789",
        "FRONTEND_URL": "http://localhost:3000",
    }
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from src.auth import models  # noqa: E402, F401
from src.database import Base, get_session  # noqa: E402
from src.main import app  # noqa: E402
from src.social import models as social_models  # noqa: E402, F401
from src.workouts import models as workouts_models  # noqa: E402, F401


@pytest.fixture()
def session_factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    # SQLite ignora FKs por padrão: sem isso CASCADE/SET NULL/RESTRICT não funcionam.
    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    yield lambda: Session(engine, expire_on_commit=False)
    engine.dispose()


@pytest.fixture()
def client(session_factory):
    def override_get_session():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
