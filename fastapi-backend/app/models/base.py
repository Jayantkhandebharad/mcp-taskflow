"""Declarative base + a naming convention shared by every table.

Why the naming convention matters
=================================
By default SQLAlchemy invents constraint names on the fly — ``ck_1``,
``fk_2``, ``ix_ab12cd`` — and Alembic's autogenerate uses whatever names it
finds. Two developers on two machines can end up with the same constraint
under two different auto-names, which means every migration diff churns and
CI complains about "unrelated" changes.

Fixing it once, here, is the standard Alembic advice. Constraint names
become deterministic: ``fk_tasks_project_id_projects``, ``uq_users_email``,
``ck_users_email_lowercase``. A reader can guess a name from the model.

The tokens (``%(table_name)s`` etc.) are SQLAlchemy's own template variables.
"""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    # Check constraints use a caller-supplied name (see the models). The
    # `constraint_name` token is only meaningful when you pass one.
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """The one declarative base every model inherits from.

    ``metadata`` is where SQLAlchemy stores every table definition. Attaching
    the naming convention to *this* MetaData means every table declared
    against ``Base`` picks it up — including tables added in later phases.
    """

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
