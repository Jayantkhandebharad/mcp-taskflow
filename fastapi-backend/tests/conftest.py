"""Shared pytest fixtures.

There is no separate test database — these tests run against the same
Postgres that ``docker compose up db`` starts. The trade is speed against a
tiny risk of stepping on developer data. The dataset in that database is
whatever the seed script produced, and every test starts by wiping it and
building the fixture rows it actually needs.

Three fixtures:

- ``engine`` (session-scoped) — one SQLAlchemy engine for the whole test run,
  with the schema built via Alembic before anything else. Building the schema
  once, rather than per test, cuts a couple of seconds off every ``pytest``.
- ``db`` (function-scoped) — a fresh session per test, and a TRUNCATE of every
  table between tests. This is the "isolated between tests" property; without
  it, one test's rows leak into the next test's assertions.
- ``client`` (function-scoped) — a FastAPI ``TestClient`` on top of ``db``,
  for tests that go through HTTP (phase 2 onwards).
- ``seeded`` (function-scoped) — runs the demo seed on the truncated tables,
  so a test can talk about WEB, API, Alice, Bob and Carol by name (phase 3
  onwards). The seed is the dataset the blog posts show; testing against it
  means the tests and the screenshots agree.
- ``token_for`` (function-scoped) — a real ``POST /auth/login`` for a seeded
  user, cached for the rest of the run. See the fixture for why the cache
  survives the TRUNCATE between tests.
"""

from __future__ import annotations

from collections.abc import Callable, Generator
import uuid

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.db import SessionLocal, engine as app_engine
from app.main import app
from scripts import seed

# The seed's three people. Every password is "password" (scripts/seed.py).
ALICE = "alice@example.com"  # admin of WEB and API
BOB = "bob@example.com"  # member of WEB only
CAROL = "carol@example.com"  # member of API only
SEED_PASSWORD = "password"


def bearer(token: str) -> dict[str, str]:
    """The header every authenticated request carries."""
    return {"Authorization": f"Bearer {token}"}


def uid(email: str) -> uuid.UUID:
    """The seeded user's id, without a query — seed ids are uuid5 of the email."""
    return seed._id("user", email)


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


@pytest.fixture
def client(db: Session) -> Generator[TestClient, None, None]:
    """An HTTP client for the FastAPI app, in-process.

    Depends on ``db`` so every test that touches the API starts from
    truncated tables too. The app opens its *own* sessions via ``get_db`` —
    same engine, same database — so rows a test creates through ``db`` must
    be ``commit()``-ed before the app can see them.

    ``TestClient`` speaks real HTTP: headers, status codes, JSON bodies. It's
    the closest thing to "test like the real client" without a network.
    """
    with TestClient(app) as c:
        yield c


@pytest.fixture
def seeded(db: Session) -> None:
    """Load the demo dataset into the (truncated) tables.

    Cheap after the first call: the seed hashes its one demo password once
    per process and caches it, so re-seeding is ~30 plain INSERTs.
    """
    seed.main()


# Tokens are cached for the whole pytest run, across the TRUNCATE that
# separates tests. That works — and is worth understanding — because a JWT
# is a signed statement "this is user <id>", not a server-side session. The
# seed gives Alice the same uuid5 id every time, so a token minted in test 1
# still names the Alice that test 40 just re-seeded. `current_user` looks the
# id up fresh on every request; nothing about the token is stored server-side.
_TOKENS: dict[str, str] = {}


@pytest.fixture
def token_for(client: TestClient, seeded: None) -> Callable[[str], str]:
    """Return ``token_for(email)`` — a bearer token for a seeded user.

    The first call for each email is a real ``POST /auth/login`` (the way
    the frontend and the MCP server get theirs); later calls reuse it. Three
    logins per run, ~0.2 s each of bcrypt, instead of three per test.
    """

    def _get(email: str, password: str = SEED_PASSWORD) -> str:
        if email not in _TOKENS:
            r = client.post("/auth/login", json={"email": email, "password": password})
            assert r.status_code == 200, r.text
            _TOKENS[email] = r.json()["access_token"]
        return _TOKENS[email]

    return _get
