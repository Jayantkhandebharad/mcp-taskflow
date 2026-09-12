"""Tools about the caller: ``whoami`` (this phase), ``my_tasks`` (phase 7)."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer
from pydantic import BaseModel

from app import backend


class WhoAmI(BaseModel):
    """What ``whoami`` returns.

    Deliberately smaller than the backend's ``/auth/me`` body: no ``id``
    (a UUID the model has no use for and might try to pass to another
    tool), no ``is_active`` (always true if this call succeeded), no
    ``created_at``. A tool's output is designed, not dumped — PLAN.md §8,
    rule 1: human identifiers only.
    """

    email: str
    full_name: str


async def whoami() -> WhoAmI:
    """Who the current TaskFlow session belongs to.

    Use this when the user asks who they are logged in as, or to confirm the
    connection to TaskFlow works before doing anything else. Takes no
    arguments. Every other tool acts as this same person.
    """
    body = await backend.get("/auth/me")
    return WhoAmI(email=body["email"], full_name=body["full_name"])


def register(server: MCPServer) -> None:
    # The docstring becomes the description the model reads, and the return
    # annotation becomes the output schema the client advertises.
    server.add_tool(whoami)
