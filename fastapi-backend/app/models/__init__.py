"""One import site for every model.

Alembic autogenerate looks at ``Base.metadata`` to know which tables exist.
Every model file has to be imported *somewhere* for its table to register
itself on that MetaData, and this ``__init__`` is the cheapest place to do
it. Anyone else who wants the models just does ``from app.models import
User, Project, ...``.
"""

from app.models.base import Base
from app.models.comment import Comment
from app.models.enums import (
    MemberRole,
    TaskPriority,
    TaskStatus,
    member_role_enum,
    task_priority_enum,
    task_status_enum,
)
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.task import Task
from app.models.user import User

__all__ = [
    "Base",
    "Comment",
    "MemberRole",
    "Project",
    "ProjectMember",
    "Task",
    "TaskPriority",
    "TaskStatus",
    "User",
    "member_role_enum",
    "task_priority_enum",
    "task_status_enum",
]
