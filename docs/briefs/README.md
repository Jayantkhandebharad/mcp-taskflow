# Briefs

One file per phase — `phase-0.md`, `phase-1.md`, and so on. These are the raw
material the blog posts are written from.

**Write them the day the work happens.** Nobody can reconstruct a debugging
session a month later, and the reconstructed version is always tidier and less
useful than what actually happened.

## What goes in one

```markdown
# Phase N — <name>

**Commits:** `<sha>` (or `<first>..<last>` for a range)

## What we built
Two or three sentences.

## Files worth showing in the post
The three or four files a reader should actually look at, with a one-line note
on why each one matters.

## Decisions made along the way
Anything we had to choose between, and why we chose it. Link to an ADR if it
turned out to deserve one.

## What went wrong
The important section. For each problem:
  - Symptom — what we actually saw, verbatim: the error, the wrong output.
  - Root cause — what was really happening.
  - Fix — what we changed.
  - What the docs didn't say — the gap that made this cost an hour instead of
    a minute.

## What surprised us
Things that worked differently than expected, even if nothing broke.

## For the post
The one idea a reader should walk away with. If you can't name it, the phase
probably isn't a post.
```

## Why the commit SHA is at the top

Posts in the portfolio reference this repo's files **pinned to a commit**:

```tsx
<RepoFile path="mcp-server/app/gating.py" branch="a1b2c3d" />
```

Clicking that chip opens the file live from GitHub *at that commit*, so the reader
sees exactly the code the post describes — even after we refactor it two phases
later. Pinning to `main` instead would mean every rename silently breaks a
published post.

The SHA is therefore the one piece of information the post author needs and can't
reconstruct later without digging through history. Write it down while you're
here. See `PLAN.md` §13.

## Why "what went wrong" is the point

A tutorial that only shows the happy path teaches someone to follow steps. The
war stories are what teach them to debug — and they're the only part of a
technical post that can't be got from the official documentation.

Include the embarrassing ones. Especially those.
