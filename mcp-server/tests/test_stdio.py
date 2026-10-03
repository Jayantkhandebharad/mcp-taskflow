"""Phase 5: the first two tools, over stdio, as a real client sees them.

Three things these tests prove, each of which a mock would have let us fake:

1. the server speaks clean MCP over stdin/stdout — if anything but protocol
   reached stdout, the SDK's client would fail to parse it and every test
   here would fail;
2. the token rides along — ``whoami`` and ``list_projects`` answer *as the
   person whose login the launcher supplied*, and only with what that person
   may see;
3. startup failures are sentences, not tracebacks.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from tests.conftest import ALICE, BOB, MCP_DIR, server_env


def test_tools_list_is_exactly_the_phase_5_pair(as_user):
    tools = as_user(ALICE).tools()
    assert sorted(t.name for t in tools) == ["list_projects", "whoami"]
    for tool in tools:
        # The description is the docstring; a model needs it to choose.
        assert tool.description and "Use this" in tool.description
        # A structured result is advertised, so a client can rely on the shape.
        assert tool.output_schema is not None


def test_whoami_is_the_person_in_the_launcher_env(as_user):
    result = as_user(ALICE).call("whoami")
    assert result.is_error is False
    assert result.structured_content == {"email": ALICE, "full_name": "Alice Adams"}
    # The text block is what a client without structured-output support shows.
    assert "Alice Adams" in result.content[0].text


def test_list_projects_is_scoped_by_the_token(as_user):
    """The whole design in one assertion: Alice's AI sees what Alice sees, and
    Bob's sees less. The MCP server didn't check anything — the backend did,
    from the token each server process logged in with."""
    alice = as_user(ALICE).call("list_projects").structured_content["result"]
    assert [(p["key"], p["my_role"]) for p in alice] == [("API", "admin"), ("WEB", "admin")]
    assert alice[1]["name"] == "TaskFlow Web"

    bob = as_user(BOB).call("list_projects").structured_content["result"]
    assert [(p["key"], p["my_role"]) for p in bob] == [("WEB", "member")]


def test_project_rows_carry_no_uuids(as_user):
    """PLAN.md §8 rule 1: tools speak in keys and emails, never ids. The
    backend's body has ``id`` and ``created_by``; the tool's must not."""
    rows = as_user(ALICE).call("list_projects").structured_content["result"]
    assert set(rows[0]) == {"key", "name", "description", "my_role"}


@pytest.mark.parametrize(
    ("env_override", "expected"),
    [
        ({"TASKFLOW_PASSWORD": "wrong"}, "Invalid email or password"),
        ({"TASKFLOW_EMAIL": None}, "needs TASKFLOW_EMAIL and TASKFLOW_PASSWORD"),
        ({"BACKEND_URL": "http://127.0.0.1:9"}, "is not reachable"),
    ],
    ids=["wrong-password", "no-login-configured", "backend-down"],
)
def test_startup_failures_are_sentences_on_stderr(backend_url, env_override, expected):
    """A desktop client shows a server that exits at startup in its log.
    What it shows must tell the reader what to fix — and must not be on
    stdout, which is reserved for protocol."""
    env = server_env(backend_url, ALICE)
    for key, value in env_override.items():
        if value is None:
            env.pop(key)
        else:
            env[key] = value
    proc = subprocess.run(
        [sys.executable, "-m", "app.server", "--stdio"], cwd=MCP_DIR, env=env, capture_output=True, text=True, timeout=60
    )
    assert proc.returncode == 1
    assert expected in proc.stderr
    assert proc.stdout == ""
