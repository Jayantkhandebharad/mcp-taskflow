"""Request and response bodies for ``/projects/*`` and its members."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import MemberRole


class ProjectCreate(BaseModel):
    # One letter, then up to nine letters or digits. No hyphens: the task ref
    # "WEB-14" is split on its hyphen, so a key containing one would make
    # "A-B-14" ambiguous. Case is accepted and uppercased by the handler
    # (the database enforces uppercase; see models/project.py).
    key: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9]{1,9}$")
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None


class ProjectOut(BaseModel):
    """A project *as seen by the caller* — hence ``my_role``.

    ``my_role`` is not a column; it's the caller's row in ``project_members``.
    The handler fills it in, which is why this class is built explicitly in
    the router rather than straight from the ORM object.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    name: str
    description: str | None
    created_by: uuid.UUID
    created_at: datetime
    my_role: MemberRole


class MemberAdd(BaseModel):
    # By email, not user id. There is no "search users" route (and there
    # won't be — PLAN.md §1 keeps the app small), so an email is the only
    # handle a caller has for someone who isn't in the project yet.
    email: EmailStr
    role: MemberRole = MemberRole.MEMBER


class MemberOut(BaseModel):
    """One row of ``GET /projects/{key}/members``: the person and their role."""

    user_id: uuid.UUID
    email: str
    full_name: str
    role: MemberRole
    added_at: datetime
