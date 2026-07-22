# fastapi-backend

**Its one job:** own the data and enforce the rules.

This is the system of record. It is the only thing in the repo that opens a
connection to PostgreSQL. Every rule about who may do what lives here, written
once.

## It must never

- Know that MCP exists.
- Know that an LLM exists.
- Trust an identity it was *told*. It verifies the token on every request.

If you find yourself wanting to add an "is this the AI calling?" branch, stop —
the whole design is that the backend can't tell, and doesn't need to.

## What will live here

```
alembic/            migrations, checked in
app/
  main.py           app, router wiring, CORS
  config.py         pydantic-settings — all env in one place
  db.py             engine, session, get_db dependency
  models/           SQLAlchemy tables
  schemas/          Pydantic request/response models
  routers/          auth · projects · tasks · comments
  security.py       password hashing, JWT encode/decode
  deps.py           current_user · require_member · require_admin
scripts/seed.py     deterministic demo data, rerunnable from empty
tests/
```

## Status

Phase 1 builds the schema, migrations and seed. Phase 2 adds auth. Phase 3 adds
the rest of the API. Nothing here yet.

See `PLAN.md` §5 (data model), §6 (auth) and §7 (API surface).
