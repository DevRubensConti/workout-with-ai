"""
Utilitários de autenticação: hash de senha, JWT e e-mail de recuperação.

Senha: SHA-256(senha + PEPPER) -> base64 -> bcrypt. O pré-hash evita o limite de
72 bytes do bcrypt e o pepper (segredo fora do banco) protege contra vazamento
isolado do banco de dados.
"""

import base64
import hashlib
from datetime import datetime, timedelta, timezone
from functools import lru_cache

import bcrypt
from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType, NameEmail
from jose import JWTError, jwt
from pydantic import SecretStr

from src.config import get_settings

settings = get_settings()


def _pre_hash_password(password: str) -> bytes:
    digest = hashlib.sha256((password + settings.PEPPER).encode("utf-8")).digest()
    return base64.b64encode(digest)


def _raw(password: str | SecretStr) -> str:
    return password.get_secret_value() if isinstance(password, SecretStr) else password


def hash_password(plain_password: str | SecretStr) -> str:
    raw = _raw(plain_password)
    if not raw:
        raise ValueError("A senha não pode estar vazia.")
    hashed = bcrypt.hashpw(_pre_hash_password(raw), bcrypt.gensalt(rounds=12))
    return hashed.decode("utf-8")


def verify_password(plain_password: str | SecretStr, hashed_password: str) -> bool:
    raw = _raw(plain_password)
    if not raw:
        return False
    try:
        return bcrypt.checkpw(_pre_hash_password(raw), hashed_password.encode("utf-8"))
    except ValueError:
        # Hash armazenado malformado
        return False


@lru_cache
def dummy_hash() -> str:
    """Hash descartável para equalizar o tempo de login quando o e-mail não existe."""
    return hash_password("dummy-password-for-timing")


def hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=15))
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None


async def send_password_reset_email(email_to: str, token: str) -> None:
    reset_link = f"{settings.FRONTEND_URL}/reset-password?token={token}"

    if not settings.mail_enabled:
        # Sem SMTP configurado: em desenvolvimento o link aparece no log.
        # Nunca logamos o token em outros ambientes.
        if settings.ENVIRONMENT == "development":
            from loguru import logger

            logger.warning(f"SMTP não configurado. Link de reset para {email_to}: {reset_link}")
        return

    mail_conf = ConnectionConfig(
        MAIL_USERNAME=settings.MAIL_USERNAME or "",
        MAIL_PASSWORD=settings.MAIL_PASSWORD or SecretStr(""),
        MAIL_FROM=settings.MAIL_FROM,  # type: ignore[arg-type]
        MAIL_FROM_NAME=settings.MAIL_FROM_NAME,
        MAIL_PORT=settings.MAIL_PORT,
        MAIL_SERVER=settings.MAIL_SERVER,  # type: ignore[arg-type]
        MAIL_STARTTLS=settings.MAIL_STARTTLS,
        MAIL_SSL_TLS=settings.MAIL_SSL_TLS,
        USE_CREDENTIALS=settings.USE_CREDENTIALS,
    )

    html = f"""
    <p>Você solicitou a recuperação de senha do {settings.APP_NAME}.</p>
    <p>Clique no link abaixo para redefinir sua senha (válido por 1 hora):</p>
    <a href="{reset_link}">{reset_link}</a>
    <p>Se você não solicitou isso, ignore este e-mail.</p>
    """

    message = MessageSchema(
        subject=f"Recuperação de senha - {settings.APP_NAME}",
        recipients=[NameEmail(name="", email=email_to)],
        body=html,
        subtype=MessageType.html,
    )

    await FastMail(mail_conf).send_message(message)
