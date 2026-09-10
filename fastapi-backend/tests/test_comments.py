"""Tests for ``/tasks/{key}-{number}/comments`` — through HTTP, on the seed.

WEB-4 has two seeded comments (Alice, then Bob). Each test is named for
the bug it catches.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import ALICE, BOB, CAROL, bearer, uid


def test_list_comments_in_created_order_with_author(client: TestClient, token_for) -> None:
    r = client.get("/tasks/WEB-4/comments", headers=bearer(token_for(BOB)))
    assert r.status_code == 200, r.text
    comments = r.json()
    assert [c["author"]["email"] for c in comments] == [ALICE, BOB]
    assert comments[0]["author"]["full_name"] == "Alice Adams"
    assert comments[0]["created_at"] <= comments[1]["created_at"]
    assert "password_hash" not in comments[0]["author"]


def test_add_comment_as_member_returns_author(client: TestClient, token_for) -> None:
    r = client.post(
        "/tasks/WEB-4/comments", json={"body": "On it."}, headers=bearer(token_for(BOB))
    )
    assert r.status_code == 201, r.text
    assert r.json()["body"] == "On it."
    assert r.json()["author"]["id"] == str(uid(BOB))
    # It's there for the next reader, at the end.
    r = client.get("/tasks/WEB-4/comments", headers=bearer(token_for(ALICE)))
    assert [c["body"] for c in r.json()][-1] == "On it."


def test_add_comment_as_non_member_is_403(client: TestClient, token_for) -> None:
    r = client.post("/tasks/WEB-4/comments", json={"body": "hi"}, headers=bearer(token_for(CAROL)))
    assert r.status_code == 403, r.text
    assert client.get("/tasks/WEB-4/comments", headers=bearer(token_for(CAROL))).status_code == 403


def test_add_comment_empty_body_is_422(client: TestClient, token_for) -> None:
    r = client.post("/tasks/WEB-4/comments", json={"body": ""}, headers=bearer(token_for(BOB)))
    assert r.status_code == 422


def test_comments_on_unknown_task_is_404(client: TestClient, token_for) -> None:
    assert client.get("/tasks/WEB-99/comments", headers=bearer(token_for(BOB))).status_code == 404
    r = client.post("/tasks/WEB-99/comments", json={"body": "?"}, headers=bearer(token_for(BOB)))
    assert r.status_code == 404
