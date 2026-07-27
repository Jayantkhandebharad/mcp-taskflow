# Curriculum — the module map

Eight modules. **M0 is the spine — everything else hangs off it.** M1 is the
anchor because it's the only module fully built as code today; teach it deeply and
use it to make the architect lenses concrete. M2–M6 are *design study* until their
phase lands (see `PLAN.md §11` build plan); when a phase ships, upgrade that module
from "read the plan" to "read the code, compare it to the plan." M7 is not linear —
it's the set of cross-cutting lessons you reinforce everywhere.

Phase status legend: **[BUILT]** code exists on disk · **[DESIGN]** specified in
PLAN.md, not yet coded.

For each module: the goal, what it depends on, repo anchors to open, the concepts,
and a bank of architect questions (use them for the Socratic checks — pick, adapt,
don't read them off like a quiz sheet).

---

## M0 — The whole system on one page  [partly BUILT / mostly DESIGN]

**Goal:** hold the entire architecture in your head — four services, the dataflow,
the one decision the whole series rests on, and the auth path end to end.

**Anchors:** `PLAN.md` §4 (architecture diagram), §6 (auth path), the three ADRs in
`docs/decisions/`, `docker-compose.yml`, and each service's `README.md`
(`fastapi-backend/`, `mcp-server/`, `chat-client/`, `frontend/`).

**Concepts:**
- The four services and the *one job each* — and, more sharply, what each must
  **never** do (backend must never know MCP exists; MCP server stores nothing).
- The request dataflow: browser → frontend → backend → db; and browser →
  chat-client → mcp-server → backend → db.
- **The load-bearing decision (ADR 0001):** the MCP server calls the backend's REST
  API, not the database. Why: one place enforces the rules; the AI is not a
  superuser; the cost is an honest extra hop.
- The auth path end to end (§6): same JWT issued by the backend rides every call,
  including MCP calls, as the *human's* token.

**Architect questions:**
- If the MCP server queried Postgres directly, name two concrete things that would
  go wrong over the next six months.
- "The backend must never know MCP exists." Why is that a stronger design
  constraint than any architecture diagram?
- Alice can't see project WEB. Mechanically, why can't Alice's AI assistant see it
  either? Where exactly is that enforced?
- Point at the single sentence in ADR 0001 that, if reversed, would collapse the
  whole design. Why that one?

---

## M1 — The data layer  [BUILT] ← the anchor module

**Goal:** defend every schema decision to a senior engineer. This is where the
architect lenses stop being slogans.

**Anchors (all real code, read them):** `fastapi-backend/app/models/*.py`
(`base.py`, `enums.py`, `user.py`, `project.py`, `project_member.py`, `task.py`,
`comment.py`), `app/config.py`, `app/db.py`,
`alembic/versions/2026_07_23_0001_initial.py`, `scripts/seed.py`,
`tests/test_invariants.py`, `tests/test_seed.py`, and `docs/briefs/phase-1.md`.

**Concepts:**
- The five tables and their dependency order (read top-down: users → projects →
  members → tasks → comments).
- **App-generated UUIDs** (`default=uuid4`) vs. Postgres `gen_random_uuid()` — why
  generate in the app.
- The **human-readable `key`** (WEB) and `WEB-14` refs — designed so a *language
  model* can hold the identifier in its head. An identifier is a UX decision.
- **`project_members` is the entire authorization model** — one tiny table every
  rule interrogates.
- **The composite foreign key** `tasks(project_id, assignee_id) →
  project_members(project_id, user_id)` enforcing "assignee must be a member." Why a
  plain FK to `users.id` can't express this; why a nullable assignee is still fine
  (MATCH SIMPLE — the FK isn't checked when a column is NULL).
- **`UNIQUE(project_id, number)`** — the per-project counter behind `WEB-14`.
- **`ON DELETE CASCADE`** on comments — DB-level cascade vs. app-level cleanup.
- **`DATABASE_URL` assembled from parts** in `config.py` — and why (Phase 0
  duplicated the password in `.env`; read `docs/briefs/phase-0.md` for the pain,
  then `phase-1.md` for the fix).
- **Idempotent seed** — how re-running leaves the same dataset, and why the delete
  order matters (FK dependencies).
- **Hand-written migration** vs. `alembic revision --autogenerate` — why this one
  was written by hand.

**Architect questions:**
- The "assignee must be a project member" rule could live in the API, or as a DB
  trigger, or as this composite FK. Argue for the FK. Now argue the strongest case
  *against* it.
- A plain foreign key `assignee_id → users.id` — what exactly does it fail to
  guarantee that the composite FK does?
- We generate UUIDs in Python. Give me one debugging advantage and one thing you'd
  lose versus letting Postgres generate them.
- Why is `WEB-14` a *better* identifier for the MCP tools than the row's UUID?
  Whose ergonomics are we optimizing for?
- The seed deletes before it inserts. What happens if it deletes comments *after*
  tasks? Why?
- Which lens does the composite FK demonstrate? (Answer you're driving at:
  invariants belong at the lowest layer that can guarantee them.)

---

## M2 — Auth, end to end  [DESIGN until Phase 2]

**Goal:** trace a token from login to a protected route, and know where
authorization state lives (and why not in the token).

**Anchors:** `PLAN.md` §6, ADR 0002. Future code: `app/security.py`, `app/deps.py`,
`app/routers/auth.py`.

**Concepts:** password hashing (bcrypt via passlib); JWT HS256 signed with
`JWT_SECRET`; **what is and isn't in the token — roles are NOT** (they live in
`project_members`, looked up per request); the three dependencies `current_user` /
`require_member` / `require_admin`; the **shared `JWT_SECRET`** between backend and
MCP server; "verify then forward — two checks on purpose," backend is the authority.

**Architect questions:**
- Alice is promoted to admin. With roles kept out of the token, does her old token
  still work correctly? Why is that the *desired* behavior, not a bug?
- The MCP server verifies the JWT signature itself. If the backend re-verifies
  anyway, why bother checking twice?
- What breaks the day the backend and MCP server have *different* `JWT_SECRET`s?

---

## M3 — The backend API + RBAC  [DESIGN until Phase 3]

**Goal:** see how a small route surface serves both the human UI and the AI tools,
with the rules written exactly once.

**Anchors:** `PLAN.md` §7 (routes), §8 (gating). Future: `app/routers/*.py`.

**Concepts:** every route maps to something the UI *and* a tool need; rules live
once in the backend; **`GET /me/capabilities`** exists specifically so the MCP gate
can ask "what may this user do?" without duplicating logic; **gating is a UX
feature, not a security feature** — the backend still 403s a gated call.

**Architect questions:**
- A member never *sees* `delete_task`. Why must the backend *still* reject it if
  called directly? What class of bug does that defend against?
- `/me/capabilities` — why an endpoint, instead of the MCP server just checking the
  user's role itself?

---

## M4 — The MCP server  [DESIGN until Phases 5–8]

**Goal:** understand MCP as a thin, safe translation layer over an existing API —
tools, resources, prompts — and how it borrows the user's identity.

**Anchors:** `PLAN.md` §8, ADR 0001, `mcp-server/README.md`. Future: `app/server.py`,
`app/auth.py`, `app/backend.py`, `app/tools/`, `app/gating.py`.

**Concepts:** what MCP is (tool calling, standardized); **tools vs. resources vs.
prompts**; tool design *for a model* — human identifiers (`WEB-14`, an email, not a
UUID), "when to use it" descriptions, **errors as instructions**, small sharp tools
over one mega-tool; **gating derived from capabilities, never from names**;
transport (stdio for Claude Desktop, Streamable HTTP for the container); **auth
passthrough** via a per-request contextvar; **no service account** — the server has
no credentials of its own.

**Architect questions:**
- `manage_task(action="delete"|"create"|...)` vs. separate `delete_task` /
  `create_task`. Which helps the model choose correctly, and why?
- `if user.email.endswith("@admin.com")` — name three separate ways this goes wrong.
- An error returns `500 Internal Server Error` vs. `"No project 'WEBB'. Call
  list_projects to see your keys."` Why does the second one make the *agent* better?

---

## M5 — The chat client (the agent)  [DESIGN until Phase 9]

**Goal:** understand the agent loop, and "who is the AI acting as."

**Anchors:** `PLAN.md` §9, ADR 0003, `chat-client/README.md`. Future:
`app/graph.py`, `app/llm.py`, `app/mcp.py`, `app/servers.yaml`.

**Concepts:** the **LangGraph loop** — agent → (tool? yes) → tools → back to agent →
(no) → END; **model independence ≠ model equivalence** (a 7B model may fail the
tool loop); the **single coupling point** `llm.py` (the only file that names a
vendor); **who the AI acts as** — per-user token, the member-vs-admin demo (same
code, same model, different token, different tools).

**Architect questions:**
- Draw the loop from memory. Where does it terminate, and what decides that?
- We made the LLM swappable. Why is "swappable" *not* the same promise as "works the
  same on every model"?
- Only `llm.py` imports a provider SDK. What future change does that one rule make a
  two-line edit instead of a refactor?

---

## M6 — The frontend  [DESIGN until Phase 4]

**Goal:** see the plain web app that proves the backend is a real product, not an
MCP fixture — and that knows nothing about MCP.

**Anchors:** `PLAN.md` §10, `frontend/README.md`. Future: `frontend/src/`.

**Concepts:** a normal React app, no MCP anywhere; token in memory + `localStorage`
(and the honest tradeoff); one `api.ts` attaching the token; the five screens.

**Architect questions:**
- The frontend and the MCP server both call the same backend with the same kind of
  token. Why is that symmetry a sign the architecture is right?
- Where would you store the token in production, and what specifically does
  `localStorage` expose you to?

---

## M7 — Production-systems thinking  [CROSS-CUTTING, ongoing]

**Goal:** the real junior→architect jump — spotting the recurring lenses in *new*
code without being prompted.

This isn't taught in sequence. Each time a lens (see SKILL.md list) shows up in
M0–M6, name it and log it in `progress.md`. The learner "masters" a lens when, shown
an unfamiliar file, they point at the lens themselves.

**Architect questions (use late, as a capstone):**
- Here's a file you haven't seen. Which of the architect lenses is it an example
  of, and what would break if it were written the naive way?
- Pick any one design decision in this repo and give me its *cost* — the price we
  pay for the clean version. (If they can't name a cost, they haven't finished
  learning it.)
