"""Tools about projects: ``list_projects`` now; ``create_project``,
``project_summary`` and ``add_project_member`` in phase 7."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer
from pydantic import BaseModel

from app import backend


class ProjectRow(BaseModel):
    """One line of ``list_projects``: the key the model will use, the name a
    human will recognise, and the caller's role, which decides what the
    other tools will let them do."""

    key: str
    name: str
    description: str | None
    my_role: str  # "admin" or "member"


async def list_projects() -> list[ProjectRow]:
    """The TaskFlow projects the current user belongs to, with their role in each.

    Use this to find a project's key (for example WEB or API) before calling
    any tool that takes one, or when the user asks what projects they have.
    Takes no arguments. There is no list of *all* projects: a project the
    user is not a member of does not exist for them, and neither does its
    key.
    """
    rows = await backend.get("/projects")
    return [
        ProjectRow(key=r["key"], name=r["name"], description=r["description"], my_role=r["my_role"])
        for r in rows
    ]


def register(server: MCPServer) -> None:
    server.add_tool(list_projects)
