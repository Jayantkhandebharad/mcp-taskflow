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

- **Streamable HTTP** on `:9000/mcp` — `python -m app.server`, the default.
  What the chat client and Docker use. Each request carries the caller's JWT
  as `Authorization: Bearer <token>`; `BearerTokenMiddleware` (`app/auth.py`)
  verifies it with the same secret the backend signs with and sets
  `current_token` for that request only, before anything else runs. Nobody
  logs in at startup — HTTP mode never sees a password, only tokens.
- **stdio** via `python -m app.server --stdio`. A desktop client (Claude
  Desktop, Claude Code) launches the server as a subprocess and talks
  JSON-RPC over its stdin and stdout. There are no request headers, so the
  server logs in once at startup as the person named in its environment
  (`TASKFLOW_EMAIL` / `TASKFLOW_PASSWORD`). `app/auth.py` explains why that is
  not a service account.

## Running it

The backend must be up on `:8000` with the seed loaded (see the root README).
Then, from this folder:

```bash
uv sync                                                    # one-time
uv run python -m app.server                                # HTTP on :9000/mcp — the default
TASKFLOW_EMAIL=alice@example.com TASKFLOW_PASSWORD=password \
  uv run python -m app.server --stdio                      # waits for a client on stdin
uv run pytest                                              # starts its own backend on a free port
```

A curl'd `tools/call`, with a real JWT, against the HTTP server:

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"alice@example.com","password":"password"}' | python3 -c 'import json,sys;print(json.load(sys.stdin)["access_token"])')

# Streamable HTTP needs an initialize handshake first — a session id comes back
# on the response headers, and every later call on the session repeats it.
SESSION=$(curl -s -i -X POST http://localhost:9000/mcp \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl","version":"0"}}}' \
  | grep -i '^mcp-session-id:' | tr -d '\r' | cut -d' ' -f2)

curl -s -X POST http://localhost:9000/mcp \
  -H "Authorization: Bearer $TOKEN" -H "Mcp-Session-Id: $SESSION" \
  -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","method":"notifications/initialized"}' >/dev/null

curl -s -X POST http://localhost:9000/mcp \
  -H "Authorization: Bearer $TOKEN" -H "Mcp-Session-Id: $SESSION" \
  -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"whoami","arguments":{}}}'
# → Alice Adams. Drop the Authorization header and the same call gets a plain 401,
# before the request reaches the MCP protocol at all.
```

Running the stdio form by hand isn't very useful — it sits there waiting for
JSON on stdin. Point a real client at it instead:

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

The tests spawn the server the same way a real client does — a subprocess,
stdio or HTTP, with a near-empty environment — and drive it with the MCP
SDK's own client. Nothing is mocked; the fixtures in `tests/conftest.py`
start the real backend on a free port and reseed first, so `uv run pytest`
needs the Compose Postgres up and `uv` on `PATH`, like the backend's tests.

## What lives here

```
app/
  server.py       the MCPServer instance, tool registration; HTTP (default) and `--stdio` entry points
  auth.py         `current_token`, BearerTokenMiddleware — how each transport sets it
  backend.py      httpx2 calls to the backend; HTTP failures → ToolError sentences
  config.py       BACKEND_URL, JWT_SECRET/ALGORITHM, MCP_PORT, TASKFLOW_EMAIL/PASSWORD; finds the repo-root .env
  tools/
    me.py         whoami                  (phase 7: my_tasks)
    projects.py   list_projects           (phase 7: create_project, project_summary, add_project_member)
  resources.py    phase 8 — taskflow://project/{key} · taskflow://task/{key}-{number}
  prompts.py      phase 8 — standup · triage
  gating.py       phase 8 — which tools this user may even see
scripts/
  claude_desktop.py   registers the server with Claude Desktop
tests/
  conftest.py     starts the real backend; launches the server over stdio and over HTTP
  test_stdio.py   the two tools over stdio, scoped by token; startup failures are sentences
  test_http.py    the two tools over HTTP, one shared server for two users; bad tokens get a clean 401
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
- **Phase 6 (done)** — Streamable HTTP on `:9000/mcp`, now the default
  transport; `BearerTokenMiddleware` verifies the caller's JWT and sets
  `current_token` per request; eight new tests (sixteen total), plus a
  curl'd `tools/call` with a real JWT (see "Running it" above).
- **Phase 7** — the other ten tools. **Phase 8** — gating, resources, prompts.

See `PLAN.md` §6, §8, `docs/decisions/0002-*`, and `docs/briefs/phase-6.md`.
