"""Database plumbing: the engine, the session factory, the request dependency.

The engine is process-wide (one connection pool). Sessions are per-request:
each HTTP request gets one, and it is closed at the end of the request. The
``get_db`` generator is what FastAPI dependency-injects into route handlers
starting in phase 2. For phase 1, ``SessionLocal`` is what the seed script
and the tests use directly.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

_settings = get_settings()

# ── The engine ───────────────────────────────────────────────────────────────
# ``future=True`` selects SQLAlchemy 2.0 style even on 1.x — harmless on 2.x
# but a useful nudge for anyone reading the code that this is 2.0 territory.
# ``pool_pre_ping=True`` sends a cheap ``SELECT 1`` before handing a connection
# out of the pool. Costs a round-trip per checkout but silently fixes the
# common "connection was killed by the DB in the middle of the night" bug.
engine = create_engine(
    _settings.database_url,
    future=True,
    pool_pre_ping=True,
)

# ── Session factory ──────────────────────────────────────────────────────────
# ``expire_on_commit=False`` keeps ORM objects usable after ``commit()`` — the
# default (True) re-fetches every attribute on next access, which is surprising
# behaviour for a reader and irrelevant to us because we don't reuse sessions.
SessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """Yield a session, close it when the caller is done.

    FastAPI turns this into a request-scoped dependency::

        def route(db: Session = Depends(get_db)): ...

    The ``try/finally`` guarantees the session is closed even if the handler
    raises — otherwise we'd leak a connection out of the pool per crash.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
