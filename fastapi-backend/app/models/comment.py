"""The ``comments`` table.

Nothing subtle here — the interesting bit is the ON DELETE CASCADE on
``task_id``. When a task is deleted, its comments go with it, at the DB level.
The ORM relationship on the Task side is configured with ``passive_deletes``
so the ORM doesn't try to emit its own DELETEs and race the database.
"""

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # ON DELETE CASCADE: deleting a task deletes its comments. This is one of
    # the three invariants listed in PLAN.md §5.
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
    )

    # We do NOT cascade on user delete — we don't delete users. The is_active
    # flag on User is how accounts go away.
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
    )

    body: Mapped[str] = mapped_column(sa.Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )

    task: Mapped["Task"] = relationship(back_populates="comments")  # noqa: F821

    # Who wrote it, as a User. Same reasoning as ProjectMember.user: a comment
    # is always displayed with its author, so join rather than lazy-load.
    author: Mapped["User"] = relationship(lazy="joined")  # noqa: F821

    def __repr__(self) -> str:
        return f"Comment(id={self.id!s}, task_id={self.task_id!s})"
