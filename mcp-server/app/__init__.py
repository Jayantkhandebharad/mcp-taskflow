"""The TaskFlow MCP server.

One job: translate the backend's REST API into MCP tools an AI can call. It
stores nothing, has no database connection, and holds no credentials of its
own — every call it makes to the backend carries the token of the human
whose AI is asking. See ``mcp-server/README.md`` and ADR 0001.
"""
