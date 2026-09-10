"""Tests for ``/projects`` and ``/projects/{key}/members`` — through HTTP.

Same rule as test_auth.py: every request goes through ``TestClient`` with a
real bearer header and is judged on status code and JSON. The data is the
seed (see conftest): WEB has Alice (admin) and Bob (member); API has Alice
(admin) and Carol (member). Each test is named for the bug it would catch.
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Task
from tests.conftest import ALICE, BOB, CAROL, bearer, uid

# ── Listing ──────────────────────────────────────────────────────────────────


def test_list_projects_shows_only_my_projects_with_my_role(client: TestClient, token_for) -> None:
    """The join on project_members *is* the authorisation for this list."""
    r = client.get("/projects", headers=bearer(token_for(BOB)))
    assert r.status_code == 200, r.text
    assert [(p["key"], p["my_role"]) for p in r.json()] == [("WEB", "member")]

    r = client.get("/projects", headers=bearer(token_for(ALICE)))
    assert [(p["key"], p["my_role"]) for p in r.json()] == [("API", "admin"), ("WEB", "admin")]


def test_list_projects_without_token_is_401(client: TestClient, seeded: None) -> None:
    assert client.get("/projects").status_code == 401


def test_project_route_without_token_is_401_even_for_unknown_key(client: TestClient, seeded: None) -> None:
    """Pins "401 beats 404": `get_project` asks for `current_user` before it
    looks the key up. The first draft didn't, and a route that listed
    `get_project` before `require_member` let an anonymous caller probe which
    keys exist by comparing 404 against 401."""
    assert client.get("/projects/WEBB").status_code == 401
    assert client.get("/projects/WEB").status_code == 401


# ── Creating ─────────────────────────────────────────────────────────────────


def test_create_project_makes_creator_admin(client: TestClient, token_for) -> None:
    """Without this there is no way for a project to ever get an admin."""
    r = client.post(
        "/projects",
        json={"key": "OPS", "name": "Operations", "description": "On-call and infra"},
        headers=bearer(token_for(CAROL)),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["key"] == "OPS"
    assert body["my_role"] == "admin"
    assert body["created_by"] == str(uid(CAROL))

    r = client.get("/projects/OPS/members", headers=bearer(token_for(CAROL)))
    assert [(m["email"], m["role"]) for m in r.json()] == [(CAROL, "admin")]


def test_create_project_uppercases_key(client: TestClient, token_for) -> None:
    """The DB CHECK constraint demands uppercase; the API shouldn't make the
    client care. `GET /projects/ops` must find it too (the read side)."""
    r = client.post("/projects", json={"key": "ops", "name": "Ops"}, headers=bearer(token_for(BOB)))
    assert r.status_code == 201, r.text
    assert r.json()["key"] == "OPS"
    assert client.get("/projects/ops", headers=bearer(token_for(BOB))).status_code == 200


def test_create_project_duplicate_key_is_409(client: TestClient, token_for) -> None:
    r = client.post("/projects", json={"key": "web", "name": "Again"}, headers=bearer(token_for(CAROL)))
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == "Project key 'WEB' is already taken"


def test_create_project_bad_key_is_422(client: TestClient, token_for) -> None:
    """One letter minimum, no hyphens (they'd break "WEB-14"), ten chars max."""
    for key in ("W", "WEB-2", "ABCDEFGHIJK", "1AB", ""):
        r = client.post("/projects", json={"key": key, "name": "x"}, headers=bearer(token_for(ALICE)))
        assert r.status_code == 422, (key, r.text)


# ── Detail ───────────────────────────────────────────────────────────────────


def test_get_project_unknown_key_is_404_with_instructive_message(client: TestClient, token_for) -> None:
    """PLAN.md §8: errors are instructions. A model reading this can recover."""
    r = client.get("/projects/WEBB", headers=bearer(token_for(ALICE)))
    assert r.status_code == 404, r.text
    assert r.json()["detail"].startswith("No project with key 'WEBB'")
    assert "GET /projects" in r.json()["detail"]


def test_get_project_as_non_member_is_403_not_404(client: TestClient, token_for) -> None:
    """The boundary. Carol is real, WEB is real, and the answer is no."""
    r = client.get("/projects/WEB", headers=bearer(token_for(CAROL)))
    assert r.status_code == 403, r.text
    assert r.json()["detail"] == "You are not a member of project 'WEB'"


def test_get_project_returns_my_role(client: TestClient, token_for) -> None:
    r = client.get("/projects/WEB", headers=bearer(token_for(BOB)))
    assert r.status_code == 200, r.text
    assert r.json()["my_role"] == "member"
    assert r.json()["name"] == "TaskFlow Web"


# ── Members: listing and adding ──────────────────────────────────────────────


def test_list_members_carries_email_and_role(client: TestClient, token_for) -> None:
    r = client.get("/projects/WEB/members", headers=bearer(token_for(BOB)))
    assert r.status_code == 200, r.text
    assert [(m["email"], m["full_name"], m["role"]) for m in r.json()] == [
        (ALICE, "Alice Adams", "admin"),
        (BOB, "Bob Brown", "member"),
    ]
    assert r.json()[0]["user_id"] == str(uid(ALICE))


def test_add_member_by_email_as_admin(client: TestClient, token_for) -> None:
    """After being added, Carol's *existing* token sees WEB. No re-login:
    membership is read per request, never from the token."""
    assert client.get("/projects/WEB", headers=bearer(token_for(CAROL))).status_code == 403

    r = client.post(
        "/projects/WEB/members", json={"email": CAROL}, headers=bearer(token_for(ALICE))
    )
    assert r.status_code == 201, r.text
    assert r.json()["email"] == CAROL
    assert r.json()["role"] == "member"  # the default
    assert r.json()["user_id"] == str(uid(CAROL))

    assert client.get("/projects/WEB", headers=bearer(token_for(CAROL))).status_code == 200


def test_add_member_as_member_is_403(client: TestClient, token_for) -> None:
    r = client.post("/projects/WEB/members", json={"email": CAROL}, headers=bearer(token_for(BOB)))
    assert r.status_code == 403, r.text
    assert r.json()["detail"] == "Only an admin of project 'WEB' can do this"


def test_add_member_unknown_email_is_404(client: TestClient, token_for) -> None:
    r = client.post(
        "/projects/WEB/members", json={"email": "dave@example.com"}, headers=bearer(token_for(ALICE))
    )
    assert r.status_code == 404, r.text
    assert "register" in r.json()["detail"]


def test_add_member_already_member_is_409(client: TestClient, token_for) -> None:
    r = client.post("/projects/WEB/members", json={"email": BOB}, headers=bearer(token_for(ALICE)))
    assert r.status_code == 409, r.text


def test_add_member_email_is_case_insensitive(client: TestClient, token_for) -> None:
    """Emails are stored lowercase (CHECK constraint); the lookup must
    lowercase too or "Carol@Example.com" is a 404 for a real user."""
    r = client.post(
        "/projects/WEB/members",
        json={"email": "Carol@Example.com", "role": "admin"},
        headers=bearer(token_for(ALICE)),
    )
    assert r.status_code == 201, r.text
    assert r.json()["email"] == CAROL
    assert r.json()["role"] == "admin"


# ── Members: removing ────────────────────────────────────────────────────────


def test_remove_member_unassigns_their_tasks_in_one_go(client: TestClient, token_for, db: Session) -> None:
    """The composite FK is RESTRICT: the DB refuses to delete a membership
    while tasks point at it. The route unassigns first, in the same
    transaction. Bob has WEB-2, WEB-3 and WEB-4 in the seed."""
    before = db.scalar(select(Task.number).where(Task.assignee_id == uid(BOB)).order_by(Task.number))
    assert before is not None  # the seed really does assign Bob something

    r = client.delete(f"/projects/WEB/members/{uid(BOB)}", headers=bearer(token_for(ALICE)))
    assert r.status_code == 204, r.text

    # Bob's tasks still exist, just unassigned — nothing was deleted but the membership.
    db.expire_all()
    assert db.scalars(select(Task).where(Task.assignee_id == uid(BOB))).all() == []
    assert db.scalar(select(Task.number).where(Task.number == 4)) == 4
    # Bob is out, and the API project (which Bob was never in) is untouched.
    assert client.get("/projects/WEB", headers=bearer(token_for(BOB))).status_code == 403
    r = client.get("/projects/API/members", headers=bearer(token_for(ALICE)))
    assert [m["email"] for m in r.json()] == [ALICE, CAROL]


def test_remove_member_as_member_is_403(client: TestClient, token_for) -> None:
    r = client.delete(f"/projects/WEB/members/{uid(ALICE)}", headers=bearer(token_for(BOB)))
    assert r.status_code == 403, r.text


def test_remove_last_admin_is_409(client: TestClient, token_for) -> None:
    """Alice removing herself would leave WEB with nobody who can manage it."""
    r = client.delete(f"/projects/WEB/members/{uid(ALICE)}", headers=bearer(token_for(ALICE)))
    assert r.status_code == 409, r.text
    assert "last admin" in r.json()["detail"]


def test_remove_non_member_is_404(client: TestClient, token_for) -> None:
    r = client.delete(f"/projects/WEB/members/{uid(CAROL)}", headers=bearer(token_for(ALICE)))
    assert r.status_code == 404, r.text
    r = client.delete(f"/projects/WEB/members/{uuid.uuid4()}", headers=bearer(token_for(ALICE)))
    assert r.status_code == 404, r.text
