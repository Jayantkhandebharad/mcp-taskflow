"""Fixtures that make the MCP server's tests behave like a real client.

Nothing is mocked. A test here spawns the server exactly the way Claude
Desktop does — as a subprocess, ``python -m app.server --stdio``, with a
near-empty environment — and talks to it with the MCP SDK's own ``Client``
over stdin/stdout. Behind the server is the *real* fastapi-backend, started
once per test run on a free port against the Compose Postgres, with the demo
seed loaded. (CLAUDE.md: "test like the real client, not an ideal one.")

What that costs: each test that talks to the server pays a process start
(about a second: importing the SDK, then a real ``/auth/login`` with
bcrypt). A dozen tests is fine; a thousand would want the in-process
``Client(server)`` the SDK also offers. We'll switch when it hurts, not
before — the subprocess is the thing that will really call us.

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
