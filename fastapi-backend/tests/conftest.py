"""Shared pytest fixtures.

There is no separate test database — these tests run against the same
Postgres that ``docker compose up db`` starts. The trade is speed against a
tiny risk of stepping on developer data. The dataset in that database is
whatever the seed script produced, and every test starts by wiping it and
building the fixture rows it actually needs.

Two fixtures:

- ``engine`` (session-scoped) — one SQLAlchemy engine for the whole test run,
  with the schema built via Alembic before anything else. Building the schema
  once, rather than per test, cuts a couple of seconds off every ``pytest``.
- ``db`` (function-scoped) — a fresh session per test, and a TRUNCATE of every
  table between tests. This is the "isolated between tests" property; without
  it, one test's rows leak into the next test's assertions.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.db import SessionLocal, engine as app_engine


@pytest.fixture(scope="session")
def engine() -> Engine:
    """Return the app's engine, with a fresh schema built via Alembic.

    We DROP anything left from a previous run before running ``upgrade
    head`` — a partial schema from an aborted migration would make ``upgrade
    head`` a no-op on ``alembic_version``, and the tests would run against
    stale tables. Nuking is cheaper than reasoning about the state.
    """
    with app_engine.begin() as conn:
        conn.execute(
            text(
                # Cascade drops the enum-dependent columns, and the DROP TYPEs
                # clean up the native enum types Alembic created.
                "DROP TABLE IF EXISTS alembic_version, comments, tasks, "
                "project_members, projects, users CASCADE"
            )
        )
        conn.execute(
            text(
                "DROP TYPE IF EXISTS task_status, task_priority, member_role"
            )
        )

    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
    return app_engine


@pytest.fixture
def db(engine: Engine) -> Generator[Session, None, None]:
    """Yield a fresh session with all tables truncated."""
    # RESTART IDENTITY resets any serial columns we might add later; CASCADE
    # cuts through the FK graph so we don't need to spell the order.
    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE users, projects, project_members, tasks, comments "
                "RESTART IDENTITY CASCADE"
            )
        )

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
