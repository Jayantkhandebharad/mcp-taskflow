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
| M1 — The data layer | **built (code on disk)** | in progress |
| M2 — Auth, end to end | design (Phase 2 unbuilt) | not started |
| M3 — Backend API + RBAC | design (Phase 3 unbuilt) | not started |
| M4 — The MCP server | design (Phases 5–8 unbuilt) | not started |
| M5 — The chat client / agent | design (Phase 9 unbuilt) | not started |
| M6 — The frontend | design (Phase 4 unbuilt) | not started |
| M7 — Production-systems thinking | cross-cutting | not started |

## Architect lenses — mastery tracker

`not met` → `met` (seen once) → `mastered` (spotted unprompted in new code).

| Lens | State |
|---|---|
| Invariants belong at the lowest layer that can guarantee them | not met |
| Single source of truth (no drift) | understood (M0) — learner derived the drift problem unprompted by asking if MCP tools could re-check the badge |
| Idempotency & reproducible-from-zero | met (M1, 2026-07-27) — via "what migrations are for" |
| Least privilege / who is the authority | understood (M0, 2026-07-27) — clicked on attempt 3 (named the DB superuser); mark mastered when spotted unprompted in new code |
| Config is a contract | not met |
| Errors are instructions | not met |
| Every clean design has a cost | not met |
| Design for the caller you'll really have | not met |

## Spaced-review queue

- **Least privilege** — CLICKED on attempt 3 (correctly named the DB superuser).
  Lower priority now; confirm it's durable by asking them to spot it in new code
  later, and mark mastered then.
- **Gating is UX, not security** — mostly held, but their phrasing "check on each
  tool" hints they may still think the CHECK lives in the MCP tool. Confirm they
  know the tool FORWARDS the badge and the BACKEND is the single authority.
- Minor misconception to watch: framed the API-not-DB rule as "MCP has no auth so we
  build our own." Reframe held — confirm it stuck (the MCP server has *no*
  credentials of its own; it reuses the human's token).

## Session log

Newest first. One entry per session: date · module · concepts covered ·
understanding level · misconceptions corrected · what to revisit.

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
