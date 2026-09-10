"""FastAPI dependencies that answer "who is calling, and may they?".

PLAN.md §6 names three: ``current_user``, ``require_member``,
``require_admin``. They form a chain, and every protected route hangs off
some link of it::

    current_user      who is this token?               401 if unknown
      └─ get_project  which project is in the URL?     404 if no such key
                      (asks current_user first, so 401 always beats 404)
           └─ require_member  is the caller in it?     403 if not
                └─ require_admin  ...as an admin?      403 if not
                └─ get_task  which task is in the URL? 404 if no such number

Each link is a plain function that FastAPI calls before the route body. A
route asks for the deepest link it needs and gets every check above it for
free — ``Depends(require_admin)`` means "valid token, real project, member,
admin", in that order.

How a dependency works, in one paragraph: a route declares a parameter like
``user: User = Depends(current_user)``. Before the route body runs, FastAPI
calls ``current_user`` (resolving *its* parameters the same way), and either
passes the return value in or, if it raised ``HTTPException``, sends that
response instead. So the route body only ever sees a real, active user.
"""

from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import MemberRole, Project, ProjectMember, Task, User
from app.security import TokenError, decode_access_token

# `auto_error=False` so a missing header reaches *our* code instead of
# FastAPI's default 403. A missing credential is a 401 ("who are you?"), not
# a 403 ("I know who you are and the answer is no") — and the two mean
# different things to the MCP server later, which maps them to different
# tool errors.
_bearer = HTTPBearer(auto_error=False)


def _unauthorized(detail: str) -> HTTPException:
    # RFC 6750 says a 401 for a bearer-protected resource should carry this
    # header. Browsers ignore it; well-behaved API clients don't.
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """Decode the bearer token and load its user. 401 on any failure.

    Every failure path is a 401 with a short reason. The reasons are for the
    developer reading a log, not a decision point for clients — a client's
    only sensible reaction to any of them is "log in again".
    """
    if creds is None:
        raise _unauthorized("Not authenticated")

    try:
        claims = decode_access_token(creds.credentials)
    except TokenError:
        raise _unauthorized("Invalid or expired token")

    # `sub` was written by us in create_access_token, so it *should* always
    # be a UUID string — but the DB lookup below should never see garbage.
    try:
        user_id = uuid.UUID(claims["sub"])
    except (KeyError, ValueError):
        raise _unauthorized("Invalid token subject")

    user = db.get(User, user_id)
    # Two cases folded into one: the user was deleted after the token was
    # issued, or an admin flipped `is_active` off. Either way the token is a
    # valid signature over an identity that may no longer act. This is the
    # one revocation-like check we get without a token blacklist.
    if user is None or not user.is_active:
        raise _unauthorized("User not found or inactive")

    return user


# ── The project links of the chain ───────────────────────────────────────────


def get_project(
    key: str,
    _: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Project:
    """Load the project named by the ``{key}`` path parameter. 404 if none.

    FastAPI fills ``key`` from the URL of whichever route is using this
    dependency — ``/projects/{key}``, ``/projects/{key}/tasks``, and so on —
    so the same function serves every route that has a key in its path.

    It also asks for ``current_user`` and then ignores the answer. That is
    deliberate: FastAPI resolves dependencies in the order they are
    declared, and the first draft of phase 3 had a route list ``get_project``
    before ``require_member`` — so an anonymous request for ``/projects/WEBB``
    got a 404 while ``/projects/WEB`` got a 401, and anyone could probe which
    keys exist without logging in. Putting the token check *inside* the
    lookup makes "401 before 404" true for every route, whatever order its
    parameters happen to be in. (``current_user`` is cached per request, so
    the token is decoded once, not twice.)

    The key is uppercased first. The model uppercases on *write*; this is
    the matching read side, so ``/projects/web`` finds ``WEB``. Language
    models in particular will send lowercase.

    The message says what to do next (PLAN.md §8: errors are instructions).
    """
    project = db.scalar(select(Project).where(Project.key == key.upper()))
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No project with key {key.upper()!r}. "
                "GET /projects lists the ones you belong to."
            ),
        )
    return project


def require_member(
    user: User = Depends(current_user),
    project: Project = Depends(get_project),
    db: Session = Depends(get_db),
) -> ProjectMember:
    """The caller must be in ``project_members`` for this project. 403 if not.

    Returns the membership row rather than nothing, because the row carries
    the role and several routes want it ("detail + my role").

    Why 403 and not 404 when the project exists: 403 means "I know who you
    are, and the answer is no". That's a different thing for a client (and,
    later, for the MCP server) to do something about than "there is no such
    project". Nothing secret leaks: the key of a project you're not in is
    not a secret in this app.

    A note on ``db``: FastAPI calls each dependency at most once per request
    and reuses the result, so ``get_db`` here, in ``get_project``, and in the
    route body all yield the *same* ``Session``. The route can commit what
    the dependencies loaded.
    """
    # Composite primary key, so `db.get` takes a tuple in PK column order.
    member = db.get(ProjectMember, (project.id, user.id))
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You are not a member of project {project.key!r}",
        )
    return member


def require_admin(
    member: ProjectMember = Depends(require_member),
    project: Project = Depends(get_project),
) -> ProjectMember:
    """Same as ``require_member``, and the role must be ``admin``. 403 if not.

    Note what this reads: the ``project_members`` row, loaded on *this*
    request. Not the token. A token issued before Alice was promoted works
    the moment the row changes — ADR 0002 and PLAN.md §6, "roles are not in
    the token".
    """
    if member.role != MemberRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Only an admin of project {project.key!r} can do this",
        )
    return member


def get_task(
    number: int,
    member: ProjectMember = Depends(require_member),
    project: Project = Depends(get_project),
    db: Session = Depends(get_db),
) -> Task:
    """Load the task named by ``{key}-{number}`` in the path. Member-only.

    Check order, by construction of the chain: token (401) → project exists
    (404) → caller is a member (403) → task number exists (404). A non-member
    never learns whether ``WEB-14`` exists.

    ``number: int`` makes FastAPI reject ``/tasks/WEB-x`` with a 422 before
    we ever run.
    """
    task = db.scalar(
        select(Task).where(Task.project_id == project.id, Task.number == number)
    )
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No task {project.key}-{number}. "
                f"GET /projects/{project.key}/tasks lists the ones that exist."
            ),
        )
    return task
