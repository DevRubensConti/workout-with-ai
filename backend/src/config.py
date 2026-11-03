from functools import lru_cache
from typing import Literal

from pydantic import EmailStr, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Workout AI"
    ENVIRONMENT: Literal["development", "testing", "production"] = "development"
    DEBUG: bool = False

    DATABASE_URL: str

    # Segredos obrigatórios: sem default de propósito, a app não sobe sem eles.
    SECRET_KEY: str = Field(min_length=32)
    PEPPER: str = Field(min_length=16)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # Cookie de sessão
    SECURE: bool = False
    SAME_SITE: Literal["lax", "strict", "none"] = "lax"
    COOKIE_DOMAIN: str | None = None

    ALLOWED_ORIGINS: str = "http://localhost:3000"
    FRONTEND_URL: str = "http://localhost:3000"

    GEMINI_API_KEY: SecretStr | None = None
    GEMINI_PERSONAL_DATA_ENABLED: bool = False
    GEMINI_MODEL: str = Field(default="gemini-3.6-flash", pattern=r"^gemini-[a-zA-Z0-9._-]+$")
    GEMINI_TIMEOUT_SECONDS: int = Field(default=90, ge=10, le=180)
    GEMINI_MAX_OUTPUT_TOKENS: int = Field(default=32768, ge=12000, le=65536)

    # E-mail (opcional)
    MAIL_SERVER: str | None = None
    MAIL_PORT: int = 587
    MAIL_USERNAME: str | None = None
    MAIL_PASSWORD: SecretStr | None = None
    MAIL_FROM: EmailStr | None = None
    MAIL_FROM_NAME: str = "Workout AI"
    MAIL_STARTTLS: bool = True
    MAIL_SSL_TLS: bool = False
    USE_CREDENTIALS: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    @property
    def mail_enabled(self) -> bool:
        return bool(self.MAIL_SERVER and self.MAIL_FROM)

    @property
    def cookie_domain(self) -> str | None:
        # Variável vazia no .env chega como "" e não pode virar domínio do cookie.
        return self.COOKIE_DOMAIN or None


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
