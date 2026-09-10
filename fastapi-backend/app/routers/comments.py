"""``/tasks/{key}-{number}/comments`` — read and add comments on a task.

PLAN.md §7::

    GET   /tasks/{key}-{number}/comments
    POST  /tasks/{key}-{number}/comments

Both go through ``get_task``, so both are members-only and answer 404/403
in the same order as every other task route. No edit, no delete: PLAN.md
§1 — every feature must earn its place, and neither teaches anything.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user, get_task
from app.models import Comment, Task, User
from app.schemas.comments import CommentCreate, CommentOut

router = APIRouter(prefix="/tasks", tags=["comments"])


@router.get("/{key}-{number}/comments", response_model=list[CommentOut])
def list_comments(task: Task = Depends(get_task), db: Session = Depends(get_db)) -> list[Comment]:
    """Oldest first — a conversation reads top to bottom."""
    return list(
        db.scalars(select(Comment).where(Comment.task_id == task.id).order_by(Comment.created_at))
    )


@router.post(
    "/{key}-{number}/comments", response_model=CommentOut, status_code=status.HTTP_201_CREATED
)
def add_comment(
    body: CommentCreate,
    task: Task = Depends(get_task),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Comment:
    """Any member of the task's project may comment."""
    comment = Comment(task_id=task.id, author_id=user.id, body=body.body)
    db.add(comment)
    db.commit()
    # `author` is a relationship the session hasn't loaded for a row it just
    # inserted; one refresh reads it (and the server-side created_at) back.
    db.refresh(comment)
    return comment
