"""``/projects`` — projects and their members.

PLAN.md §7::

    GET    /projects                          → projects I'm a member of
    POST   /projects                          → create; I become admin
    GET    /projects/{key}                    → detail + my role
    GET    /projects/{key}/members            → list members
    POST   /projects/{key}/members            → add member          [admin]
    DELETE /projects/{key}/members/{user_id}  → remove member       [admin]

The task routes under ``/projects/{key}/tasks`` live in routers/tasks.py,
next to the other task routes, so everything about tasks is in one file.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user, get_project, require_admin, require_member
from app.models import MemberRole, Project, ProjectMember, Task, User
from app.schemas.projects import MemberAdd, MemberOut, ProjectCreate, ProjectOut

router = APIRouter(prefix="/projects", tags=["projects"])


# ── Response builders ────────────────────────────────────────────────────────
# Two shapes that don't map 1:1 onto a table row: a project *plus the
# caller's role*, and a membership row *flattened with the user*. Spelling
# them out here keeps the handlers to "load, check, return".


def _project_out(project: Project, my_role: MemberRole) -> ProjectOut:
    return ProjectOut(
        id=project.id,
        key=project.key,
        name=project.name,
        description=project.description,
        created_by=project.created_by,
        created_at=project.created_at,
        my_role=my_role,
    )


def _member_out(member: ProjectMember) -> MemberOut:
    return MemberOut(
        user_id=member.user_id,
        email=member.user.email,
        full_name=member.user.full_name,
        role=member.role,
        added_at=member.added_at,
    )


# ── Projects ─────────────────────────────────────────────────────────────────


@router.get("", response_model=list[ProjectOut])
def list_projects(
    user: User = Depends(current_user), db: Session = Depends(get_db)
) -> list[ProjectOut]:
    """Projects the caller belongs to, with their role in each.

    The join *is* the authorisation: there's no "all projects" list. If you
    aren't in ``project_members`` for a project, it does not exist for you.
    """
    rows = db.execute(
        select(Project, ProjectMember.role)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .where(ProjectMember.user_id == user.id)
        .order_by(Project.key)
    ).all()
    return [_project_out(project, role) for project, role in rows]


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
    body: ProjectCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ProjectOut:
    """Create a project. The creator becomes its first admin.

    That second step is not a convenience — it's the only way a project ever
    gets an admin. Nobody else can add members to a project with none.
    """
    key = body.key.upper()

    # Checked here so the answer is a 409 with a sentence, not a 500 from the
    # UNIQUE constraint. The constraint is still there for the race where two
    # requests pass this check at once (see the IntegrityError handler in
    # main.py).
    exists = db.scalar(select(Project.id).where(Project.key == key))
    if exists is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Project key {key!r} is already taken",
        )

    project = Project(
        key=key, name=body.name, description=body.description, created_by=user.id
    )
    db.add(project)
    # Flush so `project.id` exists for the membership row, without committing
    # yet: both rows land in one transaction, or neither does.
    db.flush()
    db.add(ProjectMember(project_id=project.id, user_id=user.id, role=MemberRole.ADMIN))
    db.commit()
    return _project_out(project, MemberRole.ADMIN)


@router.get("/{key}", response_model=ProjectOut)
def get_project_detail(
    project: Project = Depends(get_project),
    member: ProjectMember = Depends(require_member),
) -> ProjectOut:
    """One project, with the caller's role in it. Members only."""
    return _project_out(project, member.role)


# ── Members ──────────────────────────────────────────────────────────────────


@router.get("/{key}/members", response_model=list[MemberOut])
def list_members(
    project: Project = Depends(get_project),
    _: ProjectMember = Depends(require_member),
    db: Session = Depends(get_db),
) -> list[MemberOut]:
    """Everyone in the project. Any member may look."""
    members = list(
        db.scalars(select(ProjectMember).where(ProjectMember.project_id == project.id))
    )
    # Admins first, then by email. The list is tiny, so sorting in Python
    # keeps the SQL to one line and the order stable across runs (the seed
    # gives every membership the same `added_at`).
    members.sort(key=lambda m: (m.role != MemberRole.ADMIN, m.user.email))
    return [_member_out(m) for m in members]


@router.post(
    "/{key}/members", response_model=MemberOut, status_code=status.HTTP_201_CREATED
)
def add_member(
    body: MemberAdd,
    project: Project = Depends(get_project),
    _: ProjectMember = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MemberOut:
    """Add a registered user to the project, by email. Admins only."""
    email = body.email.lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No user with email {email!r}. They need to register first.",
        )
    if db.get(ProjectMember, (project.id, user.id)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{email} is already a member of project {project.key!r}",
        )

    member = ProjectMember(project_id=project.id, user_id=user.id, role=body.role)
    db.add(member)
    db.commit()
    return _member_out(member)


@router.delete("/{key}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    user_id: uuid.UUID,
    project: Project = Depends(get_project),
    _: ProjectMember = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Response:
    """Remove a member. Admins only. Their tasks in this project become unassigned.

    Why the unassign step exists: ``tasks`` has a composite foreign key into
    ``project_members`` (models/task.py), and its ON DELETE rule is RESTRICT
    — the database refuses to delete a membership while any task still
    points at it. Phase 1 chose that over ``SET NULL`` on purpose: the rule
    "an assignee is a member" is never bent, and *this* route is the one
    place that knows what to do about it. Both statements run in one
    transaction, so a crash between them leaves nothing half-done.

    A project must keep at least one admin, or nobody could ever manage it
    again. Removing the last one is refused.
    """
    target = db.get(ProjectMember, (project.id, user_id))
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} is not a member of project {project.key!r}",
        )

    if target.role == MemberRole.ADMIN:
        admins = db.scalar(
            select(func.count())
            .select_from(ProjectMember)
            .where(
                ProjectMember.project_id == project.id,
                ProjectMember.role == MemberRole.ADMIN,
            )
        )
        if admins == 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Cannot remove the last admin of project {project.key!r}. "
                    "Add another admin first."
                ),
            )

    # Unassign first (Core UPDATE — the model's `onupdate` still bumps
    # `updated_at`), then delete. Same transaction; one commit.
    db.execute(
        update(Task)
        .where(Task.project_id == project.id, Task.assignee_id == user_id)
        .values(assignee_id=None)
    )
    db.delete(target)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
