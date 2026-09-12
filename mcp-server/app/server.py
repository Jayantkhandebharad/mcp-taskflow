"""The MCP server: one ``MCPServer`` instance, and how to start it.

Run it over stdio — the transport desktop clients use to launch a local
server as a subprocess and talk JSON-RPC over its stdin and stdout::

    uv run python -m app.server --stdio

The Streamable HTTP entry point on :9000 arrives in phase 6; until then the
flag is required so the command line stays the same when it does.

Stdio rule #1: **nothing but protocol goes to stdout.** A stray ``print``
corrupts the stream and the client disconnects with a parse error. Logs go
to stderr (the SDK's logger already does; so does ``sys.exit(message)``),
and a desktop client shows stderr in its own log file.
"""

from __future__ import annotations

import argparse
import sys

import anyio
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from app import backend
from app.auth import current_token
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
    if not args.stdio:
        parser.exit(2, "Streamable HTTP on :9000 arrives in phase 6. For now, run with --stdio.\n")

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


if __name__ == "__main__":
    main()
