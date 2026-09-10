"""Passwords and tokens — the two cryptographic jobs the backend has.

Both are deliberately tiny. ADR 0002 says our whole auth is "about eighty
lines you can read in one sitting"; this file is most of them.

Passwords
---------
We never store a password. We store a *bcrypt hash* of it: a one-way function
whose output can be checked against a candidate password but not reversed.
bcrypt is slow on purpose (tens of milliseconds per hash) so that guessing
billions of passwords against a leaked database takes years, not hours.

Tokens
------
A JSON Web Token (JWT) is three base64 pieces: a header, a JSON payload of
"claims", and a signature over the first two. Anyone can *read* the claims —
they are not encrypted. What the signature gives you is that nobody without
``JWT_SECRET`` could have *produced* them. So the backend can hand a token to
a browser, get it back twelve hours later, and trust the ``sub`` inside it
without a database lookup.

What is in the token, and what is not (PLAN.md §6, ADR 0002)::

    { "sub": "<user uuid>", "email": "alice@example.com",
      "iat": <issued-at, unix seconds>, "exp": <expires, unix seconds> }

No roles. Roles live in ``project_members`` and are read per request, so a
promotion takes effect immediately and a stolen token can't carry stale
privileges.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt
from passlib.context import CryptContext

from app.config import get_settings

# ── Passwords ────────────────────────────────────────────────────────────────
# One CryptContext for the whole process. `schemes` is the list of algorithms
# we accept; `deprecated="auto"` means "anything but the first one is legacy
# and should be re-hashed on next login" — irrelevant today with one scheme,
# but it's the setting that makes a future migration to argon2 a one-line
# change here and nowhere else.
#
# The seed script uses this same context so demo hashes and login hashes are
# produced by exactly one code path.
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    """Return a bcrypt hash suitable for ``users.password_hash``."""
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """True if ``plain`` is the password behind ``hashed``.

    passlib does the comparison in constant time, so an attacker can't learn
    how many leading bytes matched from how long the call took.
    """
    return _pwd_context.verify(plain, hashed)


# ── Tokens ───────────────────────────────────────────────────────────────────


class TokenError(Exception):
    """Raised when a token can't be trusted, for any reason.

    Callers (``deps.current_user``) turn this into one uniform 401. We collapse
    PyJWT's several exception types into one on purpose: a client gains
    nothing from knowing *why* its token was rejected, and an attacker gains a
    little.
    """


def create_access_token(
    user_id: uuid.UUID,
    email: str,
    *,
    expires_in: timedelta | None = None,
) -> str:
    """Sign a token for this user.

    ``expires_in`` overrides the configured lifetime. It exists for tests
    (to mint an already-expired token) — production code never passes it.
    """
    settings = get_settings()
    now = datetime.now(UTC)
    lifetime = expires_in if expires_in is not None else timedelta(
        minutes=settings.jwt_expire_minutes
    )
    claims = {
        # "sub" (subject) is the standard claim for "who this token is about".
        # It's a string in the JWT spec, so we stringify the UUID.
        "sub": str(user_id),
        # Not needed to identify the user — `sub` does that — but handy for
        # anything that wants to show "logged in as alice@…" without a lookup.
        "email": email,
        # PyJWT converts datetimes to unix timestamps for these two.
        "iat": now,
        "exp": now + lifetime,
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Verify the signature and expiry, and return the claims.

    ``algorithms=[...]`` is not optional. A JWT's header says which algorithm
    signed it, and a classic attack sets that to ``"none"``. Passing an
    explicit allow-list tells PyJWT to refuse anything we didn't choose.
    """
    settings = get_settings()
    try:
        return jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except jwt.PyJWTError as exc:  # expired, bad signature, malformed, wrong alg
        raise TokenError(str(exc)) from exc
