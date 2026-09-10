# Phase 3 — Backend API: projects, members, tasks, comments, `require_member` / `require_admin`

**Commits (oldest → newest):**

| SHA | What |
|---|---|
| `f7a8762` | housekeeping — phase-2 SHA, pytest testpaths, a flaky tamper test |
| `429c1a6` | relationships and the task ref on the models (no migration) |
| `d17a79b` | `get_project` / `require_member` / `require_admin`, projects + members routes, tests |
| `54e7bd1` | tasks — number allocation, filters, partial PATCH, admin-only delete, tests |
| `6c6533a` | comments and `/me` (tasks, capabilities), tests |
| _(next)_ | this brief + status docs |

The post for this phase ("The backend", PLAN.md §11) should pin `app/deps.py`
and `app/routers/tasks.py` to `6c6533a` — the last commit where the code
changed. Every commit above is green on its own: tests ride with the router
they test, so a post can point at any one of them and the reader gets code
*and* the proof.

## Files worth showing in the post

| File | Why |
|---|---|
| `fastapi-backend/app/deps.py` | The whole authorisation chain in one file: `current_user → get_project → require_member → require_admin`, plus `get_task`. The module docstring draws it. The `get_project` docstring explains the 401-before-404 bug and its fix. |
| `fastapi-backend/app/routers/tasks.py` | The one genuinely non-obvious piece of backend logic: `SELECT ... FOR UPDATE` on the project row before `MAX(number) + 1`. Also the PATCH handler, where "left out" and "sent null" are different. |
| `fastapi-backend/app/routers/projects.py` | `remove_member`: unassign then delete, one transaction, because the composite FK is RESTRICT. The decision phase 1 deferred, made. |
| `fastapi-backend/app/routers/me.py` | `/me/capabilities` — the route that exists for the MCP server. Facts about membership, not tool names. |
| `fastapi-backend/app/models/task.py` | The `assignee` relationship: `viewonly`, a spelled-out join, and the stale-read consequence that cost the first draft a bug. |
| `fastapi-backend/tests/test_tasks.py::test_delete_task_as_member_is_403` | The test phase 8 will point back at. Gating is a courtesy; this 403 is the rule. |
| `fastapi-backend/tests/conftest.py` | `seeded` + `token_for`: real logins, cached across tests. The comment on why a token survives `TRUNCATE` is a small JWT lesson. |

## What we built

Every route in PLAN.md §7 that wasn't already there — fifteen of them — and
the two dependencies §6 names. Verified by `uv run pytest` (87 tests, 66 of
them new) and by hand with `curl` against the seed: every status code in the
list below was produced on a running server before this was written.

- `app/deps.py` — `get_project` (404), `require_member` (403, returns the
  membership row), `require_admin` (403), `get_task` (404, member-only).
- `app/models/*` — four relationships (`Task.project`, `Task.assignee`,
  `ProjectMember.user`, `Comment.author`) and two properties (`Task.ref`,
  `Task.project_key`). No migration; `compare_metadata` reports no diff.
- `app/schemas/{projects,tasks,comments,me}.py` and `UserRef` in
  `schemas/auth.py` — the "a person, seen from another object" shape.
- `app/routers/projects.py` — list mine, create (creator becomes admin),
  detail with my role; members list, add by email (admin), remove (admin).
- `app/routers/tasks.py` — list with `status` / `assignee_id` / `overdue`
  filters, create with per-project numbering, get / patch / delete by ref.
- `app/routers/comments.py` — list, add.
- `app/routers/me.py` — `/me/tasks`, `/me/capabilities`.
- `app/main.py` — mounts them; maps `IntegrityError` to a 409.
- `tests/test_{projects,tasks,comments,me}.py` — 66 tests through HTTP,
  each named for the bug it catches.

By hand, on the seed: Bob lists projects (200, WEB as member) · `/projects/WEBB`
as Alice → 404 with "GET /projects lists the ones you belong to" · `/projects/WEB`
as Carol → 403 · `/projects/WEBB` anonymous → 401 · Bob creates a task → 201,
`WEB-9` · Alice assigns it to Carol → 409 naming the members route · Bob deletes
it → 403 · Alice deletes it → 204 · Alice adds Carol → 201, again → 409 · Alice
removes herself → 409 (last admin) · Bob's capabilities → `false, []` · Alice's
`/me/tasks` → 7 · `/docs` lists thirteen paths.

## Decisions made along the way

**Keep RESTRICT; unassign in the route.** Phase 1 left "remove member vs. the
composite FK" open. The options were a migration to `ON DELETE SET NULL
(assignee_id)` (Postgres 15+ syntax, and SQLAlchemy would just pass the string
through) or keeping the strict rule and having the one route that removes
members do the unassigning. We kept the rule: the database never has to bend
"an assignee is a member", and `remove_member` is the *only* place that needs to
know. Both statements run in one transaction. Removing the last admin is a 409.

**Number allocation: lock the parent row, then `MAX + 1`.** `FOR UPDATE` locks
rows; `MAX(...)` is an aggregate and has no row. So the project's own row is
the lock. Creates in the same project serialise; creates in different projects
don't. Known cost, recorded below: deleting the newest task frees its number.

**401 beats 404, structurally.** `get_project` asks for `current_user` and
ignores the result. See "What went wrong".

**404 for a missing key, 403 for a project you're not in.** Not 404 for both:
403 is a different instruction to a client ("ask an admin") than 404 ("check
the key"), and the MCP server will map them to different tool errors. A
project's key is not a secret in this app.

**409 for state conflicts, 422 only for malformed input.** Duplicate key,
already a member, last admin, non-member assignee — all 409, all with a
sentence saying what to do. 422 keeps FastAPI's list-shaped body and means
"the request itself is wrong". One status per body shape.

**Members by email, assignees by id.** There is no user-search route and there
won't be, so an email is the only handle a caller has for someone not yet in
the project. Assignees come from the members list, which carries ids. The MCP
tool `assign_task(email)` will translate — that translation is the MCP server's
job, and the API stays one-shape.

**Relationships, not hand-built dicts.** `TaskOut` and `CommentOut` are pure
`from_attributes`; only `ProjectOut.my_role` and the flattened `MemberOut` need
a helper. The cost is that relationships hide queries, so: `joined` where the
child is never shown without the parent, `selectin` for assignees on a list,
and `viewonly` on the one relationship that isn't backed by a real FK.

**PATCH: `exclude_unset`.** `{"assignee_id": null}` unassigns; `{}` does
nothing. `title` / `status` / `priority` are declared as non-optional types
with a `None` default so leaving them out is fine and sending `null` is a 422
rather than a NOT NULL error. It reads oddly; the docstring says why.

**Tests are seed-driven, with cached real logins.** A `seeded` fixture runs
`scripts.seed.main()` on the truncated tables (the seed caches its one bcrypt
hash per process, so re-seeding is ~30 inserts). `token_for(email)` does a real
`POST /auth/login` once per user per run. The cache is valid across `TRUNCATE`
because seed ids are uuid5 and a JWT is a signed claim about an id, not a
server-side session — worth a paragraph in the phase-6 post.

**A fifth router file.** PLAN.md §3 lists four; `/me/*` got `routers/me.py`
because neither route belongs to a project and "what's mine" is a different
question from `/auth/me`'s "who am I".

**`/me/capabilities` returns facts.** `{"can_admin_any_project": bool,
"admin_project_keys": [...]}`. Not tool names — which tools a fact unlocks is
the gate's business. Read fresh from `project_members` on every call.

**Six commits, tests with their router.** Every SHA in the history is green and
proves itself; a separate "tests" commit would leave three commits of untested
code in the published surface.

## What went wrong

### The phase-2 tamper test was flaky, and it was the test's fault

**Symptom.** Step 0 was "run the phase-2 suite before touching anything".
`test_me_with_tampered_signature_is_401` failed: `assert 200 == 401`. Six
reruns passed.

**Root cause.** The test flipped the *last* base64url character of the
signature. An HS256 signature is 32 bytes; base64url spells that in 43
characters, which is 258 bits of text for 256 bits of data. The last
character's low two bits are padding the decoder discards. So when the real
last character was `B`, `C` or `D` (or `A`, which the test flipped to `B`), the
"tampered" string decoded to the *identical* signature and verified. Four
characters in 64: about one run in sixteen.

**Fix.** Flip the first character, where all six bits are real.

**What the docs didn't say.** Nothing in the PyJWT or base64 docs will tell you
that two different base64url strings can decode to the same bytes when the
length isn't a multiple of four characters. The general lesson is older: a test
that "tampers" with an encoded value has to tamper with the *decoded* value.

### 404 before 401 — an anonymous caller could probe project keys

**Symptom.** `test_project_route_without_token_is_401_even_for_unknown_key`
failed on the first run: `GET /projects/WEBB` with no token returned 404.
`GET /projects/WEB` returned 401.

**Root cause.** FastAPI resolves a route's dependencies in the order they are
declared as parameters. `require_member` had `current_user` first — but the
*route* `get_project_detail` listed `project: Depends(get_project)` before
`member: Depends(require_member)`, so the key lookup ran before any token
check. Getting the order right inside one dependency isn't enough; every route
that uses it has to get it right too.

**Fix.** `get_project` now takes `_: User = Depends(current_user)` and ignores
it. The token check is *inside* the lookup, so it happens first on every route
no matter how the parameters are ordered. `current_user` is cached per request,
so the token is still decoded once.

**What the docs didn't say.** The FastAPI docs describe dependency resolution
order for sub-dependencies but don't call out that a *route's own* parameter
order is part of the picture, or that this has a security consequence. The
general lesson: if a guarantee depends on ordering, make the ordering
structural, not conventional.

### The PATCH response showed the old assignee

**Symptom.** Caught during design (the planning pass ran the scenario against
the seeded DB before any code was written), so it never reached a test — but it
is exactly the bug the first draft would have shipped. Reassign `WEB-4` from Bob
to Alice; the response body says Bob.

**Root cause.** `Task.assignee` is a `viewonly` relationship; writes go through
`assignee_id`. The session had already loaded `assignee` (Bob) when it loaded
the task. Setting `assignee_id` and committing doesn't re-read the
relationship, and `db.py` uses `expire_on_commit=False` (so the row stays
loaded after commit rather than being re-fetched). The response serialiser read
the cached Bob.

**Fix.** `db.refresh(task)` after the commit in `create_task` and
`update_task`. `test_patch_task_response_shows_new_assignee_not_stale` pins it.

**What the docs didn't say.** The SQLAlchemy docs for `viewonly=True` explain
that the ORM won't *write* through it. They don't say "and it won't notice when
you write the underlying column either" — which follows, but only once you've
been bitten.

### Nothing else

The seed, `TestClient`, the composite FK, and Starlette's path matching all did
what phase 1 and 2 said they would.

## What surprised us

- **`"/tasks/{key}-{number}"` just works.** Starlette compiles it to
  `(?P<key>[^/]+)-(?P<number>[^/]+)`, and `number: int` in the signature gets
  FastAPI's conversion and a 422 for `WEB-four`. No parser. Keys can't contain
  hyphens (`schemas/projects.py`), so the split is never ambiguous.
- **One `Session` per request, for free.** FastAPI caches each dependency's
  result within a request, so `get_db` in `get_project`, in `require_member`
  and in the handler all yield the same session. The handler can commit what
  the dependencies loaded. We'd assumed we'd need to thread it through.
- **A token minted in test 1 is valid in test 40**, across a `TRUNCATE` and a
  re-seed, because the seed's ids are uuid5 of the email. Obvious once said;
  it makes the test suite a small demonstration of what a JWT is.
- **`compare_metadata` said nothing.** Adding four relationships and two
  properties changed no DDL. Worth running once so the reader trusts "no
  migration" is a fact, not a hope.
- **psycopg puts the constraint name on the exception** (`exc.orig.diag.
  constraint_name`), so the 409 fallback in `main.py` can say *which* rule.

## Known limitations (said plainly, per CLAUDE.md)

- **`MAX + 1` reuses a deleted top number.** Delete `WEB-8`, create a task, it
  is `WEB-8` again, and an old comment or chat transcript saying "WEB-8" now
  points at something else. `test_create_task_after_deleting_latest_reuses_number`
  documents it. The fix is a `next_task_number` column on `projects` (one
  migration; the same row lock). Not done: nothing in phases 4–13 needs it.
- **No concurrency test for numbering.** Two requests racing inside
  `TestClient` would need two real connections; the argument is the row lock,
  and a load test belongs to phase 12 at the earliest.
- **`overdue` uses the server's date**, not the client's timezone.
- **No pagination.** Lists return everything. The seed has fifteen tasks.
- **No project delete, rename, or "leave project"; no comment edit or
  delete; no role change** (promote via remove + re-add, or add as admin).
  PLAN.md §1: every feature must earn its place.
- **The `IntegrityError` → 409 handler is untested by HTTP**, on purpose.

## Proposed commit split

The one at the top, as it landed. Six commits, each green.

## Next: phase 4

The frontend — five screens against these routes. The members screen will
want a role-change route eventually; resist it until a screen actually needs
it. `docs/architecture.md` Flow 1 (`PATCH /tasks/WEB-14`) is now real code.
