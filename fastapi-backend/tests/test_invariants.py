"""Tests for the invariants the *database* is supposed to enforce.

These are the tests worth having in phase 1: each one would catch a real bug
if the schema drifted from what PLAN.md §5 says the database has to enforce.
They deliberately try to write bad data through the ORM and assert the DB
refuses — because "the code checked" is not enough.
"""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

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


# ── Helpers ──────────────────────────────────────────────────────────────────
# Small builders so tests read as "given a project with Alice as admin, ..."
# rather than five lines of ORM plumbing each.

def _mk_user(db: Session, email: str) -> User:
    u = User(
        id=uuid.uuid4(),
        email=email,
        full_name=email.split("@", 1)[0].title(),
        password_hash="not-a-real-hash",
    )
    db.add(u)
    db.flush()
    return u


def _mk_project(db: Session, key: str, admin: User) -> Project:
    p = Project(id=uuid.uuid4(), key=key, name=f"{key} project", created_by=admin.id)
    db.add(p)
    db.flush()
    db.add(
        ProjectMember(project_id=p.id, user_id=admin.id, role=MemberRole.ADMIN)
    )
    db.flush()
    return p


def _mk_task(
    db: Session,
    project: Project,
    number: int,
    created_by: User,
    assignee: User | None = None,
) -> Task:
    t = Task(
        id=uuid.uuid4(),
        project_id=project.id,
        number=number,
        title=f"task {number}",
        status=TaskStatus.TODO,
        priority=TaskPriority.MEDIUM,
        assignee_id=assignee.id if assignee else None,
        created_by=created_by.id,
    )
    db.add(t)
    db.flush()
    return t


# ── The invariants ───────────────────────────────────────────────────────────

def test_assigning_task_to_non_member_is_rejected(db: Session) -> None:
    """The composite FK must fire when a task is assigned to a non-member.

    This is the phase's marquee test — the whole reason the composite FK
    exists. Alice is a member of WEB, Bob is not. A task in WEB assigned to
    Bob must fail at the storage layer, not because we remembered to check
    in application code.
    """
    alice = _mk_user(db, "alice@example.com")
    bob = _mk_user(db, "bob@example.com")
    web = _mk_project(db, "WEB", admin=alice)
    # Note: Bob is deliberately NOT added to WEB.

    with pytest.raises(IntegrityError) as exc:
        _mk_task(db, web, number=1, created_by=alice, assignee=bob)

    # Belt-and-suspenders: assert it's *our* FK that fired, not some other
    # constraint. If a future migration renames it, this test will tell us.
    assert "fk_tasks_assignee_is_project_member" in str(exc.value)


def test_unassigned_task_is_allowed(db: Session) -> None:
    """A NULL assignee must not trip the composite FK.

    SQL's default MATCH SIMPLE says a FK with any NULL column is skipped.
    This test proves we didn't accidentally break "unassigned is a valid
    state" while enforcing the invariant above.
    """
    alice = _mk_user(db, "alice@example.com")
    web = _mk_project(db, "WEB", admin=alice)
    t = _mk_task(db, web, number=1, created_by=alice, assignee=None)
    assert t.assignee_id is None


def test_project_task_number_is_unique(db: Session) -> None:
    """(project_id, number) is unique — two 'WEB-1's are not allowed."""
    alice = _mk_user(db, "alice@example.com")
    web = _mk_project(db, "WEB", admin=alice)
    _mk_task(db, web, number=1, created_by=alice, assignee=alice)

    with pytest.raises(IntegrityError) as exc:
        _mk_task(db, web, number=1, created_by=alice, assignee=alice)

    assert "uq_tasks_project_number" in str(exc.value)


def test_deleting_task_deletes_its_comments(db: Session) -> None:
    """ON DELETE CASCADE on comments.task_id must actually cascade."""
    alice = _mk_user(db, "alice@example.com")
    web = _mk_project(db, "WEB", admin=alice)
    task = _mk_task(db, web, number=1, created_by=alice, assignee=alice)
    db.add_all(
        [
            Comment(id=uuid.uuid4(), task_id=task.id, author_id=alice.id, body="one"),
            Comment(id=uuid.uuid4(), task_id=task.id, author_id=alice.id, body="two"),
        ]
    )
    db.commit()
    assert db.scalar(sa.select(sa.func.count()).select_from(Comment)) == 2

    # Delete the task at the SQL layer to prove the DB does the cascade —
    # not the ORM's own cascade rules.
    db.execute(sa.delete(Task).where(Task.id == task.id))
    db.commit()

    assert db.scalar(sa.select(sa.func.count()).select_from(Comment)) == 0


def test_email_lowercase_enforced_by_check(db: Session) -> None:
    """The CHECK constraint rejects a non-lowercase email inserted via raw SQL.

    The ORM validator handles well-behaved writers; this test proves the DB
    doesn't rely on the ORM for correctness.
    """
    with pytest.raises(IntegrityError) as exc:
        db.execute(
            sa.text(
                "INSERT INTO users (id, email, full_name, password_hash) "
                "VALUES (:id, :email, :name, :h)"
            ),
            {
                "id": uuid.uuid4(),
                "email": "MiXeD@Example.com",
                "name": "Mixed Case",
                "h": "x",
            },
        )
        db.commit()

    assert "ck_users_email_lowercase" in str(exc.value)
