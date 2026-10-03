"""Phase 6: Streamable HTTP transport — the bearer token rides per request.

Same two tools, same rule as phase 5 (``whoami`` and ``list_projects`` answer
as whoever's token called them), now proven over the transport the chat
client and Docker will actually use — plus what only HTTP has:

1. two users hitting the *same* running server, never restarted, and each
   still seeing only their own projects;
2. a bad token rejected by ``BearerTokenMiddleware`` before any tool, or even
   the MCP protocol itself, ever runs.
"""

from __future__ import annotations

import json
import time

import httpx2
import jwt

from app.config import get_settings
from tests.conftest import ALICE, BOB, token_for


def test_tools_list_over_http_is_exactly_the_phase_5_pair(as_http_user):
    tools = as_http_user(ALICE).tools()
    assert sorted(t.name for t in tools) == ["list_projects", "whoami"]


def test_whoami_over_http_is_the_person_the_token_names(as_http_user):
    result = as_http_user(ALICE).call("whoami")
    assert result.is_error is False
    assert result.structured_content == {"email": ALICE, "full_name": "Alice Adams"}


def test_list_projects_over_http_is_scoped_per_caller_on_one_shared_server(as_http_user):
    """Phase 5 restarted a whole process to switch users. Phase 6 doesn't
    have to: Alice and Bob call the same running server, each with their own
    token, and each still gets only their own projects back."""
    alice = as_http_user(ALICE).call("list_projects").structured_content["result"]
    assert [(p["key"], p["my_role"]) for p in alice] == [("API", "admin"), ("WEB", "admin")]

    bob = as_http_user(BOB).call("list_projects").structured_content["result"]
    assert [(p["key"], p["my_role"]) for p in bob] == [("WEB", "member")]


def test_no_authorization_header_is_rejected_before_any_tool_runs(mcp_http_url):
    response = httpx2.post(mcp_http_url, timeout=10.0)
    assert response.status_code == 401
    assert "Missing bearer token" in response.json()["detail"]


def test_authorization_header_without_bearer_scheme_is_rejected(mcp_http_url):
    """The header is there, but it isn't the scheme we read — same as no
    header at all, from BearerTokenMiddleware's point of view."""
    response = httpx2.post(mcp_http_url, headers={"Authorization": "sometoken"}, timeout=10.0)
    assert response.status_code == 401
    assert "Missing bearer token" in response.json()["detail"]


def test_garbage_token_is_rejected(mcp_http_url):
    response = httpx2.post(mcp_http_url, headers={"Authorization": "Bearer not-a-jwt"}, timeout=10.0)
    assert response.status_code == 401
    assert "Invalid token" in response.json()["detail"]


def test_expired_token_is_rejected(mcp_http_url):
    """A token that is real and correctly signed, just too old — the one
    case a garbage token can't cover. Minted with the same secret this test
    process shares with the server under test: both read the same
    repo-root ``.env`` (``app/config.py``).
    """
    settings = get_settings()
    now = time.time()
    expired = jwt.encode(
        {"sub": "irrelevant-to-this-check", "email": ALICE, "iat": now - 10, "exp": now - 1},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    response = httpx2.post(mcp_http_url, headers={"Authorization": f"Bearer {expired}"}, timeout=10.0)
    assert response.status_code == 401
    assert "Invalid token" in response.json()["detail"]


def test_a_token_signed_with_the_wrong_secret_is_rejected(mcp_http_url):
    """A forged token: correct shape, wrong signature. What
    BearerTokenMiddleware exists to catch before the backend ever sees it.
    """
    settings = get_settings()
    now = time.time()
    forged = jwt.encode(
        {"sub": "attacker", "email": ALICE, "iat": now, "exp": now + 3600},
        "not-the-real-secret-but-long-enough-for-hs256",
        algorithm=settings.jwt_algorithm,
    )
    response = httpx2.post(mcp_http_url, headers={"Authorization": f"Bearer {forged}"}, timeout=10.0)
    assert response.status_code == 401
    assert "Invalid token" in response.json()["detail"]


def test_session_id_is_not_identity(mcp_http_url, backend_url):
    """``Mcp-Session-Id`` ties a run of POSTs to one protocol session — a key
    into a dict in the server's memory. It says nothing about *who* is
    calling. Bob sends Alice's session id with his own token and gets Bob's
    answer, because ``current_token`` is set from the header on every request
    and the backend believes the token, never the session.

    The SDK's session manager *would* refuse this (it binds a session to the
    credential that opened it), but only through its own ``AuthenticatedUser``,
    which our middleware does not set. So that check is inert for us, and
    identity must never be inferred from session state. This test is the
    fence around that: if someone later makes the session carry the user,
    Bob here starts getting Alice's answer, and this goes red.
    """
    mcp = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    alice = {"Authorization": f"Bearer {token_for(backend_url, ALICE)}", **mcp}

    opened = httpx2.post(
        mcp_http_url,
        headers=alice,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}},
        },
        timeout=10.0,
    )
    assert opened.status_code == 200
    session_id = opened.headers["mcp-session-id"]
    httpx2.post(
        mcp_http_url,
        headers={**alice, "Mcp-Session-Id": session_id},
        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        timeout=10.0,
    )

    bob = {"Authorization": f"Bearer {token_for(backend_url, BOB)}", "Mcp-Session-Id": session_id, **mcp}
    response = httpx2.post(
        mcp_http_url,
        headers=bob,
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "whoami", "arguments": {}}},
        timeout=10.0,
    )
    assert response.status_code == 200
    # The reply is one SSE frame: "event: message\ndata: {...}\n\n".
    payload = next(line for line in response.text.splitlines() if line.startswith("data: "))
    result = json.loads(payload.removeprefix("data: "))["result"]
    assert result["structuredContent"]["email"] == BOB
