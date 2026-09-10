# Phase 2 — Auth: register, login, JWT, `current_user`

**Commits (oldest → newest):** `8bbd4e6` — phase 2 landed as a *single*
commit, not the six-way split proposed at the bottom of this brief. The
split is still the right shape for the post to walk through; the SHA is the
one to pin to. (Recorded during phase 3, which is exactly the archaeology
`docs/briefs/README.md` warns about — the line was blank for a phase.)

The blog post for this phase ("Auth, understood", PLAN.md §11) should pin
`app/security.py` and `app/deps.py` to the commit where they land — those two
files *are* the post.

## Files worth showing in the post

| File | Why |
|---|---|
| `fastapi-backend/app/security.py` | The whole of "our own JWT" in ~100 lines: hash, verify, sign, decode. The docstring explains what a JWT is and what we chose not to put in it. |
| `fastapi-backend/app/deps.py` | `current_user` — the dependency every protected route hangs off. Also why a missing token is 401 and not FastAPI's default 403. |
| `fastapi-backend/app/routers/auth.py` | Three routes. The login handler is where "one error message for every failure" is explained. |
| `fastapi-backend/tests/test_auth.py` | Fifteen tests, each named for the bug it catches. `test_token_carries_no_roles` pins ADR 0002's key detail. |
| `fastapi-backend/app/config.py` | The JWT settings, and the `cors_origin_list` trick for comma-separated env vars. |

## What we built

The smallest thing that satisfies PLAN.md §11's "done when": *can get a
token and hit `/auth/me`*.

- `app/security.py` — `hash_password`, `verify_password` (bcrypt via
  passlib, unchanged from phase 1's seed) and `create_access_token`,
  `decode_access_token` (HS256 via PyJWT). One `TokenError` for every
  way a token can be bad.
- `app/deps.py` — `current_user`. Reads the bearer header, decodes, loads
  the row, refuses deleted or deactivated users. `require_member` and
  `require_admin` are **not** here yet: they need a project key in the URL
  to check against, and no route has one until phase 3.
- `app/schemas/auth.py` — `RegisterRequest`, `LoginRequest`, `TokenResponse`,
  `UserOut`. `UserOut` is the only shape a user ever leaves the server in,
  and it has no `password_hash` field, so there is no route that *could*
  leak it.
- `app/routers/auth.py` — `POST /auth/register` (201, or 409 on a duplicate
  email), `POST /auth/login` (JSON in, token out), `GET /auth/me`.
- `app/main.py` — the `FastAPI` app, CORS from `CORS_ORIGINS`, `/health`.
- `scripts/seed.py` — now hashes through `app.security.hash_password`
  instead of its own `CryptContext`, so demo hashes and login verification
  can't drift apart.
- `tests/conftest.py` gains a `client` fixture; `tests/test_auth.py` has
  fifteen tests, all through HTTP.

Verified by hand as well as by pytest: seed, `uvicorn`, `curl` login as
Alice, `curl /auth/me` with the token, `curl /auth/me` without it (401),
wrong password (401, same body as unknown email), and a CORS preflight
from `http://localhost:5173` (allowed, with credentials).

## Decisions made along the way

**Login takes JSON, not an OAuth2 form.** FastAPI's tutorial uses
`OAuth2PasswordRequestForm` (`application/x-www-form-urlencoded`, fields
named `username`/`password`), which buys the "Authorize" button in the
`/docs` page. PLAN.md §6 shows a JSON body with `email`/`password`, and
that is what the frontend and the chat client will actually send. *Test
like the real client* wins over the Swagger button. Cost: `/docs` can't
log you in interactively; paste a token into the `HTTPBearer` box instead.

**PyJWT, not python-jose.** One dependency, two functions (`encode`,
`decode`), and the MCP server will use the same library to verify the same
tokens in phase 6 — so PLAN.md §6's `jwt.decode(token, JWT_SECRET,
algorithms=["HS256"])` snippet is literally the code. python-jose wraps
several crypto backends and has had unpatched CVEs; not worth explaining.

**A missing token is 401, not 403.** FastAPI's `HTTPBearer` defaults to
`auto_error=True`, which returns **403** when the header is absent. RFC
6750 says 401 with `WWW-Authenticate: Bearer`, and the distinction matters
later: the MCP server will map 401 ("log in again") and 403 ("you're not
allowed") to different tool errors. `auto_error=False` routes the missing
case into our code, and `test_me_without_token_is_401_not_403` pins it.

**One 401 body for every login failure.** Unknown email, wrong password,
and deactivated account all return `{"detail": "Invalid email or
password"}`. Distinguishing them would let anyone enumerate which emails
have accounts. Honest limitation: the *timing* still differs slightly,
because an unknown email skips the bcrypt call. The fix (a dummy verify
on the miss path) is two lines, and we chose not to add them to a
learning app — noted in the handler's comment rather than pretended away.

**Register does not return a token.** One route mints tokens. The
frontend does register → login, one extra round-trip, and the code has
one place to reason about token issuance.

**Passwords capped at 72 characters.** bcrypt silently ignores bytes past
72. Rather than accept a 100-character password and verify only its
prefix, the schema rejects >72 with a 422. Also a minimum of 8; no other
rules.

**No roles in the token — and a test that says so.** ADR 0002 already
decided it; `test_token_carries_no_roles` decodes the JWT without
verifying and asserts the claim set is exactly `{sub, email, iat, exp}`.
If a future change adds `role`, that test's docstring explains the
regression it would cause (promotions not taking effect until re-login).

**Deleted or deactivated users are refused even with a valid token.**
`current_user` loads the row and checks `is_active`. That one indexed
lookup per request is the closest thing to revocation we have without a
token blacklist — and it's the same lookup phase 3 needs anyway to answer
membership questions.

**Still passlib.** Phase 1's `bcrypt<4.1` pin stays. Migrating to
`pwdlib` or raw `bcrypt` would be a phase of its own with nothing to
teach about MCP; the pin is annotated and the seed and login now share one
`CryptContext`, so a later migration touches exactly one file.

**No backend container yet.** Phase 1's brief expected phase 2 to
"introduce the container and decide which host is used from where". PLAN.md
§11 puts all four Dockerfiles in phase 12, and PLAN.md is the source of
truth. So `POSTGRES_HOST=localhost` stays, the backend runs with
`uv run uvicorn`, and two comments (`docker-compose.yml`, `.env.example`)
that said "phase 1" / "phase 2+" now say phase 12. The phase-1 brief is
left as written — it records what we believed that day.

**`CORS_ORIGINS` stays a string in `Settings`.** pydantic-settings parses
`list[str]` fields from env as *JSON*, so `CORS_ORIGINS=["http://…"]`
would be the required form. A plain comma-separated string plus a
`cors_origin_list` property is friendlier to anyone editing `.env`.

## What went wrong

### `EmailStr` failed at *import* time, not at validation time

- **Symptom:** `from app.schemas.auth import ...` raised
  `ImportError: email-validator is not installed, run pip install
  'pydantic[email]'`. Not on the first bad request — on module import,
  which means the whole app refuses to start.
- **Root cause:** pydantic builds the validation schema for a model class
  when the class body executes. `EmailStr`'s schema builder imports
  `email_validator` right then. It's an optional dependency of pydantic
  (`pydantic[email]`), and neither `fastapi` nor `fastapi[standard]` pulls
  it in.
- **Fix:** `"pydantic[email]>=2.7,<3"` in `pyproject.toml`, annotated.
- **What the docs didn't say:** FastAPI's docs use `EmailStr` in examples
  without mentioning the extra, and the pydantic docs list it under
  "optional dependencies" without saying the failure is at import time.
  For a trainee the surprise is the *when*: a validation helper that
  breaks startup.

### Starlette 1.6 wants `httpx2`, not `httpx`

- **Symptom:** `pytest` passed, but with
  `StarletteDeprecationWarning: Using 'httpx' with 'starlette.testclient'
  is deprecated; install 'httpx2' instead.`
- **Root cause:** httpx 2.x is published on PyPI under a *different name*
  (`httpx2`) so 1.x and 2.x can coexist. Starlette's `testclient.py`
  tries `import httpx2 as httpx` first, falls back to `httpx` with a
  deprecation warning, and will presumably drop the fallback in a later
  release.
- **Fix:** the dev dependency is `httpx2>=2.12,<3` instead of `httpx`.
  All fifteen tests pass unchanged; `fastapi.testclient.TestClient` is
  just a re-export of Starlette's.
- **What the docs didn't say:** FastAPI's testing page still says
  `pip install httpx`. The only hint is the warning text itself. Worth
  one line in the post because every FastAPI tutorial the reader has seen
  says `httpx`.

### `uv add` rewrites `pyproject.toml` and drops the blank lines

- **Symptom:** after `uv add fastapi uvicorn pyjwt`, the carefully
  commented dependency list had lost every blank line between comment
  blocks, and the new entries were appended bare at the end. `uv add
  --group dev` then *re-sorted* the dev group, leaving an orphaned comment
  above the wrong package.
- **Root cause:** `uv add` re-serialises the array. It preserves comments
  attached to lines but not the spacing between blocks, and it keeps
  groups sorted.
- **Fix:** hand-edit after every `uv add`, and check `uv lock --check`
  still passes. Small, but this repo's `pyproject.toml` is a teaching
  document, so it's worth knowing the tool will fight you.
- **What the docs didn't say:** nothing in `uv add --help` mentions
  reformatting.

### Nothing else

The JWT round-trip, `current_user`, CORS, the 401 paths, and the seed
sharing one hash function all worked first time. All fifteen auth tests
were green on the first run.

## What surprised us

- **How little code it is.** ADR 0002 promised "about eighty lines you can
  read in one sitting." `security.py` is ~60 lines of code under ~50 lines
  of docstring; `deps.py` is ~30 lines of code. The ADR's bet holds.
- **The 401-vs-403 choice is invisible unless you test through HTTP.**
  We knew `HTTPBearer`'s 403 default from the docs and set
  `auto_error=False` up front, so nothing failed — but only
  `test_me_without_token_is_401_not_403` keeps it that way. A test that
  called `current_user` directly could never notice the header-less case,
  because FastAPI answers it before the function runs.
- **`db.refresh()` after commit was *not* needed.** The first draft of
  `register` refreshed the user to pull back the `server_default` columns
  (`created_at`, `is_active`). Checked before writing that up: on Postgres,
  SQLAlchemy 2.0 adds `RETURNING created_at, is_active` to the INSERT and
  fills the object in the same round-trip (`eager_defaults="auto"`), so the
  values were already there. The refresh is gone and the comment in the
  router says why. Lesson for the post: verify a "load-bearing" claim
  before writing it in a comment — this one would have been wrong.

## Known limitations (said plainly, per CLAUDE.md)

- No refresh tokens, no logout that invalidates anything (ADR 0002).
- No rate limiting on `/auth/login` — brute-forcing is only slowed by
  bcrypt itself.
- Login timing leaks "email exists" a little (see above).
- The backend listens on the host, not in Compose, until phase 12.

## Proposed commit split

One logical change each, so the history reads like the post:

1. `Phase 2: FastAPI, PyJWT, uvicorn, httpx2 — the deps auth needs`
   (`pyproject.toml`, `uv.lock`)
2. `Phase 2: JWT + CORS settings in config.py`
3. `Phase 2: security.py — hash, verify, sign, decode` (+ seed reuses it)
4. `Phase 2: current_user dependency, auth schemas, /auth routes, the app`
5. `Phase 2: auth tests through HTTP, like the real client`
6. `Phase 2 brief + status: README, PLAN §14, CLAUDE.md, stale phase comments`

## Next: phase 3

Projects, members, tasks, comments — every route in PLAN.md §7 — plus
`require_member` / `require_admin` in `deps.py` and `/me/capabilities`.
Phase 1's brief flagged the composite-FK RESTRICT question for "remove
member"; that decision is due then.
