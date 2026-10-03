# Learning progress

> This is the living tracker for the `/learn` skill. It is personal state, not
> project code — if you'd rather keep it out of the public repo, gitignore this
> one file. The skill reads it at the start of every session and updates it at the
> end. Keep the logging **honest** — a nod is not mastery.

## Learner profile

- **Self-assessed level:** junior, "very less understanding" (own words, 2026-07-27).
- **Goal:** become an architect — understand the *decisions* and production-systems
  essence, not memorize code.
- **Started:** 2026-07-27.

## Status legend

`not started` → `in progress` → `understood` (can explain the decision) →
`can defend` (can argue it *and* name its cost / the rejected alternative,
unprompted).

## Module status

| Module | Phase status | Understanding |
|---|---|---|
| M0 — The system on one page | partly built / mostly design | in progress |
| M1 — The data layer | **built (code on disk)** | in progress — composite FK **can defend** (2026-09-20); seed/UNIQUE/MATCH SIMPLE remain |
| M2 — Auth, end to end | **built (Phase 2, `8bbd4e6`)** | touched via M4 (2026-10-01): shared `JWT_SECRET`, "two checks on purpose", roles-not-in-token — not taught in its own right |
| M3 — Backend API + RBAC | **built (Phase 3, `f7a8762`..`6c6533a`)** | not started |
| M4 — The MCP server | **built through Phase 6 (HTTP transport, uncommitted at session time)**; 7–8 design | in progress — phase 6 covered (2026-10-01): transports, ContextVar per request, SDK OAuth vs own middleware, ASGI scope/receive/send, test design. Tools/backend.py/errors-as-instructions not yet covered |
| M5 — The chat client / agent | design (Phase 9 unbuilt) | not started |
| M6 — The frontend | **built (Phase 4, `4ce4dff`)** | not started |
| M7 — Production-systems thinking | cross-cutting | not started |

## Architect lenses — mastery tracker

`not met` → `met` (seen once) → `mastered` (spotted unprompted in new code).

| Lens | State |
|---|---|
| Invariants belong at the lowest layer that can guarantee them | understood (M1, 2026-09-20) — via composite FK + TOCTOU; mark mastered when spotted unprompted |
| Single source of truth (no drift) | understood (M0) — learner derived the drift problem unprompted by asking if MCP tools could re-check the badge |
| Idempotency & reproducible-from-zero | met (M1, 2026-07-27) — via "what migrations are for" |
| Least privilege / who is the authority | **mastered (M4, 2026-10-01)** — spotted unprompted in new code: "backend is our last and mandatory authorization point… same backend is used elsewhere so its check can never be removed." Exactly the lens, with the right reason (other callers bypass the middleware). |
| Config is a contract | met (M4, 2026-10-01) — shared `JWT_SECRET` as a cross-service contract, briefly |
| Errors are instructions | met (M1, 2026-09-20); reinforced M4 — the 401-at-the-door vs sad-tool-result point was *taught*, not reached by the learner |
| Every clean design has a cost | understood (M1); applied M4 — learner took the "build against a consumer you have" lens and immediately proposed reordering the plan (9 before 6). Right reflex, missing step: weigh against the dependency graph and rework bill before acting. **A lens is a consideration, not a command** — taught, not yet demonstrated. |
| Design for the caller you'll really have | met (M4, 2026-10-01) — via raw-request-vs-SDK-client test design; learner's first answer was "it checks like a real client" with no argument. Reached the real answer only after being walked through ASGI scope/receive. |

## Spaced-review queue

- **Least privilege** — mastered 2026-10-01 (spotted unprompted in the middleware
  discussion). Off the queue.
- **"Understood" without answering — recurring.** Happened again 2026-10-01 on the
  SDK-fit check (`client_id`/`scopes`). Held the line once and they answered.
  Keep holding it: do not accept "I understood, move on" as a demonstration.
- **The phase-6 guess — never answered.** Asked twice: "what would phase 10's chat
  client need that `BearerTokenMiddleware` can't give it?" They pivoted both times
  (to reordering the plan; to the OAuth question). Re-ask cold when phase 10 is
  near. Expected: token expiry mid-session (no refresh — ADR 0002), or the client
  holding a session cookie and needing to translate cookie → bearer for MCP calls.
- **"Smallest thing to prove the AI acts as the human, from zero"** — asked, not
  answered. Re-ask as a capstone; it tests whether they can find the risky core.
- **A lens is a consideration, not a command** — taught after the 9-before-6
  proposal. Not yet demonstrated. Next time they propose a change, ask them to
  name the dependency it breaks and the rework it costs *before* arguing for it.
- **JWT pre-check ≠ ADR 0001** — they conflated "verify the token in the MCP
  server" with "a tool might bypass the API." Corrected once. Check it stuck.
- **Roles-in-token** — their instinct for the SDK was `scopes = role`, which is
  the design ADR 0002 rejects. Re-check when M2 is taught properly: "why aren't
  roles in the token?" — they should now reach promotion-is-instant themselves.
- **Gating is UX, not security** — mostly held, but their phrasing "check on each
  tool" hints they may still think the CHECK lives in the MCP tool. Confirm they
  know the tool FORWARDS the badge and the BACKEND is the single authority.
- **Soft-delete dissolves FK guarantees** — taught at the end of session 3; learner
  said "understood" WITHOUT answering the walkthrough. **Not demonstrated.** Re-ask
  cold next session: "we add project_members.deleted_at — what does the composite FK
  do now?" Expected: Postgres accepts (row exists), rule falls back to Python.
- **"Reading the DB is not the DB enforcing"** — the session-3 core miss. Re-check
  with a *new* invariant later: do they reach for SELECT-then-branch again?
- **The drift test** ("worst outcome if the copies disagree?") — taught, not yet
  restated by the learner. Make them apply it cold to a different pair.
- Minor misconception to watch: framed the API-not-DB rule as "MCP has no auth so we
  build our own." Reframe held — confirm it stuck (the MCP server has *no*
  credentials of its own; it reuses the human's token).

## Session log

Newest first. One entry per session: date · module · concepts covered ·
understanding level · misconceptions corrected · what to revisit.

### 2026-10-01 — Session 4: M4, phase 6 (HTTP transport + bearer passthrough), pre-commit
- **Context:** phase 6 was implemented and tested but uncommitted; learner asked to
  understand it before the commit. Jumped M2/M3 to get here — M2's shared-secret
  and roles-not-in-token facts were introduced inline, not taught properly.
- **Build order (stdio → HTTP).** Learner correctly rejected my first two reasons
  ("no ASGI app" — factually wrong, `streamable_http_app()` always existed; "HTTP
  is harder to debug" — a vibe, not an argument). Good skepticism. Real reason,
  from the two "done when" lines: phase 5 proves against a real existing client
  (Claude Desktop); phase 6 can only prove against curl/SDK because its consumer
  (chat client) is phase 9. **Build against a consumer you have.**
- **Then over-applied it:** proposed 9-before-6, then "plain chat first, then plug
  in an existing MCP, then ours." Walked the dependency graph (9 needs a transport;
  stdio is a dead end for 10's per-user identity; 9 needs 7's `create_task`) and
  the rework bill (posts pinned to SHAs). Also corrected my own overstatement: the
  SDK client in `as_http_user` IS the real consumer's library; the guess is only
  the bearer convention. Their underlying itch: Desktop verification is painful →
  pointed out HTTP mode already removes that; offered a `scripts/call.py` dev loop.
- **Q1 two checks:** backend-as-authority with the "other callers" reason —
  unprompted, correct → least privilege **mastered**. Our check: got "cheap reject,
  don't hold a connection"; missed the 401-at-the-door error-quality point. Conflated
  the pre-check with ADR 0001 DB-bypass — corrected.
- **Q2 ContextVar:** right analogy (request-id in logging) but no mechanism; nailed
  the failure mode (Alice sees Bob's data, silent, last-writer-wins). Taught: new
  task copies context at creation; "bugs that don't throw are the expensive ones."
- **Q3 SDK OAuth vs own middleware:** first answer thin ("features we don't need").
  Learner asked for the full picture → taught from the SDK source: `AuthSettings`
  requires `issuer_url`/`resource_server_url`; `AccessToken` requires `client_id`/
  `scopes`; the WWW-Authenticate discovery hook; the AS half (`/authorize`,
  `/token`…). Named the cost honestly (no WWW-Authenticate → OAuth clients can't
  discover us; brief gets a limitation line). Check: they said "understood" without
  answering; held the line; answer was `client_id = user id, scopes = role` → used
  it to show the SDK's shape pushes you back to roles-in-token (ADR 0002 violation).
  **Good kind of wrong.**
- **Q4 raw-request tests:** "it checks like a real client" with no why. Taught ASGI
  scope/receive/send at their request (genuine curiosity — asked how the body
  arrives, where it waits, re-drainability). They read the `!= "http"` branch
  backwards — corrected. Reached the defense after the walkthrough: middleware reads
  scope type + one header, never the body, so the raw request is the real request
  minus what the code ignores.
- **Session fixture:** half right ("stdio can't distinguish requests" — wrong;
  JSON-RPC has ids). Taught the real axis: **process-bound vs request-bound
  identity.**
- **Pattern to watch:** three questions dodged by pivoting (the guess ×2, from-zero
  capstone). Curiosity is high; follow-through on diagnostic questions is the gap.
- **Next time:** finish M4 — `backend.py::_explain` and errors-as-instructions,
  the tool modules (`me.py`, `projects.py`), why `add_tool` over the decorator, the
  stdio brief's "agent went around the server" story (gating is UX). Then M2
  properly, since three of today's corrections were M2 facts.

### 2026-09-20 — Session 3: the composite FK (M1 flagship)
- **Gap:** ~8 weeks since session 2. Did not re-ask session 2's open questions;
  went straight at the flagship instead. Session 2's two checks remain unanswered.
- **Learner's own framing, unprompted:** "most of the time when i code i just create
  technical debt." Used it as the spine of the session — debt reframed as *a rule
  living somewhere that cannot guarantee it*.
- **Got right (a):** a plain `assignee_id -> users.id` does not enforce membership;
  any writer can assign a non-member. Sharpened: their phrasing "if the route
  handling it doesn't exist" still implied a route check would suffice — corrected
  to "a route check protects that route, not the table."
- **The real diagnostic (b):** said "I'd handle it in the DB now" but then described
  a SELECT-membership-then-branch **inside the assign route** — i.e. the app check,
  not the DB. Key misconception surfaced: **reading the DB for an opinion is not the
  DB enforcing anything.** Taught TOCTOU with the concrete race (membership revoked
  between the SELECT and the INSERT; no error anywhere; discovered weeks later), and
  why the FK has no window (check *is* the write, parent row locked).
- **Encouraging:** their reflex matched `_check_assignee` (tasks.py:39-56) almost
  line for line. Framed as "not wrong, incomplete" — the repo has both layers.
- **Duplication question** ("a reviewer says delete `_check_assignee`, it duplicates
  the FK — but you argued in M0 that copies drift"): answered "custom error, so maybe
  don't avoid it." Right seed, hedged. Firmed into a reusable test:
  **if the copies drift, what is the worst outcome?** Bad message => convenience
  layer, ship it. Bad data / unauthorized action => second authority => debt.
  Contrasted directly with the ADR 0001 case where the MCP copy *would* be an
  authority. Learner has not yet re-stated this test in their own words.
- **Errors are instructions:** introduced via the real 409 detail string, which names
  the two endpoints to recover with, and why that matters when the caller is an LLM.

- **Session 3, part 2 — `created_by` contrast + member removal:**
  - Nailed (b): creator leaves the project, composite `created_by` would break/bar
    history. Sharpened (a): their reason was "no rule about who creates" (wrong —
    `require_member` gates it). Real distinction is **time**: `assignee_id` is a
    claim about NOW and must stay true; `created_by` is a past event. Rule given:
    "a constraint is re-checked forever, so only put facts in it that must stay
    true forever."
  - **Learner asked the session's best question, unprompted:** what happens to an
    assigned task when the member is removed? Answered from code: composite FK has
    no `ondelete` → RESTRICT; `remove_member` (projects.py:175-229) unassigns then
    deletes in one transaction; plus the last-admin guard.
  - **Cost question** ("what does RESTRICT cost the team over a year?"): answered
    with the employee-offboarding case and proposed **soft delete** — independently
    arriving at the repo's existing `is_active` policy (user.py:40-44,
    comment.py:34-35). Strong: reasoned a constraint forward in time until it broke.
    Added the fuller bill (every removal path inherits the unassign obligation;
    GDPR erasure is a genuine open problem `is_active` does not solve).
  - **Not demonstrated:** applied soft delete to `project_members` too, which would
    silently kill the composite FK. Posed it as a walkthrough; learner replied
    "understood" and moved on. Gave the 4-line answer. See review queue.
- **Next in M1:** MATCH SIMPLE / why a nullable assignee is still fine,
  `UNIQUE(project_id, number)` behind "WEB-14", cascade on comments, the idempotent
  seed and its delete order. Then M2 (auth) — now built, and the natural sequel
  since `require_admin` came up repeatedly here.

### 2026-07-27 — Session 2: M1 begins — the Alembic setup
- **Covered:** what a migration is (version control for schema; reproducible-from-
  zero); the file map (alembic.ini / env.py / versions/ / base.py / config.py);
  then env.py line by line — import-for-side-effect registering tables on
  Base.metadata, URL pulled from app.config (single source of truth), blank
  sqlalchemy.url in the ini, target_metadata, NullPool, compare_type/
  compare_server_default, transactional DDL run.
- **Callback:** single-source-of-truth (from M0) reappears 3× in this setup (DB URL,
  password parts, constraint naming convention). Learner is now *seeing* the lens in
  code, not just arguing it — good reinforcement toward mastery.
- **Check posed:** (1) which lens is the blank-URL-in-ini trick; (2) forget to import
  a new model → what autogenerate produces (tests real understanding of side-effect
  registration). Awaiting answers.
- **Next in M1:** the actual initial migration (versions/2026_07_23_0001_initial.py)
  — the composite FK, unique constraints, cascade. Then config.py / base.py deep
  dives if wanted, then the models themselves.

### 2026-07-27 — Session 1 (cont. 2): least privilege clicked + single source of truth
- **Breakthrough:** on the 3-sentence check, correctly said (a) our design checks
  *the user's* permissions, (b) the direct-DB design runs as a **superuser** with no
  check to stop it. Least-privilege lens LANDED (was missed twice before).
- **Architect-level question, unprompted:** "couldn't the MCP tools do the badge
  checking themselves?" — Yes. Used it to deliver ADR 0001's 2nd pillar: if the MCP
  server re-checks, the rule lives in TWO places → they DRIFT. Learner reached the
  doorway of single-source-of-truth on their own.
- **Refined:** their #3 ("check on each tool") is exactly the design we avoid — our
  tool FORWARDS the badge; the backend checks once.
- **M0 core complete.** Still open in M0: the full auth path step-by-step (§6).
  Next: offer M1 (the data layer — real, built code).

### 2026-07-27 — Session 1 (cont.): the member-vs-admin scenario
- **Attempted** the Alice scenario. Two correct points: tool gating (Alice won't
  see delete_task) and operational/schema coupling of a direct DB connection.
- **Core miss (again):** answered "who is the AI acting as?" as *the user, in both
  designs.* In the direct-DB design the AI acts as a **DB superuser**, not as Alice
  — her permissions are never consulted. Least-privilege lens has NOT landed yet.
- **New misconception:** treats tool-gating as the security boundary. It's UX; the
  backend is the boundary. Introduced "gating is UX, not security" + the
  member-calls-delete_task→403 test.
- **Minor:** "conflicting transactions" isn't the real risk of a 2nd DB connection
  (Postgres handles concurrency); the risk is bypassing the rules.
- Posed a tighter confirmation question; awaiting answer before marking mastery.

### 2026-07-27 — Session 1: M0, the map
- **Covered:** the four services + their one job; the two request dataflow paths;
  the load-bearing decision (ADR 0001 — MCP server calls the API, not the DB).
- **Calibration:** learner reports having *worked on* services / JWT / MCP before —
  treat as "junior with real exposure," keep verifying rather than assuming.
- **Got right:** the decoupling benefit (backend owns the schema; MCP server doesn't
  chase migrations) — named it as separation of concerns, but as a nice-to-have.
- **Missed:** the load-bearing reason — *least privilege / the AI is not a
  superuser.* Taught it. Also grazed but didn't state "rules live once → no drift."
- **Corrected:** "MCP has no auth so we build our own" → the MCP server holds NO
  credentials; it reuses the human's JWT, which is what makes least privilege work.
- **Left open:** posed the Alice member-vs-admin scenario; awaiting their answer.
- **Understanding:** M0 in progress. Two lenses met (least privilege, single source
  of truth), both to be verified next session.

### 2026-07-27 — Skill created
- Built the `/learn` skill (SKILL.md, curriculum.md, this tracker).
- Placement not yet done. **Next session:** start with M0 (the system on one page),
  after a quick 2-minute placement to gauge starting depth.
