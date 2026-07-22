# 0001 — The MCP server calls the API, not the database

**Status:** accepted · **Date:** 2026-07-22

## The question

Our MCP server needs task data. It could get it two ways:

1. **Connect to Postgres directly** — the MCP server gets its own database
   connection and runs its own queries.
2. **Call the backend's REST API** — the MCP server behaves like any other
   client, over HTTP.

## The decision

**Option 2.** The MCP server has no database connection, no ORM models, and no
knowledge of our schema. It speaks HTTP to `fastapi-backend`, carrying the token
of whichever human is talking to the AI.

## Why

**One place holds the rules.** "Only an admin can delete a task" is one check, in
one file, in the backend. With a direct database connection that rule would have
to exist twice — once for the humans and once for the AI — and the two copies
would eventually disagree. When they disagree, the AI path is the one nobody is
looking at.

**The AI is not a superuser.** This is the important one. A direct database
connection needs credentials, and those credentials would belong to the *MCP
server*, not to a person. Every request would run with the same broad access
regardless of who was asking — and the MCP server would have to reimplement "may
this particular user see this particular project?" from scratch. By forwarding the
user's own token instead, the answer is automatic: if Alice can't see project WEB,
neither can Alice's AI assistant. There is no service account to steal and no
"trust me, I'm the AI" path into the data.

**It keeps MCP a layer, not an architecture.** The backend and the frontend don't
know MCP exists. You could delete the `mcp-server/` folder and the product would
still work. That's the shape we want readers to copy: MCP is something you add to
an application you already have.

**It's testable.** The MCP server's tests can point at a real backend and assert
that a member gets a 403 from `delete_task`. Nothing is mocked, so nothing is
mocked *wrongly*.

## What it costs

**An extra network hop.** A tool call is now MCP → HTTP → SQL rather than MCP →
SQL. In a Compose network that is a fraction of a millisecond, and next to an LLM
round trip it is invisible — but it is real, and we will measure it rather than
pretend the clean design is free.

**Some N+1 shapes.** A tool that needs a project and its tasks and its members
makes three HTTP calls where SQL would make one query. Where that actually hurts,
the fix is to add a purpose-built backend endpoint (as we did with
`/me/capabilities`) — not to reach past the backend into the database.

## What we rejected, and why

**"Read from the database, write through the API."** Tempting, and worse than
either pure option: you get the duplication of option 1 for every read path, plus
two mental models to hold. Half a boundary is not a boundary.

**A privileged service token for the MCP server, with the user id passed as a
parameter.** This is how a lot of MCP servers are actually built, and it is the
thing this ADR exists to argue against. It means a single leaked token is
unrestricted access to every user's data, and it means every endpoint has to be
trusted to correctly apply an identity it was *told* rather than one it
*verified*. Forwarding the user's own token removes that entire class of bug.

## See also

- `PLAN.md` §4 — architecture
- `PLAN.md` §6 — the full auth path, end to end
- ADR 0002 — why we issue our own JWTs
