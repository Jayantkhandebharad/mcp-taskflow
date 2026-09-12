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

**Streamable HTTP (phase 6).** Each MCP request arrives with an
``Authorization: Bearer`` header. The server verifies it and sets
``current_token`` for the duration of that request. Two users talking at
once get two contexts and never see each other's token — which is what a
context variable is for.

**stdio (this phase).** A desktop client such as Claude Desktop launches the
server as a subprocess and talks JSON over its stdin and stdout. There are
no headers. There is also only ever *one* human: the one who launched the
app. So the server logs in once, at startup, with ``TASKFLOW_EMAIL`` and
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
file on your disk, and we say so rather than hide it. Phase 6 removes even
that: over HTTP the server only ever sees tokens, never passwords.
"""

from __future__ import annotations

from contextvars import ContextVar

# `None` means "nobody" — backend.py refuses to make an authenticated call
# in that state rather than sending a request with no header.
current_token: ContextVar[str | None] = ContextVar("current_token", default=None)
