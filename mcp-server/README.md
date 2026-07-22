# mcp-server

**Its one job:** translate the backend's REST API into MCP tools an AI can call.

It stores nothing. It has no database connection, no ORM, and no knowledge of our
schema. It speaks HTTP to `fastapi-backend` like any other client — carrying the
token of whichever human is talking to the AI.

## The rule this whole folder is built around

> **The MCP server has no credentials of its own.** Everything it does, it does as
> the person whose AI is asking. There is no service account, no admin key, and no
> "trust me, I'm the AI" path into the data.

If Alice can't see project WEB, neither can Alice's assistant. That falls out of
the design rather than being checked for.

## Two ways in, one set of tools

- **Streamable HTTP** on `:9000/mcp` — the default; what the chat client and
  Docker use.
- **stdio** via `python -m app.server --stdio` — so you can point Claude Desktop
  or Claude Code at it locally and see your own tools in a real client.

## What will live here

```
app/
  server.py       FastMCP instance, transport wiring
  auth.py         read the bearer token, verify it, hold it for the request
  backend.py      httpx client — attaches that token to every outbound call
  tools/          one module per tool group
  resources.py    taskflow://project/{key} · taskflow://task/{key}-{number}
  prompts.py      standup · triage
  gating.py       which tools this user may even see
```

## Tool design rules

1. Tools take **human identifiers** — `WEB-14`, `alice@example.com` — never UUIDs.
   The model has to be able to produce the argument from the conversation.
2. Descriptions are written **for a model**, not a developer. Say *when to use
   this*, not just what it does.
3. **Errors are instructions.** "No project with key 'WEBB'. Call list_projects to
   see the keys you have access to." A model can recover from that. A 500 teaches
   it nothing.
4. **Small, sharp tools beat one clever tool.** No `manage_task(action=...)`.

## Status

Phase 5 builds the first tools over stdio. Phase 6 adds HTTP and auth
passthrough. Phase 7 fills out the toolset. Phase 8 adds gating, resources and
prompts. Nothing here yet.

See `PLAN.md` §8 and `docs/decisions/0001-*`.
