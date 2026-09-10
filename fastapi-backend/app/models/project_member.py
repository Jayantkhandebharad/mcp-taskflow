"""The ``project_members`` table — the whole authorisation model.

Every question about "may X do Y in project Z?" is answered by asking this
table. It exists on purpose: keeping membership in its own table means the
tasks table can reference it with a *composite* foreign key (see models/task.py),
which lets the database enforce the invariant "a task's assignee is a member
of that task's project" — no application-level check required.

Composite primary key: ``(project_id, user_id)``. No surrogate id, no fuss.
"""

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import MemberRole, member_role_enum


class ProjectMember(Base):
    __tablename__ = "project_members"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        # ON DELETE CASCADE: if a project is deleted, its membership rows go
        # with it. (We don't yet expose a "delete project" action, but the
        # constraint should say what we mean regardless.)
        sa.ForeignKey("projects.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )

    role: Mapped[MemberRole] = mapped_column(member_role_enum, nullable=False)

    added_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )

    # The member as a User, for "list members" — a membership row is never
    # shown without the person's email and name, so one JOIN beats N follow-up
    # SELECTs. Read-side convenience only; no schema change (phase 3).
    user: Mapped["User"] = relationship(lazy="joined")  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"ProjectMember(project_id={self.project_id!s}, "
            f"user_id={self.user_id!s}, role={self.role.value})"
        )
