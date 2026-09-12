"""The only way out of this service: HTTP calls to fastapi-backend.

Every function here does three things and nothing else:

1. attach the current user's token (``auth.current_token``) as a bearer header;
2. make the request;
3. turn any failure into a ``ToolError`` whose message says what to do next.

Point 3 is the one worth reading. The MCP SDK sends a ``ToolError``'s message
back to the model as the tool's result (flagged ``isError``), so the model
can read it and recover — "No project with key 'WEBB'. GET /projects lists
the ones you belong to." Any *other* exception becomes a bare "Error
executing tool" with the details only in our log. The backend already writes
its error bodies as instructions (PLAN.md §8, rule 3), so most of the time
this file just forwards the sentence it was given.

No connection pool, on purpose
==============================
Each call opens and closes its own ``httpx2.AsyncClient``. A pooled client
would save a TCP handshake per call, but a pool is bound to the event loop
that created it — and in stdio mode the login happens on one loop and the
tools on another. ADR 0001 promised to *measure* the extra hop before
optimising it; until then, simple and obviously-correct wins.
"""

from __future__ import annotations

from typing import Any

import httpx2
from mcp.server.mcpserver.exceptions import ToolError

from app.auth import current_token
from app.config import get_settings

# Tokens last twelve hours (JWT_EXPIRE_MINUTES). In stdio mode the only way
# to get a new one is to restart the process; phase 6's HTTP mode makes this
# the client's problem instead.
_SESSION_OVER = (
    "Your TaskFlow login is no longer valid (tokens expire after 12 hours). "
    "Restart the MCP server to log in again."
)


async def login(email: str, password: str) -> str:
    """``POST /auth/login`` → the access token. The one unauthenticated call."""
    response = await _request("POST", "/auth/login", json={"email": email, "password": password}, authed=False)
    return response.json()["access_token"]


async def get(path: str, **params: Any) -> Any:
    """``GET path`` as the current user, returning the decoded JSON body.

    ``params`` become the query string (``list_tasks`` will pass
    ``status=...``); ``None`` values are dropped so callers can forward
    optional tool arguments as-is.
    """
    query = {k: v for k, v in params.items() if v is not None}
    response = await _request("GET", path, params=query)
    return response.json()


async def _request(method: str, path: str, *, authed: bool = True, **kwargs: Any) -> httpx2.Response:
    settings = get_settings()

    headers: dict[str, str] = {}
    if authed:
        token = current_token.get()
        if token is None:
            # A programming error, not a user error: a tool ran before
            # anything set the token. Say so plainly.
            raise ToolError("The MCP server has no login for this session. This is a bug in the server.")
        headers["Authorization"] = f"Bearer {token}"

    try:
        async with httpx2.AsyncClient(base_url=settings.backend_url, timeout=10.0) as client:
            response = await client.request(method, path, headers=headers, **kwargs)
    except httpx2.TransportError:
        # Connection refused, DNS failure, timeout. The fix is always the
        # same, so the message says it.
        raise ToolError(
            f"The TaskFlow backend at {settings.backend_url} is not reachable. "
            "Start it (cd fastapi-backend && uv run uvicorn app.main:app --port 8000) "
            "and try again."
        )

    if response.is_success:
        return response
    raise ToolError(_explain(response, authed))


def _explain(response: httpx2.Response, authed: bool) -> str:
    """The sentence to show for a failed response.

    FastAPI puts its message under ``detail``: a string for the errors our
    handlers raise, or a list of ``{loc, msg}`` objects for a 422 validation
    failure. Anything else (a proxy's HTML, an empty body) falls back to the
    raw text.
    """
    try:
        detail = response.json().get("detail")
    except ValueError:
        detail = None

    if isinstance(detail, list):  # 422: one line per bad field
        detail = "; ".join(f"{'.'.join(map(str, e.get('loc', [])))}: {e.get('msg')}" for e in detail)
    if not detail:
        detail = response.text.strip() or f"HTTP {response.status_code}"

    if response.status_code == 401 and authed:
        return _SESSION_OVER
    if response.status_code >= 500:
        return (
            f"The TaskFlow backend answered {response.status_code} for "
            f"{response.request.method} {response.request.url.path}. "
            "That is a backend bug, not a problem with your request; check its log."
        )
    # 400/401-on-login/403/404/409/422: the backend wrote the sentence.
    return str(detail)
