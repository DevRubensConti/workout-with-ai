from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from loguru import logger
from sqlalchemy.orm import Session

from src.auth.dependencies import COOKIE_NAME, require_permissions
from src.auth.models import TrainingProfile, User
from src.auth.permissions import permissions_for_role
from src.auth.schemas import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
    TrainingProfileIn,
    TrainingProfileOut,
    UserResponse,
    WorkoutPreferences,
)
from src.auth.service import (
    EmailAlreadyRegisteredError,
    authenticate_user,
    change_password,
    create_password_reset_token,
    create_user,
    get_user_by_email,
    reset_password_with_token,
)
from src.auth.utils import create_access_token, send_password_reset_email
from src.config import get_settings
from src.database import get_session

settings = get_settings()

# Prefixo "/auth" configurado em main.py
router = APIRouter()


def _user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        permissions=permissions_for_role(user.role),
    )


def _set_auth_cookie(response: Response, user: User) -> None:
    """Emite o JWT em cookie HttpOnly (inacessível ao JavaScript, mitiga XSS)."""
    token = create_access_token(
        data={"sub": str(user.id), "role": user.role},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.SECURE,
        samesite=settings.SAME_SITE,
        domain=settings.cookie_domain,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )


async def _send_reset_email_safely(email: str, token: str) -> None:
    try:
        await send_password_reset_email(email, token)
        logger.info("E-mail de recuperação processado.")
    except Exception as e:
        logger.error(f"Falha ao enviar e-mail de recuperação: {e}")


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=UserResponse)
def register(
    body: RegisterRequest,
    response: Response,
    session: Session = Depends(get_session),
):
    """Cadastro público. Já deixa o usuário logado."""
    try:
        user = create_user(body.name, body.email, body.password.get_secret_value(), session)
    except EmailAlreadyRegisteredError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="E-mail já cadastrado.")

    _set_auth_cookie(response, user)
    return _user_response(user)


@router.post("/login", response_model=MessageResponse)
def login(body: LoginRequest, response: Response, session: Session = Depends(get_session)):
    user = authenticate_user(body.email, body.password.get_secret_value(), session)
    if user is None:
        # Mensagem genérica: não revela se o e-mail existe
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="E-mail ou senha inválidos."
        )

    _set_auth_cookie(response, user)
    return MessageResponse(message="Login realizado com sucesso")


@router.post("/logout", response_model=MessageResponse)
def logout(response: Response):
    # Parâmetros idênticos ao set_cookie, senão o browser não remove o cookie
    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
        domain=settings.cookie_domain,
        secure=settings.SECURE,
        samesite=settings.SAME_SITE,
    )
    return MessageResponse(message="Logout realizado com sucesso")


@router.get("/me", response_model=UserResponse)
def read_me(current_user: User = Depends(require_permissions("profile:read"))):
    return _user_response(current_user)


@router.get("/workout-preferences", response_model=WorkoutPreferences)
def read_workout_preferences(current_user: User = Depends(require_permissions("profile:read"))):
    return WorkoutPreferences(rest_timer_enabled=current_user.rest_timer_enabled)


@router.put("/workout-preferences", response_model=WorkoutPreferences)
def save_workout_preferences(
    body: WorkoutPreferences,
    current_user: User = Depends(require_permissions("profile:write")),
    session: Session = Depends(get_session),
):
    current_user.rest_timer_enabled = body.rest_timer_enabled
    session.commit()
    return body


@router.get("/training-profile", response_model=TrainingProfileOut | None)
def read_training_profile(
    current_user: User = Depends(require_permissions("profile:read")),
    session: Session = Depends(get_session),
):
    return session.get(TrainingProfile, current_user.id)


@router.put("/training-profile", response_model=TrainingProfileOut)
def save_training_profile(
    body: TrainingProfileIn,
    current_user: User = Depends(require_permissions("profile:write")),
    session: Session = Depends(get_session),
):
    profile = session.get(TrainingProfile, current_user.id)
    if profile is None:
        profile = TrainingProfile(user_id=current_user.id)
        session.add(profile)
    profile.age = body.age
    profile.weight_kg = Decimal(str(body.weight_kg)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    profile.height_cm = body.height_cm
    session.commit()
    session.refresh(profile)
    return profile


@router.delete("/training-profile", status_code=status.HTTP_204_NO_CONTENT)
def delete_training_profile(
    current_user: User = Depends(require_permissions("profile:write")),
    session: Session = Depends(get_session),
):
    profile = session.get(TrainingProfile, current_user.id)
    if profile is not None:
        session.delete(profile)
        session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(
    body: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    """Resposta idêntica exista o e-mail ou não (evita enumeração de usuários)."""
    user = get_user_by_email(body.email, session)
    if user is not None and user.is_active:
        token = create_password_reset_token(user, session)
        # O envio (lento) acontece depois da resposta
        background_tasks.add_task(_send_reset_email_safely, user.email, token)

    return MessageResponse(message="Se o e-mail estiver cadastrado, enviaremos um link.")


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(body: ResetPasswordRequest, session: Session = Depends(get_session)):
    if not reset_password_with_token(body.token, body.new_password.get_secret_value(), session):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token inválido, expirado ou já utilizado.",
        )
    return MessageResponse(message="Senha redefinida com sucesso. Você já pode fazer login.")


@router.patch("/change-password", response_model=MessageResponse)
def change_my_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(require_permissions("profile:write")),
    session: Session = Depends(get_session),
):
    if not change_password(
        current_user,
        body.current_password.get_secret_value(),
        body.new_password.get_secret_value(),
        session,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Senha atual incorreta."
        )
    return MessageResponse(message="Senha atualizada com sucesso.")
