"""Issue #319 (ADR-0032's own Verify phase, blocked by #318 -- both merged
before this ticket started): originally a live behavior-parity check between
the OLD direct-call path (`agent/main.py`'s hand-built `@function_tool`/
`ROLES` construction, invoked via a since-removed `conftest.invoke_agent_tool`
helper) and the NEW `mcp_servers=[server]`-routed path (`agent/mcp_roles.py`,
issue #318, invoked via `conftest.invoke_role_mcp_tool`) -- the two
constructions ADR-0032 said must be proven equivalent (or have every
difference named plainly) before a later "contract" ticket was allowed to
delete the OLD path.

Issue #573 was that later ticket: `agent/main.py`'s `@function_tool` wrapper
layer is now deleted in full (all six roles reach every tool over MCP alone),
so there is no more OLD path left to compare against. The parity checks below
were rewritten to exercise the NEW path alone -- the comparison they existed
to make is complete, not lost; see this file's git history for the actual
OLD-vs-NEW comparisons they replace, and `agent/mcp_roles.py`'s own module
docstring for the standing summary of what that comparison found. What
remains here is real regression coverage in its own right: the NEW path's
returned values, error-surfacing shape, and per-call latency, plus (below)
the raw-protocol regression guard for finding 3.

THREE FINDINGS CAME OUT OF BUILDING THIS CHECK ORIGINALLY -- two were fixed
directly in `agent/mcp_roles.py` (since they made the harness this ticket
needed unusable, not merely a comparison result), one is a genuine,
documented limitation this file's own tests captured on purpose rather than
silently avoiding, and is now fully fixed (see point 3 below):

1. FIXED -- `build_role_mcp_server` never set `env`, so the spawned
   subprocess got only a small OS-safe env allowlist (confirmed directly
   against `mcp/client/stdio/__init__.py`'s `get_default_environment()`),
   missing `DATABASE_URL` and everything else this repo's tools read from
   the environment. Every DB-touching tool would have failed inside the
   subprocess with a bare `KeyError`, for a reason unrelated to MCP
   routing. See `agent/mcp_roles.py`'s own docstring and
   `tests/test_mcp_roles.py::test_build_role_mcp_server_passes_the_parent_
   process_environment_through`.

2. FIXED -- `MCPServerStdio`'s own default `client_session_timeout_seconds`
   is 5 (confirmed against the installed SDK), so ANY tool call still
   running after 5 seconds was aborted client-side with "Timed out while
   waiting for response to ClientRequest", regardless of the tool's own
   `timeout_s` argument -- this repo's real EM/circuit solvers default
   `timeout_s` to 600-3600 seconds specifically because real solves take
   that long, so EVERY one of them would have silently failed the instant
   a real solve took more than 5 seconds. See `agent/mcp_roles.py`'s own
   docstring and `tests/test_mcp_roles.py::test_build_role_mcp_server_
   disables_the_default_five_second_client_session_timeout`.

3. FIXED HERE, AFTER BEING MIS-ROOT-CAUSED ONCE -- on native Windows, a
   tool whose implementation shells out to its OWN subprocess (every
   `run_*_simulation` tool, plus `generate_freecad_curved_geometry`,
   `ingest_arxiv_paper` and `ingest_patent`) never returned AT ALL over
   the MCP-routed path -- not slow, not merely past the old 5s timeout,
   but permanently deadlocked -- even though the SAME call over the OLD
   path succeeded normally, in well under a second on top of the tool's
   own real work.

   The cause is not the one this file, `docs/adr/0032-tool-registration-
   consolidates-onto-the-mcp-server.md` and the tickets around them
   recorded for months. That reading blamed FastMCP dispatching a
   synchronous tool function on its own event-loop thread with no
   `anyio.to_thread` wrapping. Measured directly against a stripped-down
   FastMCP server, that explanation does not survive: a sync tool that
   merely sleeps blocks the event loop exactly as hard and returns fine,
   and wrapping the subprocess call in `anyio.to_thread.run_sync` does NOT
   lift the deadlock. Blocking the event loop was never the problem.

   What is: the child process inherits the server's standard input, which
   is the pipe the MCP protocol itself arrives on. A Windows anonymous
   pipe is a synchronous file object, and the kernel serializes every
   operation on it behind whatever read is already in flight -- and this
   server always has a read in flight, because that is how it waits for
   the next request. CPython asks its own standard handles what kind of
   file they are while starting up, so the child stops there, before its
   first line of Python, until the server receives another message; the
   server cannot receive one until the child it is waiting on finishes.
   Isolated with no `mcp` package involved at all: a parent blocked
   reading a pipe stdin, spawning a child that inherits it, reproduces
   the freeze exactly; passing `stdin=subprocess.DEVNULL` clears it; a
   `cmd.exe` child (which never queries the handle) is unaffected either
   way, which is why the deadlock looks Python-specific and why POSIX,
   with no such per-handle serialization, never showed it at all.

   `mcp_server/server.py`'s `isolate_transport_stdin()` fixes it at the
   one place that owns the problem: the server keeps a private handle for
   the transport and leaves the null device in the slot children inherit.
   That covers every tool at once -- including any added later -- rather
   than 15-odd call sites that would drift apart.

Every test below is still bounded (`conftest.invoke_role_mcp_tool`'s own
`harness_timeout_s`, default 30s) rather than left to hang indefinitely if
this regresses -- matching this repo's own "warn, never block" principle
applied to its own test suite. The tests that used to branch on platform
and assert the hang now run the SAME real value-level check everywhere, and
`test_raw_mcp_sdk_completes_a_subprocess_shelling_tool` (no Agents SDK import
at all, so a failure there points at the server process rather than at this
repo's `agent/mcp_roles.py` or the SDK's conversion layer) is the regression
guard for the fix itself.
"""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

import numpy as np
import pytest
import skrf as rf
from conftest import DIPOLE_GEOMETRY, invoke_role_mcp_tool, make_fake_executable

from orchestration.design_loop import start_design_loop
from orchestration.tooling import inspect_design_loop_state as _inspect_design_loop_state


def _decode_mcp_tool_output(raw):
    """Normalize a NEW-path `on_invoke_tool()` return value for a VALUE-
    level comparison against the OLD path's native Python return value.
    `MCPUtil.invoke_mcp_tool` (`agents/mcp/util.py`, read directly) wraps a
    single text content item as a bare `{"type": "text", "text": ...}`
    dict rather than returning agent/main.py's own native Python value --
    that SHAPE difference is itself one of this file's findings (see the
    module docstring), so callers that want to inspect the raw shape read
    `on_invoke_tool()`'s result directly and only call this helper once
    they're ready to compare decoded VALUES. Falls back to the original
    string on a JSON decode failure (a human-readable, non-JSON error
    message is a real, correctly-observed case here -- see the error-
    surfacing tests below -- not a bug in this helper)."""
    if isinstance(raw, dict) and raw.get("type") == "text" and "text" in raw:
        raw = raw["text"]
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return raw
    return raw


# ---------------------------------------------------------------------------
# AC1 (issue #319; the OLD-path comparison itself completed by issue #573):
# a representative sample spanning a plain-schema tool, a strict_mode=False
# geometry/circuit-dict tool, and a strict_mode=False design-loop-state tool,
# now exercised over the NEW path alone.
# ---------------------------------------------------------------------------


def _make_touchstone_file() -> str:
    """Mirrors `tests/test_calculation_tool_recording.py`'s helper of the
    same name/shape exactly -- a real, tiny 2-port .s2p file on disk, not a
    hand-built dict, so `analyze_touchstone_file` exercises its actual
    skrf.Network file-reading path."""
    tmp_dir = Path(tempfile.mkdtemp())
    f = rf.Frequency(1, 3, 3, unit="ghz")
    s = np.zeros((3, 2, 2), dtype=complex)
    s[:, 0, 0] = 10 ** (-20 / 20)
    s[:, 1, 0] = 10 ** (-3 / 20)
    ntwk = rf.Network(frequency=f, s=s, z0=50)
    path = tmp_dir / "parity_fixture.s2p"
    ntwk.write_touchstone(path.with_suffix(""))
    return str(path)


def test_plain_schema_simulator_tool_returns_the_analyzed_result():
    """analyze_touchstone_file: AC1's "plain-schema simulator tool" bucket
    -- plain-schema (strict_mode default True; `path`/`design_id` are a
    `str`/`int | None`, no free-form dict), and squarely in the simulator/
    measurement domain (a real .s2p network-parameter file, the kind of
    output NEC2++/openEMS/HFSS/a real bench measurement all produce), on
    the "microwave"/"antenna"/"test" roles. No `design_id` here, so no
    database write to check either -- see the error-surfacing test below for
    this same tool's failure path."""
    path = _make_touchstone_file()

    new_raw = invoke_role_mcp_tool("microwave", "analyze_touchstone_file", path=path)

    assert isinstance(new_raw, dict) and new_raw.get("type") == "text"
    result = _decode_mcp_tool_output(new_raw)
    assert result["ports"] == 2
    assert result["provenance"] == "CALCULATED"


def test_plain_schema_tool_returns_the_computed_value():
    """calculate_wavelength: a second, minimal plain-schema (strict_mode
    default True) example, on the "systems" role. The NEW path returns a
    JSON-encoded string wrapped in a `{"type": "text", ...}` envelope, not a
    bare Python float -- kept alongside analyze_touchstone_file above (this
    file's canonical "plain-schema simulator tool" per AC1) because it shows
    the wrapped-scalar shape most crisply."""
    new_raw = invoke_role_mcp_tool("systems", "calculate_wavelength", frequency_hz=1e9)

    assert new_raw == {"type": "text", "text": "0.299792458"}
    assert _decode_mcp_tool_output(new_raw) == pytest.approx(0.299792458)


def test_design_loop_state_tool_works_over_the_new_path(tmp_path: Path):
    """inspect_design_loop_state: a strict_mode=False tool (its `state`
    param is a free-form dict) on the "principal" role.

    Built with no `design_id` (orchestration.design_loop.start_design_loop
    is the pure, no-database constructor `start_new_design_loop`/
    `start_design_loop`'s tool wrapper itself calls after creating a real
    `designs` row -- calling it directly here keeps this check database-free,
    matching the tool's own documented "without a design_id, this never
    touches the database" behavior)."""
    state = start_design_loop({"gain_dbi": {"threshold": 5.0, "unit": "dBi"}}).to_dict()

    new_raw = invoke_role_mcp_tool("principal", "inspect_design_loop_state", state=state)

    assert isinstance(new_raw, dict) and new_raw.get("type") == "text"
    assert _decode_mcp_tool_output(new_raw) == _inspect_design_loop_state(state)


def _write_fake_nec2pp_exit_0(tmp_path: Path) -> Path:
    body = "import sys\nsys.exit(0)\n"
    return make_fake_executable(tmp_path, body, name="fast_nec2pp")


def test_geometry_dict_tool_completes_over_the_new_path(tmp_path, monkeypatch):
    """run_nec2_simulation: a strict_mode=False tool (its `geometry` param
    is a free-form dict) on the "antenna" role, which shells out to a real
    subprocess (`simulation.nec2pp.Nec2ppSimulator.run`'s own
    `subprocess.run()` call against whatever `NEC2PP_BIN` names -- faked out
    here exactly as `tests/test_nec2pp.py` already does, per this repo's own
    solver-adapter-test convention).

    This is AC1's "strict_mode=False geometry/circuit-dict tool" bucket, and
    it is also the concrete case behind finding 3 in this file's module
    docstring: a call that used to deadlock forever on native Windows because
    the faked "solver" inherited the server's own protocol pipe as its
    standard input. It completes now, with the value this ticket originally
    wanted compared against the OLD path -- see
    `test_raw_mcp_sdk_completes_a_subprocess_shelling_tool` below for the
    same regression guard with no Agents SDK involved at all."""
    script = _write_fake_nec2pp_exit_0(tmp_path)
    monkeypatch.setenv("NEC2PP_BIN", str(script))

    new_raw = invoke_role_mcp_tool(
        "antenna",
        "run_nec2_simulation",
        harness_timeout_s=20,
        geometry=DIPOLE_GEOMETRY,
        frequency_hz=300e6,
        timeout_s=10,
    )
    assert isinstance(new_raw, dict) and new_raw.get("type") == "text"
    new_result = _decode_mcp_tool_output(new_raw)
    assert new_result["provenance"] == "SIMULATED"
    assert new_result["status"] == "COMPLETED"


# ---------------------------------------------------------------------------
# AC2 (issue #319): error-surfacing behavior, for a tool that can genuinely
# raise. Split into two cases -- a clean, non-subprocess exception and the
# subprocess-based SimulatorError case -- because for as long as finding 3's
# deadlock stood, only the first could answer ADR-0032's "isError=true text
# result, not a raised Python exception" question at all. Both now run over
# the NEW path alone (issue #573 deleted the OLD one): a server-side
# exception becomes an `isError=true` text result -- FastMCP's own "Error
# executing tool <name>: ..." (`mcp/server/fastmcp/tools/base.py`'s
# `ToolError` message) wrapped in the same `{"type": "text", "text": ...}`
# envelope as every other NEW-path result -- not a raised Python exception a
# caller could catch by type.
# ---------------------------------------------------------------------------


def test_error_surfacing_for_a_clean_non_subprocess_exception():
    """analyze_touchstone_file with a nonexistent path: rf_tools.touchstone.
    analyze_touchstone raises a plain `FileNotFoundError`, no subprocess
    involved, so this completes even before finding 3's fix (unlike the
    geometry/circuit-dict case below)."""
    bad_path = "C:/this/path/does/not/exist/on/purpose.s2p"

    new_raw = invoke_role_mcp_tool("microwave", "analyze_touchstone_file", path=bad_path)

    assert isinstance(new_raw, dict) and new_raw.get("type") == "text"
    assert new_raw["text"] == f"Error executing tool analyze_touchstone_file: {bad_path}"
    assert bad_path in new_raw["text"]


def _write_fake_nec2pp_exit_1(tmp_path: Path) -> Path:
    body = 'import sys\nsys.stderr.write("boom: bad geometry card\\n")\nsys.exit(1)\n'
    return make_fake_executable(tmp_path, body, name="failing_nec2pp")


def test_error_surfacing_for_a_genuine_simulator_error(tmp_path, monkeypatch):
    """run_nec2_simulation with a fake solver that fails (nonzero exit) --
    the concrete `SimulatorError` scenario ADR-0032's acceptance criteria
    names by example. `simulation.nec2pp.Nec2ppSimulator.run` raises
    `SimulatorError(f"NEC2++ failed ({code}): {stderr}")`, exercised here
    exactly as `tests/test_nec2pp.py::test_run_nec2_simulation_propagates_
    simulator_error_on_failure` already does for the underlying function.

    ADR-0032's error-surfacing question went unanswered for this whole tool
    category while the deadlock in this file's finding 3 preempted it: the
    call never returned, error or otherwise. With that fixed (and the OLD
    path since deleted by issue #573), this is the same answer
    `test_error_surfacing_for_a_clean_non_subprocess_exception` above gives
    -- a plain text result carrying the failure detail, not a raised,
    catchable-by-type exception."""
    script = _write_fake_nec2pp_exit_1(tmp_path)
    monkeypatch.setenv("NEC2PP_BIN", str(script))

    new_raw = invoke_role_mcp_tool(
        "antenna",
        "run_nec2_simulation",
        harness_timeout_s=20,
        geometry=DIPOLE_GEOMETRY,
        frequency_hz=300e6,
        timeout_s=10,
    )
    assert isinstance(new_raw, dict) and new_raw.get("type") == "text"
    assert "NEC2++ failed (1)" in new_raw["text"]
    assert "boom: bad geometry card" in new_raw["text"]


# ---------------------------------------------------------------------------
# AC3 (issue #319): latency class sanity check -- NOT a formal benchmark,
# just enough to catch a per-call cost that looks like a hang rather than a
# transport hop. Originally an OLD-vs-NEW ratio bound; issue #573 deleted the
# OLD path, so this is now an absolute sanity bound on the NEW path alone.
# ---------------------------------------------------------------------------


def test_latency_sanity_new_path_per_call_cost_is_not_a_gross_regression():
    """Per-call cost only -- deliberately excludes the one-time subprocess
    connect+list_tools cost (measured and reported separately below,
    unasserted): a real Agent session in production connects one
    MCPServerStdio per role ONCE and reuses it for every tool call within
    that run (see agent/mcp_roles.py's own docstring), so the one-time
    setup cost is amortized across a whole session, not paid per call --
    asserting a tight bound on it here would be sanity-checking the wrong
    thing. What actually matters is the cost of each individual call once
    connected, which this measures directly by re-using ONE connection
    across N calls, mirroring real usage.

    The bound is deliberately generous (sanity, not a formal benchmark, per
    the ticket's own wording) -- this only needs to catch a call that looks
    like a hang, not to hold this repo to a strict SLA on a shared,
    variably-loaded CI/dev machine."""
    import asyncio

    from agents import RunContextWrapper
    from agents.tool_context import ToolContext

    from agent.mcp_roles import build_role_agent

    n_calls = 5

    async def _measure_new_path():
        agent = build_role_agent("systems")
        server = agent.mcp_servers[0]
        connect_start = time.perf_counter()
        async with server:
            connect_s = time.perf_counter() - connect_start
            run_context = RunContextWrapper(context=None)
            tools = await agent.get_mcp_tools(run_context)
            tool = next(t for t in tools if t.name == "calculate_wavelength")
            args_json = json.dumps({"frequency_hz": 1e9})
            ctx = ToolContext(
                context=None,
                tool_name="calculate_wavelength",
                tool_call_id="test-call",
                tool_arguments=args_json,
            )
            call_start = time.perf_counter()
            for _ in range(n_calls):
                await tool.on_invoke_tool(ctx, args_json)
            per_call_s = (time.perf_counter() - call_start) / n_calls
        return connect_s, per_call_s

    connect_s, new_per_call_s = asyncio.run(_measure_new_path())

    print(
        f"\nlatency sanity: NEW per-call={new_per_call_s * 1000:.2f}ms, "
        f"NEW one-time connect+list_tools={connect_s * 1000:.1f}ms (unasserted, "
        "amortized across a session in real usage)"
    )

    # A sanity threshold, not a benchmark: catch a call that looks like a
    # hang, not a normal, expected stdio JSON-RPC round trip cost.
    assert new_per_call_s < 2.0, (
        f"NEW path per-call cost {new_per_call_s:.3f}s looks like a hang, not overhead"
    )


# ---------------------------------------------------------------------------
# Regression guard for finding 3 (module docstring), through the raw `mcp`
# package's own client with NO OpenAI Agents SDK import at all -- so a
# failure here points at the spawned server process itself rather than at
# agent/mcp_roles.py's construction or the Agents SDK's MCPUtil conversion
# layer. Bounded rather than left to hang if the fix ever regresses.
# ---------------------------------------------------------------------------


def test_raw_mcp_sdk_completes_a_subprocess_shelling_tool(tmp_path, monkeypatch):
    """Calls a tool that shells out to its own subprocess against the exact
    same `python -m mcp_server.server` process a real session talks to,
    using ONLY the `mcp` package's own `stdio_client`/`ClientSession` -- no
    `agents` import anywhere in this test. `read_timeout_seconds=None`
    mirrors `agent/mcp_roles.py`'s own `client_session_timeout_seconds=None`
    (finding 2 in this file's module docstring), so nothing client-side is
    bounding the call: what this asserts is that the server answers, not
    that some timeout is generous enough.

    This is where the deadlock in finding 3 would resurface if
    `mcp_server.server.isolate_transport_stdin()` were dropped, moved after
    the server starts serving, or stopped covering a newly added tool that
    spawns a process some other way. The bound below exists so that
    regression shows up as one failing test in a normal run rather than a
    suite that never finishes.

    The `asyncio.wait_for` bound is caught INSIDE the two `async with`
    blocks, not around them: cancelling `session.call_tool()` mid-flight
    leaves the stdio reader/writer task group in a state where exiting
    `stdio_client`'s own `async with` afterward can itself raise an
    `anyio.BrokenResourceError` wrapped in an `ExceptionGroup`, which would
    otherwise mask the plain assertion failure this test wants to report."""
    import asyncio
    import contextlib
    import os
    import sys

    from anyio import BrokenResourceError
    from mcp import ClientSession, StdioServerParameters, stdio_client

    script = _write_fake_nec2pp_exit_0(tmp_path)
    monkeypatch.setenv("NEC2PP_BIN", str(script))
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_server.server"],
        env=dict(os.environ),
    )
    result = None

    async def _call():
        nonlocal result
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write, read_timeout_seconds=None) as session:
                await session.initialize()
                with contextlib.suppress(TimeoutError):
                    result = await asyncio.wait_for(
                        session.call_tool(
                            "run_nec2_simulation",
                            {
                                "geometry": DIPOLE_GEOMETRY,
                                "frequency_hz": 300e6,
                                "timeout_s": 10,
                            },
                        ),
                        timeout=30,
                    )

    with contextlib.suppress(BaseExceptionGroup, BrokenResourceError):
        asyncio.run(_call())

    assert result is not None, (
        "the raw mcp SDK call never returned -- the server is deadlocking on a "
        "tool that shells out to its own subprocess again"
    )
    assert json.loads(result.content[0].text)["status"] == "COMPLETED"
