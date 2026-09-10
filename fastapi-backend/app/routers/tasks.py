"""Tasks — under a project for listing and creating, by ref for everything else.

PLAN.md §7::

    GET    /projects/{key}/tasks     → filters: status, assignee_id, overdue
    POST   /projects/{key}/tasks     → create                        [member]
    GET    /tasks/{key}-{number}     → detail
    PATCH  /tasks/{key}-{number}     → partial update
    DELETE /tasks/{key}-{number}     → delete                        [admin]

Two path families, one file: everything about tasks is here. The router has
no prefix for that reason.

About ``/tasks/{key}-{number}``: Starlette turns that into the pattern
``(?P<key>[^/]+)-(?P<number>[^/]+)``, so ``WEB-14`` arrives as ``key="WEB"``,
``number="14"``, and FastAPI converts ``number`` to ``int`` (or answers 422).
Project keys can't contain hyphens (schemas/projects.py), so the split is
never ambiguous. No parsing code needed.
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi import status as http_status  # `status` is a query parameter below
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_project, get_task, require_admin, require_member
from app.models import Project, ProjectMember, Task, TaskStatus
from app.schemas.tasks import TaskCreate, TaskOut, TaskPatch

router = APIRouter(tags=["tasks"])


def _check_assignee(db: Session, project: Project, assignee_id: uuid.UUID | None) -> None:
    """409 unless ``assignee_id`` is a member of ``project`` (or is None).

    The database enforces this too — the composite FK on ``tasks`` — but a
    constraint violation surfaces as a 500 with a Postgres message. This
    check turns it into a sentence that says what to do next.
    """
    if assignee_id is None:
        return
    if db.get(ProjectMember, (project.id, assignee_id)) is None:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail=(
                f"User {assignee_id} is not a member of project {project.key!r}. "
                f"Add them with POST /projects/{project.key}/members first, "
                f"or pick someone from GET /projects/{project.key}/members."
            ),
        )


# ── Under a project ──────────────────────────────────────────────────────────


@router.get("/projects/{key}/tasks", response_model=list[TaskOut])
def list_tasks(
    status: TaskStatus | None = None,
    assignee_id: uuid.UUID | None = None,
    overdue: bool = False,
    project: Project = Depends(get_project),
    _: ProjectMember = Depends(require_member),
    db: Session = Depends(get_db),
) -> list[Task]:
    """The project's tasks, oldest first, with optional filters.

    Filters combine with AND. ``overdue`` is a flag, not a value: a client
    either asks for overdue tasks or doesn't, so ``false`` and "absent" mean
    the same thing. "Overdue" is *past due and not done* — a finished task
    is never overdue, however late it was.
    """
    query = select(Task).where(Task.project_id == project.id).order_by(Task.number)
    if status is not None:
        query = query.where(Task.status == status)
    if assignee_id is not None:
        query = query.where(Task.assignee_id == assignee_id)
    if overdue:
        # Server-local date. Good enough for a learning app; a real one
        # would take the client's timezone into account.
        query = query.where(Task.due_date < date.today(), Task.status != TaskStatus.DONE)
    return list(db.scalars(query))


@router.post(
    "/projects/{key}/tasks", response_model=TaskOut, status_code=http_status.HTTP_201_CREATED
)
def create_task(
    body: TaskCreate,
    project: Project = Depends(get_project),
    member: ProjectMember = Depends(require_member),
    db: Session = Depends(get_db),
) -> Task:
    """Create a task. Any member. It gets the project's next number.

    Where "next number" comes from — the one non-obvious part of this file:

    ``number`` is a per-project counter with no sequence behind it (the
    database only enforces that ``(project_id, number)`` is unique). So we
    compute ``MAX(number) + 1`` ourselves — and two requests doing that at
    the same moment would both read 8 and both try to insert 9; the UNIQUE
    constraint would reject the loser with a 500.

    The fix is to take a lock first. ``SELECT ... FOR UPDATE`` locks *rows*,
    and ``MAX(...)`` is an aggregate with no row to lock — so we lock the
    project's own row instead. Any other creator in the same project then
    waits at that line until this transaction commits, reads the new MAX,
    and gets the next number. Creates in *different* projects don't wait
    for each other. "One task at a time per project" is a cost nobody will
    ever notice in a tracker.
    """
    _check_assignee(db, project, body.assignee_id)

    db.execute(select(Project.id).where(Project.id == project.id).with_for_update())
    current_max = db.scalar(select(func.max(Task.number)).where(Task.project_id == project.id))
    next_number = (current_max or 0) + 1

    task = Task(
        project_id=project.id,
        number=next_number,
        title=body.title,
        description=body.description,
        status=body.status,
        priority=body.priority,
        assignee_id=body.assignee_id,
        created_by=member.user_id,
        due_date=body.due_date,
    )
    db.add(task)
    db.commit()
    # Re-read so `assignee` (a view-only relationship, see models/task.py)
    # and the server-side timestamps reflect the row we just wrote.
    db.refresh(task)
    return task


# ── By ref ───────────────────────────────────────────────────────────────────


@router.get("/tasks/{key}-{number}", response_model=TaskOut)
def get_task_detail(task: Task = Depends(get_task)) -> Task:
    """One task by ref, e.g. ``WEB-14``. Members only (via ``get_task``)."""
    return task


@router.patch("/tasks/{key}-{number}", response_model=TaskOut)
def update_task(
    body: TaskPatch,
    task: Task = Depends(get_task),
    project: Project = Depends(get_project),
    db: Session = Depends(get_db),
) -> Task:
    """Change any of: title, description, status, priority, assignee, due date.

    Any member may change anything, and any status may move to any other —
    no workflow rules. PLAN.md §1 keeps the app boring on purpose.
    """
    # Only the fields the client actually sent — see TaskPatch's docstring.
    changes = body.model_dump(exclude_unset=True)

    if changes.get("assignee_id") is not None:
        _check_assignee(db, project, changes["assignee_id"])

    for field, value in changes.items():
        setattr(task, field, value)
    # `updated_at` bumps by itself: the column's `onupdate` fires on any ORM
    # UPDATE (models/task.py). Nothing to do here.
    db.commit()
    # The first draft returned `task` straight after commit — and the
    # response showed the *old* assignee. `assignee` is a view-only
    # relationship the session had already loaded; changing `assignee_id`
    # doesn't re-read it. Refresh does.
    db.refresh(task)
    return task


@router.delete("/tasks/{key}-{number}", status_code=http_status.HTTP_204_NO_CONTENT)
def delete_task(
    task: Task = Depends(get_task),
    _: ProjectMember = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Response:
    """Delete a task and its comments. **Admins only.**

    This is the route the MCP server's tool gating will hide from members
    (phase 8) — and the route that still says no if a member calls it
    anyway. The gate is a courtesy; this 403 is the rule.
    """
    # Comments go with it: ON DELETE CASCADE on comments.task_id, and the
    # relationship is `passive_deletes=True`, so the ORM issues one DELETE
    # and lets Postgres do the rest.
    db.delete(task)
    db.commit()
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)
