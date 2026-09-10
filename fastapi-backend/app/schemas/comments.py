"""Request and response bodies for a task's comments."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.auth import UserRef


class CommentCreate(BaseModel):
    body: str = Field(min_length=1)


class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    # Who, as a person — read straight off the `Comment.author` relationship.
    author: UserRef
    body: str
    created_at: datetime
