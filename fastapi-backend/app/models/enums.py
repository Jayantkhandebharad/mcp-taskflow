"""The enum types used by our tables.

These are Python ``str`` enums (so the value is JSON-safe and human-readable
in logs) *and* Postgres native ``ENUM`` types (so bad values are rejected at
the database level, not just by the app).

Each ``sa.Enum(...)`` below has:

- ``name=`` — the Postgres type name; without this you get a nonsense
  generated name that Alembic then can't manage.
- ``values_callable=lambda e: [m.value for m in e]`` — otherwise SQLAlchemy
  writes the *Python attribute names* (``TaskStatus.IN_PROGRESS``) into the
  DB, not the lowercase values (``in_progress``) we want.
- ``native_enum=True`` — the default, but stating it makes the intent
  obvious: this is a real Postgres type, not a check-constraint pretending
  to be one.
"""

from enum import Enum

import sqlalchemy as sa


class TaskStatus(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    DONE = "done"


class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class MemberRole(str, Enum):
    ADMIN = "admin"
    MEMBER = "member"


# Factory helpers so every column definition uses identical settings.
def _enum(py_enum: type[Enum], name: str) -> sa.Enum:
    return sa.Enum(
        py_enum,
        name=name,
        values_callable=lambda e: [m.value for m in e],
        native_enum=True,
    )


task_status_enum = _enum(TaskStatus, "task_status")
task_priority_enum = _enum(TaskPriority, "task_priority")
member_role_enum = _enum(MemberRole, "member_role")
