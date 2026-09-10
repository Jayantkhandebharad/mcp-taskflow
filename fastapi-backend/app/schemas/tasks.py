"""Request and response bodies for tasks."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import TaskPriority, TaskStatus
from app.schemas.auth import UserRef


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    # A user id, not an email: the members list (GET /projects/{key}/members)
    # gives a client the ids. The MCP server's `assign_task` takes an email
    # and translates it to an id with that list — the translation lives
    # there, the API stays one-shape. Must be a member; the handler checks
    # and the composite FK backs it up.
    assignee_id: uuid.UUID | None = None
    due_date: date | None = None


class TaskPatch(BaseModel):
    """A partial update. Every field is optional; only the ones sent change.

    Two different things a client can say about a field, and both matter:

    - **leave it out**  → don't touch it.
    - **send ``null``** → clear it (unassign, drop the due date).

    Pydantic tracks which fields were actually present in the JSON
    (``model_fields_set``); the handler uses ``model_dump(exclude_unset=True)``
    to get only those. So ``{"assignee_id": null}`` unassigns, and ``{}``
    changes nothing.

    ``title``, ``status`` and ``priority`` can't be cleared — a task always
    has them. Declaring them as ``str`` (not ``str | None``) with a default
    of ``None`` gets exactly that: leaving them out is fine (the default is
    never validated), sending ``null`` is a 422 instead of a NOT NULL error
    from the database. It reads oddly, hence this paragraph.
    """

    title: str = Field(default=None, min_length=1, max_length=500)  # type: ignore[assignment]
    description: str | None = None
    status: TaskStatus = None  # type: ignore[assignment]
    priority: TaskPriority = None  # type: ignore[assignment]
    assignee_id: uuid.UUID | None = None
    due_date: date | None = None


class TaskOut(BaseModel):
    """A task as every route returns it.

    ``ref`` ("WEB-14") and ``project_key`` are properties on the ORM model,
    and ``assignee`` is a relationship — ``from_attributes`` reads all three
    the same way it reads a column. See models/task.py.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ref: str
    project_key: str
    number: int
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    assignee: UserRef | None
    created_by: uuid.UUID
    due_date: date | None
    created_at: datetime
    updated_at: datetime
