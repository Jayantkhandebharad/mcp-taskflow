# Phase 5 — The first MCP server: stdio, `whoami`, `list_projects`

**Commits (oldest → newest):**

| SHA | What |
|---|---|
| `2c33538` | mcp-server: `MCPServer` over stdio, `whoami` + `list_projects`, the backend client, stdio tests, the Claude Desktop script |
| _(next)_ | this brief + status docs |

The post for this phase ("Your first MCP server", PLAN.md §11 — a flagship)
should pin `mcp-server/app/server.py`, `app/auth.py`, `app/backend.py` and
`tests/test_stdio.py` to `2c33538`. The tests pass at that SHA against the
phase-4 backend, which did not change.

## Files worth showing in the post

| File | Why |
|---|---|
| `mcp-server/app/server.py` | The whole server is one object and one `run("stdio")`. The docstring carries stdio rule #1 (nothing but protocol on stdout), and `main()` logs in *before* serving so a bad password is a sentence at startup, not an error on the first tool call. |
| `mcp-server/app/auth.py` | Twelve lines of code, sixty of docstring — the post's core. The `current_token` contextvar from PLAN.md §6, why stdio sets it once and HTTP will set it per request, and why an email and password in the launcher's config is *your* login, not a service account. |
| `mcp-server/app/backend.py` | Errors are instructions, mechanically: every failed HTTP call becomes a `ToolError`, because that is the one exception the SDK relays to the model verbatim. The `_explain` function is the mapping from FastAPI's error bodies to sentences. |
| `mcp-server/app/tools/me.py` | A tool is a typed function with a docstring. The docstring is the description the model reads; the return annotation is the output schema the client advertises. The `WhoAmI` model is smaller than `/auth/me` on purpose — no UUIDs. |
| `mcp-server/tests/conftest.py` | "Test like the real client": the server is a subprocess with a six-variable environment, driven by the SDK's own `Client`, in front of a real backend the fixture starts on a free port. |
| `mcp-server/tests/test_stdio.py::test_list_projects_is_scoped_by_the_token` | ADR 0001 as one assertion. Alice's server sees WEB and API; Bob's sees WEB. The MCP server checked nothing. |
| `mcp-server/scripts/claude_desktop.py` | "No manual clicking that isn't also a script." The three things the config entry has to get right — absolute `uv`, `--directory`, the login in `env` — each with its reason. |

## What we built

The `mcp-server` folder went from a README to a running service: `pyproject.toml`
and `uv.lock`, seven modules under `app/`, two test files, one script. Two tools —
`whoami` and `list_projects` — over stdio, wired to Claude Desktop by running
`scripts/claude_desktop.py`, which merged the entry into the real config file
on this machine. Launched exactly as that entry says (absolute `uv`, `cwd=/`,
an environment of `HOME`, `PATH` and the two login variables), the server
answers `tools/list` with the two tools and both calls succeed.

Eight tests, 6 seconds, nothing mocked. `.env.example` (and this machine's
`.env`) changed `BACKEND_URL` to `http://localhost:8000` for the host phases,
with the same "two answers" comment `POSTGRES_HOST` got in phase 1.

## Decisions made along the way

**`mcp` 2.x, not a pin to 1.x.** The current SDK renamed `FastMCP` to
`MCPServer` and moved it to `mcp.server.mcpserver`. PLAN.md, the SDK's own
README on PyPI, and every tutorial say `FastMCP`. We could have pinned `mcp<2`
to match the plan; instead the code uses the name a reader gets from `pip
install mcp` today, and PLAN.md §2 grew a parenthetical. The error message the
SDK prints on the old import path is excellent, and is quoted below.

**Stdio logs in with email and password.** A stdio server gets no request
headers, so the token can't ride along the way PLAN.md §6 step 5 describes for
HTTP. Two options: put a *token* in the launcher's environment, or put a
*login* there. A token expires in twelve hours, so a config file holding one
is broken by tomorrow morning; a login works on every launch. We chose the
login and wrote down the cost: a password in `claude_desktop_config.json`.
`auth.py` argues why this is still "no credentials of its own" — they are the
human's credentials, on the human's machine, for a process acting as the
human. Phase 6's HTTP mode never sees a password.

**The contextvar arrives now, set once.** `current_token` could have been a
module global for stdio. It is a `ContextVar` from day one so that phase 6
changes *where it is set* (per request, from the header) and nothing else.
Setting it in the main thread before `server.run()` works because every task
the event loop creates copies the current context — and the tests prove it.

**Log in before serving.** A wrong password or a stopped backend fails at
startup with one sentence on stderr and exit code 1. Claude Desktop shows a
server that exited clearly; a server that answers every call with an error
looks like the model's fault.

**One `httpx2.AsyncClient` per call.** A pooled client is bound to the event
loop that created it, and in stdio mode the startup login runs on one loop
(`anyio.run`) and the tools on another (`server.run`). Per-call clients have
no cross-loop state. ADR 0001 promised to measure the extra hop before
optimising it; this is where that measurement will happen.

**Output models, not pass-through dicts.** `list_projects` returns
`list[ProjectRow]` with `key`, `name`, `description`, `my_role` — not the
backend's body, which also has `id` and `created_by`. Rule 1 of PLAN.md §8
(human identifiers) applies to what a tool *returns*, because whatever a tool
returns, the model will try to pass to the next one. A test checks the key
set.

**`server.add_tool(fn)` instead of `@server.tool()`.** The decorator needs
the server instance at import time, and the server module needs to import
the tool modules to register them — a circular import that works only if you
get the order right. Plain functions plus a one-line `register(server)` per
module has no order to get right, and keeps the whole tool list in one place
for phase 8's gating to filter.

**Tests spawn the real thing.** The SDK offers an in-process
`Client(server)` for tests. We use it nowhere. Each test launches `python -m
app.server --stdio` with a six-variable environment and talks to it through
the SDK's stdio client, in front of a real backend the session fixture starts
on a free port after re-running the seed. The cost is about a second per
process start; the benefit is that a `print()` on stdout, a dependency on the
launcher's environment, or a log line on the wrong stream would fail the
suite — none of which an in-process client can see.

**Claude Desktop wiring is a script.** `scripts/claude_desktop.py` writes the
entry, keeps a `.bak`, and prints it. `--dry-run` prints without writing, so
the same JSON serves any stdio-launching client. It was run on this machine;
the entry it wrote was then launched by hand, from `/`, with a stripped
environment, and both tools answered.

**The `--stdio` flag is required today.** HTTP is the default transport in
PLAN.md §8 and arrives in phase 6. Requiring the flag now means the Desktop
config written today keeps working after phase 6 lands.

## What went wrong

### The driver grep caught our own comment

**Symptom.** CLAUDE.md rule 2 (`grep -rniE 'psycopg|sqlalchemy|asyncpg'
mcp-server/`) printed one line: the `pyproject.toml` comment saying "no
SQLAlchemy, no psycopg".

**Root cause.** The check is a grep for words, and a comment is words.

**Fix.** Reworded the comment to "no ORM, no database driver of any kind",
with a note that the grep is why it doesn't name them. Trivial, and worth
keeping: a check that is just a grep will catch prose, and that is fine — the
alternative is a check that needs a parser.

### Nothing else

The server ran on the first try, the tests passed on the first run, and the
Desktop entry launched from a stripped environment. Most of that is because
the API was probed *before* any file was written (a scratch venv, the SDK's
`Client` against a throwaway `MCPServer`, four fake tools) — which turned up
every surprise below while it was still cheap.

## What surprised us

- **`FastMCP` is gone.** `from mcp.server.fastmcp import FastMCP` on 2.x
  raises: *"This is mcp 2.x, where FastMCP was renamed to MCPServer (from
  mcp.server.mcpserver import MCPServer) and other APIs changed; see the
  migration guide … or pin 'mcp<2' to keep running v1 code."* The best
  ImportError we've ever seen. Quote it in the post.
- **Snake case on the Python side.** In 2.x every model field is
  `snake_case` (`tool.input_schema`, `result.is_error`,
  `result.structured_content`) while the wire stays `camelCase`
  (`inputSchema`, `isError`, `structuredContent`). The first probe script
  crashed on `t.inputSchema`. Use `model_dump(by_alias=True)` to see what
  actually went over the wire.
- **The two error paths look different to the model.** `raise ToolError("No
  project 'WEBB'. Call list_projects.")` reaches the model as *"Error
  executing tool boom: No project 'WEBB'. Call list_projects."* with
  `isError: true`. `raise RuntimeError("unexpected")` reaches it as *"Error
  executing tool crash"* — nothing else — and the traceback goes to the
  server's log. That single difference is why `backend.py` exists.
- **A return annotation is an output schema.** `-> WhoAmI` makes the SDK
  advertise a JSON schema in `tools/list` and return both a text block (the
  JSON, pretty-printed) and `structuredContent`. `-> list[ProjectRow]` gets
  wrapped as `{"result": [...]}` because a bare array isn't an object. No
  code for either.
- **Sync tools run in a worker thread.** The migration guide says a `def`
  tool is run via `anyio.to_thread.run_sync`; there is no event loop in that
  thread. Ours are `async def` for that reason, and because phase 6's HTTP
  transport will want them on the loop anyway.
- **A stdio client passes almost no environment.** The SDK's default is
  `HOME`, `LOGNAME`, `PATH`, `SHELL`, `TERM`, `USER` — six variables. Claude
  Desktop is similar, and its `PATH` is the OS default, not your shell's. So:
  absolute path to `uv` in the config, `--directory` so `uv` finds the
  project, and the repo-root `.env` located from `config.py`'s own file
  path rather than the working directory. The tests hand the server the same
  six-ish variables so a regression here fails locally.
- **Stdin EOF is a clean exit.** Run the server by hand in a terminal with
  nothing attached to stdin and it exits at once, code 0. That is correct —
  the client hung up — and confusing for ten seconds. It also bit the
  "drive it with `printf | python -m app.server`" demo: `printf` closes the
  pipe the moment it has written, so the server saw EOF before it had
  answered the second request and the reply was `Connection closed`. Keep
  the pipe open (`(printf …; sleep 3) | …`) and all three answers arrive.
- **A tool list is not a fence.** Asked about projects, tasks and members
  with only two tools available, Claude Code called `whoami` and
  `list_projects` — and then said "tasks and members aren't accessible
  through it yet, I'll fetch those directly from the backend API", and did,
  with curl against port 8000 as Alice (screenshot 9). Nothing went wrong:
  it acted as the same person, through the same API, with the same
  permissions. But it is the sharpest preview of PLAN.md §8's line that
  gating is UX, not security: an agent with a shell treats a missing tool
  as an inconvenience. The phase-9 chat client has no shell, so for it the
  tool list *is* the whole world — and the backend's `require_admin` is the
  fence for both.
- **A client loads its MCP servers at session start.** After `claude mcp
  add-json`, the session already open in VS Code showed no `taskflow`; a new
  session did (screenshots 7 and 7b). Obvious in hindsight, ten minutes of
  "is the config in the wrong place?" in the moment.
- **What "the backend is down" looks like from the client.** Next morning,
  Docker wasn't running, so neither was the backend. Claude Code's session
  reported `taskflow (CONNECTION_CLOSED): "Connection closed"` and nothing
  more. The sentence — *"The TaskFlow backend at http://localhost:8000 is
  not reachable. Start it (…) and try again."* — was there, on stderr, in
  the client's log, exactly as designed; the client's summary just doesn't
  quote it. Log-in-before-serve was still the right call: the failure is
  one line at startup rather than an error on every tool call.
- **httpx2 logs each request at INFO on stderr** (`HTTP Request: GET
  http://localhost:8000/projects "HTTP/1.1 200 OK"`). Handy in Desktop's log;
  no header values, so no token leaks into it.

## Screenshots

In `scratch/screenshots/` (gitignored; copy into the post's assets):

| File | Shows |
|---|---|
| `7-claude-code-vscode-before-new-session.png` | Claude Code in VS Code, MCP servers dialog, *no* taskflow — the session predates the config entry. |
| `7b-claude-code-vscode-taskflow-connected.png` | Same dialog in a fresh session: `Local (1) · taskflow · Connected`. |
| `8-claude-desktop-mcp-servers-taskflow.png` | Claude Desktop's MCP servers dialog for this project: `taskflow · Desktop · Local ✓`. |
| `9-claude-desktop-whoami-list-projects.png` | The money shot: `Used taskflow: whoami` → Alice Adams, `Used taskflow: list projects` → API and WEB as admin. And then the agent going *around* the server (below). |
| `10-claude-desktop-list-projects-only.png` | Told "only use the list project mcp tool": the tool's output alone, as a table. |

## Known limitations (said plainly)

- **Password in the Desktop config.** The stdio trade, above. Phase 6's HTTP
  transport removes it for the chat client; a desktop client over stdio will
  keep it until we add a token-in-env option or an OAuth flow (series #1
  covers the latter).
- **Twelve-hour sessions, restart to renew.** The token is fetched once at
  startup. When it expires, every tool returns the "restart the MCP server"
  sentence. Correct, and clunky.
- **The screenshots are of Claude Desktop's *Code* mode, not its chat.**
  Both entries (Desktop's config and Claude Code's local scope) point at the
  same command, and Desktop's Code session shows `taskflow · Desktop · Local ✓`
  and calls both tools. The plain chat's tool picker was not captured; the
  server it would launch is the same one.
- **Claude Code: verified, by CLI only.** `claude mcp add-json taskflow
  '<the --dry-run entry>' -s local` followed by `claude mcp list` shows
  `taskflow … ✔ Connected`. We did not go on to ask it a question through
  the tools; that is the Desktop screenshot's job.
- **No HTTP transport.** `python -m app.server` without `--stdio` exits with
  "arrives in phase 6".

## For the post

An MCP server is a thin thing. Two tools took seven small files, and the
only file with real thought in it is the one that decides *who the server is
acting as*. Everything else — schema, transport, error relay — the SDK does
from type hints and docstrings. If the reader comes away thinking "the hard
part of an MCP server is identity, not protocol," the rest of the series
(HTTP passthrough, gating, the client) follows from that.

## Next: phase 6

Streamable HTTP on `:9000/mcp`. `current_token` set per request from the
`Authorization` header, verified with the shared `JWT_SECRET` before
forwarding. `curl` a `tools/call` with a real JWT and watch it work.
