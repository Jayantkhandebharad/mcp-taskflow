"""The ``projects`` table.

A project has a short human key like ``WEB`` or ``API``. Task refs read as
``WEB-14`` — humans and language models both do better with those than with
UUIDs (see PLAN.md §5, "Why ``key`` exists"). Uppercase is enforced by both
the app and the database, for the same reason we enforce email lowercase.
"""

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.models.base import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Short human identifier. Length 10 is generous — everyone's project keys
    # are three or four letters.
    key: Mapped[str] = mapped_column(sa.String(10), nullable=False, unique=True)

    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    description: Mapped[str | None] = mapped_column(sa.Text, nullable=True)

    # Who made it. Kept even after they leave the project — audit trail.
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )

    __table_args__ = (
        sa.CheckConstraint("key = upper(key)", name="key_uppercase"),
    )

    @validates("key")
    def _uppercase_key(self, _key: str, value: str) -> str:
        return value.upper() if value is not None else value

    def __repr__(self) -> str:
        return f"Project(key={self.key!r}, name={self.name!r})"
