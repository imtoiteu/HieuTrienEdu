"""Application configuration.

Every setting is overridable by environment variable so the same image runs in dev, CI and
production. Defaults are chosen so that ``uvicorn app.main:app`` works with zero configuration
against a local SQLite file — that keeps the "clone and run" path short, while Docker Compose
supplies PostgreSQL via ``DATABASE_URL``.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", Path.cwd() / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- identity -------------------------------------------------------------------
    platform_name: str = "HieuTrienEducation"
    environment: str = Field(default="development")
    debug: bool = True

    # ---- database -------------------------------------------------------------------
    # SQLite default keeps the zero-dependency dev path working. Compose overrides it.
    database_url: str = Field(default=f"sqlite:///{REPO_ROOT / 'data' / 'hietedu.db'}")

    # ---- cache ----------------------------------------------------------------------
    # Optional. When unreachable the app degrades to an in-process cache rather than failing.
    redis_url: str | None = Field(default=None)

    # ---- auth -----------------------------------------------------------------------
    secret_key: str = Field(default="dev-only-insecure-secret-change-me")
    access_token_expire_minutes: int = 60 * 2
    refresh_token_expire_days: int = 30
    jwt_algorithm: str = "HS256"

    # ---- http -----------------------------------------------------------------------
    api_v1_prefix: str = "/api/v1"
    # Several ports are allowed by default because port 3000 is frequently already taken on a
    # developer machine; the web app falls back to the next free one.
    #
    # `NoDecode` is essential here. For a complex field type such as list[str], pydantic-settings
    # JSON-decodes the environment value *before* any validator runs — so a comma-separated
    # CORS_ORIGINS would raise SettingsError at import and the API would refuse to start, which
    # is exactly what Docker Compose passes. NoDecode hands the raw string to the validator below.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3100",
            "http://127.0.0.1:3100",
        ]
    )

    # ---- content --------------------------------------------------------------------
    content_dir: Path = Field(default=REPO_ROOT / "content")

    # ---- integrations (all optional, all abstracted) --------------------------------
    ai_provider: str = Field(default="disabled")  # disabled | echo | openai | anthropic
    ai_api_key: str | None = None
    ai_model: str | None = None

    live_class_provider: str = Field(default="manual")  # manual | zoom
    zoom_account_id: str | None = None
    zoom_client_id: str | None = None
    zoom_client_secret: str | None = None

    storage_provider: str = Field(default="local")  # local | s3 | r2 | external
    storage_bucket: str | None = None
    storage_public_base_url: str | None = None

    payment_provider: str = Field(default="manual")  # manual | vnpay | momo | stripe

    geogebra_enabled: bool = False

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Accept a JSON array or a comma-separated string.

        Because the field is annotated `NoDecode`, pydantic-settings hands us the raw environment
        string and does no JSON parsing of its own — so this validator has to handle both forms.
        Comma-separated is what a human writes in a .env file or a Compose environment block;
        JSON is what tooling tends to emit.
        """
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("["):
                import json

                try:
                    return json.loads(stripped)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"CORS_ORIGINS looks like JSON but is invalid: {exc}") from exc
            return [item.strip() for item in stripped.split(",") if item.strip()]
        return value

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.is_sqlite:
        # Ensure the parent directory of the SQLite file exists before SQLAlchemy connects.
        raw = settings.database_url.split("///", 1)[-1]
        Path(raw).parent.mkdir(parents=True, exist_ok=True)
    return settings


settings = get_settings()
