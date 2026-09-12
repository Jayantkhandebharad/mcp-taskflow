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
the design rather than being checked for — `tests/test_stdio.py::
test_list_projects_is_scoped_by_the_token` is the proof.

## Two ways in, one set of tools

- **stdio** via `python -m app.server --stdio` — what exists today. A desktop
  client (Claude Desktop, Claude Code) launches the server as a subprocess and
  talks JSON-RPC over its stdin and stdout. There are no request headers, so the
  server logs in once at startup as the person named in its environment
  (`TASKFLOW_EMAIL` / `TASKFLOW_PASSWORD`). `app/auth.py` explains why that is
  not a service account.
- **Streamable HTTP** on `:9000/mcp` — phase 6. What the chat client and Docker
  will use. Each request carries the user's JWT as a bearer header.

## Running it

The backend must be up on `:8000` with the seed loaded (see the root README).
Then, from this folder:

```bash
uv sync                                                    # one-time
TASKFLOW_EMAIL=alice@example.com TASKFLOW_PASSWORD=password \
  uv run python -m app.server --stdio                      # waits for a client on stdin
uv run pytest                                              # starts its own backend on a free port
```

Running it by hand isn't very useful — it sits there waiting for JSON on stdin.
Point a real client at it instead:

```bash
uv run python -m scripts.claude_desktop alice@example.com password
```

That merges a `taskflow` entry into `claude_desktop_config.json` (backing the
file up first) and prints what it wrote. Restart Claude Desktop, start a new
chat, and the two tools are under the tools button. Ask "who am I logged in
as?" and "what projects do I have?". Use `--dry-run` to see the entry without
writing it. The same JSON works for any client that launches stdio servers.
For Claude Code, from the repo root:

```bash
claude mcp add-json taskflow "$(uv run --directory mcp-server python -m scripts.claude_desktop alice@example.com password --dry-run | python3 -c 'import json,sys; print(json.dumps(json.load(sys.stdin)["mcpServers"]["taskflow"]))')" -s local
claude mcp list        # taskflow: ... - ✔ Connected
```

`-s local` keeps the entry (and the password) in your own Claude Code config,
not in the repo.

The tests spawn the server the same way a desktop client does — as a
subprocess, with a near-empty environment — and drive it with the MCP SDK's
own client. Nothing is mocked; the fixture in `tests/conftest.py` starts the
real backend on a free port and reseeds first, so `uv run pytest` needs the
Compose Postgres up and `uv` on `PATH`, like the backend's tests.

## What lives here

```
app/
  server.py       the MCPServer instance, tool registration, `--stdio` entry point
  auth.py         `current_token`, the context variable every outbound call reads
  backend.py      httpx2 calls to the backend; HTTP failures → ToolError sentences
  config.py       BACKEND_URL, TASKFLOW_EMAIL/PASSWORD; finds the repo-root .env
  tools/
    me.py         whoami                  (phase 7: my_tasks)
    projects.py   list_projects           (phase 7: create_project, project_summary, add_project_member)
  resources.py    phase 8 — taskflow://project/{key} · taskflow://task/{key}-{number}
  prompts.py      phase 8 — standup · triage
  gating.py       phase 8 — which tools this user may even see
scripts/
  claude_desktop.py   registers the server with Claude Desktop
tests/
  conftest.py     starts the real backend; launches the server over stdio
  test_stdio.py   the two tools, scoped by token; startup failures are sentences
```

## Tool design rules

1. Tools take **human identifiers** — `WEB-14`, `alice@example.com` — never UUIDs.
   The model has to be able to produce the argument from the conversation. The
   same rule applies to what tools *return*: `list_projects` gives keys and
   roles, not ids.
2. Descriptions are written **for a model**, not a developer. Say *when to use
   this*, not just what it does. The docstring is the description.
3. **Errors are instructions.** "No project with key 'WEBB'. GET /projects lists
   the ones you belong to." A model can recover from that. A 500 teaches it
   nothing. `backend.py` turns every failed HTTP call into a `ToolError` with a
   sentence, because that is the one exception type the SDK relays to the
   model verbatim.
4. **Small, sharp tools beat one clever tool.** No `manage_task(action=...)`.

## A note on the SDK's name

PLAN.md says "FastMCP". Version 2 of the official `mcp` package renamed that
class to `MCPServer` (`from mcp.server.mcpserver import MCPServer`); same
decorator-style API, new name. Tutorials written against 1.x still say
`FastMCP`, and `pip install mcp` gives you 2.x. `docs/briefs/phase-5.md` has
the other 2.x differences that bit us.

## Status

- **Phase 5 (done)** — `MCPServer` over stdio, `whoami` and `list_projects`,
  wired to Claude Desktop by script, eight tests through a real stdio client.
- **Phase 6** — Streamable HTTP on `:9000`, bearer token per request.
- **Phase 7** — the other ten tools. **Phase 8** — gating, resources, prompts.

See `PLAN.md` §8, `docs/decisions/0001-*`, and `docs/briefs/phase-5.md`.
