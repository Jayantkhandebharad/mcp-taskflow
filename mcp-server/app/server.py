"""The MCP server: one ``MCPServer`` instance, and how to start it.

Two ways to run it:

    uv run python -m app.server                # Streamable HTTP on :9000/mcp (the default)
    uv run python -m app.server --stdio         # stdin/stdout, for Claude Desktop / Claude Code

HTTP is the default per PLAN.md §8 — it's what the chat client and Docker
use. ``--stdio`` exists for local desktop clients that launch the server as a
subprocess and have no way to send an HTTP request.

Stdio rule #1: **nothing but protocol goes to stdout.** A stray ``print``
corrupts the stream and the client disconnects with a parse error. Logs go
to stderr (the SDK's logger already does; so does ``sys.exit(message)``),
and a desktop client shows stderr in its own log file.
"""

from __future__ import annotations

import argparse
import sys

import anyio
import uvicorn
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from app import backend
from app.auth import BearerTokenMiddleware, current_token
from app.config import get_settings
from app.tools import register_all

server = MCPServer(
    name="taskflow",
    # Shown to the model by clients that support it — a one-paragraph
    # briefing before it sees the tool list.
    instructions=(
        "TaskFlow is a small task tracker: projects (identified by a short "
        "key like WEB), tasks (WEB-14), members and comments. Every tool acts "
        "as the logged-in user; call whoami to see who that is and "
        "list_projects to see their projects and roles."
    ),
)
register_all(server)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.server", description=__doc__.split("\n\n")[0])
    parser.add_argument("--stdio", action="store_true", help="serve over stdin/stdout (for Claude Desktop, Claude Code, the tests)")
    args = parser.parse_args(argv)

    if args.stdio:
        _run_stdio()
    else:
        _run_http()


def _run_stdio() -> None:
    settings = get_settings()
    if not settings.taskflow_email or not settings.taskflow_password:
        sys.exit(
            "stdio mode needs TASKFLOW_EMAIL and TASKFLOW_PASSWORD in the environment: "
            "the server acts as that user for the whole session. See app/auth.py."
        )

    # Log in once, before serving. A wrong password or a backend that isn't
    # running fails *here*, with a sentence, instead of on the first tool
    # call — a desktop client shows a server that exited at startup much
    # more clearly than one that answers every call with an error.
    try:
        token = anyio.run(backend.login, settings.taskflow_email, settings.taskflow_password)
    except ToolError as exc:
        sys.exit(f"Could not log in to TaskFlow as {settings.taskflow_email}: {exc}")

    # Set in the main thread before the event loop starts, so every task the
    # server creates inherits it (a new task copies the current context).
    current_token.set(token)
    server.run("stdio")


def _run_http() -> None:
    # No login here: nobody to log in as yet. Each request brings its own
    # token, verified per request by BearerTokenMiddleware (app/auth.py).
    settings = get_settings()
    http_app = server.streamable_http_app()
    http_app.add_middleware(BearerTokenMiddleware)
    uvicorn.run(http_app, host="127.0.0.1", port=settings.mcp_port, log_level="info")


if __name__ == "__main__":
    main()
