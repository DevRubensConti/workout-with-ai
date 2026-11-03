from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from src.config import get_settings

settings = get_settings()


class Base(DeclarativeBase):
    """Base declarativa de todos os models (usada também pelo Alembic)."""


engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_recycle=1800,
)

SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_session():
    """Dependência para injeção de sessão no FastAPI."""
    with SessionLocal() as session:
        yield session
