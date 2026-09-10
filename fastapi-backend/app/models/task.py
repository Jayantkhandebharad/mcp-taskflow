"""The ``tasks`` table — where the load-bearing composite FK lives.

The invariant this file is really about
=======================================
"A task's assignee must be a member of the task's project."

The naive way to write it is::

    assignee_id → users.id

That does not express the invariant at all — it only says "the assignee is
*some* user". You'd then need application code, on every path that writes a
task, to check ``(project_id, assignee_id) ∈ project_members``. Miss the
check once and you have bad data forever.

The right way is a **composite foreign key** into ``project_members``::

    (project_id, assignee_id) → project_members(project_id, user_id)

Now the invariant is a physical property of the database:

- ``project_members`` has PK ``(project_id, user_id)``. That's what makes it
  a valid FK target.
- INSERT/UPDATE fails at the storage layer if no matching membership row
  exists. No application code has to remember to check.
- SQL's default ``MATCH SIMPLE`` says: if *any* column of the FK is NULL,
  the constraint isn't checked. So ``assignee_id IS NULL`` (unassigned)
  passes through — exactly what we want. Unassigned tasks are allowed.
- Removing a user from a project fails (RESTRICT is the default) while they
  still have tasks assigned. That is arguably the right rule — the app can
  unassign first — and we accept the trade for now.

We deliberately do *not* add a separate ``assignee_id → users.id`` FK. It
would be redundant (``project_members`` already FKs to ``users``), and two
overlapping constraints are harder to reason about than one.
"""

import uuid
from datetime import date, datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import (
    TaskPriority,
    TaskStatus,
    task_priority_enum,
    task_status_enum,
)


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # The project this task lives in. A plain (non-composite) FK to projects
    # is required always — a task must live in a valid project.
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Per-project counter. Combined with the project key, this is what gives
    # us "WEB-14". Uniqueness of ``(project_id, number)`` is enforced by the
    # ``__table_args__`` UniqueConstraint below.
    number: Mapped[int] = mapped_column(sa.Integer, nullable=False)

    title: Mapped[str] = mapped_column(sa.Text, nullable=False)
    description: Mapped[str | None] = mapped_column(sa.Text, nullable=True)

    # Default handled in Python land; a server default would work too but
    # this keeps the enum's default visible in the model.
    status: Mapped[TaskStatus] = mapped_column(
        task_status_enum, nullable=False, default=TaskStatus.TODO
    )
    priority: Mapped[TaskPriority] = mapped_column(
        task_priority_enum, nullable=False, default=TaskPriority.MEDIUM
    )

    # Nullable on purpose — see the module docstring. The composite FK below
    # ties this to project_members when it *is* set.
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    # Author of the row. Plain FK to users — no membership check, because a
    # user who later leaves a project can still be recorded as the creator.
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
    )

    due_date: Mapped[date | None] = mapped_column(sa.Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        # ``onupdate`` fires on ORM updates; the seed writes rows directly so
        # it sets the value itself. When the FastAPI routers arrive (phase 3)
        # they will just PATCH via the ORM and pick this up for free.
        onupdate=sa.func.now(),
    )

    # ── Relationships ────────────────────────────────────────────────────────
    # A relationship is a Python attribute the ORM fills in by following a
    # foreign key. None of these change the schema — they only tell the ORM
    # how to *read* rows that already point at each other. (Phase 3 added
    # them; no migration was needed.)

    # A task is never shown without its project's key ("WEB-14" needs "WEB"),
    # so load the project in the same query. `lazy="joined"` means one SQL
    # JOIN instead of one extra SELECT per task; `innerjoin=True` because
    # project_id is NOT NULL — an INNER JOIN can never drop a row here and
    # is cheaper than the LEFT OUTER JOIN the ORM would otherwise emit.
    project: Mapped["Project"] = relationship(  # noqa: F821
        lazy="joined", innerjoin=True
    )

    # The assignee, as a User. Two things to know:
    #
    # 1. `assignee_id` has no FK to `users` — the only constraint on it is the
    #    composite FK into project_members (see __table_args__). The ORM can't
    #    infer a join from that, so `primaryjoin` spells the join out and
    #    `foreign_keys` says "treat assignee_id as the pointer".
    # 2. `viewonly=True`: this attribute is for *reading*. Writes go through
    #    `assignee_id`, so the composite FK is always what the database
    #    checks. The cost — the first draft of phase 3 hit it — is that after
    #    you change `assignee_id` the ORM does NOT re-read this attribute on
    #    its own (the session keeps loaded objects after commit; see
    #    expire_on_commit=False in db.py). A route that changes the assignee
    #    must `db.refresh(task)` before returning it, or it answers with the
    #    old person.
    #
    # `lazy="selectin"` loads assignees for a whole list of tasks in one
    # extra SELECT ... WHERE id IN (...), rather than one per task.
    assignee: Mapped["User | None"] = relationship(  # noqa: F821
        "User",
        primaryjoin="Task.assignee_id == User.id",
        foreign_keys="Task.assignee_id",
        viewonly=True,
        lazy="selectin",
    )

    # cascade="all, delete-orphan" + passive_deletes=True: the DB does the
    # cascade (see the FK on Comment.task_id below), the ORM stays out of the
    # way and doesn't emit N extra DELETEs.
    comments: Mapped[list["Comment"]] = relationship(  # noqa: F821
        back_populates="task",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # ── Derived attributes ───────────────────────────────────────────────────
    # These are plain properties, not columns. Pydantic's `from_attributes`
    # reads them like any other attribute, so the API can answer with
    # "WEB-14" without a database column that would have to be kept in sync
    # with `project.key`.
    @property
    def ref(self) -> str:
        """The human (and language-model) identifier: ``"WEB-14"``."""
        return f"{self.project.key}-{self.number}"

    @property
    def project_key(self) -> str:
        return self.project.key

    __table_args__ = (
        # Per-project ticket number is unique — this is what "WEB-14" rests on.
        sa.UniqueConstraint("project_id", "number", name="uq_tasks_project_number"),
        # THE composite FK. This is the invariant this file exists for.
        sa.ForeignKeyConstraint(
            ["project_id", "assignee_id"],
            ["project_members.project_id", "project_members.user_id"],
            name="fk_tasks_assignee_is_project_member",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"Task(id={self.id!s}, project_id={self.project_id!s}, "
            f"number={self.number}, status={self.status.value})"
        )
