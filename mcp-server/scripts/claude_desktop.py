"""Point Claude Desktop at this server — as a script, not a copy-paste.

    uv run python -m scripts.claude_desktop alice@example.com password
    uv run python -m scripts.claude_desktop alice@example.com password --dry-run

It adds (or replaces) a ``taskflow`` entry under ``mcpServers`` in Claude
Desktop's config file, leaves everything else in the file alone, and keeps a
``.bak`` copy of what was there. Restart Claude Desktop afterwards; the tools
appear under the "search and tools" button in a new chat.

What the entry says, and why each part is the way it is:

- ``command`` is the *absolute* path to ``uv``. Claude Desktop is launched by
  the OS, not by your shell, so it does not have your shell's ``PATH`` and
  a bare ``uv`` would not be found.
- ``--directory <this folder>`` makes ``uv`` run from ``mcp-server/`` so it
  finds the right ``pyproject.toml`` and venv, whatever the app's own
  working directory is.
- ``env`` carries the login. Stdio has no headers to put a token in, so the
  server logs in as you at startup (see ``app/auth.py``). It is your
  password in a file on your disk; that is the honest cost of stdio, and
  phase 6's HTTP transport does not have it.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sys
from pathlib import Path

MCP_DIR = Path(__file__).resolve().parents[1]


def config_path() -> Path:
    """Where Claude Desktop keeps its config, per OS (from its own docs)."""
    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    if system == "Windows":
        return Path(os.environ["APPDATA"]) / "Claude" / "claude_desktop_config.json"
    return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


def server_entry(email: str, password: str) -> dict:
    uv = shutil.which("uv")
    if uv is None:
        sys.exit("uv is not on PATH; install it first (https://docs.astral.sh/uv/).")
    return {
        "command": uv,
        "args": ["--directory", str(MCP_DIR), "run", "python", "-m", "app.server", "--stdio"],
        "env": {"TASKFLOW_EMAIL": email, "TASKFLOW_PASSWORD": password},
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Register the TaskFlow MCP server with Claude Desktop.")
    parser.add_argument("email", help="the TaskFlow account the server should act as")
    parser.add_argument("password")
    parser.add_argument("--dry-run", action="store_true", help="print the entry; change nothing")
    args = parser.parse_args(argv)

    entry = server_entry(args.email, args.password)
    path = config_path()

    if args.dry_run:
        print(json.dumps({"mcpServers": {"taskflow": entry}}, indent=2))
        return

    config = json.loads(path.read_text()) if path.exists() else {}
    if path.exists():
        shutil.copy(path, path.with_suffix(".json.bak"))
    config.setdefault("mcpServers", {})["taskflow"] = entry
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2) + "\n")
    print(f"Wrote mcpServers.taskflow to {path}")
    print("Restart Claude Desktop, open a new chat, and look for the taskflow tools.")


if __name__ == "__main__":
    main()
