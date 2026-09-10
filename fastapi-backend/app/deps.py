"""FastAPI dependencies that answer "who is calling, and may they?".

PLAN.md §6 names three: ``current_user``, ``require_member``,
``require_admin``. Phase 2 ships the first. The other two need a project in
the URL to check membership against, so they arrive with the project routes
in phase 3.

How a dependency works, in one paragraph: a route declares a parameter like
``user: User = Depends(current_user)``. Before the route body runs, FastAPI
calls ``current_user`` (resolving *its* parameters the same way), and either
passes the return value in or, if it raised ``HTTPException``, sends that
response instead. So the route body only ever sees a real, active user.
"""

from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.security import TokenError, decode_access_token

# `auto_error=False` so a missing header reaches *our* code instead of
# FastAPI's default 403. A missing credential is a 401 ("who are you?"), not
# a 403 ("I know who you are and the answer is no") — and the two mean
# different things to the MCP server later, which maps them to different
# tool errors.
_bearer = HTTPBearer(auto_error=False)


def _unauthorized(detail: str) -> HTTPException:
    # RFC 6750 says a 401 for a bearer-protected resource should carry this
    # header. Browsers ignore it; well-behaved API clients don't.
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """Decode the bearer token and load its user. 401 on any failure.

    Every failure path is a 401 with a short reason. The reasons are for the
    developer reading a log, not a decision point for clients — a client's
    only sensible reaction to any of them is "log in again".
    """
    if creds is None:
        raise _unauthorized("Not authenticated")

    try:
        claims = decode_access_token(creds.credentials)
    except TokenError:
        raise _unauthorized("Invalid or expired token")

    # `sub` was written by us in create_access_token, so it *should* always
    # be a UUID string — but the DB lookup below should never see garbage.
    try:
        user_id = uuid.UUID(claims["sub"])
    except (KeyError, ValueError):
        raise _unauthorized("Invalid token subject")

    user = db.get(User, user_id)
    # Two cases folded into one: the user was deleted after the token was
    # issued, or an admin flipped `is_active` off. Either way the token is a
    # valid signature over an identity that may no longer act. This is the
    # one revocation-like check we get without a token blacklist.
    if user is None or not user.is_active:
        raise _unauthorized("User not found or inactive")

    return user
