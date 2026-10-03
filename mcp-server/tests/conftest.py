"""Fixtures that make the MCP server's tests behave like a real client.

Nothing is mocked. A stdio test spawns the server exactly the way Claude
Desktop does — as a subprocess, ``python -m app.server --stdio``, with a
near-empty environment — and talks to it with the MCP SDK's own ``Client``
over stdin/stdout. An HTTP test spawns it the way the chat client will —
``python -m app.server``, one process for the whole session — and talks to
it over a real socket with a real JWT from a real ``/auth/login``. Behind
either transport is the *real* fastapi-backend, started once per test run on
a free port against the Compose Postgres, with the demo seed loaded.
(CLAUDE.md: "test like the real client, not an ideal one.")

What that costs: each stdio test pays a process start (about a second:
importing the SDK, then a real ``/auth/login`` with bcrypt) because stdio
mode logs in once at startup. HTTP tests share one process and pay only the
login's cost, since the token rides on each call instead. A dozen tests is
fine either way; a thousand would want the in-process ``Client(server)`` the
SDK also offers. We'll switch when it hurts, not before — the subprocess is
the thing that will really call us.

Requires ``uv`` on PATH and ``docker compose up db`` running, like the
backend's own tests.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx2
import pytest
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from mcp.client.streamable_http import streamable_http_client
from mcp.types import CallToolResult, Tool

MCP_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = MCP_DIR.parent / "fastapi-backend"

# The seed's people (fastapi-backend/scripts/seed.py). Every password is "password".
ALICE = "alice@example.com"  # admin of WEB and API
BOB = "bob@example.com"  # member of WEB only
SEED_PASSWORD = "password"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def backend_url() -> Iterator[str]:
    """Start the real backend on a free port with the seed loaded; yield its URL.

    The seed is re-run first because the backend's own tests leave the
    database truncated. Both commands go through ``uv run`` in the backend's
    folder so they use *its* venv and read ``../.env`` the way it expects.
    """
    subprocess.run(
        ["uv", "run", "python", "-m", "scripts.seed"], cwd=BACKEND_DIR, check=True, capture_output=True
    )

    port = _free_port()
    url = f"http://127.0.0.1:{port}"
    proc = subprocess.Popen(
        ["uv", "run", "uvicorn", "app.main:app", "--port", str(port), "--log-level", "warning"],
        cwd=BACKEND_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 30
        while True:
            try:
                if httpx2.get(f"{url}/health", timeout=1.0).status_code == 200:
                    break
            except httpx2.TransportError:
                pass
            if proc.poll() is not None or time.monotonic() > deadline:
                stderr = proc.stderr.read() if proc.stderr else ""
                raise RuntimeError(f"backend did not come up on {url}:\n{stderr}")
            time.sleep(0.2)
        yield url
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def server_env(backend_url: str, email: str | None, password: str | None = SEED_PASSWORD) -> dict[str, str]:
    """The environment a desktop client would hand the server: almost nothing.

    Only ``PATH`` and ``HOME`` from the outside world — the MCP SDK's stdio
    client passes just those and a few like them — plus the three variables
    this server actually reads. If the server ever depended on something
    else being in the environment, these tests would be the first to know.
    """
    env = {k: os.environ[k] for k in ("PATH", "HOME") if k in os.environ}
    env["BACKEND_URL"] = backend_url
    if email is not None:
        env["TASKFLOW_EMAIL"] = email
    if password is not None:
        env["TASKFLOW_PASSWORD"] = password
    return env


def server_params(env: dict[str, str]) -> StdioServerParameters:
    """How to launch the server: this venv's Python, ``-m app.server --stdio``,
    from the mcp-server folder — the same command line Claude Desktop runs."""
    return StdioServerParameters(command=sys.executable, args=["-m", "app.server", "--stdio"], env=env, cwd=MCP_DIR)


@pytest.fixture
def as_user(backend_url: str):
    """``as_user(email)`` → a small sync handle on a server running as that user.

    Two methods: ``tools()`` lists them, ``call(name, **args)`` calls one.
    Each method starts a fresh server process and shuts it down again, which
    is slow but exactly what a client does: no state survives between calls
    except what the backend holds.
    """

    class Handle:
        def __init__(self, email: str) -> None:
            self.params = server_params(server_env(backend_url, email))

        def tools(self) -> list[Tool]:
            async def go() -> list[Tool]:
                async with Client(self.params) as client:
                    return (await client.list_tools()).tools

            return _run(go)

        def call(self, name: str, **arguments: Any) -> CallToolResult:
            async def go() -> CallToolResult:
                async with Client(self.params) as client:
                    result = await client.call_tool(name, arguments)
                    assert isinstance(result, CallToolResult)
                    return result

            return _run(go)

    return Handle


def _run(coro_fn):
    """Run one async client conversation to completion from a sync test."""
    import anyio

    return anyio.run(coro_fn)


def token_for(backend_url: str, email: str, password: str = SEED_PASSWORD) -> str:
    """A real JWT from the real backend — what a browser or the chat client
    would hold. HTTP-mode tests send this as ``Authorization: Bearer <token>``
    instead of the login-at-startup that stdio mode uses.
    """
    response = httpx2.post(f"{backend_url}/auth/login", json={"email": email, "password": password}, timeout=10.0)
    response.raise_for_status()
    return response.json()["access_token"]


def _wait_for_http_server(url: str, proc: subprocess.Popen) -> None:
    """The server is up once it answers *anything*. A bare request with no
    token gets a 401 from ``BearerTokenMiddleware`` before the MCP app ever
    sees it, which is proof enough that the whole ASGI stack is serving.
    """
    deadline = time.monotonic() + 30
    while True:
        try:
            if httpx2.post(url, timeout=1.0).status_code == 401:
                return
        except httpx2.TransportError:
            pass
        if proc.poll() is not None or time.monotonic() > deadline:
            stderr = proc.stderr.read() if proc.stderr else ""
            raise RuntimeError(f"mcp-server did not come up on {url}:\n{stderr}")
        time.sleep(0.2)


@pytest.fixture(scope="session")
def mcp_http_url(backend_url: str) -> Iterator[str]:
    """Start the real server in HTTP mode on a free port; yield its ``/mcp`` URL.

    One process for the whole session. Unlike stdio, HTTP mode logs nobody in
    at startup (PLAN.md §6) — there is no per-user state to isolate, so every
    test in ``test_http.py`` shares this one server and picks its user with
    whatever token it sends.
    """
    port = _free_port()
    url = f"http://127.0.0.1:{port}/mcp"
    env = {k: os.environ[k] for k in ("PATH", "HOME") if k in os.environ}
    env["BACKEND_URL"] = backend_url
    env["MCP_PORT"] = str(port)
    proc = subprocess.Popen(
        [sys.executable, "-m", "app.server"],
        cwd=MCP_DIR,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        _wait_for_http_server(url, proc)
        yield url
    finally:
        proc.terminate()
        proc.wait(timeout=10)


@pytest.fixture
def as_http_user(mcp_http_url: str, backend_url: str):
    """``as_http_user(email)`` → a handle on the shared HTTP server, calling
    as that user's real token. The HTTP counterpart of ``as_user``: instead of
    a fresh process per user, one server and a different ``Authorization``
    header per call — the thing PLAN.md §6 step 5 actually describes.
    """

    class Handle:
        def __init__(self, email: str) -> None:
            self.token = token_for(backend_url, email)

        def _client(self) -> Client:
            transport = streamable_http_client(
                mcp_http_url,
                http_client=httpx2.AsyncClient(headers={"Authorization": f"Bearer {self.token}"}),
            )
            return Client(transport)

        def tools(self) -> list[Tool]:
            async def go() -> list[Tool]:
                async with self._client() as client:
                    return (await client.list_tools()).tools

            return _run(go)

        def call(self, name: str, **arguments: Any) -> CallToolResult:
            async def go() -> CallToolResult:
                async with self._client() as client:
                    result = await client.call_tool(name, arguments)
                    assert isinstance(result, CallToolResult)
                    return result

            return _run(go)

    return Handle
