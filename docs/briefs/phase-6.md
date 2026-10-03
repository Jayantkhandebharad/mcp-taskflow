# Phase 6 — MCP over HTTP, with auth: Streamable HTTP and the bearer token per request

**Commits (oldest → newest):**

| SHA | What |
|---|---|
| `88c2002` | mcp-server: Streamable HTTP as the default transport, `BearerTokenMiddleware`, `JWT_SECRET`/`MCP_PORT` config, the HTTP test fixtures and eight HTTP tests, the old "no `--stdio` → error" test removed |
| _(next)_ | this brief + status docs |

The post for this phase ("MCP over HTTP, with auth", PLAN.md §11) should pin
`mcp-server/app/auth.py`, `app/server.py`, `app/config.py`, `tests/conftest.py`
and `tests/test_http.py` to `88c2002`. The backend did not change; the tests
pass at that SHA against the phase-3 backend and the phase-1 seed.

## Files worth showing in the post

| File | Why |
|---|---|
| `mcp-server/app/auth.py` | The whole phase in one file. The docstring now has three parts: how each transport gets the token in, why it's a `ContextVar`, and a new section on why we wrote ~50 lines instead of using the SDK's auth. `BearerTokenMiddleware` is plain ASGI — reads `scope["type"]` and one header, never the body. |
| `mcp-server/app/server.py` | `main()` is now a two-way switch. `_run_http()` is four lines: build the Starlette app, add the middleware, hand it to uvicorn. Note what is *absent*: no login. |
| `mcp-server/app/config.py` | `JWT_SECRET` and `JWT_ALGORITHM` with the same names and defaults as the backend's — the one shared value in the system, and the docstring says so. |
| `mcp-server/tests/conftest.py` | `mcp_http_url` is `scope="session"`: one server process for every HTTP test, because identity now rides per request. Contrast with `as_user`, which still spawns a process per call for stdio. The two fixtures side by side *are* the phase. |
| `mcp-server/tests/test_http.py::test_list_projects_over_http_is_scoped_per_caller_on_one_shared_server` | Alice and Bob on the same running server, each seeing only their own. Phase 5 needed two processes to show this. |
| `mcp-server/tests/test_http.py::test_session_id_is_not_identity` | Bob sends Alice's `Mcp-Session-Id` with his own token and gets Bob's answer. A fence around "the token decides, never the session". See *What surprised us*. |
| `mcp-server/README.md`, "Running it" | The four-curl sequence that is this phase's done-when: login, `initialize`, `notifications/initialized`, `tools/call`. It is longer than a one-liner, and the post should say why (below). |

## What we built

`python -m app.server` with no flag now serves Streamable HTTP on `:9000/mcp`.
Each request carries `Authorization: Bearer <jwt>`; `BearerTokenMiddleware`
verifies the signature and expiry with the shared `JWT_SECRET`, sets
`current_token` for that request, and everything from `backend.py` down is
unchanged from phase 5. A missing, malformed, forged or expired token gets a
plain HTTP 401 before the request reaches the MCP app. `--stdio` behaves
exactly as in phase 5.

Sixteen tests, under eight seconds, nothing mocked. Eight of them are new:
three go through the SDK's real `Client` over a real socket with real tokens
from a real `/auth/login`; four send raw requests with bad tokens and assert
the 401; one opens a session as Alice and calls as Bob. The old test that
asserted "no `--stdio` → exit 2" is gone, because the same command line now
serves forever — it hung the suite for 60 s before it was removed, which is
how we noticed the HTTP server came up on the first try.

Two new dependencies in `pyproject.toml`, both already installed transitively
and both now declared because we import them directly: `pyjwt` (same range as
the backend) and `uvicorn` (we call `uvicorn.run` ourselves — see below).

Verified by hand, not only by pytest: a real JWT, four curls, `whoami` answers
as Alice; drop the header, same call, 401. The transcript is in the README.

## Decisions made along the way

**HTTP is the default; `--stdio` is the flag.** PLAN.md §8 said so from the
start, and phase 5 required the flag precisely so that this flip would not
change any Desktop config. It didn't.

**Our own middleware, not the SDK's auth.** The SDK ships
`AuthSettings` / `TokenVerifier` / `RequireAuthMiddleware`, and it is good.
It is also an OAuth 2.1 *resource server*: `AuthSettings.issuer_url` is
required and means "the authorization server that issues your tokens";
`AccessToken` requires `client_id` and `scopes`; the 401 carries a
`WWW-Authenticate` header pointing at `/.well-known/oauth-protected-resource`
so a client can discover how to log in. We have none of those things, on
purpose (ADR 0002: the backend issues its own HS256 JWT; PLAN.md §6 defers
OAuth). Using the SDK's auth would have meant inventing a `client_id`, an
issuer URL for a server that doesn't exist, and a `scopes` list — and the
natural thing to put in `scopes` is the user's role, which is exactly the
roles-in-token design ADR 0002 rejects. So: the SDK's `BearerAuthBackend`,
minus the OAuth vocabulary, in our own 50 lines. When the OAuth bonus phase
lands, these 50 lines are deleted and the SDK's go in. The cost is recorded
under *Known limitations*.

**Verify here, and again at the backend.** PLAN.md §6's "two checks, on
purpose". Ours is an optimisation and a courtesy: garbage is rejected without
a round trip, and the client gets a 401 at the door instead of a sad tool
result after a successful handshake. The backend's check is the gate, because
the frontend and curl reach `:8000` without passing through us. Drop ours and
things get slower and ruder; drop the backend's and `:8000` is open.

**Claims are thrown away.** `_verify_signature` decodes and discards. The MCP
server still has no `user` object, no role, no email it acts on. The backend
reads `sub` fresh on every call. Keeping it this way is what makes "the MCP
server has no credentials of its own" stay true over HTTP.

**`uvicorn.run` ourselves instead of `server.run("streamable-http")`.** The
SDK's `run_streamable_http_async` builds the Starlette app and hands it to
uvicorn with no hook to add middleware. So `_run_http()` calls
`server.streamable_http_app()` (public, returns a Starlette instance), calls
`.add_middleware(BearerTokenMiddleware)`, and runs uvicorn directly. Four
lines, and it is why `uvicorn` is now declared in `pyproject.toml`.

**Port from the environment, host hardcoded.** `MCP_PORT` was already in
`.env.example`; tests set it to a free port the same way the backend fixture
does. The bind host is `127.0.0.1` in code — the same as the backend's
`uvicorn` default. Phase 12 will need `0.0.0.0` inside a container and will
add `MCP_HOST` then, not now.

**One server process for all HTTP tests.** Stdio had to spawn a process per
user because the login was baked in at startup. HTTP doesn't: the user is
whatever the header says. `mcp_http_url` is session-scoped; `as_http_user`
only changes the `Authorization` header. The stdio suite was 66 s for eight
tests; the HTTP suite is under 8 s for sixteen. That number is the clearest
demonstration of what "identity per request" buys.

**Raw requests for the 401 tests, the real client for the 200s.** CLAUDE.md's
rule is "test like the real client, not an ideal one". The 401 tests send
`httpx2.post(url)` with no body and no `Accept` — not valid MCP. That is
honest because the code under test reads `scope["type"]` and one header and
never calls `receive()`; a real client with a bad token hits the identical
path, and the body it would have sent is never looked at. The success tests
go through `mcp.Client` because *that* path runs the SDK's session manager,
which very much reads the body. One sentence for the post: *a raw request is
fine when the code under test cannot tell the difference.*

## What went wrong

### A curl one-liner was never going to work

**Symptom.** PLAN.md's done-when is "a curl'd `tools/call` with a real JWT
works". The first attempt was one curl. It got `400 Bad Request: Missing
session ID`.

**Root cause.** Streamable HTTP is stateful by default. `tools/call` needs a
session, a session needs `initialize`, and the session id comes back in a
response header (`mcp-session-id`) that every later call must repeat. A
`notifications/initialized` is expected between the two. And every request
needs `Accept: application/json, text/event-stream` or the transport answers
406.

**Fix.** Four curls, documented in `mcp-server/README.md`. The done-when is
met; the post should show the handshake rather than pretend a single curl
does it, because a reader who tries the single curl will get the 400.

### The old "no flag" test hung the suite

**Symptom.** First `uv run pytest` after the change: 7 passed, 1 failed
after 60 s with `TimeoutExpired`. The subprocess's stderr showed `Uvicorn
running on http://127.0.0.1:9000`.

**Root cause.** `test_without_the_flag_it_says_what_is_missing` asserted that
`python -m app.server` exits 2 with "phase 6" on stderr. It now serves
forever. The test's premise was the thing this phase removes.

**Fix.** Deleted it; `test_http.py` is its replacement. The failure was good
news: the HTTP server came up before any HTTP test existed.

### `/health` said yes while Postgres was down

**Symptom.** Two days into the phase, a hand probe got empty bodies from
`/auth/login` even though the fixture-style wait loop on `/health` had passed.
The backend log: `connection to server at "127.0.0.1", port 5433 failed`.
Docker Desktop had stopped overnight.

**Root cause.** `/health` returns `{"status": "ok"}` without touching the
database. It proves the process is up, not that it can do anything.

**Fix.** For the probe, check `pg_isready` first. For the repo: nothing
changed yet, but the phase-12 healthcheck must hit the database, not `/health`
as it is. Noted for then.

### zsh does not split `$H`

**Symptom.** The session-ownership probe, written as a shell script with the
MCP headers in a variable (`H='-H Content-Type:… -H Accept:…'`) and expanded
unquoted, got 406 and a server log line showing a session id of
`deadbeef… Content-Type:application/json -`.

**Root cause.** The shell here is zsh. zsh does not word-split unquoted
variables (`SH_WORD_SPLIT` is off), so `$H` was one argument and curl took
the whole string as a single header value. The first manual walkthrough had
worked only because its headers were written out literally.

**Fix.** Rewrote the probe in Python with `httpx2` and a headers dict. Kept
as the shape of `test_session_id_is_not_identity`. The README's curl examples
write every `-H` out in full for the same reason.

### `InsecureKeyLengthWarning` in the forged-token test

**Symptom.** One warning in the test output: the HMAC key is 19 bytes, below
the 32 recommended for SHA-256.

**Root cause.** The test signed the forged token with the literal
`"not-the-real-secret"`. PyJWT 2.13 warns on short keys at encode time.

**Fix.** A longer fake secret. Trivial; worth a line because the warning is
new in recent PyJWT and will surprise anyone copying the backend's test
helpers.

## What surprised us

- **The SDK's `ServerMiddleware` is the wrong tier for auth.** The obvious
  hook — `MCPServer(middleware=[...])` — wraps each *JSON-RPC message*,
  after the HTTP request has been accepted and the body parsed. Its
  `ctx.request` is the Starlette `Request`, so headers *are* reachable there,
  but a rejection would be a JSON-RPC error inside a 200, and `initialize`
  would already have run. Transport-level auth belongs at the ASGI tier,
  before the SDK sees anything. An hour went into reading `context.py` and
  `runner.py` before that was clear; `Context.headers` has a docstring
  saying "Not currently constructed by `ServerRunner`", which did not help.
- **`Starlette.add_middleware` must run before the first request.** It
  inserts at index 0 of `user_middleware` and raises if the middleware stack
  has already been built. Fine for us (we add it right after construction),
  but it means you cannot bolt auth on to an app that has already served.
- **`streamable_http_app()` was always there.** The ASGI app existed,
  unused, throughout phase 5. Nothing about "stdio first" was an SDK
  limitation; it was our sequencing. The honest reason for the order: phase 5
  could be proven against a real existing client (Claude Desktop); phase 6's
  consumer, the chat client, is phase 9, so this phase can only be proven
  against curl and the SDK's own client.
- **Every reply is an SSE frame.** With the default `json_response=False`,
  even a single `tools/call` reply comes back as `Content-Type:
  text/event-stream` with `event: message` / `data: {...}`. The transport
  does this so a server can send progress, logs or a sampling request on the
  same response while the tool runs. `json_response=True` gives plain JSON
  and disables server→client requests. We left the default.
- **Sessions are a dict in RAM, 30-minute idle, 10 000 max.**
  `StreamableHTTPSessionManager._server_instances` keyed by the id. Unknown
  id → 404 `Session not found`; no id on a non-`initialize` → 400; over the
  limit → 503. Two replicas behind a load balancer would 404 each other's
  sessions. `stateless_http=True` makes a fresh transport per request and
  drops the dict; for a tools-only server it loses nothing. Phase 12's call.
- **The SDK's session-owner check is inert for us.** The manager binds a
  session to the credential that opened it and 404s a different one
  (`streamable_http_manager.py:270–279`) — but it reads `scope["user"]` and
  only acts when that is its own `AuthenticatedUser`. Our middleware never
  sets it, so `_session_owners` stays empty. Probed on 2026-10-01: Bob with
  Alice's session id and Bob's token gets `whoami` → Bob. No leak: the
  contextvar is per request, so the backend saw Bob. But the session object
  is shared, and that would matter the day a tool pushes a notification onto
  a session's GET stream. Pinned by `test_session_id_is_not_identity`;
  listed below.
- **HTTP tests are nearly ten times faster than stdio tests.** Not because
  HTTP is fast — because there is no bcrypt login per process. One login per
  *user* instead of per *test*.
- **Starlette runs each request in its own task, and that is the whole
  isolation story.** `create_task` copies the current context; `set()` in
  the middleware writes to that copy; `get()` in `backend.py` reads it in the
  same task. A module global instead would be last-writer-wins across users
  with no exception anywhere — Alice's backend call going out with Bob's
  token. The learner session on this (`.claude/skills/learn/progress.md`,
  2026-10-01) spent most of its time here, and it was time well spent.

## Known limitations (said plainly)

- **No `WWW-Authenticate` on our 401.** The SDK's auth sends one with a
  `resource_metadata` URL so an OAuth-speaking client can discover how to log
  in. Ours sends `{"detail": "..."}` and nothing else. Our own chat client
  (phase 10) will log in at the backend and hold the JWT, so it doesn't need
  discovery. A hosted MCP client that only knows the OAuth dialect would get a
  401 and have nowhere to go. That is the price of ADR 0002, and it is paid
  here.
- **The bearer convention is unvalidated by a real client.** Phase 10 is the
  first time something other than curl or the SDK's test client sends
  `Authorization: Bearer <jwt>` to this server. If the chat client turns out
  to need something else — a cookie it must translate, a refresh on expiry —
  that is where we find out. Kept the guessed surface small for that reason.
- **Session ownership is not enforced.** Above. A valid token plus someone
  else's session id lets you use their session *as yourself*. Harmless today;
  revisit if sessions ever carry server→client traffic.
- **Stateful sessions, one process.** Scaling out needs sticky routing on
  `Mcp-Session-Id` or `stateless_http=True`. Deferred to phase 12 with the
  rest of deployment.
- **One `httpx2.AsyncClient` per backend call, still unmeasured.** Every
  tool call opens a new TCP connection to `:8000`. ADR 0001 promised a
  measurement before optimising; we now have an HTTP path to measure on, and
  haven't.
- **Bind host is hardcoded to `127.0.0.1`.** Correct for the host phases,
  wrong inside a container. `MCP_HOST` arrives with phase 12.
- **Token expiry mid-session is the client's problem.** Over stdio the
  server restarts to renew. Over HTTP the server just 401s and the client
  must log in again. No refresh tokens (ADR 0002).
- **No screenshots this phase.** Nothing visual changed; the curl transcript
  in the README is the evidence. A private learning artifact ("Request
  Isolation Atlas") was drawn for the mentoring session; it is not repo
  content and not reproducible from a clone, so it is not referenced from
  the post.

## For the post

Phase 5 ended with "the hard part of an MCP server is identity, not
protocol". Phase 6 is the proof: the transport changed completely, and the
only line that moved is *where* `current_token.set()` is called. The
interesting material is all in the margins — why we didn't take the SDK's
auth, what a session is and isn't, and the one-sentence reason a ContextVar
is not a convenience but a correctness requirement. If the reader comes away
able to explain, cold, what Alice would see with a module global, the post
did its job.

## Next: phase 7

The other ten tools. `create_project`, `project_summary`,
`add_project_member`, `list_tasks` with filters, `create_task`,
`update_task_status`, `assign_task`, `comment_on_task`, `my_tasks`,
`delete_task`. Descriptions written for a model; errors that tell it what to
do next; human identifiers only. `backend.py` grows `post`, `patch`, `delete`.
No transport work.
