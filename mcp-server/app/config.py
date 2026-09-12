"""Settings for the mcp-server service.

Environment variables only, like every service in this repo. Three of them
matter in phase 5:

- ``BACKEND_URL`` — where fastapi-backend is. ``http://localhost:8000`` while
  the backend runs on your machine; ``http://fastapi-backend:8000`` once both
  run inside Compose (phase 12) and reach each other by service name.
- ``TASKFLOW_EMAIL`` / ``TASKFLOW_PASSWORD`` — **stdio mode only.** Who the
  server acts as when a desktop client launches it. See ``auth.py`` for why
  stdio needs these and HTTP mode (phase 6) will not.

Why the ``.env`` path is absolute
=================================
The backend reads ``../.env`` relative to the *current directory*, because it
is always started from ``fastapi-backend/``. This server is not: Claude
Desktop launches it as a subprocess from whatever directory the app happens
to be in, with an almost empty environment (the MCP SDK's own stdio client
passes through only ``HOME``, ``PATH``, ``USER`` and three others). So we
locate the repo-root ``.env`` from this file's own location instead. A
missing file is fine — pydantic-settings just skips it — which is what will
happen inside a container, where Compose supplies the variables directly.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# mcp-server/app/config.py → parents[0]=app, [1]=mcp-server, [2]=the repo root.
REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    # Process environment wins over the file, so a launcher (Claude Desktop,
    # the tests) can override what's in `.env` without editing it.
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    backend_url: str = Field(default="http://localhost:8000", alias="BACKEND_URL")

    # No defaults on purpose: the server must not silently act as anyone.
    taskflow_email: str | None = Field(default=None, alias="TASKFLOW_EMAIL")
    taskflow_password: str | None = Field(default=None, alias="TASKFLOW_PASSWORD")


@lru_cache
def get_settings() -> Settings:
    """The process-wide Settings singleton (same pattern as the backend)."""
    return Settings()
