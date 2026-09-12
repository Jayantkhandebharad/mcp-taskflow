"""The tools, one module per group (PLAN.md §8).

Each module defines plain async functions and a ``register(server)`` that
adds them. The functions are ordinary Python — importable, readable,
testable — and the registration is one visible line per tool. Phase 8's
gating will filter this list per user; keeping the list in one place is
what makes that a small change.

    me.py         whoami · (phase 7) my_tasks
    projects.py   list_projects · (phase 7) create_project, project_summary, add_project_member
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from app.tools import me, projects


def register_all(server: MCPServer) -> None:
    me.register(server)
    projects.register(server)
