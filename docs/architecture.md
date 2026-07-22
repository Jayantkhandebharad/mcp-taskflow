# Architecture

`PLAN.md` §4 has the diagram and the service table. This document is the part that
diagram can't show: **what actually happens during a single request.**

---

## Flow 1 — a human uses the website

Alice opens the board and drags `WEB-14` from *To Do* to *In Progress*.

```
1. Browser        PATCH /tasks/WEB-14   { "status": "in_progress" }
                  Authorization: Bearer <alice's JWT>
                        │
2. fastapi-backend      ▼
   current_user()   decode the JWT → user id → load Alice. 401 if anything is off.
   require_member() is Alice in project_members for WEB? 403 if not.
   handler          parse "WEB-14" → project WEB, task number 14
                    UPDATE tasks SET status = 'in_progress' WHERE ...
                        │
3. Browser         ◀────┘   200 { task }
```

Three checks, in order: **who are you** → **are you allowed** → **do the thing.**
Nothing surprising. Hold onto it, because the next flow is the same picture with
one more box.

---

## Flow 2 — a human asks the AI to do the same thing

Alice types *"move WEB-14 to in progress"* into the chat client.

```
1. Browser         POST /chat  { "message": "move WEB-14 to in progress" }
                   Cookie: session=<alice's chat session>
                         │
2. chat-client           ▼
   look up Alice's JWT from her session
   connect to mcp-server, sending  Authorization: Bearer <alice's JWT>
   tools/list  ──────────────────────────────────▶
                                                  │
3. mcp-server                                     ▼
   verify the JWT signature (fast reject on garbage)
   ask the backend: GET /me/capabilities  (with Alice's token)
   filter the tool list → Alice is a member, so no delete_task
   ◀────────────────────────────────────────  11 tools
                         │
4. chat-client           ▼
   build the LangGraph agent, bind those 11 tools to the model
   send the conversation to the LLM
   ◀──── the model replies: call update_task_status(task_ref="WEB-14",
                                                    status="in_progress")
                         │
5. chat-client           ▼
   tools/call  ─────────────────────────────────▶
                                                  │
6. mcp-server                                     ▼
   PATCH /tasks/WEB-14  { "status": "in_progress" }
   Authorization: Bearer <alice's JWT>     ← the SAME token, untouched
                                                  │
7. fastapi-backend                                ▼
   current_user() → Alice.  require_member() → yes.  UPDATE.
   ◀────────────────────────────────────────  200 { task }
                         │
8. mcp-server            ▼
   format for a model: "Moved WEB-14 'Fix login redirect' to In Progress."
   ◀──────────────────────────────────────── tool result
                         │
9. chat-client           ▼
   append the result, send back to the LLM
   ◀──── "Done — WEB-14 is now in progress."
                         │
10. Browser        ◀─────┘
```

### The three things to notice

**Step 7 is identical to step 2 of Flow 1.** The backend cannot tell these two
requests apart, and doesn't need to. Same route, same checks, same rule. That's
what "MCP is a layer, not an architecture" means in practice.

**Alice's token is never swapped.** It goes browser → chat-client → mcp-server →
backend without ever being exchanged for a more powerful one. There is no service
account anywhere in this picture. If Alice loses access to project WEB, every
single one of these steps starts failing immediately — including the AI's.

**Step 3 decides what the model can even imagine doing.** Tool gating happens
before the model sees anything. `delete_task` isn't refused later; it is never
offered. That's a UX win — the model won't promise something it can't deliver —
but it is *not* the security boundary. The backend is. We prove that with a test
that calls `delete_task` directly as a member and asserts a 403.

---

## Why the extra hops

Flow 2 makes four HTTP round trips where a direct-to-database MCP server would
make one query. We chose that deliberately; the reasoning is in
[ADR 0001](decisions/0001-mcp-server-calls-the-api-not-the-database.md).

Short version: the rules get written once, and the AI inherits the human's
permissions instead of being handed its own. Inside a Compose network the extra
hops are a fraction of a millisecond, and next to a single LLM round trip they are
invisible. We'll measure it rather than assert it.

---

## Where each rule lives

| Question | Answered by | Where |
|---|---|---|
| Is this token real? | `current_user` | backend `deps.py` |
| Is this token *shaped* right? | signature check | mcp-server `auth.py` — an optimisation only |
| Can this user see this project? | `require_member` | backend `deps.py` |
| Can this user delete a task? | `require_admin` | backend `deps.py` |
| Should this user *see* the delete tool? | capability gate | mcp-server `gating.py` |

Read that table top to bottom: every real decision is in the backend. The MCP
server's two entries are both conveniences — one for speed, one for UX. Neither is
load-bearing for security, and if either were removed the system would still be
correct, just slower and ruder.
