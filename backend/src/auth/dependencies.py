"""
Dependências de autenticação/autorização do FastAPI.

O JWT vive em cookie HttpOnly `access_token` (também aceitamos
`Authorization: Bearer` para clientes não-browser). O usuário e suas permissões
são sempre lidos do banco: desativar um usuário ou mudar seu papel vale na hora.
"""

import uuid

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from src.auth.models import User
from src.auth.permissions import permissions_for_role
from src.auth.service import get_user_by_id
from src.auth.utils import decode_access_token
from src.database import get_session

COOKIE_NAME = "access_token"


def _unauthorized() -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário não logado")


def _extract_token(request: Request) -> str | None:
    value = request.cookies.get(COOKIE_NAME) or request.headers.get("Authorization")
    if not value:
        return None
    scheme, _, token = value.partition(" ")
    if token:
        return token if scheme.lower() == "bearer" else None
    return value


def get_current_user(
    request: Request,
    required_permissions: list[str],
    session: Session,
    match_any: bool = False,
) -> User:
    token = _extract_token(request)
    if not token:
        raise _unauthorized()

    payload = decode_access_token(token)
    if not payload or not payload.get("sub"):
        raise _unauthorized()

    try:
        user_id = uuid.UUID(payload["sub"])
    except ValueError:
        raise _unauthorized()

    user = get_user_by_id(user_id, session)
    if user is None or not user.is_active:
        raise _unauthorized()

    if required_permissions:
        user_permissions = set(permissions_for_role(user.role))
        needed = set(required_permissions)
        allowed = bool(needed & user_permissions) if match_any else needed <= user_permissions
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Operação não permitida. Permissões insuficientes.",
            )

    return user


def require_permissions(*permissions: str, match_any: bool = False):
    """
    Dependência que exige login e as permissões informadas (TODAS por padrão,
    ou PELO MENOS UMA com `match_any=True`). Sem argumentos, exige só login.

    Uso: current_user: User = Depends(require_permissions("user:read"))
    """

    def dependency(request: Request, session: Session = Depends(get_session)) -> User:
        return get_current_user(request, list(permissions), session, match_any)

    return dependency
