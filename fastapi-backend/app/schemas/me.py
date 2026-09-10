"""Response bodies for ``/me/*``."""

from __future__ import annotations

from pydantic import BaseModel


class CapabilitiesOut(BaseModel):
    """What the caller is allowed to do, as facts — not as tool names.

    This shape exists for the MCP server (PLAN.md §8): before it shows a
    user their tool list, it asks this route and hides admin-only tools
    from people who can't admin anything. The backend answers with facts
    about *membership*; deciding which tools those facts unlock is the MCP
    server's job. That way the rule "only admins delete" is written once,
    here, and the gate can never drift from it.
    """

    can_admin_any_project: bool
    admin_project_keys: list[str]
