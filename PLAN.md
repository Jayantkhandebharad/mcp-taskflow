# TaskFlow — MCP From Scratch, Properly

> **What this is:** the single source of truth for MCP project #2 and blog series #2.
> Small app, whole setup, every line understood. Drop this in as the repo's
> `CLAUDE.md` so any session can pick up here.
>
> **Supersedes** the earlier "Full-Stack + MCP + Cloud" plan in this file. That
> plan tried to do app + MCP + Kubernetes + cloud in one go. Kubernetes and cloud
> are now **deferred to a future series #3** so this one actually ships.

---

## 0. Why this project exists

Project #1 (`MCP-LMS-OSS`) wrapped Moodle. Moodle is a 20-year-old PHP monolith,
and a huge amount of energy went into *fighting Moodle* rather than *learning MCP*.
The blog series that came out of it is good and stays published — but a reader who
wants to learn MCP has to wade through Moodle web-service quirks to get there.

**This project removes the noise.** Every piece is ours, small, and readable.

**Goals, in priority order:**

1. **Understand every line.** The target reader — and the target author — is a
   trainee engineer. If a line of code exists, we can explain why. No copy-paste
   from a tutorial we didn't read.
2. **A complete, honest setup.** Four independent containerised services, a real
   database, real auth on both ends, one `docker compose up`. Nothing hand-waved,
   nothing mocked.
3. **Blog series #2** — the "learn MCP properly" series, written from a repo the
   reader can clone and run.
4. **Keep it small.** Boring app, interesting plumbing. Every feature must earn
   its place by teaching something about MCP.

**Non-goals:** Kubernetes, cloud deployment, scale, pixel-perfect design,
re-teaching what series #1 already covered (link back instead).

**What stays as-is:** `MCP-LMS-OSS` and its blog series (`mcp` slug in the
portfolio) remain published and untouched. This is a *new* repo and a *new* slug.

---

## 1. The app — TaskFlow

A minimal task/project tracker. Think "Trello with the fun removed."

**Why this one:** every reader already understands projects and tasks, so their
attention is free for the MCP layer. It has real multi-user structure (a project
has members with roles), which gives us an honest RBAC story — something a
single-owner app like an expense tracker can't provide. And the tools it produces
(`create_task`, `my_tasks`, `move_status`, `project_summary`) are exactly the
shape of tools people actually want to build.

**What it does:**

- A user signs up and logs in.
- A user creates a **project**. They become its **admin**.
- An admin adds other users to the project as **admin** or **member**.
- Any member creates **tasks** in that project, assigns them, moves them through
  statuses, and comments on them.
- Only an admin can delete a task or manage members.

That is the whole product. No sprints, no labels, no attachments, no
notifications. If you feel the urge to add one — write it in `docs/ideas.md`
instead.

---

## 2. Stack — locked

| Layer | Choice | Why |
|---|---|---|
| Database | **PostgreSQL 16** | Real DB, real migrations, real constraints |
| Backend | **FastAPI + SQLAlchemy 2.0 + Alembic + Pydantic v2** | Python end-to-end; type hints do the documenting |
| Auth | **Own JWT (HS256)** issued by the backend | Small enough to read in one sitting. Keycloak/OIDC becomes a *later* post, not a day-1 wall |
| MCP server | **Python + official `mcp` SDK (FastMCP)** | The reference implementation; what the docs describe |
| Chat client | **FastAPI + LangGraph + `langchain-mcp-adapters`** | The agent loop is visible, not hidden in a framework |
| LLM | **Provider-agnostic** — `init_chat_model()`, model named by one env var | Claude / GPT / Gemini / local Ollama, swapped without touching code. See §9.1 |
| Frontend | **React + Vite + TypeScript + Tailwind** | Matches the portfolio; no state library needed at this size |
| Packaging | **`uv`** per Python service | One tool, one lockfile, fast installs |
| Local infra | **Docker Compose** | One command boots the world |

**Deliberately not used:** Redis, Celery, nginx, Kubernetes, a message queue, an
ORM-free query builder, GraphQL. Each of those would be one more thing to explain.

---

## 3. Repository layout

Public GitHub repo, name: **`mcp-taskflow`**.

```
mcp-taskflow/
├── README.md                  # what it is, how to run it, architecture diagram
├── PLAN.md                    # this file (also copied to CLAUDE.md)
├── docker-compose.yml         # postgres + 4 services, one command
├── .env.example               # every variable, documented, no secrets
│
├── fastapi-backend/           # the system of record. owns the database.
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── alembic/               # migrations, checked in
│   ├── app/
│   │   ├── main.py            # FastAPI app, router wiring, CORS
│   │   ├── config.py          # pydantic-settings; all env in one place
│   │   ├── db.py              # engine, session, get_db dependency
│   │   ├── models/            # SQLAlchemy tables
│   │   ├── schemas/           # Pydantic request/response models
│   │   ├── routers/           # auth.py, projects.py, tasks.py, comments.py
│   │   ├── security.py        # password hashing, JWT encode/decode
│   │   └── deps.py            # current_user, require_member, require_admin
│   ├── scripts/seed.py        # deterministic demo data — rerunnable
│   └── tests/
│
├── mcp-server/                # the MCP layer. owns NO data.
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── app/
│       ├── server.py          # FastMCP instance, transport wiring
│       ├── auth.py            # read bearer token, verify, hold per-request
│       ├── backend.py         # httpx client that calls fastapi-backend
│       ├── tools/             # one module per tool group
│       ├── resources.py
│       ├── prompts.py
│       └── gating.py          # which tools this user may even see
│
├── chat-client/               # the MCP client. talks to the LLM.
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── app/
│   │   ├── main.py            # FastAPI: /login, /chat, serves the UI
│   │   ├── graph.py           # the LangGraph agent
│   │   ├── llm.py             # provider-agnostic model factory — the ONLY
│   │   │                      #   file that knows which vendor we're using
│   │   ├── mcp.py             # connects to one or many MCP servers
│   │   └── servers.yaml       # MCP servers this client knows about
│   └── static/                # plain HTML/CSS/JS chat page
│
├── frontend/                  # the normal web app. no MCP anywhere.
│   ├── Dockerfile
│   ├── package.json
│   └── src/
│
└── docs/
    ├── architecture.md
    ├── decisions/             # ADR-style: why we chose X
    └── briefs/                # phase-N.md — raw material for the blog posts
```

**The rule that keeps this clean:** each folder is one container, one
`Dockerfile`, one dependency file, one job. If you can't say a folder's job in one
sentence, it's doing too much.

---

## 4. Architecture

```
                        ┌──────────────────┐
   Browser ────HTTP────▶│    frontend      │ :5173   React app, no MCP
                        │   (React/Vite)   │
                        └────────┬─────────┘
                                 │ REST + JWT
                                 ▼
                        ┌──────────────────┐
                        │ fastapi-backend  │ :8000   ← the ONLY thing that
                        │  (FastAPI)       │            touches the database
                        └────────┬─────────┘
                                 │ SQL
                                 ▼
                        ┌──────────────────┐
                        │    postgres      │ :5432
                        └──────────────────┘
                                 ▲
                                 │ REST + the SAME JWT
                        ┌────────┴─────────┐
                        │   mcp-server     │ :9000   MCP tools/resources/prompts
                        │   (FastMCP)      │         over Streamable HTTP
                        └────────▲─────────┘
                                 │ MCP protocol + Bearer JWT
                        ┌────────┴─────────┐
   Browser ────HTTP────▶│   chat-client    │ :8100   LangGraph agent
                        │ (FastAPI+LangGraph)         + minimal chat UI
                        └────────┬─────────┘
                                 │ HTTPS
                                 ▼
                          Anthropic API (Claude)
```

### The decision that shapes everything

**The MCP server never touches the database.** It calls the backend's REST API,
exactly like the frontend does, carrying the user's own token.

Why this matters, and why we'll write a whole post about it:

- **One place enforces the rules.** "Only admins delete tasks" is written once, in
  the backend. If the MCP server queried Postgres directly, that rule would have to
  exist twice — and the two copies would drift.
- **The AI is not a superuser.** The MCP server has no privileged credentials of
  its own. It can only do what the *logged-in human's* token allows. If Alice can't
  see project WEB, neither can Alice's AI assistant.
- **It's honest about the cost.** There's an extra network hop. We'll measure it
  and say so, rather than pretending the clean design is free.

### The four jobs, one line each

| Service | Its one job |
|---|---|
| `fastapi-backend` | Own the data and enforce the rules. Knows nothing about MCP or AI. |
| `frontend` | Let a human use the app with a mouse. Knows nothing about MCP or AI. |
| `mcp-server` | Translate the backend's REST API into MCP tools an AI can call. Stores nothing. |
| `chat-client` | Let a human use the app by typing English. Runs the agent loop. |

Notice that the first two don't know MCP exists. **That's the point** — MCP is a
layer you add to a working app, not an architecture you build around.

---

## 5. Data model

Five tables. Read them top to bottom; each one only depends on the ones above it.

```
users ──┬──< project_members >──┬── projects
        │                       │
        │                       └──< tasks ──< comments
        └───────────────────────────┘
             (assignee, created_by, author)
```

### `users`
| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | generated in the app, not the DB — easier to log |
| `email` | text, unique, lowercased | the login identifier |
| `full_name` | text | shown in the UI and in tool output |
| `password_hash` | text | bcrypt via `passlib`. **Never** the password itself |
| `is_active` | bool, default true | soft "disable account" without deleting rows |
| `created_at` | timestamptz | |

### `projects`
| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `key` | varchar(10), unique, uppercase | `WEB`, `API`. Humans and AIs say "WEB-14", not a UUID |
| `name` | text | |
| `description` | text, nullable | |
| `created_by` | UUID → users.id | |
| `created_at` | timestamptz | |

> **Why `key` exists:** an LLM writing `get_task("WEB-14")` is far more reliable
> than an LLM writing `get_task("3f2b8c91-...")`. Designing identifiers that a
> language model can actually hold in its head is a real MCP design skill, and
> this column is where we teach it.

### `project_members`
| Column | Type | Notes |
|---|---|---|
| `project_id` | UUID → projects.id | part of composite PK |
| `user_id` | UUID → users.id | part of composite PK |
| `role` | enum `admin` \| `member` | |
| `added_at` | timestamptz | |

This tiny table is the entire authorisation model. Everything else asks it
questions.

### `tasks`
| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `project_id` | UUID → projects.id | |
| `number` | int | per-project counter. `UNIQUE(project_id, number)` → "WEB-14" |
| `title` | text | |
| `description` | text, nullable | |
| `status` | enum `todo` \| `in_progress` \| `in_review` \| `done` | |
| `priority` | enum `low` \| `medium` \| `high`, default `medium` | |
| `assignee_id` | UUID → users.id, nullable | must be a member of the project |
| `created_by` | UUID → users.id | |
| `due_date` | date, nullable | makes `overdue_tasks` and `standup` interesting |
| `created_at` / `updated_at` | timestamptz | |

### `comments`
| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `task_id` | UUID → tasks.id, ON DELETE CASCADE | |
| `author_id` | UUID → users.id | |
| `body` | text | |
| `created_at` | timestamptz | |

**Invariants the database enforces** (not just the code):
- A task's `assignee_id` must be a member of the task's project.
- `(project_id, number)` is unique.
- Deleting a task deletes its comments.

---

## 6. Auth — the full path, end to end

This is the part most tutorials skip. We won't.

### Step 1 — the backend issues a token

```
POST /auth/login  { "email": "...", "password": "..." }
  → 200 { "access_token": "<jwt>", "token_type": "bearer" }
```

The JWT is signed with HS256 using `JWT_SECRET`. Payload:

```json
{ "sub": "<user uuid>", "email": "alice@example.com", "iat": 1..., "exp": 1... }
```

**Note what is *not* in the token: roles.** Roles live in `project_members` and
are looked up per request. A token issued before Alice was made an admin still
works the moment she's promoted — no re-login. This is a deliberate teaching
point about where authorisation state belongs.

### Step 2 — every backend route checks it

```python
@router.post("/projects/{key}/tasks")
def create_task(key: str, body: TaskCreate,
                user: User = Depends(current_user),
                _: None  = Depends(require_member)):
    ...
```

Three dependencies do all the work:
- `current_user` — decode the token, load the user, 401 if bad.
- `require_member` — is this user in `project_members` for this project? 403 if not.
- `require_admin` — same, but `role == 'admin'`.

### Step 3 — the frontend

Logs in, keeps the token, sends `Authorization: Bearer <jwt>` on every call.
(We'll store it in memory + `localStorage` and be explicit in the post about why
that's acceptable for a learning app and what you'd do differently in production.)

### Step 4 — the chat client logs in on the user's behalf

The chat client is **not** a trusted service with its own god-token. The human logs
into the chat client with the *same* credentials, the chat client gets the *same*
kind of JWT, and holds it for that browser session.

### Step 5 — the token rides along on every MCP call

```
chat-client ──▶ mcp-server
    POST /mcp
    Authorization: Bearer <the user's JWT>
```

### Step 6 — the MCP server verifies, then forwards

```python
# mcp-server/app/auth.py — the shape of it
token = request.headers["authorization"].removeprefix("Bearer ").strip()
claims = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])   # fail fast, cheaply
current_token.set(token)                                        # contextvar, per request
```

```python
# mcp-server/app/backend.py — every outbound call
headers = {"Authorization": f"Bearer {current_token.get()}"}
```

**Two checks, on purpose.** The MCP server verifies the signature so it can reject
garbage instantly and return a clean MCP error. But it treats its own check as an
*optimisation only* — the backend re-verifies and is the real authority. If the two
ever disagree, the backend wins.

### The rule we will repeat until it's boring

> **The MCP server has no credentials of its own.** Everything it does, it does as
> the human who is talking to the AI. There is no service account, no admin key, no
> "trust me, I'm the AI" path into the data.

### Deliberately deferred

Refresh tokens, token revocation, Keycloak/OIDC, and full OAuth 2.1 resource-server
setup are **later phases**. Series #1 already covers OAuth for MCP in depth; we link
to it and swap the token issuer in as a bonus post if there's appetite.

---

## 7. Backend API surface

Small on purpose. Every route maps to something the UI *and* a tool need.

```
POST   /auth/register                          → create account
POST   /auth/login                             → token
GET    /auth/me                                → current user

GET    /projects                               → projects I'm a member of
POST   /projects                               → create (I become admin)
GET    /projects/{key}                         → detail + my role
GET    /projects/{key}/members                 → list members
POST   /projects/{key}/members                 → add member          [admin]
DELETE /projects/{key}/members/{user_id}       → remove member       [admin]

GET    /projects/{key}/tasks                   → filters: status, assignee, overdue
POST   /projects/{key}/tasks                   → create              [member]
GET    /tasks/{key}-{number}                   → detail
PATCH  /tasks/{key}-{number}                   → title/desc/status/priority/assignee/due
DELETE /tasks/{key}-{number}                   → delete              [admin]

GET    /tasks/{key}-{number}/comments
POST   /tasks/{key}-{number}/comments

GET    /me/tasks                               → assigned to me, across projects
GET    /me/capabilities                        → { "can_admin_any_project": bool, ... }
```

`/me/capabilities` exists **for the MCP server's benefit** — it's how tool gating
asks "what is this user allowed to do?" without duplicating the rule. More in §8.

---

## 8. MCP server design

### Transport

Two entry points over the same tool code:

- **Streamable HTTP** on `:9000/mcp` — the default. This is what the chat client
  uses and what runs in Docker.
- **stdio** via `python -m app.server --stdio` — so we can point Claude Desktop /
  Claude Code at it locally and see our own tools in a real client. That screenshot
  is worth a whole section of a blog post.

### Tools

Twelve tools. Each returns human-readable text *and* structured content, because
that's what real clients want.

| Tool | Who can call it | What it does |
|---|---|---|
| `whoami` | anyone logged in | who the token belongs to. The "is auth working" tool |
| `list_projects` | anyone | projects I'm a member of, with my role |
| `create_project` | anyone | new project; I become admin |
| `list_tasks` | member | filter by project / status / assignee / overdue |
| `get_task` | member | full task by ref, e.g. `WEB-14` |
| `create_task` | member | |
| `update_task_status` | member | `WEB-14` → `in_progress` |
| `assign_task` | member | assign by **email**, not UUID |
| `comment_on_task` | member | |
| `my_tasks` | anyone | everything assigned to me, across projects |
| `project_summary` | member | counts by status, overdue list, unassigned list |
| `delete_task` | **admin** | |
| `add_project_member` | **admin** | |

**Design rules we're enforcing and will write about:**

1. **Tools take human identifiers.** `WEB-14`, `alice@example.com`, `todo` — never
   a UUID. The model has to be able to produce the argument from the conversation.
2. **Tool descriptions are written for a model, not a developer.** Each says *when
   to use it*, not just what it does. ("Use this when the user asks what they should
   work on next.")
3. **Errors are instructions.** `"No project with key 'WEBB'. Call list_projects to
   see the keys you have access to."` — a model can recover from that. `500 Internal
   Server Error` teaches it nothing.
4. **Small, sharp tools beat one clever tool.** No `manage_task(action=...)`
   mega-tool. The model picks better from a clear menu.

### Tool gating — derived from capabilities, never from names

`tools/list` is filtered per user. A member never sees `delete_task` at all.

The gate asks the backend `GET /me/capabilities` and filters on the answer. It
does **not** parse the username, does **not** keep a hardcoded list of admin
emails, does **not** infer anything from the tool's name.

This is the single most-repeated lesson from project #1 and it gets its own post:

> **Derive permissions from capabilities, not from names.** The moment you write
> `if user.email.endswith("@admin.com")`, you've built something that will break
> silently and be wrong in a way nobody notices for months.

Gating is a *UX* feature, not a *security* feature — the backend still rejects the
call if a gated tool is invoked directly. We'll say that explicitly, and prove it
with a test that calls `delete_task` as a member and asserts a 403.

### Resources

| URI | Returns |
|---|---|
| `taskflow://project/{key}` | project overview as markdown |
| `taskflow://task/{key}-{number}` | one task, with comments, as markdown |

Two is enough to teach the difference between a **resource** (something the client
reads and puts in context) and a **tool** (something the model decides to call).

### Prompts

| Prompt | Arguments | Produces |
|---|---|---|
| `standup` | `project_key` | "Write my standup update" — pulls my tasks, groups by status |
| `triage` | `project_key` | "Find tasks that are stuck" — no assignee, overdue, or stale |

Prompts are the least-understood MCP primitive and the easiest to demo. Cheap to
build, great screenshot.

---

## 9. Chat client design (the MCP client)

A FastAPI service on `:8100` that serves a plain chat page and runs a LangGraph agent.

### 9.1 The model layer — no vendor lock-in

**Rule: exactly one file in this repo knows which LLM vendor we use.** That file is
`chat-client/app/llm.py`. Nothing else imports a provider SDK, ever.

```python
# chat-client/app/llm.py — the whole thing
from langchain.chat_models import init_chat_model

def build_llm():
    return init_chat_model(
        settings.LLM_MODEL,          # e.g. "anthropic:claude-opus-4-8"
        temperature=settings.LLM_TEMPERATURE,
    )
```

```bash
# .env — switching providers is this line, and nothing else
LLM_MODEL=anthropic:claude-opus-4-8
# LLM_MODEL=openai:gpt-4.1
# LLM_MODEL=google_genai:gemini-2.0-flash
# LLM_MODEL=ollama:qwen2.5:14b            # fully local, no API key, no internet
```

`init_chat_model` is LangChain's own provider factory. `"provider:model"` in,
a chat model with a uniform `.bind_tools()` interface out. Every provider package
we support is a normal dependency; the API key for whichever one is selected comes
from env like everything else.

**Why this and not LiteLLM as the default:** LiteLLM proxy is excellent, but it's a
fifth container, a config file, and a layer of indirection between the reader and
the thing they're trying to understand. `init_chat_model` is one function call with
zero infrastructure. We keep the ceiling open, though — because `llm.py` is the only
coupling point, pointing the whole app at a LiteLLM gateway is a two-line change:

```bash
# Optional: front everything with a LiteLLM proxy (adds a container)
LLM_MODEL=openai:whatever-you-named-it
OPENAI_API_BASE=http://litellm:4000
```

Any OpenAI-compatible endpoint works the same way — LiteLLM, vLLM, OpenRouter,
Groq, LM Studio. We'll document that as the "going further" path, not the default.

### 9.2 The catch nobody mentions: not every model can do this

MCP is tool calling. **Model independence is not model equivalence.** The agent loop
in §9.3 asks the model to pick the right tool from twelve, fill in its arguments
correctly, read the result, and decide whether to call another one. Frontier models
do that reliably. A 7B model running on a laptop often will not — it hallucinates
tool names, invents arguments, or loops.

So the repo ships with:

- **A documented baseline.** One model we've actually verified end to end, named in
  `.env.example`, so a reader who just wants it to work has a known-good setting.
- **A capability note in the README** — a short table of what we tested and how it
  behaved (works / works with fewer tools / fails), written honestly. Not a
  benchmark, just field notes.
- **A `--tools` filter on the chat client**, so a weaker model can be given four
  tools instead of twelve and actually succeed. That's a genuinely useful technique
  and a good demo of *why* small sharp tools (§8) matter.

This is a blog post on its own, and an honest one: *"we made the LLM swappable — here
is what actually changed when we swapped it."* Most write-ups claim provider
independence and never test it. We're going to test it and publish the results,
including the failures.

### 9.3 The graph

```
        ┌─────────┐
   ─────▶  agent  │  Claude, bound to the MCP tools
        └────┬────┘
             │  did it ask for a tool?
       ┌─────┴─────┐
      yes         no
       │           │
  ┌────▼────┐      └────▶ END
  │  tools  │  execute via MCP, append results
  └────┬────┘
       └──────────▶ back to agent
```

That's it — two nodes and one conditional edge. We will draw this diagram, then
walk through one real request message-by-message: user text in, tool call out,
tool result back, final answer. **Understanding this loop is understanding agents.**

### 9.4 Connecting to MCP

```yaml
# chat-client/app/servers.yaml
servers:
  taskflow:
    url: http://mcp-server:9000/mcp
    transport: streamable_http
    auth: forward_user_token      # ← send the logged-in user's JWT
```

`langchain-mcp-adapters` turns each MCP server's `tools/list` into LangChain tools.
The file is a **list** from day one, so adding a second MCP server later (a public
one — time, fetch, or our own second server) is a config change, not a refactor.
That's a whole post: *"Your agent doesn't care where the tools came from."*

### 9.5 The auth path, again

1. Human logs in at `/login` → chat-client calls backend `/auth/login`.
2. Token goes in a server-side session (httpOnly cookie holds the session id, not
   the JWT).
3. Every `/chat` request → tools are loaded *for that user*, with their token in
   the MCP request headers.

**Consequence worth showing off:** log in as a member, ask "delete WEB-3", and the
model answers that it can't — because `delete_task` was never in its tool list. Log
in as an admin, same question, it works. Same code, same model, different token.

### 9.6 The UI

One HTML page. Messages, plus a collapsible panel per turn showing **which tools
were called with which arguments and what came back**. Not decoration — that panel
is how the reader sees MCP actually happening.

---

## 10. Frontend design

The boring, important part: a normal React app that proves the backend is a real
product and not just an MCP fixture.

Screens: Login/Register → Projects list → Project board (tasks by status column) →
Task detail (comments, assignee, status) → Members (admin only).

No Redux, no React Query if `fetch` + `useState` will do. One `api.ts` that attaches
the token. Tailwind for layout. The frontend gets **one** blog post and does not
get to consume more than that.

---

## 11. Build plan

Every phase ends with: it runs, it's tested, it's committed, and there's a
`docs/briefs/phase-N.md` written the same day. Blog-bearing phases marked 📝.

| # | Phase | Done when | Blog |
|---|---|---|---|
| 0 | **Skeleton** — repo, folders, `.env.example`, compose with just Postgres, README | `docker compose up db` works | — |
| 1 | **Schema + migrations + seed** — the five tables, Alembic, `seed.py` with 3 users / 2 projects / ~15 tasks | `alembic upgrade head && python scripts/seed.py` is rerunnable from empty | 📝 Designing the data |
| 2 | **Auth** — register, login, JWT, `current_user` | Can get a token and hit `/auth/me` | 📝 Auth, understood |
| 3 | **Backend API** — projects, members, tasks, comments + `require_member` / `require_admin` + tests | Every route in §7 exists and is tested | 📝 The backend |
| 4 | **Frontend** — all five screens against the real API | Can do the whole flow with a mouse | 📝 The frontend |
| 5 | **First MCP tool** — FastMCP, stdio, `whoami` + `list_projects`, wired to Claude Desktop | Screenshot of our tools in a real client | 📝 **Your first MCP server** |
| 6 | **HTTP transport + auth passthrough** — Streamable HTTP, bearer → backend | A curl'd `tools/call` with a real JWT works | 📝 MCP over HTTP, with auth |
| 7 | **The full toolset** — all 12 tools, good descriptions, useful errors | Tools do everything the UI does | 📝 Designing tools for a model |
| 8 | **Gating + resources + prompts** — capability-driven `tools/list`, 2 resources, 2 prompts | Member and admin see different tool lists; test proves the backend still blocks | 📝 **RBAC + the other two primitives** |
| 9 | **Chat client** — LangGraph agent, `llm.py`, MCP tools, chat UI with a tool-call panel | Can create a task by typing English | 📝 **Building an MCP client** |
| 10 | **Client auth** — login in the chat client, per-user tokens, the member-vs-admin demo | The demo in §9.5 works | 📝 Who is the AI acting as? |
| 11 | **Model independence** — run the same agent on 3+ providers incl. a local one, `--tools` filter, capability notes in README | Same conversation replayed on each; results written down, failures included | 📝 **Swapping the brain** |
| 12 | **Containerise everything** — 4 Dockerfiles, healthchecks, one compose file, 12-factor config | `git clone && docker compose up` on a clean machine | 📝 Shipping the whole thing |
| 13 | **Polish** — README, architecture diagram, screenshots, `docs/decisions/` | A stranger can run it and follow it | — |

**Rough shape:** phases 0–4 are "build a normal app" and should move fast. Phases
5–11 are the actual subject and deserve the time.

---

## 12. How we work

Carried forward from project #1 because they worked:

- **Explain, then write.** Before a file gets written, say in plain words what it
  does and why it exists. If that explanation is hard, the design is wrong — fix
  the design, not the wording.
- **Small commits, reviewable diffs.** Show the diff, explain it, wait for the
  go-ahead. The git history should read like the blog series.
- **Reproducible from zero, always.** Everything via `docker compose up` plus
  scripted seeds. No manual clicking that isn't also a script.
- **Log the real problems the day they happen.** Symptom → root cause → fix → what
  the docs didn't tell us. Those war stories are the soul of the posts; nobody can
  reconstruct them a month later.
- **Test like the real client, not like an ideal one.** Project #1's hardest bug
  was a test that built the "perfect" request and passed while every actual client
  failed. Tests must behave like the thing that will really call us.
- **Never fake a capability.** If a client can't do something (Claude Code can't do
  MCP sampling — hard-won lesson), say so in the post. Honest limitations are more
  useful than a demo that doesn't reproduce.
- **The blog lives in the portfolio repo, not here.** This repo produces
  `docs/briefs/`; the writer turns them into posts.

### Conventions

- **Ports:** db `5432`, backend `8000`, mcp-server `9000`, chat-client `8100`,
  frontend `5173`. Same numbers everywhere — compose, `.env.example`, docs.
- **Config:** every service reads env vars only. `.env.example` lists all of them
  with a comment each. `JWT_SECRET` is shared by backend and mcp-server and that
  fact is documented loudly. `LLM_MODEL` is a single `provider:model` string —
  changing providers must never require a code change.
- **No provider SDK outside `llm.py`.** No `import anthropic`, no `import openai`
  anywhere else in the repo. If a second file needs the model, it takes it as an
  argument. This is enforced by a one-line grep in CI, because conventions that
  aren't checked don't survive.
- **Naming:** snake_case in Python and the database, camelCase in TypeScript.
  Tool names are `verb_noun` (`create_task`, not `taskCreate`).
- **Tests:** pytest for both Python services. The backend tests the rules; the MCP
  server tests that gating and auth passthrough behave. Not chasing coverage —
  chasing the tests that would have caught a real bug.

---

## 13. Blog series #2

- **Slug:** `mcp-fullstack` in the portfolio repo. (Series #1 keeps `mcp`.)
- **Prerequisite:** series #1 is linked as the "what is MCP" intro; this series
  assumes the reader knows the vocabulary but nothing else.
- **Audience bar:** a third-year student or a trainee engineer. Define every term
  the first time. Short sentences. Every code block is explained line by line, and
  every post ends with something the reader can run.
- **The spine of the series:** *here is a small, complete, real application — now
  watch us give it an AI interface without changing a line of the app.*

Posts map 1:1 to the 📝 phases in §11 — eleven posts, four of them flagship
(first MCP server, RBAC, building the client, swapping the brain).

### How code gets from this repo into a post

The portfolio site renders posts as TSX and pulls code **live from GitHub**. The
loop is:

```
  build a phase here  →  commit  →  note the SHA  →  write the post over there
                                          │
                                          └── posts pin to that SHA, forever
```

1. **Register the series once** in `portfolio/src/content/blog.ts`:

   ```ts
   {
     slug: 'mcp-fullstack',
     title: 'MCP, From Scratch',
     category: 'MCP · Series',
     repoUrl: 'https://github.com/Jayantkhandebharad/mcp-taskflow',  // ← this repo
     posts: [ /* one entry per post */ ],
   }
   ```

   `repoUrl` is what makes code references resolve. It's set on the *series*, not
   per post.

2. **Write the post body** as `portfolio/src/content/blog/mcp-fullstack/<slug>.tsx`,
   and register it in the `posts` array with its metadata (summary, weight,
   readingTime, date, phase, lessonType, language, prerequisites).

3. **Reference real files by path, pinned to a commit:**

   ```tsx
   <RepoFile path="mcp-server/app/gating.py" branch="a1b2c3d" />
   ```

   That renders an inline chip. Clicking it opens the file **live from GitHub** in
   a side panel, at that exact commit.

### The constraint this puts on us

> **A published post is a permanent link into this repo's history.** Pin every
> `RepoFile` to the commit SHA the post was written against — never to `main`.

If a post pins to `main` and we later rename `gating.py` or move a folder, the
post silently starts 404-ing in the code panel. Pinning to a SHA makes the
reference immutable: the reader sees exactly the code the post is describing, even
after we refactor it three phases later.

Series #1 already does this (`<RepoFile path="CLAUDE.md" branch="7188235" />`) and
says so in its description — "pinned to real commits". We keep the habit.

**Therefore:** every brief in `docs/briefs/` records the commit SHA (or range) for
its phase. That field is not bookkeeping — it is the thing the post author needs
and cannot recover later without archaeology.

### What this means for how we commit

Because posts pin to commits, the git history is *published surface*, not just
process:

- One logical change per commit, so a post can point at a commit that does exactly
  one thing.
- Commit messages get written for a reader, not for us.
- Don't force-push or rewrite `main` after a post ships pinned to it.

---

## 14. Status

- [x] App chosen — TaskFlow (§1)
- [x] Stack locked (§2)
- [x] Architecture decided — MCP server calls the API, not the DB (§4)
- [x] Data model designed (§5)
- [x] Auth designed end to end (§6)
- [x] Tool surface designed (§8)
- [x] LLM layer is provider-agnostic, one coupling point (§9.1)
- [x] Phase 0 — repo skeleton
- [x] Phase 1 — schema + migrations + seed
- [x] Phase 2 — auth: register, login, JWT, `current_user`
- [x] Phase 3 — backend API: every route in §7, `require_member` / `require_admin`
- [x] Phase 4 — frontend: the five screens in §10, `api.ts`, scripted walkthrough
- [ ] ...
