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

    Falls back to the raw string on a JSON decode failure (added for issue
    #319): a tool that raises is caught by the OpenAI Agents SDK's own
    default failure handling (no caller here has ever set
    `failure_error_function=None`) and returned as a plain, human-readable,
    NOT-JSON error string ("An error occurred while running the tool...")
    rather than propagated -- `tests/test_mcp_tool_call_parity.py` is the
    first caller to deliberately exercise that path, and a bare
    `json.loads` would crash on it instead of handing the caller the
    message to inspect.
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
    if not isinstance(raw, str):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return raw


class McpRoutedToolCallTimedOut(TimeoutError):
    """Raised by `invoke_role_mcp_tool` when the NEW `mcp_servers=[server]`-
    routed path (issue #318, `agent/mcp_roles.py`) does not return within
    `timeout_s`. Issue #319 found this is not hypothetical: on native
    Windows, a tool whose implementation shells out to its own subprocess
    (every `run_*_simulation` tool -- NEC2++, openEMS, HFSS, Elmer, Palace,
    MEEP, gprMax, Qucs, LTspice, ngspice, Xyce, gerber2ems -- calls its own
    `subprocess.run()` from inside `mcp_server.server`'s own stdio-transport
    subprocess) never returns at all over this path -- confirmed
    independent of the OpenAI Agents SDK using the raw `mcp` client
    directly (see `tests/test_mcp_tool_call_parity.py`'s module docstring
    for that reproduction): a genuine third-party (`mcp`/`anyio`) Windows
    stdio-transport limitation, not a bug in this repo's own
    `agent/mcp_roles.py` construction. A caller hitting this is not a test
    bug to silence with a longer timeout -- it is the documented finding
    itself. `build_role_mcp_server`'s own `client_session_timeout_seconds=
    None` (issue #319's other fix) means the SDK itself will never time
    this out on its own -- this wrapper's `timeout_s` is the only thing
    bounding a call that would otherwise hang the test suite forever."""


async def _invoke_role_mcp_tool_async(role_key: str, tool_name: str, **kwargs):
    from agents import RunContextWrapper

    from agent.mcp_roles import build_role_agent

    agent = build_role_agent(role_key)
    server = agent.mcp_servers[0]
    async with server:
        run_context = RunContextWrapper(context=None)
        tools = await agent.get_mcp_tools(run_context)
        tool = next(t for t in tools if t.name == tool_name)
        args_json = json.dumps(kwargs)
        ctx = ToolContext(
            context=None,
            tool_name=tool_name,
            tool_call_id="test-call",
            tool_arguments=args_json,
        )
        return await tool.on_invoke_tool(ctx, args_json)


def invoke_role_mcp_tool(
    role_key: str, tool_name: str, *, harness_timeout_s: float = 30.0, **kwargs
):
    """Call a tool through the NEW `mcp_servers=[server]`-routed path built
    in issue #318 (`agent/mcp_roles.py`, ADR-0032) -- the live behavior-
    parity counterpart `invoke_agent_tool` above (the OLD direct-call path)
    issue #319 exists to compare against.

    Reuses `agent.mcp_roles.build_role_agent`'s REAL `Agent` object and its
    REAL `Agent.get_mcp_tools()` (the exact method `Runner.run` calls at
    the start of every turn to gather an agent's tools, confirmed by
    reading `agents/agent.py` directly) rather than hand-rolling the MCP
    tool-listing/conversion machinery a second time, so this genuinely
    exercises the same code path production would -- not an approximation
    of it. Spawns a real `python -m mcp_server.server` subprocess (see
    `agent/mcp_roles.py`'s own docstring for why one per role, not a shared
    connection) for the lifetime of this one call and tears it down again;
    a real Agent session in production connects once and reuses the
    connection across many tool calls within a run, so this per-call
    connect/disconnect overhead is test-harness cost, not part of what's
    being measured for behavioral equivalence -- see
    `tests/test_mcp_tool_call_parity.py`'s latency-sanity check, which
    measures per-call cost separately from one-time connection setup for
    exactly this reason.

    Returns the RAW `on_invoke_tool()` result unchanged -- unlike
    `invoke_agent_tool` above, this does NOT unwrap/JSON-decode it, because
    that shape difference (a bare Python value on the OLD path vs. a
    `{"type": "text", "text": "<json>"}` envelope on the NEW path, or an
    un-parseable plain-English error string on either path) is itself part
    of what issue #319 exists to compare -- decoding it away here would
    hide the finding from every caller. Use `_decode_mcp_tool_output` in
    `tests/test_mcp_tool_call_parity.py` to normalize both sides for a
    value-level comparison once the raw shapes have been inspected.

    Bounded by `harness_timeout_s` (default 30s, keyword-only and
    harness-prefixed deliberately -- several real tools, `run_nec2_
    simulation` included, already have their OWN `timeout_s` parameter
    forwarded through `**kwargs`, and this wrapper's bound must never
    collide with that): raises `McpRoutedToolCallTimedOut` -- not a bare,
    unexplained `asyncio.TimeoutError` -- if the call does not return in
    time, since issue #319 found real, reproducible cases (any tool that
    shells out to its own subprocess) where it never returns at all on
    this platform.
    """
    try:
        return asyncio.run(
            asyncio.wait_for(
                _invoke_role_mcp_tool_async(role_key, tool_name, **kwargs),
                timeout=harness_timeout_s,
            )
        )
    except TimeoutError as exc:
        raise McpRoutedToolCallTimedOut(
            f"{tool_name!r} on role {role_key!r} did not return within "
            f"{harness_timeout_s}s over the MCP-routed path -- see "
            "McpRoutedToolCallTimedOut's own docstring."
        ) from exc


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
