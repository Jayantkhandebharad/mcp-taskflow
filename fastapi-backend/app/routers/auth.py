"""``/auth`` — register, login, and "who am I?".

Three routes, PLAN.md §7::

    POST /auth/register   → create account
    POST /auth/login      → token
    GET  /auth/me         → current user
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user
from app.models import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserOut
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: Session = Depends(get_db)) -> User:
    """Create an account. Does *not* log the user in — call /auth/login next.

    Returning a token here would be one fewer round-trip for the frontend,
    but it would also mean two places mint tokens. One is easier to reason
    about.
    """
    # The ORM lowercases on assignment (models/user.py), but we want the
    # duplicate check to be case-insensitive too, so lowercase up front.
    email = body.email.lower()

    exists = db.scalar(select(User.id).where(User.email == email))
    if exists is not None:
        # 409 Conflict, not 400: the request was well-formed, it just clashes
        # with state that already exists. Frontends key their "that email is
        # taken" message off this code.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        )

    user = User(
        email=email,
        full_name=body.full_name,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    # `created_at` and `is_active` are server_default — Postgres fills them
    # in on INSERT. No `db.refresh()` is needed afterwards: on Postgres,
    # SQLAlchemy 2.0 appends `RETURNING created_at, is_active` to the INSERT
    # and populates the object in the same round-trip (`eager_defaults`
    # defaults to "auto"). The phase-2 brief records checking this.
    db.commit()
    return user


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Exchange email + password for a bearer token."""
    user = db.scalar(select(User).where(User.email == body.email.lower()))

    # One message for "no such user", "wrong password" and "deactivated".
    # Telling them apart would let anyone enumerate which emails have
    # accounts. (The timing still differs a little — a missing user skips the
    # bcrypt call. Padding that out with a dummy verify is a known refinement
    # we're not doing in a learning app; the brief says so.)
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return TokenResponse(access_token=create_access_token(user.id, user.email))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)) -> User:
    """Return the user behind the bearer token.

    This is the smallest possible protected route, and the one every later
    client — frontend, MCP server, chat client — uses to check "is this
    token still good?".
    """
    return user
