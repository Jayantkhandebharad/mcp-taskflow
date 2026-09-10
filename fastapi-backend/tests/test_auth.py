"""Tests for ``/auth/*`` — driven through HTTP, the way real clients will.

The rule from CLAUDE.md: *test like the real client, not an ideal one.* So
every test here sends JSON bodies and ``Authorization: Bearer`` headers via
``TestClient`` and asserts on status codes and response JSON — nothing
reaches into the router functions directly. Each test names the bug it
would catch.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import User
from app.security import create_access_token, hash_password

ALICE = {"email": "alice@example.com", "full_name": "Alice Adams", "password": "correct-horse"}


# ── Helpers ──────────────────────────────────────────────────────────────────


def _register(client: TestClient, **overrides) -> dict:
    body = {**ALICE, **overrides}
    r = client.post("/auth/register", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _login(client: TestClient, email: str = ALICE["email"], password: str = ALICE["password"]):
    return client.post("/auth/login", json={"email": email, "password": password})


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ── The happy path — the phase's "done when" ────────────────────────────────


def test_register_login_me_round_trip(client: TestClient) -> None:
    """PLAN.md §11: phase 2 is done when you can get a token and hit /auth/me."""
    created = _register(client)
    assert created["email"] == ALICE["email"]
    assert created["full_name"] == ALICE["full_name"]
    assert created["is_active"] is True
    # The single most important assertion in this file: the hash never
    # leaves the server, on any response shape.
    assert "password" not in created and "password_hash" not in created

    r = _login(client)
    assert r.status_code == 200, r.text
    token = r.json()
    assert token["token_type"] == "bearer"

    r = client.get("/auth/me", headers=_bearer(token["access_token"]))
    assert r.status_code == 200, r.text
    assert r.json()["id"] == created["id"]
    assert "password_hash" not in r.json()


def test_seeded_demo_password_logs_in(client: TestClient, db: Session) -> None:
    """The seed hashes through app.security; login verifies through it.

    If the two ever used different CryptContexts this is the test that says
    so. It mirrors the seed's row rather than importing the seed, so a seed
    refactor doesn't couple to this file.
    """
    db.add(
        User(
            email="bob@example.com", full_name="Bob", password_hash=hash_password("password")
        )
    )
    db.commit()
    assert _login(client, "bob@example.com", "password").status_code == 200


# ── Register: the ways it should refuse ─────────────────────────────────────


def test_register_duplicate_email_is_409(client: TestClient) -> None:
    _register(client)
    r = client.post("/auth/register", json=ALICE)
    assert r.status_code == 409
    assert r.json()["detail"] == "Email already registered"


def test_register_duplicate_email_is_case_insensitive(client: TestClient) -> None:
    """``Alice@Example.com`` and ``alice@example.com`` are the same account.

    Guards the lowercase-on-the-way-in step in the router. Without it, the
    ORM validator would still lowercase the second row, and the *database*
    unique constraint would fire — as a 500, not a 409.
    """
    _register(client)
    r = client.post("/auth/register", json={**ALICE, "email": "Alice@Example.com"})
    assert r.status_code == 409


def test_register_rejects_bad_input_with_422(client: TestClient) -> None:
    """FastAPI's validation error — the shape every later client will parse."""
    r = client.post("/auth/register", json={**ALICE, "email": "not-an-email"})
    assert r.status_code == 422
    r = client.post("/auth/register", json={**ALICE, "password": "short"})
    assert r.status_code == 422
    # 73 bytes: bcrypt would silently truncate. We refuse instead.
    r = client.post("/auth/register", json={**ALICE, "password": "x" * 73})
    assert r.status_code == 422


# ── Login: the ways it should refuse, all identically ───────────────────────


def test_login_wrong_password_is_401(client: TestClient) -> None:
    _register(client)
    r = _login(client, password="wrong")
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


def test_login_unknown_email_looks_exactly_like_wrong_password(client: TestClient) -> None:
    """Same status, same body — no account enumeration via the login form."""
    _register(client)
    wrong_pw = _login(client, password="wrong")
    no_user = _login(client, email="nobody@example.com")
    assert wrong_pw.status_code == no_user.status_code == 401
    assert wrong_pw.json() == no_user.json()


def test_login_email_is_case_insensitive(client: TestClient) -> None:
    _register(client)
    assert _login(client, email="ALICE@EXAMPLE.COM").status_code == 200


def test_login_inactive_user_is_401(client: TestClient, db: Session) -> None:
    """Soft-delete works: ``is_active = False`` blocks login without a DELETE."""
    created = _register(client)
    user = db.get(User, uuid.UUID(created["id"]))
    user.is_active = False
    db.commit()
    assert _login(client).status_code == 401


# ── /auth/me: every way a token can be bad ──────────────────────────────────


def test_me_without_token_is_401_not_403(client: TestClient) -> None:
    """Missing credentials is 401 ("who are you?").

    FastAPI's ``HTTPBearer`` default is 403 here, which is wrong by RFC 6750
    and would confuse the MCP server's error mapping later. This pins the
    ``auto_error=False`` choice in ``deps.py``.
    """
    r = client.get("/auth/me")
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


def test_me_with_garbage_token_is_401(client: TestClient) -> None:
    assert client.get("/auth/me", headers=_bearer("not.a.jwt")).status_code == 401


def test_me_with_tampered_signature_is_401(client: TestClient) -> None:
    """Flip one character of the signature. The claims are untouched, so a
    decoder that skipped verification would happily accept it.

    Why the *first* character and not the last: an HS256 signature is 32
    bytes, which base64url spells in 43 characters — 258 bits of text for
    256 bits of data. The final character's low two bits are padding that
    the decoder throws away, so flipping it to a neighbour (``B`` → ``A``)
    can produce a *different string for the same signature*, and the
    "tampered" token verifies. Phase 2 shipped that version and it failed
    about one run in sixteen (docs/briefs/phase-3.md). Every bit of the
    first character is real.
    """
    _register(client)
    token = _login(client).json()["access_token"]
    head, payload, sig = token.split(".")
    bad_sig = ("A" if sig[0] != "A" else "B") + sig[1:]
    r = client.get("/auth/me", headers=_bearer(f"{head}.{payload}.{bad_sig}"))
    assert r.status_code == 401


def test_me_with_expired_token_is_401(client: TestClient) -> None:
    created = _register(client)
    token = create_access_token(
        uuid.UUID(created["id"]), created["email"], expires_in=timedelta(seconds=-1)
    )
    assert client.get("/auth/me", headers=_bearer(token)).status_code == 401


def test_me_for_deleted_user_is_401(client: TestClient, db: Session) -> None:
    """A valid signature over a user that no longer exists is still a 401.

    This is the closest thing to revocation we have without a blacklist
    (ADR 0002): delete or deactivate the row, and every outstanding token
    for it stops working on the next request.
    """
    created = _register(client)
    token = _login(client).json()["access_token"]
    db.delete(db.get(User, uuid.UUID(created["id"])))
    db.commit()
    assert client.get("/auth/me", headers=_bearer(token)).status_code == 401


def test_token_carries_no_roles(client: TestClient) -> None:
    """ADR 0002's notable detail, pinned: claims are exactly sub/email/iat/exp.

    If someone adds ``role`` to the token, promotions stop taking effect
    until re-login, and this test explains why that's a regression.
    """
    import jwt  # decoded *without* verification — we only want the claim names

    _register(client)
    token = _login(client).json()["access_token"]
    claims = jwt.decode(token, options={"verify_signature": False})
    assert set(claims) == {"sub", "email", "iat", "exp"}
