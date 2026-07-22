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

1. Login / Register
2. Projects list
3. Project board — tasks in columns by status
4. Task detail — description, assignee, status, comments
5. Members — admin only

## Deliberately not used

No Redux, no React Query, no component library. `fetch` plus `useState` is enough
at this size, and every dependency is something a reader has to learn before they
can read the code. One `api.ts` attaches the JWT to every request; Tailwind does
the layout.

The frontend gets **one** blog post and does not get to consume more than that.

## Status

Phase 4. Nothing here yet.

See `PLAN.md` §10.
