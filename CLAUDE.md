# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Working agreement

**Read [`PLAN.md`](PLAN.md) first.** It is the source of truth for this repo: the
app, the data model, the auth path, the tool design, and the build order. This
file is about *how we work*; the two sections below are practical orientation for
a fresh session.

## Orientation

- **[`PLAN.md`](PLAN.md)** — the whole design in one file: the app, the five-table
  data model, the end-to-end auth path, all 12 MCP tools, and the 14-phase build
  order (§11). Read it before touching code.
- **[`docs/decisions/`](docs/decisions/)** — three ADRs for the load-bearing
  choices: the MCP server calls the API not the DB (0001), we issue our own JWT
  (0002), the LLM is swappable (0003). Revisiting one of these means a new ADR, not
  a silent code change.
- **[`docs/briefs/`](docs/briefs/)** — one `phase-N.md` per phase, written the day
  the work happens (symptom → root cause → fix → what the docs didn't tell us).
  Each brief records the commit SHA(s) its blog post pins to (PLAN.md §13), so that
  SHA line is load-bearing, not bookkeeping.
- **Current state:** phases 0–3 are done. PostgreSQL runs in Compose; the backend
  runs on the host via `uv` with the five tables, migrations, a seed, and every
  route in PLAN.md §7 behind the `current_user` → `get_project` →
  `require_member` → `require_admin` chain in `app/deps.py`. 87 tests, all
  through HTTP against the seed. Phase 4 (the frontend) is next.
  `mcp-server`, `chat-client`, `frontend` still hold only a README each.
  [`README.md`](README.md) §Status tracks the phase checklist; keep it and PLAN.md
  §14 in sync as phases land.

## Commands

The repo is built one phase at a time, so most tooling arrives with the phase that
needs it. Do not invent commands that a phase hasn't created yet. What runs today:

```bash
cp .env.example .env          # first run only; .env is gitignored
docker compose up             # phase 0: starts Postgres, nothing else
docker compose up db          # just the database
docker compose ps             # what's running
docker compose exec db psql -U taskflow -d taskflow -c '\dt'   # list tables
docker compose down           # stop; add -v to wipe the db volume for a clean slate
```

The backend runs on the host until phase 12 containerises it. From `fastapi-backend/`:

```bash
uv sync                                          # install from uv.lock into .venv/
uv run alembic upgrade head                      # build the schema
uv run python -m scripts.seed                    # demo data; wipe-and-reinsert, rerunnable
uv run pytest                                    # all tests, against the Compose Postgres
uv run pytest tests/test_auth.py::test_register_login_me_round_trip
uv run uvicorn app.main:app --reload --port 8000 # the API; /docs for the OpenAPI page
```

The two rules under *"Two rules that are checked"* below have **no CI yet** —
verify them by hand until the CI phase lands:

```bash
# 1. No provider SDK imported outside chat-client/app/llm.py (must print nothing):
grep -rn --include='*.py' -E '(import|from) (anthropic|openai)' . | grep -v 'chat-client/app/llm.py'
# 2. The MCP server never imports a database driver (must print nothing):
grep -rniE 'psycopg|sqlalchemy|asyncpg' mcp-server/
```

Conventions for the tooling that lands in later phases (§2 of PLAN.md locks these):

- **Python services** are packaged with **`uv`**, one lockfile each. Tests are
  **pytest**, run from the service folder: `uv run pytest`, and a single test with
  `uv run pytest tests/test_x.py::test_name`.
- **Migrations** are Alembic in `fastapi-backend`: `alembic upgrade head`, then
  `python scripts/seed.py` (rerunnable) for deterministic demo data.
- **Frontend** is Vite + TypeScript: `npm run dev` / `npm run build` (phase 4+).
- **The MCP server has a second entry point** — `python -m app.server --stdio` —
  for pointing Claude Desktop / Claude Code at it locally (phase 5+).

## The audience is a trainee engineer

Everything in this repo — code, comments, docs, commit messages — is written for
someone in their third year who has never built an MCP server. That is not a
disclaimer; it is the design constraint.

- Define a term the first time it appears.
- Short sentences. Plain words.
- Every non-obvious line gets a comment explaining *why*, not *what*.

## Explain, then write

Before a file gets written, say in plain words what it does and why it exists. If
that explanation comes out tangled, the design is wrong — fix the design, not the
wording.

## Small commits, reviewable diffs

Show the diff, explain it, wait for the go-ahead. One logical change per commit.
The git history should read like the blog series, because the blog series is
written from it.

## Reproducible from zero, always

Everything via `docker compose up` plus scripted seeds. No manual clicking that
isn't also a script. If a step only exists in someone's terminal history, it
doesn't exist.

## Log the real problems the day they happen

Each phase gets `docs/briefs/phase-N.md`, written *while* the work happens:
symptom → root cause → fix → what the docs didn't tell us. Nobody can reconstruct
these a month later, and they are the most valuable thing in the repo.

## Test like the real client, not an ideal one

The hardest bug in the previous project was a test that constructed the "perfect"
request, passed happily, and shipped something every actual client rejected. Tests
must behave like the thing that will really call us.

## Never fake a capability

If a client can't do something, say so — in the code comment and in the post. An
honest limitation is more useful to a reader than a demo that doesn't reproduce on
their machine.

## Two rules that are checked, not just agreed

1. **No provider SDK outside `chat-client/app/llm.py`.** No `import anthropic`, no
   `import openai`, anywhere else. CI greps for it.
2. **The MCP server never imports a database driver.** It calls the backend's API.
   CI greps for that too.

Conventions that aren't checked stop being true within a month.

## Conventions

- **Ports:** db `5432`, backend `8000`, mcp-server `9000`, chat-client `8100`,
  frontend `5173`. The same numbers in Compose, `.env.example`, and every doc.
- **Config:** environment variables only, all of them listed in `.env.example`
  with a comment each.
- **Naming:** `snake_case` in Python and the database, `camelCase` in TypeScript.
  Tool names are `verb_noun` — `create_task`, never `taskCreate`.
- **Tests:** pytest for both Python services. Not chasing coverage — chasing the
  tests that would have caught a real bug.
