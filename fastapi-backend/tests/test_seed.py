"""Tests for the seed script.

The only interesting property is idempotency: running the seed a second
time must not error and must leave exactly the dataset the first run
produced. The row counts *and* the primary keys (which are deterministic
uuid5 values) both have to match — a change of either would mean a rerun
produced different data.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.models import Comment, Project, ProjectMember, Task, User
from scripts import seed


def _snapshot(db: Session) -> dict[str, tuple[int, list]]:
    """Return per-table (row count, sorted list of ids) — enough to
    compare two seeds byte-for-byte on identity.
    """
    return {
        "users": (
            db.scalar(sa.select(sa.func.count()).select_from(User)) or 0,
            sorted(str(u) for u in db.scalars(sa.select(User.id)).all()),
        ),
        "projects": (
            db.scalar(sa.select(sa.func.count()).select_from(Project)) or 0,
            sorted(str(p) for p in db.scalars(sa.select(Project.id)).all()),
        ),
        "project_members": (
            db.scalar(sa.select(sa.func.count()).select_from(ProjectMember))
            or 0,
            sorted(
                (str(pm.project_id), str(pm.user_id))
                for pm in db.scalars(sa.select(ProjectMember)).all()
            ),
        ),
        "tasks": (
            db.scalar(sa.select(sa.func.count()).select_from(Task)) or 0,
            sorted(str(t) for t in db.scalars(sa.select(Task.id)).all()),
        ),
        "comments": (
            db.scalar(sa.select(sa.func.count()).select_from(Comment)) or 0,
            sorted(str(c) for c in db.scalars(sa.select(Comment.id)).all()),
        ),
    }


def test_seed_is_idempotent(db: Session, engine: Engine) -> None:
    # First run against the truncated DB the `db` fixture leaves us.
    seed.main()
    first = _snapshot(db)

    # Row counts we deliberately picked so a regression is obvious.
    assert first["users"][0] == 3
    assert first["projects"][0] == 2
    assert first["project_members"][0] == 4
    assert first["tasks"][0] == 15
    assert first["comments"][0] == 4

    # Second run — no errors, identical dataset.
    seed.main()
    # Re-open a session so we see the second-run data, not the first-run
    # cache. (The wipe-then-insert inside seed.main() would otherwise appear
    # as "gone" to our session's identity map.)
    db.expire_all()
    second = _snapshot(db)

    assert first == second
