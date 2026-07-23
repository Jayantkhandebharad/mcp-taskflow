"""Deterministic, rerunnable demo data for TaskFlow.

Run it like this::

    uv run python -m scripts.seed
    # or:
    uv run python scripts/seed.py

What "deterministic" means
--------------------------
Every UUID this script writes is derived from a *name* via ``uuid.uuid5``.
Alice's UUID is ``uuid5(NAMESPACE, "alice@example.com")``, always. That means:

- Two developers running seed produce the same UUIDs, so screenshots and
  copy-pasted queries in blog posts refer to real, findable rows.
- Tests can hard-code an expected UUID and never flake.
- Re-running the seed produces the same primary keys, so we can wipe the
  data and re-insert it without any risk of drift.

What "rerunnable" means
-----------------------
``main()`` is a single transaction:

    BEGIN
    DELETE FROM comments, tasks, project_members, projects, users
    INSERT everything fresh
    COMMIT

Either the whole thing lands or nothing does. Running it a second time
produces byte-identical data. There is no "seed only if empty" branch and
no upsert logic — wipe-then-insert is the shortest thing that survives
schema changes without needing constant edits.

The dataset itself
------------------
- **3 users** — Alice (admin), Bob, Carol.
- **2 projects** — WEB (Alice admin, Bob member), API (Alice admin,
  Carol member).
- **~15 tasks** across both projects, covering every status and priority,
  with a few overdue due-dates so later MCP tools like ``overdue_tasks``
  and ``project_summary`` have something interesting to show.
- **A handful of comments** on a few tasks.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

from passlib.context import CryptContext
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import (
    Comment,
    MemberRole,
    Project,
    ProjectMember,
    Task,
    TaskPriority,
    TaskStatus,
    User,
)

# ── Deterministic-UUID setup ─────────────────────────────────────────────────
# A fixed UUID5 namespace so uuid5(NAMESPACE, "alice@example.com") is
# reproducible across machines. The value itself is arbitrary — what matters
# is that it never changes.
NAMESPACE = uuid.UUID("6c8a1b2e-7d3f-4e5a-9b0c-1f2d3e4a5b6c")


def _id(kind: str, *parts: str) -> uuid.UUID:
    """Return a deterministic UUID for a named object.

    ``_id("user", "alice@example.com")`` and
    ``_id("task", "WEB", "1")`` both always produce the same UUID.
    """
    return uuid.uuid5(NAMESPACE, ":".join([kind, *parts]))


# passlib is intentionally reused across every seeded user — bcrypt is
# expensive (that's the point), and we only need one hash per distinct
# password.
_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
_HASH_CACHE: dict[str, str] = {}


def _hash(pw: str) -> str:
    if pw not in _HASH_CACHE:
        _HASH_CACHE[pw] = _pwd.hash(pw)
    return _HASH_CACHE[pw]


# A single "now" for the whole seed so re-runs don't drift by microseconds.
_NOW = datetime(2026, 7, 23, 12, 0, 0, tzinfo=UTC)
_TODAY = _NOW.date()


def _wipe(db: Session) -> None:
    """Delete every row in the five tables, in reverse-dependency order.

    Comments before tasks (task_id FK), tasks before project_members
    (composite FK), project_members before projects and users. ``DELETE``
    rather than ``TRUNCATE`` so this stays valid when a future migration
    partitions a table or a test wants finer control.
    """
    db.execute(delete(Comment))
    db.execute(delete(Task))
    db.execute(delete(ProjectMember))
    db.execute(delete(Project))
    db.execute(delete(User))


def _seed(db: Session) -> None:
    # ── Users ────────────────────────────────────────────────────────────────
    # Everyone's password is "password" for demos. Real login for these
    # accounts (phase 2 onwards) will still bcrypt-verify — the demo password
    # is deliberately obvious rather than a real user's actual choice.
    users = {
        "alice": User(
            id=_id("user", "alice@example.com"),
            email="alice@example.com",
            full_name="Alice Adams",
            password_hash=_hash("password"),
            created_at=_NOW,
        ),
        "bob": User(
            id=_id("user", "bob@example.com"),
            email="bob@example.com",
            full_name="Bob Brown",
            password_hash=_hash("password"),
            created_at=_NOW,
        ),
        "carol": User(
            id=_id("user", "carol@example.com"),
            email="carol@example.com",
            full_name="Carol Chen",
            password_hash=_hash("password"),
            created_at=_NOW,
        ),
    }
    db.add_all(users.values())
    db.flush()  # settle FKs before the next batch of inserts

    # ── Projects ─────────────────────────────────────────────────────────────
    projects = {
        "WEB": Project(
            id=_id("project", "WEB"),
            key="WEB",
            name="TaskFlow Web",
            description="The React frontend and the routes that serve it.",
            created_by=users["alice"].id,
            created_at=_NOW,
        ),
        "API": Project(
            id=_id("project", "API"),
            key="API",
            name="TaskFlow API",
            description="The FastAPI backend and its data model.",
            created_by=users["alice"].id,
            created_at=_NOW,
        ),
    }
    db.add_all(projects.values())
    db.flush()

    # ── Memberships ──────────────────────────────────────────────────────────
    # Alice is admin of both; Bob is a member of WEB only; Carol is a member
    # of API only. This gives us clean cross-project tests: assigning a WEB
    # task to Carol must fail the composite FK.
    memberships = [
        ProjectMember(
            project_id=projects["WEB"].id,
            user_id=users["alice"].id,
            role=MemberRole.ADMIN,
            added_at=_NOW,
        ),
        ProjectMember(
            project_id=projects["WEB"].id,
            user_id=users["bob"].id,
            role=MemberRole.MEMBER,
            added_at=_NOW,
        ),
        ProjectMember(
            project_id=projects["API"].id,
            user_id=users["alice"].id,
            role=MemberRole.ADMIN,
            added_at=_NOW,
        ),
        ProjectMember(
            project_id=projects["API"].id,
            user_id=users["carol"].id,
            role=MemberRole.MEMBER,
            added_at=_NOW,
        ),
    ]
    db.add_all(memberships)
    db.flush()

    # ── Tasks ────────────────────────────────────────────────────────────────
    # Table of task specs. Every status and priority appears at least once,
    # a few tasks have due dates (some overdue), and a few are unassigned.
    # ``assignee`` is a key into ``users`` or None.
    Spec = tuple[str, int, str, TaskStatus, TaskPriority, str | None, date | None]
    task_specs: list[Spec] = [
        # WEB — 8 tasks
        ("WEB", 1, "Set up Vite + Tailwind",
            TaskStatus.DONE, TaskPriority.HIGH, "alice",
            _TODAY - timedelta(days=20)),
        ("WEB", 2, "Login screen",
            TaskStatus.DONE, TaskPriority.HIGH, "bob",
            _TODAY - timedelta(days=15)),
        ("WEB", 3, "Projects list page",
            TaskStatus.IN_REVIEW, TaskPriority.MEDIUM, "bob",
            _TODAY + timedelta(days=2)),
        ("WEB", 4, "Task board (drag between columns)",
            TaskStatus.IN_PROGRESS, TaskPriority.HIGH, "bob",
            _TODAY - timedelta(days=3)),  # overdue
        ("WEB", 5, "Comments panel on task detail",
            TaskStatus.TODO, TaskPriority.MEDIUM, "alice",
            _TODAY + timedelta(days=7)),
        ("WEB", 6, "Members admin screen",
            TaskStatus.TODO, TaskPriority.LOW, None, None),  # unassigned
        ("WEB", 7, "Handle 401 by redirecting to /login",
            TaskStatus.IN_PROGRESS, TaskPriority.MEDIUM, "alice",
            _TODAY - timedelta(days=1)),  # overdue by a day
        ("WEB", 8, "Empty-state illustrations",
            TaskStatus.TODO, TaskPriority.LOW, None, None),  # unassigned

        # API — 7 tasks
        ("API", 1, "Design the five tables",
            TaskStatus.DONE, TaskPriority.HIGH, "alice",
            _TODAY - timedelta(days=25)),
        ("API", 2, "Alembic migration for the initial schema",
            TaskStatus.DONE, TaskPriority.HIGH, "alice",
            _TODAY - timedelta(days=22)),
        ("API", 3, "Auth: register + login + JWT",
            TaskStatus.IN_PROGRESS, TaskPriority.HIGH, "alice",
            _TODAY + timedelta(days=3)),
        ("API", 4, "Projects router + membership rules",
            TaskStatus.TODO, TaskPriority.HIGH, "carol",
            _TODAY + timedelta(days=5)),
        ("API", 5, "Tasks router with filters",
            TaskStatus.TODO, TaskPriority.MEDIUM, "carol",
            _TODAY + timedelta(days=10)),
        ("API", 6, "Comments router",
            TaskStatus.TODO, TaskPriority.LOW, None,
            _TODAY - timedelta(days=2)),  # overdue AND unassigned
        ("API", 7, "OpenAPI docs polish",
            TaskStatus.TODO, TaskPriority.LOW, "alice", None),
    ]

    tasks: dict[tuple[str, int], Task] = {}
    for key, number, title, status, priority, assignee_key, due in task_specs:
        assignee_id = users[assignee_key].id if assignee_key else None
        # created_by defaults to the project admin, Alice.
        created_by = users["alice"].id
        task = Task(
            id=_id("task", key, str(number)),
            project_id=projects[key].id,
            number=number,
            title=title,
            status=status,
            priority=priority,
            assignee_id=assignee_id,
            created_by=created_by,
            due_date=due,
            created_at=_NOW,
            updated_at=_NOW,
        )
        tasks[(key, number)] = task
        db.add(task)
    db.flush()

    # ── Comments ─────────────────────────────────────────────────────────────
    # Just enough that ``task/{key}-{n}`` renders as a real conversation.
    comments = [
        Comment(
            id=_id("comment", "WEB", "4", "1"),
            task_id=tasks[("WEB", 4)].id,
            author_id=users["alice"].id,
            body="Bumped priority — this is blocking the board demo.",
            created_at=_NOW - timedelta(days=2),
        ),
        Comment(
            id=_id("comment", "WEB", "4", "2"),
            task_id=tasks[("WEB", 4)].id,
            author_id=users["bob"].id,
            body="Have a proof-of-concept on a branch. PR tomorrow.",
            created_at=_NOW - timedelta(days=1),
        ),
        Comment(
            id=_id("comment", "API", "3", "1"),
            task_id=tasks[("API", 3)].id,
            author_id=users["alice"].id,
            body="Landed register + login. JWT signing next.",
            created_at=_NOW,
        ),
        Comment(
            id=_id("comment", "API", "6", "1"),
            task_id=tasks[("API", 6)].id,
            author_id=users["alice"].id,
            body="Needs an owner.",
            created_at=_NOW - timedelta(days=1),
        ),
    ]
    db.add_all(comments)


def main() -> None:
    """Wipe the five tables and re-seed them, all in one transaction."""
    with SessionLocal.begin() as db:  # opens a transaction, commits on success
        _wipe(db)
        _seed(db)
    print("seeded 3 users, 2 projects, 15 tasks, 4 comments")


if __name__ == "__main__":
    main()
