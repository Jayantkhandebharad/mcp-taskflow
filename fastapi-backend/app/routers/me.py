"""``/me`` — things about the caller that cut across projects.

PLAN.md §7::

    GET /me/tasks          → assigned to me, across projects
    GET /me/capabilities   → { "can_admin_any_project": bool, ... }

Not in PLAN.md §3's list of router files; it got its own because neither
route belongs to a project, and ``/auth/me`` (who am I) is a different
question from ``/me/*`` (what's mine, what may I do).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user
from app.models import MemberRole, Project, ProjectMember, Task, User
from app.schemas.me import CapabilitiesOut
from app.schemas.tasks import TaskOut

router = APIRouter(prefix="/me", tags=["me"])


@router.get("/tasks", response_model=list[TaskOut])
def my_tasks(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[Task]:
    """Everything assigned to the caller, in every project they're in.

    No membership check is needed: the composite FK guarantees an assignee
    is a member, so "assigned to me" already implies "I may see it". Sorted
    by due date with undated tasks last — the order someone would work in.
    """
    query = (
        select(Task)
        .where(Task.assignee_id == user.id)
        .order_by(Task.due_date.asc().nulls_last(), Task.project_id, Task.number)
    )
    return list(db.scalars(query))


@router.get("/capabilities", response_model=CapabilitiesOut)
def my_capabilities(
    user: User = Depends(current_user), db: Session = Depends(get_db)
) -> CapabilitiesOut:
    """Which projects the caller admins. Read fresh from project_members —
    never from the token — so a promotion shows up on the next call."""
    keys = list(
        db.scalars(
            select(Project.key)
            .join(ProjectMember, ProjectMember.project_id == Project.id)
            .where(ProjectMember.user_id == user.id, ProjectMember.role == MemberRole.ADMIN)
            .order_by(Project.key)
        )
    )
    return CapabilitiesOut(can_admin_any_project=bool(keys), admin_project_keys=keys)
