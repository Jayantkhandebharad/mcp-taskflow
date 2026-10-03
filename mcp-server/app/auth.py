"""Who is the server acting as? One variable answers it: ``current_token``.

PLAN.md §6, step 6, is the shape of this file::

    token = <the caller's JWT>
    current_token.set(token)          # per request
    ...
    headers = {"Authorization": f"Bearer {current_token.get()}"}   # backend.py

``current_token`` is a **context variable** — a value that is local to the
task currently running, not shared across the whole process. Every tool
reads it, ``backend.py`` attaches it to every outbound request, and nothing
else in this service knows who the user is. That is deliberate: there is no
``user`` object here, no role, no "is admin" flag. The backend decides all of
that from the token, per request, and the MCP server just carries it.

Two transports, two ways the token gets in
==========================================

**Streamable HTTP (this phase, the default).** Each MCP request arrives with
an ``Authorization: Bearer`` header. ``BearerTokenMiddleware`` below verifies
it and sets ``current_token`` for the duration of *that HTTP request only* —
Starlette runs each request in its own task, and a context variable set
inside a task is invisible to other tasks, so two users calling at once get
two contexts and never see each other's token.

**stdio.** A desktop client such as Claude Desktop launches the server as a
subprocess and talks JSON over its stdin and stdout. There are no headers.
There is also only ever *one* human: the one who launched the app. So the
server logs in once, at startup, with ``TASKFLOW_EMAIL`` and
``TASKFLOW_PASSWORD`` from its environment, and sets ``current_token`` once
for the life of the process. (``server.py`` does this before the first
request, so every request task inherits the value.)

Is that "credentials of its own"? No — and the distinction matters. The rule
in the README is that the MCP server has no *service* credentials: no admin
key, no god-token, nothing that would let it act as anyone but the person in
front of it. Your email and password in the launcher's config are *your*
credentials, on *your* machine, for a process that acts as *you* — the same
trust you extend to the frontend when you type them into its login form.

The trade we made: a token lasts twelve hours (``JWT_EXPIRE_MINUTES``), so a
config file holding a token would go stale by tomorrow morning; a config
file holding a login works every launch. The cost is a password in a JSON
file on your disk, and we say so rather than hide it. HTTP mode has no such
trade: it never sees a password, only the token each request already came
with — that's the whole point of phase 6.

Verifying the token ourselves, not the SDK's OAuth machinery
==============================================================
The ``mcp`` SDK ships a full OAuth 2.1 resource-server story
(``AuthSettings``, ``TokenVerifier``, ``RequireAuthMiddleware`` — see
``mcp.server.auth``): metadata endpoints, scopes, an authorization server to
talk to. PLAN.md §6 deliberately defers all of that to a later phase. What we
need today is smaller: decode the JWT with the secret we already share with
the backend, reject garbage before it goes anywhere, and hand the raw token
on. ``BearerTokenMiddleware`` is that — plain ASGI, no SDK auth settings
involved, in keeping with ADR 0002's "eighty lines you can read in one
sitting". The backend re-verifies on every call regardless; this check is an
optimisation, not the real gate (PLAN.md §6, "two checks, on purpose").
"""

from __future__ import annotations

from contextvars import ContextVar

import jwt
from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import get_settings

# `None` means "nobody" — backend.py refuses to make an authenticated call
# in that state rather than sending a request with no header.
current_token: ContextVar[str | None] = ContextVar("current_token", default=None)


class BearerTokenMiddleware:
    """ASGI middleware: pull the bearer token off the request, verify it
    cheaply, set ``current_token`` — or reject with 401 before anything else
    runs.

    Sits in front of the Streamable HTTP app (``server.py`` adds it with
    ``app.add_middleware``). Only ``scope["type"] == "http"`` requests carry
    headers; other scope types (the ASGI ``lifespan`` startup/shutdown
    events) pass straight through.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        token = _bearer_token(Headers(scope=scope).get("authorization"))
        if token is None:
            await _reject(scope, receive, send, "Missing bearer token. Send 'Authorization: Bearer <jwt>'.")
            return

        try:
            _verify_signature(token)
        except jwt.PyJWTError as exc:
            await _reject(scope, receive, send, f"Invalid token: {exc}")
            return

        current_token.set(token)
        await self.app(scope, receive, send)


def _bearer_token(header_value: str | None) -> str | None:
    """The token out of an ``Authorization: Bearer <token>`` header, or
    ``None`` if the header is missing or doesn't use the ``Bearer`` scheme."""
    if header_value is None:
        return None
    scheme, _, token = header_value.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token


def _verify_signature(token: str) -> None:
    """Decode just far enough to know the token isn't forged or expired.

    The claims themselves (``sub``, ``email``) are thrown away — the backend
    reads them fresh from its own ``decode_access_token`` on every call and
    is the actual authority (PLAN.md §6). This call exists only so a bad
    token gets a clean 401 here instead of a round trip to the backend.
    """
    settings = get_settings()
    jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


async def _reject(scope: Scope, receive: Receive, send: Send, detail: str) -> None:
    await JSONResponse({"detail": detail}, status_code=401)(scope, receive, send)
