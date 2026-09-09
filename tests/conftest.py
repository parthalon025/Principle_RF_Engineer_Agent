from __future__ import annotations

import asyncio
import json
import os
import platform
import stat
import sys
from pathlib import Path

import psycopg
import pytest
from agents.tool_context import ToolContext
from dotenv import load_dotenv

import agent.main as agent_main

load_dotenv()


def make_fake_executable(tmp_path: Path, body: str, name: str = "fake_exe") -> Path:
    """Write `body` (Python source, with NO shebang line of its own) as a
    small stand-in for a real solver/geometry-tool binary, and return a
    path that can be handed straight to `subprocess.run()` as the literal
    executable to launch -- on POSIX *and* on native Windows.

    Every solver-adapter test in this suite fakes out a real binary this
    way, so it can drive the adapter's actual subprocess-invocation code
    (argument shape, exit-code handling, timeouts) without a real solver
    installed. Until issue #159, every one of these test doubles was a
    `#!/bin/sh`-shebang (or `#!{python}`-shebang) script with its
    executable bit set, launched directly as the subprocess target --
    which only ever worked because every environment that had run these
    tests (Linux CI) honors a shebang line for direct execution. Native
    Windows never does, for *any* interpreter: asked to start such a
    script directly, Windows tries to load it as a native PE `.exe` and
    fails with `OSError: [WinError 193] %1 is not a valid Win32
    application` -- regardless of which interpreter the shebang names.

    - On POSIX, this writes `body` behind a `#!{sys.executable}` shebang
      and sets the executable bit, exactly as every one of these fakes did
      before issue #159 -- the OS still resolves the shebang and launches
      it directly. Nothing changes here.
    - On native Windows, this instead writes `body` to a plain `.py` file
      and generates a `.bat` launcher next to it that explicitly invokes
      `sys.executable` on that file, forwarding every argument (`%*`).
      Windows' process launcher (`CreateProcess`) special-cases `.bat`/
      `.cmd` files -- it runs them through `cmd.exe` automatically -- so
      `subprocess.run([returned_path, *args])` launches the wrapper
      directly, with no `shell=True` and no change to any solver adapter's
      own subprocess-invocation code. The wrapper is the only thing that's
      platform-specific; `body` itself is ordinary, portable Python.
    """
    if platform.system() == "Windows":
        script = tmp_path / f"{name}.py"
        script.write_text(body)
        launcher = tmp_path / f"{name}.bat"
        launcher.write_text(f'@echo off\r\n"{sys.executable}" "{script}" %*\r\n')
        return launcher
    else:
        script = tmp_path / name
        script.write_text(f"#!{sys.executable}\n" + body)
        script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        return script


def invoke_agent_tool(tool_name: str, **kwargs):
    """Call an `agent/main.py` `@function_tool`-wrapped tool through the real
    `agents.tool.FunctionTool.on_invoke_tool` machinery, and return its
    (JSON-decoded) result.

    `@function_tool` wraps the original function into a non-callable `Tool`
    object -- a plain `agent_main.<tool_name>(...)` call is not available to
    test at all, and even if it were, a plain Python call would trivially
    pass even if the SDK's own JSON-schema generation had silently stripped
    a parameter the wrapper's signature added (exactly the issue #287/#317
    bug class this exists to catch: a wrapper param present in the source
    but absent from the schema the agent runtime actually offers).

    Originally three near-identical copies of this helper (differing only in
    the hardcoded tool name) lived one-per-file in tests/
    test_ltspice_agent_wiring.py (the pattern's origin, issue #287),
    tests/test_elmer_agent_wiring.py, and
    tests/test_freecad_curved_agent_wiring.py (both issue #317). Code review
    of #317 flagged that duplication (Fowler: Duplicated Code) and it moved
    here so a fourth wiring-regression test doesn't grow a fourth copy.
    """
    all_tools = (t for role in agent_main.ROLES.values() for t in role.tools)
    tool = next(t for t in all_tools if t.name == tool_name)
    args_json = json.dumps(kwargs)
    ctx = ToolContext(
        context=None,
        tool_name=tool_name,
        tool_call_id="test-call",
        tool_arguments=args_json,
    )
    raw = asyncio.run(tool.on_invoke_tool(ctx, args_json))
    return json.loads(raw) if isinstance(raw, str) else raw


@pytest.fixture
def db_conn():
    """A real connection to the local Postgres, wrapped in a transaction
    that's rolled back on teardown so tests never leave data behind.

    Matches tests/test_touchstone.py's real-I/O-not-mocked philosophy,
    applied to the database instead of the filesystem.
    """
    conn = psycopg.connect(os.environ["DATABASE_URL"])
    try:
        yield conn
    finally:
        conn.rollback()
        conn.close()
