"""Request and response bodies for ``/auth/*``."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    # EmailStr rejects things like "alice" or "a@b" before our code runs.
    # It needs the `email-validator` package — hence `pydantic[email]` in
    # pyproject.toml.
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=200)
    # bcrypt ignores everything past 72 *bytes*. Rather than silently
    # truncate, we reject longer passwords so the user isn't surprised later
    # when "the first 72 characters" is what actually logs them in.
    password: str = Field(min_length=8, max_length=72)


class LoginRequest(BaseModel):
    # Login takes JSON, not an OAuth2 form. PLAN.md §6 shows the JSON shape,
    # and it's what the frontend and the chat client will actually send.
    # (FastAPI's OAuth2PasswordRequestForm would give us the Swagger
    # "Authorize" button for free, but at the cost of the tests and the
    # frontend speaking a different dialect from the plan.)
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    # Always "bearer". Included because that's the shape every OAuth-style
    # client already knows how to read.
    token_type: str = "bearer"


class UserOut(BaseModel):
    """The public view of a user. No ``password_hash``, ever."""

    # `from_attributes=True` lets FastAPI build this straight from an ORM
    # `User` object (it reads attributes instead of dict keys).
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
    created_at: datetime
