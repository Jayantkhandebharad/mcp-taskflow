# Working agreement

**Read [`PLAN.md`](PLAN.md) first.** It is the source of truth for this repo: the
app, the data model, the auth path, the tool design, and the build order. This
file is only about *how we work*.

## The audience is a trainee engineer

Everything in this repo — code, comments, docs, commit messages — is written for
someone in their third year who has never built an MCP server. That is not a
disclaimer; it is the design constraint.

- Define a term the first time it appears.
- Short sentences. Plain words.
- Every non-obvious line gets a comment explaining *why*, not *what*.

## Explain, then write

Before a file gets written, say in plain words what it does and why it exists. If
that explanation comes out tangled, the design is wrong — fix the design, not the
wording.

## Small commits, reviewable diffs

Show the diff, explain it, wait for the go-ahead. One logical change per commit.
The git history should read like the blog series, because the blog series is
written from it.

## Reproducible from zero, always

Everything via `docker compose up` plus scripted seeds. No manual clicking that
isn't also a script. If a step only exists in someone's terminal history, it
doesn't exist.

## Log the real problems the day they happen

Each phase gets `docs/briefs/phase-N.md`, written *while* the work happens:
symptom → root cause → fix → what the docs didn't tell us. Nobody can reconstruct
these a month later, and they are the most valuable thing in the repo.

## Test like the real client, not an ideal one

The hardest bug in the previous project was a test that constructed the "perfect"
request, passed happily, and shipped something every actual client rejected. Tests
must behave like the thing that will really call us.

## Never fake a capability

If a client can't do something, say so — in the code comment and in the post. An
honest limitation is more useful to a reader than a demo that doesn't reproduce on
their machine.

## Two rules that are checked, not just agreed

1. **No provider SDK outside `chat-client/app/llm.py`.** No `import anthropic`, no
   `import openai`, anywhere else. CI greps for it.
2. **The MCP server never imports a database driver.** It calls the backend's API.
   CI greps for that too.

Conventions that aren't checked stop being true within a month.

## Conventions

- **Ports:** db `5432`, backend `8000`, mcp-server `9000`, chat-client `8100`,
  frontend `5173`. The same numbers in Compose, `.env.example`, and every doc.
- **Config:** environment variables only, all of them listed in `.env.example`
  with a comment each.
- **Naming:** `snake_case` in Python and the database, `camelCase` in TypeScript.
  Tool names are `verb_noun` — `create_task`, never `taskCreate`.
- **Tests:** pytest for both Python services. Not chasing coverage — chasing the
  tests that would have caught a real bug.
