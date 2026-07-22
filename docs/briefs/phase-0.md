# Phase 0 — Skeleton

## What we built

The repo shell: four empty service folders each with a README stating its single
job, `.env.example` documenting every variable the project will ever read, a
Compose file running PostgreSQL 16, three ADRs recording the decisions that shape
everything else, and the docs scaffolding.

No application code yet. Deliberately.

## Decisions made along the way

**Folder READMEs instead of empty directories.** Git can't track an empty folder,
so something had to go in each one. Rather than `.gitkeep`, each service folder
got a README that states its one-sentence job and — more usefully — what it must
*never* do. `fastapi-backend/README.md` says "must never know that MCP exists."
Writing those four sentences before writing any code was the most clarifying part
of the phase.

**Three ADRs up front.** Normally ADRs get written after an argument. These were
written before any code because they're the decisions the whole series is *about*:

- [0001](../decisions/0001-mcp-server-calls-the-api-not-the-database.md) — the MCP
  server calls the API, not the database
- [0002](../decisions/0002-own-jwt-instead-of-an-identity-provider.md) — we issue
  our own JWTs rather than running Keycloak
- [0003](../decisions/0003-the-llm-is-swappable.md) — the LLM is swappable, and
  exactly one file knows which one we use

**A named volume, not a bind mount.** `db_data:/var/lib/postgresql/data` rather
than `./data:/var/lib/postgresql/data`. A bind mount would put database files in
the working tree — where they'd need gitignoring, and where file-permission
mismatches between the container's postgres user and the host user cause failures
that are miserable to debug on macOS. `docker compose down -v` wipes the volume
when we want a clean slate.

## What went wrong

**Nothing broke.** It's a Compose file with one service. But two things are worth
recording because they'll bite a reader.

### The Docker daemon wasn't running

- **Symptom:** `unable to get image 'postgres:16-alpine': failed to connect to the
  docker API at unix:///Users/.../docker.sock ... no such file or directory`
- **Root cause:** Docker Desktop wasn't started. The `docker` CLI exists on PATH
  independently of the daemon, so `docker` is a valid command that fails at the
  point of actually needing the engine.
- **Fix:** start Docker Desktop.
- **What the docs didn't say:** the error names a socket path, which reads like a
  configuration problem. It almost never is — it means the engine isn't running.
  Worth a line in the README's quick start.

### Postgres reports "started" before it can accept queries

- **Symptom:** none yet — but this is the classic Compose failure, and it will hit
  us in phase 1 the moment the backend starts alongside the database.
- **Root cause:** the container's entrypoint starts Postgres, briefly accepts
  connections during initialisation, shuts down, and restarts. A service that
  connects during that window gets a connection refused or a database-does-not-exist
  error, and it looks intermittent.
- **Fix, applied now rather than later:** a `pg_isready` healthcheck on the `db`
  service, so that dependent services can use `depends_on: condition:
  service_healthy` instead of the useless default `service_started`.
- **What the docs didn't say:** plenty of Compose examples use bare `depends_on`,
  which only waits for the container to *start*. That's the single most common
  cause of "it works on the second `docker compose up`."

## What surprised us

**The database password has to be written twice, and Compose can't help.**
`.env` contains both:

```bash
POSTGRES_PASSWORD=taskflow_dev_only
DATABASE_URL=postgresql+psycopg://taskflow:taskflow_dev_only@db:5432/taskflow
```

The obvious move — `DATABASE_URL=postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/...`
— doesn't work. Compose interpolates variables inside `compose.yaml`, but **not
inside `.env` itself**; the value would arrive at the backend as a literal string
containing `${POSTGRES_PASSWORD}`.

So the credentials are duplicated, and changing one without the other produces a
password-authentication-failed error that points at the database rather than at
the config file. We've added a comment in `.env.example` rather than pretending
it's elegant. (The alternative — having the backend assemble the URL from the
parts — is arguably cleaner, and is worth revisiting in phase 1 when `config.py`
exists.)

## For the post

**Phase 0 isn't blog-bearing, but one idea from it is worth carrying into post 1:**
write down what each part of the system *must never do* before you write what it
does. "The backend must never know MCP exists" is a stronger design constraint
than any diagram, and it took four sentences.
