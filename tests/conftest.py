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
from agents import RunContextWrapper
from agents.tool_context import ToolContext
from dotenv import load_dotenv

import agent.main as agent_main
from agent.mcp_roles import build_role_agent
from knowledge import extraction

load_dotenv()


# A minimal center-fed half-wave dipole `run_nec2_simulation`/
# `generate_nec2_deck` geometry dict -- one wire, 7 segments, resonant near
# 300 MHz. Shared here (issue #319 code review: this was a byte-for-byte
# copy between tests/test_nec2pp.py and tests/test_mcp_tool_call_parity.py
# -- the exact pattern this file's own invoke_agent_tool docstring already
# names as a smell it moved here to avoid, Fowler: Duplicated Code) so a
# third NEC2-geometry-needing test file reuses this constant instead of
# retyping it.
DIPOLE_GEOMETRY = {
    "wires": [
        {
            "tag": 1,
            "segments": 7,
            "x1_m": 0.0,
            "y1_m": 0.0,
            "z1_m": -0.25,
            "x2_m": 0.0,
            "y2_m": 0.0,
            "z2_m": 0.25,
            "radius_m": 0.001,
        }
    ],
}


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


def write_pdf(path: Path, lines: list[str]) -> None:
    """Hand-rolled minimal single-page PDF with the given text lines -- no
    third-party PDF-authoring library is a project dependency, so this
    writes the raw PDF object structure directly.

    Moved here from tests/test_ingest.py (issue #458 code review: a third
    near-identical copy of this exact helper was about to be added for a
    new cross-module round-trip test, on top of the two -- tests/
    test_ingest.py and tests/test_read.py -- that already existed;
    tests/test_read.py's own copy already carried a comment noting it
    "mirrors tests/test_ingest.py's helper" rather than importing it. Same
    Fowler: Duplicated Code smell this file's own `invoke_agent_tool`
    docstring already names for a different helper, fixed the same way:
    one copy here, imported by every test file that needs a real (not
    mocked) PDF to ingest."""
    content = "BT /F1 14 Tf 72 700 Td 16 TL\n"
    for line in lines:
        esc = line.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
        content += f"({esc}) Tj T*\n"
    content += "ET"
    content_bytes = content.encode("latin-1")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> "
            b"/MediaBox [0 0 612 792] /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        (
            f"<< /Length {len(content_bytes)} >>\nstream\n".encode("latin-1")
            + content_bytes
            + b"\nendstream"
        ),
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode("latin-1") + obj + b"\nendobj\n"

    xref_offset = len(out)
    n = len(objects) + 1
    out += f"xref\n0 {n}\n".encode("latin-1")
    out += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        out += f"{off:010d} 00000 n \n".encode("latin-1")
    out += (f"trailer\n<< /Size {n} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF").encode(
        "latin-1"
    )

    path.write_bytes(bytes(out))


def extraction_error(document_id: int) -> str | None:
    """Fetch the captured extraction-error text for a document, for use in
    assertion-failure messages -- so a red `extraction_status` check shows
    *why* parsing failed (per issue #141) instead of just a bare status
    mismatch. `ingest_document`'s return value doesn't carry this text (only
    the stored row's metadata does), so this is a small direct DB read.

    Moved here from tests/test_ingest.py alongside `write_pdf` (issue #458)
    -- tests/test_read.py had an identical copy of this one too."""
    conn = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT metadata->>'extraction_error' FROM documents WHERE id = %s",
                (document_id,),
            )
            row = cur.fetchone()
            return row[0] if row else None
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def _isolated_solver_artifacts_dir(tmp_path, monkeypatch):
    """Issue #466: `simulation.base.new_solver_workdir`'s default directory
    lives inside the repository tree ON PURPOSE -- that is what makes it
    durable across a container restart (the whole repo is bind-mounted in
    docker-compose.yml's `app` service). That same durability is exactly
    the hazard in a test run: any test that calls `run_palace_simulation`/
    `run_meep_simulation` (or `MeepSimulator.run`) without an explicit
    `workdir` would otherwise leave real, uncommitted directories behind in
    THIS checkout every time the suite runs. Redirecting
    `SOLVER_ARTIFACTS_DIR` to pytest's own per-test `tmp_path` keeps the
    default-path behaviour genuinely exercised (a test can still assert
    against it) without ever writing into the real repository. Autouse:
    every test gets this for free, with no per-file import needed, the same
    way `no_ocr`'s neighbours below opt individual tests INTO a patch --
    this one is a blanket safety net instead, since forgetting it is a
    filesystem-pollution bug rather than a test-correctness one."""
    monkeypatch.setenv("SOLVER_ARTIFACTS_DIR", str(tmp_path / "solver_artifacts"))


@pytest.fixture
def no_ocr(monkeypatch):
    """Forces `ingest_document`'s internal `parse_document` call to run with
    OCR (image-to-text) switched off, for tests whose fixture PDF already
    has a real, selectable text layer and never needs it.

    Patches the `parse_document` name as looked up inside `knowledge.ingest`
    (not `knowledge.extraction`'s own default) so this is scoped to the
    tests that opt into it -- `parse_document`'s own default (`do_ocr=True`)
    is untouched, so any other caller (real ingestion of a scanned document)
    still gets OCR by default (issue #141).

    A pytest fixture, unlike `write_pdf`/`extraction_error` above: living in
    conftest.py already makes it available to every test file by name, with
    no import needed -- moved here from tests/test_ingest.py (issue #458),
    which had the same fixture duplicated (byte for byte) in
    tests/test_read.py."""
    monkeypatch.setattr(
        "knowledge.ingest.parse_document",
        lambda path: extraction.parse_document(path, do_ocr=False),
    )


@pytest.fixture
def cleanup_documents():
    """Tracks document ids created by ingest_document (which commits its
    own connection) and deletes them afterward -- unlike knowledge/db.py's
    tests, this can't rely on a rolled-back transaction for isolation.

    Deletes one row at a time in REVERSED (LIFO) append order, not a single
    bulk `WHERE id = ANY(%s)` statement -- a later-appended document can
    reference an earlier one via supersedes_document_id (self-referential
    FK), and a single bulk DELETE gives Postgres no row-order guarantee, so
    it can (and did, in practice: ForeignKeyViolation on
    documents_supersedes_document_id_fkey) try to delete the referenced row
    before the referencing one. Deleting newest-first always clears any such
    reference before reaching the row it points to.

    Moved here from tests/test_ingest.py alongside `no_ocr` (issue #458),
    for the same reason: tests/test_read.py already had an identical copy."""
    ids: list[int] = []
    yield ids
    if not ids:
        return
    conn = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)
    try:
        with conn.cursor() as cur:
            for doc_id in reversed(ids):
                cur.execute("DELETE FROM documents WHERE id = %s", (doc_id,))
    finally:
        conn.close()


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
    `harness_timeout_s`. This is not a hypothetical bound: every tool that
    shells out to its own subprocess deadlocked permanently over this path
    on native Windows until `mcp_server.server.isolate_transport_stdin()`
    landed (see `tests/test_mcp_tool_call_parity.py`'s module docstring for
    what the deadlock actually was, and for how it was mis-diagnosed twice
    before that). A caller hitting this today is reporting a regression of
    that class, not a test that needs a longer timeout.

    `build_role_mcp_server`'s own `client_session_timeout_seconds=None`
    (issue #319's other fix) means the SDK itself will never time a call
    out -- this wrapper's bound is the only thing standing between a stuck
    call and a test suite that never finishes."""


async def _invoke_role_mcp_tool_async(role_key: str, tool_name: str, **kwargs):
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
    time, because a whole class of tools once did not return at all here
    (see that exception's own docstring).
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
