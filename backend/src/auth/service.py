import secrets
import uuid
from datetime import datetime, timedelta, timezone

from loguru import logger
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.auth.models import PasswordResetToken, User
from src.auth.utils import (
    dummy_hash,
    hash_password,
    hash_reset_token,
    verify_password,
)

RESET_TOKEN_TTL = timedelta(hours=1)


class EmailAlreadyRegisteredError(ValueError):
    pass


def normalize_email(email: str) -> str:
    return email.strip().lower()


def get_user_by_email(email: str, session: Session) -> User | None:
    return session.scalar(select(User).where(User.email == normalize_email(email)))


def get_user_by_id(user_id: uuid.UUID, session: Session) -> User | None:
    return session.get(User, user_id)


def create_user(name: str, email: str, password: str, session: Session, role: str = "user") -> User:
    email = normalize_email(email)
    if get_user_by_email(email, session):
        raise EmailAlreadyRegisteredError("E-mail já cadastrado.")

    user = User(name=name.strip(), email=email, password_hash=hash_password(password), role=role)
    session.add(user)
    try:
        session.commit()
    except IntegrityError as e:
        # Corrida entre dois cadastros simultâneos com o mesmo e-mail
        session.rollback()
        raise EmailAlreadyRegisteredError("E-mail já cadastrado.") from e
    return user


def authenticate_user(email: str, password: str, session: Session) -> User | None:
    """Valida credenciais. Executa o bcrypt mesmo sem usuário (anti timing attack)."""
    user = get_user_by_email(email, session)
    if user is None:
        verify_password(password, dummy_hash())
        return None
    if not verify_password(password, user.password_hash) or not user.is_active:
        return None
    return user


def create_password_reset_token(user: User, session: Session) -> str:
    """Gera o token em texto (para o e-mail) e persiste somente o hash."""
    raw_token = secrets.token_urlsafe(32)
    session.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_reset_token(raw_token),
            expires_at=datetime.now(timezone.utc) + RESET_TOKEN_TTL,
        )
    )
    session.commit()
    return raw_token


def reset_password_with_token(token: str, new_password: str, session: Session) -> bool:
    """Consome o token (uso único) e troca a senha atomicamente."""
    now = datetime.now(timezone.utc)

    # UPDATE condicional: dois requests simultâneos não consomem o mesmo token.
    user_id = session.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.token_hash == hash_reset_token(token),
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > now,
        )
        .values(used_at=now)
        .returning(PasswordResetToken.user_id)
    ).scalar_one_or_none()

    if user_id is None:
        session.rollback()
        return False

    user = session.get(User, user_id)
    if user is None:
        session.rollback()
        logger.warning(f"Token de reset válido, mas usuário {user_id} não existe mais.")
        return False

    user.password_hash = hash_password(new_password)

    # Invalida os demais tokens pendentes do usuário
    session.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user_id, PasswordResetToken.used_at.is_(None))
        .values(used_at=now)
    )
    session.commit()
    logger.info(f"Senha redefinida para o usuário {user_id}.")
    return True


def change_password(user: User, current_password: str, new_password: str, session: Session) -> bool:
    if not verify_password(current_password, user.password_hash):
        return False
    user.password_hash = hash_password(new_password)
    session.commit()
    return True
