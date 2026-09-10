"""The FastAPI application. Routers are mounted here and nowhere else.

Run it locally with::

    uv run uvicorn app.main:app --reload --port 8000

Then open http://localhost:8000/docs for the interactive API page FastAPI
generates from the type hints. (Phase 12 puts this behind a Dockerfile; until
then it runs on your machine against the Postgres that Compose publishes.)
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import auth, projects

settings = get_settings()

app = FastAPI(
    title="TaskFlow API",
    version="0.1.0",
    description=(
        "The system of record. Owns the data, enforces the rules, "
        "knows nothing about MCP or AI."
    ),
)

# CORS — the browser-side frontend (5173) and chat client (8100) call this
# API from a different origin than the one that served their HTML, and the
# browser blocks that unless we say it's allowed. Non-browser clients (the
# MCP server, curl, tests) don't care about any of this.
#
# `allow_credentials=True` is required for the `Authorization` header to be
# sent on cross-origin requests. It also means we can't use the wildcard
# origin — the list has to be explicit, which is why it comes from config.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(projects.router)


@app.get("/health", tags=["ops"])
def health() -> dict[str, str]:
    """Liveness check. Compose's healthcheck hits this in phase 12."""
    return {"status": "ok"}
