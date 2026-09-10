"""Tests for ``/me/tasks`` and ``/me/capabilities`` — through HTTP, on the seed.

Alice is admin of WEB and API and holds WEB-1, 5, 7 and API-1, 2, 3, 7.
Bob is a member of WEB only and holds WEB-2, 3, 4. Carol is a member of
API only. Each test is named for the bug it catches.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import ALICE, BOB, CAROL, bearer


def test_my_tasks_spans_projects(client: TestClient, token_for) -> None:
    r = client.get("/me/tasks", headers=bearer(token_for(ALICE)))
    assert r.status_code == 200, r.text
    refs = {t["ref"] for t in r.json()}
    assert refs == {"WEB-1", "WEB-5", "WEB-7", "API-1", "API-2", "API-3", "API-7"}
    assert all(t["assignee"]["email"] == ALICE for t in r.json())


def test_my_tasks_sorted_by_due_date_with_undated_last(client: TestClient, token_for) -> None:
    dues = [t["due_date"] for t in client.get("/me/tasks", headers=bearer(token_for(ALICE))).json()]
    dated, undated = [d for d in dues if d], [d for d in dues if not d]
    assert dated == sorted(dated)
    assert dues == dated + undated  # API-7 has no date and comes last


def test_my_tasks_excludes_other_peoples_tasks(client: TestClient, token_for) -> None:
    r = client.get("/me/tasks", headers=bearer(token_for(BOB)))
    assert {t["ref"] for t in r.json()} == {"WEB-2", "WEB-3", "WEB-4"}


def test_my_tasks_without_token_is_401(client: TestClient, seeded: None) -> None:
    assert client.get("/me/tasks").status_code == 401


def test_capabilities_for_admin_of_two_projects(client: TestClient, token_for) -> None:
    r = client.get("/me/capabilities", headers=bearer(token_for(ALICE)))
    assert r.status_code == 200, r.text
    assert r.json() == {"can_admin_any_project": True, "admin_project_keys": ["API", "WEB"]}


def test_capabilities_for_member_only(client: TestClient, token_for) -> None:
    r = client.get("/me/capabilities", headers=bearer(token_for(BOB)))
    assert r.json() == {"can_admin_any_project": False, "admin_project_keys": []}


def test_capabilities_for_user_with_no_projects(client: TestClient, seeded: None) -> None:
    dave = {"email": "dave@example.com", "full_name": "Dave Dunn", "password": "correct-horse"}
    assert client.post("/auth/register", json=dave).status_code == 201
    token = client.post("/auth/login", json={"email": dave["email"], "password": dave["password"]}).json()
    r = client.get("/me/capabilities", headers=bearer(token["access_token"]))
    assert r.json() == {"can_admin_any_project": False, "admin_project_keys": []}
    assert client.get("/me/tasks", headers=bearer(token["access_token"])).json() == []


def test_capabilities_reflect_promotion_without_relogin(client: TestClient, token_for) -> None:
    """ADR 0002 from the other side: roles are not in the token, so Bob's
    *existing* token answers differently the moment his membership row
    changes. (`token_for` caches tokens for the whole run — this test only
    works *because* of that; it is not working around it.)"""
    bob = bearer(token_for(BOB))
    assert client.get("/me/capabilities", headers=bob).json()["can_admin_any_project"] is False

    alice = bearer(token_for(ALICE))
    assert client.post("/projects", json={"key": "OPS", "name": "Ops"}, headers=alice).status_code == 201
    r = client.post("/projects/OPS/members", json={"email": BOB, "role": "admin"}, headers=alice)
    assert r.status_code == 201, r.text

    assert client.get("/me/capabilities", headers=bob).json() == {
        "can_admin_any_project": True,
        "admin_project_keys": ["OPS"],
    }
    # And the admin-only route agrees, with the same old token.
    r = client.post("/projects/OPS/members", json={"email": CAROL}, headers=bob)
    assert r.status_code == 201, r.text
