"""Schemas Pydantic de entrada/saída do módulo de autenticação."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, StrictBool


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=120, description="Nome do usuário")
    email: EmailStr
    password: SecretStr = Field(..., min_length=8, max_length=128, description="Senha (8+)")


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: SecretStr = Field(..., min_length=1, max_length=128)


class ForgotPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(..., min_length=1, max_length=256)
    new_password: SecretStr = Field(..., min_length=8, max_length=128)


class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: SecretStr = Field(..., min_length=1, max_length=128)
    new_password: SecretStr = Field(..., min_length=8, max_length=128)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    email: str
    role: str
    permissions: list[str]


class MessageResponse(BaseModel):
    message: str


class WorkoutPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rest_timer_enabled: StrictBool


class TrainingProfileIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    age: int = Field(strict=True, ge=18, le=100)
    weight_kg: float = Field(ge=20, le=400, allow_inf_nan=False)
    height_cm: int = Field(strict=True, ge=100, le=250)


class TrainingProfileOut(TrainingProfileIn):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    updated_at: datetime
