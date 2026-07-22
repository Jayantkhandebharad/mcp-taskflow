# chat-client

**Its one job:** let a human use the app by typing English. Runs the agent loop.

A FastAPI service that serves a plain chat page and drives a LangGraph agent whose
tools come from one or more MCP servers.

## The graph is two nodes

```
        ┌─────────┐
   ─────▶  agent  │  the model, bound to the MCP tools
        └────┬────┘
             │  did it ask for a tool?
       ┌─────┴─────┐
      yes         no
       │           │
  ┌────▼────┐      └────▶ END
  │  tools  │  execute via MCP, append results
  └────┬────┘
       └──────────▶ back to agent
```

That's the whole thing. Understanding this loop is understanding agents.

## Bring your own model

Exactly one file — `app/llm.py` — knows which LLM vendor is in use. Nothing else
in this repo imports a provider SDK, and CI checks that. Switching providers is
one line in `.env`:

```bash
LLM_MODEL=anthropic:claude-opus-4-8
LLM_MODEL=ollama:qwen2.5:14b          # local, free, no API key
```

⚠️ Independence is not equivalence — MCP is tool calling, and small models are
often bad at it. `LLM_ALLOWED_TOOLS` exists so a weaker model can be given four
tools instead of twelve. See `docs/decisions/0003-*`.

## Auth

The chat client is **not** a trusted service with a god-token. The human logs in
with the same credentials they'd use on the website, gets the same kind of JWT,
and that token rides along on every MCP call.

The demo worth building: log in as a member and ask it to delete a task — it
can't, because `delete_task` was never in its tool list. Log in as an admin, same
question, it works. Same code, same model, different token.

## What will live here

```
app/
  main.py         FastAPI: /login, /chat, serves the UI
  graph.py        the LangGraph agent
  llm.py          the model factory — the ONLY vendor-aware file
  mcp.py          connects to one or many MCP servers
  servers.yaml    which MCP servers this client knows about
static/           one HTML page, with a panel showing every tool call
```

`servers.yaml` is a **list** from day one, so adding a second MCP server later is
a config change rather than a refactor.

## Status

Phase 9 builds the agent. Phase 10 adds per-user auth. Phase 11 tests it across
providers. Nothing here yet.

See `PLAN.md` §9.
