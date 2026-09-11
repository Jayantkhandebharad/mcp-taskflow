# Phase 4 — Frontend: five screens against the real API

**Commits (oldest → newest):**

| SHA | What |
|---|---|
| `4ce4dff` | frontend: Vite + React + TypeScript + Tailwind, the five screens, `api.ts`, the scripted walkthrough |
| _(next)_ | this brief + status docs |

The post for this phase ("The frontend", PLAN.md §11) should pin
`frontend/src/api.ts` and `frontend/src/pages/TaskPage.tsx` to `4ce4dff` — the
only commit where the code changed. The walkthrough passes at that SHA.

## Files worth showing in the post

| File | Why |
|---|---|
| `frontend/src/api.ts` | The only `fetch` in the app. Attaches the JWT, turns FastAPI's two error-body shapes into one sentence, and — the subtle bit — treats a 401 as "session over" *only* when the request carried a token. A wrong password is also a 401 and must not bounce the user. |
| `frontend/src/types.ts` | The Pydantic schemas as TypeScript, in snake_case on purpose. The comment explains why the camelCase convention stops at the wire. |
| `frontend/src/pages/TaskPage.tsx` | `diff()` — the PATCH body is only what changed, and `""` becomes `null`. `JSON.stringify` drops `undefined` and keeps `null`, which is exactly the backend's "left out vs. sent null" distinction from phase 3. |
| `frontend/src/hooks.ts` | `useAsync`: the "no React Query" decision as thirty lines, with the cancelled flag that StrictMode forces you to write. |
| `frontend/src/pages/MembersPage.tsx` | Hide, but never rely on hiding. Admin controls are hidden for members; the backend's 403/409 sentences are shown verbatim when something is refused. Phase 8's tool gating has the same shape. |
| `frontend/vite.config.ts` | One `.env` for every service: `envDir` points Vite at the repo root, and the `VITE_` prefix is the only thing keeping the database password out of the browser bundle. |
| `frontend/scripts/walkthrough.mjs` | The "done when" as a script: every screen, in a real Chrome, with checks, and the database left as it was found. Zero dependencies — Node's built-in `WebSocket` and Chrome's DevTools Protocol. |

## What we built

Everything in PLAN.md §10: login/register, projects list (with "assigned to
me", because `/me/tasks` exists and the chat client's `my_tasks` tool will
want a UI to compare against), the board with four status columns, task
detail with comments, and members. Fourteen source files, no component
library, no state library. `npm run typecheck` and `npm run build` are clean.

Verified by `npm run walkthrough` against the seed — 19 checks, all passing:
wrong password shows "Invalid email or password" and stays on `/login`; Alice
sees both projects; a card moves `todo → in_review → todo` through the
select; "Only overdue" changes the list *via the API* (4 of 8 shown); a task
is created, reassigned to Bob with priority high in one PATCH, commented on,
and deleted by the admin; removing the last admin shows the backend's 409
sentence; Carol is added and removed; Bob (a member) sees no Members link,
gets a read-only members page by URL, no Delete button, and the 403 sentence
on `/projects/API`; a garbage token in `localStorage` lands on `/login` with
the token cleared. Zero console errors.

## Decisions made along the way

**React Router, and nothing else beyond React.** `frontend/README.md` bans
Redux, React Query and component libraries; it didn't mention routing. Five
URLs that must survive a reload and the back button is exactly what a router
is for, and a hand-rolled one is forty lines a reader has to trust rather
than one they already know. React Router 7 in plain `<BrowserRouter>` mode
— no loaders, no data APIs — so it stays a route table.

**`useAsync` instead of React Query.** Four pages need "fetch on mount, show
the error, refetch after a write". That is one hook. The cancelled flag in
it is the part worth reading: React 19 StrictMode mounts twice in dev, and
the first mount's response can land after the second's.

**snake_case types.** The convention is camelCase in TypeScript; `types.ts`
keeps `full_name` and `my_role`. Those types describe JSON we don't own, and
a rename layer is where "works in curl, not in the app" bugs live. Our own
identifiers are camelCase.

**Filters go to the API.** "Only mine" and "Only overdue" send `assignee_id`
and `overdue` to `GET /projects/{key}/tasks` rather than filtering in the
browser. The MCP `list_tasks` tool will use the same parameters, so the two
clients can't drift on what "overdue" means.

**PATCH sends the diff.** `TaskPage` compares the form to the loaded task and
sends only changed fields; empty strings become `null`. Sending everything
would have worked, but it would have hidden the one thing phase 3's PATCH
was designed around.

**Hide, don't enforce.** Admin controls (Members link, Delete task, the
add/remove member form) are hidden for members. Nothing in the frontend
*prevents* anything — a member who edits the URL gets the backend's sentence
in the error banner. This is deliberately the same shape as tool gating
(PLAN.md §8): the gate is a courtesy, `require_admin` is the rule.

**Token in `localStorage`, said plainly.** PLAN.md §6 promised we'd be
explicit: anyone running JavaScript on the origin can read it; the
alternative (httpOnly cookie) needs CSRF protection and a different CORS
setup, which is a post of its own. `api.ts` says so in a comment.

**One `.env`.** Vite defaults to `frontend/.env`; `envDir` moves it to the
repo root so `.env.example` stays the single list. `FRONTEND_PORT` is read
with `loadEnv` (all variables, config-side); the browser bundle only ever
sees `VITE_*`.

**`npm run build` type-checks first.** Vite uses esbuild, which strips types
without checking them. The first build of this phase passed with a real
type error in `api.ts`. `"build": "tsc --noEmit && vite build"` is the fix.

**No Dockerfile.** PLAN.md §11 puts all four in phase 12 and the backend
still runs on the host. The Compose comment that said "frontend (phase 4)"
now says phase 12.

**The walkthrough is a script, in the repo.** CLAUDE.md: "no manual clicking
that isn't also a script". It needs Chrome and both servers running, which
is more setup than pytest — so it is *not* wired into `npm run build`, and
the backend rules are still tested by pytest. It leaves the database as it
found it (creates then deletes; adds then removes; moves then moves back).

## What went wrong

### Vite built a bundle with a type error in it

**Symptom.** First `npx tsc --noEmit`: `error TS2345: Argument of type
'TaskFilters' is not assignable to parameter of type 'Record<string, string |
boolean | undefined>'. Index signature for type 'string' is missing`. First
`npx vite build`, same tree: `✓ built in 310ms`.

**Root cause.** Two things. Vite transpiles with esbuild, which removes type
annotations and never checks them; `vite build` succeeding says nothing
about types. And the error itself: TypeScript infers an implicit index
signature for object *type aliases* but refuses to for *interfaces* (an
interface can be extended later with a property of any type, so the
compiler won't promise `Record<string, X>` holds). `TaskFilters` was an
`interface`.

**Fix.** `TaskFilters` became a `type`, with a comment. `build` runs `tsc
--noEmit` first so this class of bug can't ship.

**What the docs didn't say.** The Vite docs mention that it doesn't type
check, in the TypeScript features page — not next to `vite build`. The
interface-vs-type rule is in a 2017 TypeScript issue, not the handbook.

### The browser walkthrough's first draft used `nth-of-type` on selects

**Symptom.** `timed out waiting for selector form select:nth-of-type(3)` on
the task page, while the page text showed all four selects present.

**Root cause.** `:nth-of-type` counts siblings *within one parent*. Each
select sits inside its own `<label>` (`components/ui.tsx`, `Field`), so
every select is the first of its type. A script bug, not an app bug — but
it cost a run.

**Fix.** Index into `document.querySelectorAll("form select")`, and give the
board's selects an `aria-label` so a test can name them. The aria-label
also makes them readable to a screen reader, which is the right reason to
have it.

**What the docs didn't say.** MDN does say this about `:nth-of-type`. We
didn't read it.

### Nothing else

CORS worked on the first request — phase 3 had already listed
`http://localhost:5173`. The date input's `YYYY-MM-DD` value is exactly
what Pydantic's `date` wants, so no conversion. Tailwind v4 needed no
config file. Node 25, Vite 8, TypeScript 7 (the native port) and React 19.3
were all a day old and all just worked.

## What surprised us

- **A 401 is two different things.** From `/auth/login` it's "wrong
  password"; from anything else it's "your token is dead". The first draft
  of `api.ts` bounced the user to `/login` on both — which on the login page
  meant the error message flashed and vanished. The fix is one condition:
  only a 401 on a request that *carried* a token ends the session.
- **`JSON.stringify` already speaks PATCH.** `undefined` keys vanish, `null`
  keys survive. A `TaskPatch` with optional-and-nullable fields maps onto the
  wire with no code at all.
- **Node has a WebSocket client now** (22+), and Chrome's DevTools Protocol
  is just JSON over it. A headless-browser test in ~200 lines with no
  `npm install` was not something we expected to be able to say.
- **`react-refresh` shows up in `curl localhost:5173`.** Vite injects it
  into `index.html` in dev. Harmless; confusing for ten seconds.

## Known limitations (said plainly)

- **No tests in the pytest sense.** The walkthrough needs Chrome and two
  running servers, so it isn't in `build` and won't be in CI as-is. The
  rules are tested in `fastapi-backend/tests`; the UI is proved by running
  it. Honest, and enough for one post.
- **No pagination, no search, no drag-and-drop.** The board is four
  columns and a select. PLAN.md §1.
- **No role change.** Promote someone by removing and re-adding as admin.
  The members screen didn't need more, so the backend doesn't get a route.
- **The token is in `localStorage`.** See `api.ts`.
- **The seed date is fixed, so "overdue" drifts.** The seed's due dates are
  in July 2026; every one of them is now overdue on the board. Cosmetic.
- **`window.confirm` for destructive actions.** A modal would be nicer and
  teach nothing.

## For the post

The frontend and the MCP server are the same kind of client. Both log in,
both hold a JWT, both send `Authorization: Bearer` to the same fifteen
routes, and both hide what you can't do while trusting the backend to
refuse it. If the reader gets that symmetry from this post, phase 6's "the
token rides along" and phase 8's gating will read as obvious.

## Next: phase 5

The first MCP server — FastMCP over stdio, `whoami` and `list_projects`,
pointed at Claude Desktop. It calls the same `/auth/me` and `/projects` this
frontend just used.
