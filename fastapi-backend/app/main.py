"""The FastAPI application. Routers are mounted here and nowhere else.

Run it locally with::

    uv run uvicorn app.main:app --reload --port 8000

Then open http://localhost:8000/docs for the interactive API page FastAPI
generates from the type hints. (Phase 12 puts this behind a Dockerfile; until
then it runs on your machine against the Postgres that Compose publishes.)
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.routers import auth, comments, me, projects, tasks

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
app.include_router(tasks.router)
app.include_router(comments.router)
app.include_router(me.router)


@app.exception_handler(IntegrityError)
def integrity_error_is_a_conflict(_: Request, exc: IntegrityError) -> JSONResponse:
    """Turn a database constraint violation into a 409, not a 500.

    Every rule the database enforces (unique project key, unique task
    number, assignee-must-be-member) is *also* checked in the handler that
    could break it, with a message that says what to do. So in normal use
    this never runs. It exists for the race those checks can't see: two
    requests that both pass "is the key taken?" and then both INSERT. The
    loser lands here, and gets a conflict with the constraint's name — a
    client can retry; a 500 would tell it nothing.

    No HTTP test reaches this on purpose: making two requests collide
    inside TestClient would need two real connections racing, and the
    argument for correctness is the constraint itself, not a test.
    """
    diag = getattr(exc.orig, "diag", None)  # psycopg attaches the details here
    name = getattr(diag, "constraint_name", None) or "a database constraint"
    return JSONResponse(
        status_code=409,
        content={"detail": f"The request conflicts with {name}. Re-read and try again."},
    )


@app.get("/health", tags=["ops"])
def health() -> dict[str, str]:
    """Liveness check. Compose's healthcheck hits this in phase 12."""
    return {"status": "ok"}
