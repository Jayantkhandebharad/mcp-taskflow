"""Settings for the fastapi-backend service.

Every configurable value lives in an environment variable — nothing is read
from a file that isn't `.env`, and nothing is hardcoded. Twelve-factor, and
also the only pattern that survives once the same code has to run on a
developer laptop, in Compose, and (eventually) on real infrastructure.

Why we assemble ``DATABASE_URL`` from parts instead of reading it whole
=====================================================================
Phase 0 had this in ``.env``::

    POSTGRES_PASSWORD=taskflow_dev_only
    DATABASE_URL=postgresql+psycopg://taskflow:taskflow_dev_only@db:5432/taskflow

Two copies of the same password. Docker Compose *cannot* interpolate a
variable into another variable inside ``.env`` itself, so the obvious
``postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@...`` does not
work — Compose passes the literal string through, and the backend fails to
authenticate. See ``docs/briefs/phase-0.md``.

The fix, applied in phase 1: keep only the *parts* in the environment, and
have the backend assemble the URL here. One source of truth for the password.
"""

from functools import lru_cache

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Where pydantic-settings looks for values ─────────────────────────────
    # It reads process environment first, then the ``.env`` at the repo root.
    # ``extra="ignore"`` means unrelated variables (LLM_MODEL, VITE_API_URL,
    # everything meant for the other services) don't cause a validation error.
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Postgres connection, one part per env var ────────────────────────────
    # Defaults are development-only. Production must set every one explicitly.
    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_user: str = Field(default="taskflow", alias="POSTGRES_USER")
    postgres_password: str = Field(default="taskflow_dev_only", alias="POSTGRES_PASSWORD")
    postgres_db: str = Field(default="taskflow", alias="POSTGRES_DB")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        """The SQLAlchemy URL, assembled from the parts above.

        ``postgresql+psycopg://`` selects the psycopg 3 driver (not psycopg2,
        which SQLAlchemy would pick if we just said ``postgresql://``).
        """
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide Settings singleton.

    ``lru_cache`` is how we make ``Settings`` a singleton without a global. The
    first call parses env + ``.env``; every later call returns the same object.
    Tests that want a different config can call ``get_settings.cache_clear()``.
    """
    return Settings()
