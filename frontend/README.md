# frontend

**Its one job:** let a human use the app with a mouse.

A normal React app. It exists to prove TaskFlow is a real product and not just a
fixture for the MCP server — and to give readers something familiar to compare the
chat client against.

## It must never

Know that MCP exists. Know that an LLM exists. There is no AI anywhere in this
folder, and that is deliberate: **MCP is a layer you add to a working app, not an
architecture you build around.**

## Screens

1. Login / Register — `src/pages/LoginPage.tsx`
2. Projects list (plus "assigned to me") — `src/pages/ProjectsPage.tsx`
3. Project board — tasks in columns by status — `src/pages/BoardPage.tsx`
4. Task detail — description, assignee, status, comments — `src/pages/TaskPage.tsx`
5. Members — admin only — `src/pages/MembersPage.tsx`

## Running it

The backend must be up on `:8000` with the seed loaded (see the root README).
Then, from this folder:

```bash
npm install          # one-time, from package-lock.json
npm run dev          # http://localhost:5173 — reloads on save
npm run typecheck    # tsc, no output on success
npm run build        # typecheck, then a production bundle in dist/
npm run walkthrough  # drives every screen in headless Chrome; needs `npm run dev` running
```

Log in as `alice@example.com` / `password` (Bob and Carol work the same way).
Configuration comes from the repo-root `.env` — `VITE_API_URL` says where the
API is, `FRONTEND_PORT` which port to serve on. See `vite.config.ts` for why the
`VITE_` prefix matters.

## How it is put together

```
src/
  main.tsx          mounts <App> inside the router and the auth provider
  App.tsx           the five routes, and the guard that needs a login for four of them
  api.ts            the ONLY file that calls fetch: attaches the JWT, shapes errors, notices 401s
  auth.tsx          who is logged in (React context); login / register / logout
  types.ts          the backend's Pydantic schemas as TypeScript types
  hooks.ts          useAsync — "load on mount, show error, reload after a write"
  labels.ts         display names for the enums, date helpers
  components/       Layout (header), ui (badges, form bits)
  pages/            one file per screen
scripts/
  walkthrough.mjs   the scripted click-through (Chrome DevTools Protocol, no deps)
```

## Deliberately not used

No Redux, no React Query, no component library. `fetch` plus `useState` is enough
at this size, and every dependency is something a reader has to learn before they
can read the code. One `api.ts` attaches the JWT to every request; Tailwind does
the layout. React Router is the one library beyond React itself — five URLs that
must survive a reload and the back button are exactly its job.

The token lives in memory and `localStorage`. That is fine for a learning app on
localhost and the comment in `api.ts` says what you'd do differently in
production.

The frontend gets **one** blog post and does not get to consume more than that.

## Status

Phase 4 — done. All five screens work against the real API; `npm run
walkthrough` proves it. No Dockerfile yet: that is phase 12, with the other
three.

See `PLAN.md` §10 and `docs/briefs/phase-4.md`.
