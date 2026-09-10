"""Tests for tasks — ``/projects/{key}/tasks`` and ``/tasks/{key}-{number}``.

All through HTTP against the seed (conftest). WEB: Alice admin, Bob member,
tasks 1–8 (1 and 2 done; Bob has 2, 3, 4; 6 and 8 unassigned). API: Alice
admin, Carol member, tasks 1–7. Each test is named for the bug it catches.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Comment
from tests.conftest import ALICE, BOB, CAROL, bearer, uid

# ── Listing ──────────────────────────────────────────────────────────────────


def test_list_tasks_returns_ref_project_key_and_assignee_object(client: TestClient, token_for) -> None:
    r = client.get("/projects/WEB/tasks", headers=bearer(token_for(BOB)))
    assert r.status_code == 200, r.text
    tasks = r.json()
    assert [t["ref"] for t in tasks] == [f"WEB-{n}" for n in range(1, 9)]
    assert all(t["project_key"] == "WEB" for t in tasks)
    web4 = tasks[3]
    assert web4["assignee"] == {"id": str(uid(BOB)), "email": BOB, "full_name": "Bob Brown"}
    assert tasks[5]["assignee"] is None  # WEB-6 is unassigned
    assert "password_hash" not in web4["assignee"]


def test_list_tasks_as_non_member_is_403(client: TestClient, token_for) -> None:
    assert client.get("/projects/WEB/tasks", headers=bearer(token_for(CAROL))).status_code == 403


def test_list_tasks_filter_by_status(client: TestClient, token_for) -> None:
    r = client.get("/projects/WEB/tasks", params={"status": "done"}, headers=bearer(token_for(BOB)))
    assert [t["ref"] for t in r.json()] == ["WEB-1", "WEB-2"]


def test_list_tasks_filter_by_assignee_id(client: TestClient, token_for) -> None:
    r = client.get(
        "/projects/WEB/tasks", params={"assignee_id": str(uid(BOB))}, headers=bearer(token_for(BOB))
    )
    assert [t["ref"] for t in r.json()] == ["WEB-2", "WEB-3", "WEB-4"]


def test_list_tasks_filter_overdue_uses_today_and_excludes_done(client: TestClient, token_for) -> None:
    """The seed's due dates are relative to a *fixed* day (2026-07-23), so
    they say nothing about "today". Build three tasks around the real clock
    instead: one overdue, one late-but-done, one due tomorrow."""
    alice = bearer(token_for(ALICE))
    assert client.post("/projects", json={"key": "OPS", "name": "Ops"}, headers=alice).status_code == 201
    yesterday, tomorrow = str(date.today() - timedelta(days=1)), str(date.today() + timedelta(days=1))
    for title, due, status in (
        ("late", yesterday, "todo"),
        ("late but finished", yesterday, "done"),
        ("not yet", tomorrow, "todo"),
        ("no date", None, "todo"),
    ):
        r = client.post(
            "/projects/OPS/tasks", json={"title": title, "due_date": due, "status": status}, headers=alice
        )
        assert r.status_code == 201, r.text

    r = client.get("/projects/OPS/tasks", params={"overdue": "true"}, headers=alice)
    assert [t["title"] for t in r.json()] == ["late"]
    # `overdue=false` and "not asked" are the same thing: no filter.
    r = client.get("/projects/OPS/tasks", params={"overdue": "false"}, headers=alice)
    assert len(r.json()) == 4


def test_list_tasks_invalid_status_is_422(client: TestClient, token_for) -> None:
    r = client.get("/projects/WEB/tasks", params={"status": "finished"}, headers=bearer(token_for(BOB)))
    assert r.status_code == 422


# ── Creating ─────────────────────────────────────────────────────────────────


def test_create_task_allocates_next_number_per_project(client: TestClient, token_for) -> None:
    """The counter is per project: WEB is at 8, API at 7."""
    r = client.post("/projects/WEB/tasks", json={"title": "Ninth"}, headers=bearer(token_for(BOB)))
    assert r.status_code == 201, r.text
    assert (r.json()["number"], r.json()["ref"]) == (9, "WEB-9")

    r = client.post("/projects/API/tasks", json={"title": "Eighth"}, headers=bearer(token_for(CAROL)))
    assert r.status_code == 201, r.text
    assert r.json()["ref"] == "API-8"


def test_create_task_defaults_status_todo_priority_medium_and_records_creator(client: TestClient, token_for) -> None:
    r = client.post("/projects/WEB/tasks", json={"title": "Minimal"}, headers=bearer(token_for(BOB)))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "todo"
    assert body["priority"] == "medium"
    assert body["assignee"] is None
    assert body["due_date"] is None
    assert body["created_by"] == str(uid(BOB))
    assert body["created_at"] == body["updated_at"]


def test_create_task_as_non_member_is_403(client: TestClient, token_for) -> None:
    r = client.post("/projects/WEB/tasks", json={"title": "Nope"}, headers=bearer(token_for(CAROL)))
    assert r.status_code == 403, r.text


def test_create_task_with_non_member_assignee_is_409_with_instruction(client: TestClient, token_for) -> None:
    """Carol is a real user but not in WEB. The DB would refuse this via the
    composite FK (a 500); the handler answers first, with what to do."""
    r = client.post(
        "/projects/WEB/tasks",
        json={"title": "For Carol", "assignee_id": str(uid(CAROL))},
        headers=bearer(token_for(ALICE)),
    )
    assert r.status_code == 409, r.text
    assert "POST /projects/WEB/members" in r.json()["detail"]


def test_create_task_with_member_assignee_returns_assignee_object(client: TestClient, token_for) -> None:
    r = client.post(
        "/projects/WEB/tasks",
        json={"title": "For Bob", "assignee_id": str(uid(BOB)), "priority": "high", "due_date": "2026-12-31"},
        headers=bearer(token_for(ALICE)),
    )
    assert r.status_code == 201, r.text
    assert r.json()["assignee"]["email"] == BOB
    assert r.json()["priority"] == "high"
    assert r.json()["due_date"] == "2026-12-31"


def test_create_task_after_deleting_latest_reuses_number(client: TestClient, token_for) -> None:
    """Documents a known limitation, on purpose. `MAX(number) + 1` means
    deleting the newest task frees its number for the next one — an old
    comment saying "WEB-8" may now point at a different task. The fix is a
    counter column on `projects`; not done in phase 3 (see the brief)."""
    alice = bearer(token_for(ALICE))
    assert client.delete("/tasks/WEB-8", headers=alice).status_code == 204
    r = client.post("/projects/WEB/tasks", json={"title": "Reuses 8"}, headers=alice)
    assert r.json()["ref"] == "WEB-8"


def test_create_task_bad_body_is_422(client: TestClient, token_for) -> None:
    for body in ({}, {"title": ""}, {"title": "x", "status": "finished"}, {"title": "x", "due_date": "soon"}):
        r = client.post("/projects/WEB/tasks", json=body, headers=bearer(token_for(BOB)))
        assert r.status_code == 422, (body, r.text)


# ── Detail ───────────────────────────────────────────────────────────────────


def test_get_task_by_ref(client: TestClient, token_for) -> None:
    r = client.get("/tasks/WEB-4", headers=bearer(token_for(BOB)))
    assert r.status_code == 200, r.text
    assert r.json()["title"] == "Task board (drag between columns)"
    assert r.json()["status"] == "in_progress"


def test_get_task_lowercase_key_works(client: TestClient, token_for) -> None:
    """A language model will write `web-4`. The read side uppercases."""
    assert client.get("/tasks/web-4", headers=bearer(token_for(BOB))).status_code == 200


def test_get_task_unknown_number_is_404_with_instruction(client: TestClient, token_for) -> None:
    r = client.get("/tasks/WEB-99", headers=bearer(token_for(BOB)))
    assert r.status_code == 404, r.text
    assert r.json()["detail"].startswith("No task WEB-99")
    assert "GET /projects/WEB/tasks" in r.json()["detail"]


def test_get_task_unknown_project_is_404(client: TestClient, token_for) -> None:
    assert client.get("/tasks/WEBB-1", headers=bearer(token_for(BOB))).status_code == 404


def test_get_task_as_non_member_is_403(client: TestClient, token_for) -> None:
    """A non-member learns nothing about WEB-4 — not even whether it exists.
    Same answer for a number that doesn't exist."""
    assert client.get("/tasks/WEB-4", headers=bearer(token_for(CAROL))).status_code == 403
    assert client.get("/tasks/WEB-99", headers=bearer(token_for(CAROL))).status_code == 403


def test_get_task_non_numeric_number_is_422(client: TestClient, token_for) -> None:
    assert client.get("/tasks/WEB-four", headers=bearer(token_for(BOB))).status_code == 422


def test_get_task_without_token_is_401(client: TestClient, seeded: None) -> None:
    assert client.get("/tasks/WEB-4").status_code == 401


# ── Updating ─────────────────────────────────────────────────────────────────


def test_patch_task_partial_update_leaves_other_fields_alone(client: TestClient, token_for) -> None:
    before = client.get("/tasks/WEB-4", headers=bearer(token_for(BOB))).json()
    r = client.patch("/tasks/WEB-4", json={"status": "in_review"}, headers=bearer(token_for(BOB)))
    assert r.status_code == 200, r.text
    after = r.json()
    assert after["status"] == "in_review"
    for field in ("title", "description", "priority", "assignee", "due_date", "created_at"):
        assert after[field] == before[field], field


def test_patch_task_assignee_null_unassigns_but_absent_keeps(client: TestClient, token_for) -> None:
    """`{"assignee_id": null}` and `{}` must do different things."""
    bob = bearer(token_for(BOB))
    r = client.patch("/tasks/WEB-4", json={"title": "Renamed"}, headers=bob)
    assert r.json()["assignee"]["email"] == BOB  # absent → untouched

    r = client.patch("/tasks/WEB-4", json={"assignee_id": None}, headers=bob)
    assert r.status_code == 200, r.text
    assert r.json()["assignee"] is None  # null → cleared

    r = client.patch("/tasks/WEB-4", json={"due_date": None}, headers=bob)
    assert r.json()["due_date"] is None


def test_patch_task_cannot_null_title_status_or_priority(client: TestClient, token_for) -> None:
    """A task always has these. Null is a 422, not a NOT NULL error."""
    for body in ({"title": None}, {"status": None}, {"priority": None}, {"title": ""}):
        r = client.patch("/tasks/WEB-4", json=body, headers=bearer(token_for(BOB)))
        assert r.status_code == 422, (body, r.text)


def test_patch_task_assign_to_non_member_is_409(client: TestClient, token_for) -> None:
    r = client.patch(
        "/tasks/WEB-4", json={"assignee_id": str(uid(CAROL))}, headers=bearer(token_for(BOB))
    )
    assert r.status_code == 409, r.text
    # Nothing changed.
    assert client.get("/tasks/WEB-4", headers=bearer(token_for(BOB))).json()["assignee"]["email"] == BOB


def test_patch_task_response_shows_new_assignee_not_stale(client: TestClient, token_for) -> None:
    """The bug the first draft had: the relationship was loaded before the
    UPDATE, and the response said Bob after reassigning to Alice."""
    r = client.patch(
        "/tasks/WEB-4", json={"assignee_id": str(uid(ALICE))}, headers=bearer(token_for(BOB))
    )
    assert r.status_code == 200, r.text
    assert r.json()["assignee"]["email"] == ALICE
    assert client.get("/tasks/WEB-4", headers=bearer(token_for(BOB))).json()["assignee"]["email"] == ALICE


def test_patch_task_bumps_updated_at(client: TestClient, token_for) -> None:
    before = client.get("/tasks/WEB-4", headers=bearer(token_for(BOB))).json()
    after = client.patch("/tasks/WEB-4", json={"priority": "low"}, headers=bearer(token_for(BOB))).json()
    assert after["updated_at"] > before["updated_at"]
    assert after["created_at"] == before["created_at"]


def test_patch_task_any_status_transition_is_allowed(client: TestClient, token_for) -> None:
    r = client.patch("/tasks/WEB-1", json={"status": "todo"}, headers=bearer(token_for(BOB)))  # done → todo
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "todo"


def test_patch_task_as_non_member_is_403(client: TestClient, token_for) -> None:
    r = client.patch("/tasks/WEB-4", json={"title": "x"}, headers=bearer(token_for(CAROL)))
    assert r.status_code == 403, r.text


def test_patch_task_invalid_status_is_422(client: TestClient, token_for) -> None:
    r = client.patch("/tasks/WEB-4", json={"status": "finished"}, headers=bearer(token_for(BOB)))
    assert r.status_code == 422


# ── Deleting ─────────────────────────────────────────────────────────────────


def test_delete_task_as_admin_deletes_task_and_its_comments(client: TestClient, token_for, db: Session) -> None:
    """WEB-4 carries two of the seed's four comments."""
    comments_before = db.scalar(select(func.count()).select_from(Comment))
    r = client.delete("/tasks/WEB-4", headers=bearer(token_for(ALICE)))
    assert r.status_code == 204, r.text
    assert r.content == b""
    assert client.get("/tasks/WEB-4", headers=bearer(token_for(ALICE))).status_code == 404
    assert db.scalar(select(func.count()).select_from(Comment)) == comments_before - 2


def test_delete_task_as_member_is_403(client: TestClient, token_for) -> None:
    """THE boundary test. In phase 8 the MCP server will hide `delete_task`
    from members — that's a courtesy. This 403 is the rule, and it holds
    even when a member calls the route directly."""
    r = client.delete("/tasks/WEB-4", headers=bearer(token_for(BOB)))
    assert r.status_code == 403, r.text
    assert r.json()["detail"] == "Only an admin of project 'WEB' can do this"
    assert client.get("/tasks/WEB-4", headers=bearer(token_for(BOB))).status_code == 200


def test_delete_task_as_non_member_is_403(client: TestClient, token_for) -> None:
    assert client.delete("/tasks/WEB-4", headers=bearer(token_for(CAROL))).status_code == 403


def test_delete_unknown_task_is_404(client: TestClient, token_for) -> None:
    assert client.delete("/tasks/WEB-99", headers=bearer(token_for(ALICE))).status_code == 404
