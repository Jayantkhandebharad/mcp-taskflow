"""The ``users`` table.

One row per human. The login identity is the email. Passwords are stored as
bcrypt hashes, never plaintext (see ``passlib`` usage in phase 2 / seed).
"""

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    # UUIDs are generated in Python (default=uuid4), not by the DB. Two reasons:
    # 1. We can log the id *before* the INSERT — useful in error paths.
    # 2. Any process (tests, seed script, migrations) can construct one without
    #    a round-trip to the database.
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Two layers guard email casing:
    #   - the @validates hook below lowercases whatever the ORM is given, so
    #     application code doesn't have to remember;
    #   - the CHECK constraint below rejects a lowercase-mismatched row even if
    #     someone bypasses the ORM (raw SQL, a rogue migration, psql).
    email: Mapped[str] = mapped_column(sa.Text, nullable=False, unique=True)

    full_name: Mapped[str] = mapped_column(sa.Text, nullable=False)

    # The output of passlib's bcrypt (~60 chars). Never the password itself.
    password_hash: Mapped[str] = mapped_column(sa.Text, nullable=False)

    # Soft delete: setting False disables login without dropping the row (and
    # without breaking every FK that points at this user).
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.true()
    )

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )

    __table_args__ = (
        # The DB-level backstop for email casing. Named so migrations can
        # reference it — see the naming convention in models/base.py.
        sa.CheckConstraint("email = lower(email)", name="email_lowercase"),
    )

    @validates("email")
    def _lowercase_email(self, _key: str, value: str) -> str:
        # Called by SQLAlchemy whenever `user.email = ...` is set. Fires on
        # ORM writes only — the CHECK above covers everything else.
        return value.lower() if value is not None else value

    def __repr__(self) -> str:
        return f"User(id={self.id!s}, email={self.email!r})"
