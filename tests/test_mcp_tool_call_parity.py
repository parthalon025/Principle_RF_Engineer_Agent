"""Issue #319 (ADR-0032's own Verify phase, blocked by #318 -- both merged
before this ticket started): a live behavior-parity check between the OLD
direct-call path (`agent/main.py`'s hand-built `@function_tool`/`ROLES`
construction, invoked via `conftest.invoke_agent_tool`) and the NEW
`mcp_servers=[server]`-routed path (`agent/mcp_roles.py`, issue #318,
invoked via `conftest.invoke_role_mcp_tool`) -- the two constructions ADR-
0032 says must be proven equivalent (or have every difference named
plainly) before a later "contract" ticket is allowed to delete the OLD
path.

`tests/test_advance_design_status_release_approval.py` and
`tests/test_calculation_tool_recording.py` already compare an "agent" layer
against an "mcp" layer, but that "mcp" layer calls FastMCP's own
`mcp_module.mcp.call_tool()` directly, in-process -- it proves the
`@mcp.tool()`-wrapped function itself is correct, but never exercises the
real `mcp_servers=[server]` transport (a spawned `python -m mcp_server.
server` subprocess, talked to over stdio, converted into `FunctionTool`
objects by the OpenAI Agents SDK's own `MCPUtil`) that #318 actually built
and that #319 exists to verify. This file is that missing check, built
against issue #318's own `agent/mcp_roles.py` construction rather than a
second, hand-rolled approximation of it (see `conftest.invoke_role_mcp_tool`
for how).

THREE FINDINGS CAME OUT OF BUILDING THIS CHECK -- two were fixed here
(directly in `agent/mcp_roles.py`, since they made the harness this ticket
needed unusable, not merely a comparison result), one is a genuine,
documented, NOT-fixed limitation this file's own tests capture on purpose
rather than silently avoid:

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

3. NOT FIXED, DOCUMENTED, CONFIRMED PLATFORM-SPECIFIC -- on native Windows,
   a tool whose implementation shells out to its OWN subprocess (every
   `run_*_simulation` tool: NEC2++, openEMS, HFSS, Elmer, Palace, MEEP,
   gprMax, Qucs, LTspice, ngspice, Xyce, gerber2ems -- roughly half this
   repo's real engineering tool surface) never returns AT ALL over the
   MCP-routed path -- not slow, not merely past the old 5s timeout, but
   genuinely hung indefinitely (observed for 60+ seconds with fix #2 in
   place, i.e. with no client-side timeout left to mask it) -- even though
   the SAME call over the OLD path succeeds normally, in well under a
   second on top of the tool's own real work.

   Confirmed WINDOWS-SPECIFIC, not a general `mcp`/`anyio` defect: this
   file's `_IS_WINDOWS`-gated tests below were run against this exact code
   inside a `python:3.12-slim` Linux container (network-joined to this
   repo's own `docker-compose.yml` Postgres service, `uv sync --frozen
   --group dev`) as part of this ticket's own code review -- every one of
   them completes normally there, `run_nec2_simulation` included, in
   seconds, with no timeout needed at all. That is why the three tests
   naming this finding branch on platform (`_IS_WINDOWS`) instead of
   unconditionally asserting a hang: CI (`.github/workflows/ci.yml`) runs
   `pytest` on `ubuntu-latest` only, so an unconditional
   `pytest.raises(McpRoutedToolCallTimedOut)` here would never observe the
   hang it asserts and would fail CI outright, not merely mis-describe the
   finding.

   Root-caused down to the raw `mcp` package's own Windows-specific stdio
   client/server transport, independent of both this repo's
   `agent/mcp_roles.py` construction and the OpenAI Agents SDK entirely:
   reproduced with `mcp.client.stdio.stdio_client`/`mcp.ClientSession`
   called directly, with NO Agents SDK import at all --

       from mcp import ClientSession, StdioServerParameters, stdio_client
       params = StdioServerParameters(
           command=sys.executable, args=["-m", "mcp_server.server"], env=env,
       )
       async with stdio_client(params) as (read, write):
           async with ClientSession(read, write, read_timeout_seconds=None) as session:
               await session.initialize()
               await session.call_tool("run_nec2_simulation", {...})  # never returns

   Likely implicated (not confirmed further -- this is a third-party `mcp`/
   `anyio` library issue, out of this repo's own code to fix): FastMCP's
   sync-tool dispatch (`mcp/server/fastmcp/utilities/func_metadata.py`'s
   `call_fn_with_arg_validation`) calls a synchronous tool function
   (`return fn(**kwargs)`) directly on the server's own event-loop thread
   with no `anyio.to_thread`/`asyncio.to_thread` wrapping at all, so a tool
   that itself blocks on `subprocess.run()` blocks that entire event loop;
   combined with `mcp`'s own Windows-specific subprocess launch path
   (`mcp/os/win32/utilities.py`'s Job-Object-based process-tree management
   for the OUTER `mcp_server.server` subprocess itself), a nested
   `subprocess.run()` call from inside that blocked loop appears to
   deadlock rather than merely delay. This was NOT chased further inside
   the installed `mcp`/`anyio` packages -- that is upstream, third-party
   code, not this repo's to patch -- but it is a real, load-bearing,
   reproducible finding that must be resolved (or the affected tools moved
   off the stdio transport, or their subprocess calls moved onto a worker
   thread inside `mcp_server/server.py` itself, or the transport itself
   swapped) before a later "contract" ticket may safely delete the OLD
   direct-call path these tools currently work over. `docs/adr/0032-tool-
   registration-consolidates-onto-the-mcp-server.md`'s own "Consequences"
   section already named exactly this risk in the abstract ("Nothing in
   this session confirmed that round trip is behaviorally identical"); this
   file is that confirmation, and the answer for subprocess-shelling tools
   is "it is not," not "yes, with different wording." Tracked as its own
   ticket, separate from the "delete the old path" contract ticket (#320)
   this blocks: issue #372.

Every test below is bounded (`conftest.invoke_role_mcp_tool`'s own
`harness_timeout_s`, default 30s) so this finding is captured as a normal, fast,
PASSING test run (asserting the honestly-observed-today behavior) rather
than an indefinite CI hang -- matching this repo's own "warn, never block"
principle applied to its own test suite. On Windows, the two tests named
`*_known_hung_on_windows*` below expect the hang directly
(`pytest.raises(McpRoutedToolCallTimedOut)`); on every other platform
(confirmed Linux, above) they instead run the SAME real value-level
comparison every other test in this file runs, since the call genuinely
completes there -- a platform this finding does not reproduce on gets a
platform-appropriate assertion, not a skip and not a false "it hangs
everywhere" claim. `test_raw_mcp_sdk_reproduces_the_hang_independent_of_
the_agents_sdk` (this finding's root-cause isolation, with no Agents SDK
import at all) is `skipif`'d off non-Windows platforms outright instead of
branching, since its entire point is isolating a hang that platform does
not have. If finding 3 is ever resolved upstream (or worked around in this
repo) such that Windows itself stops hanging, the Windows branches of
these tests will start FAILING (the call will complete within the timeout
instead of raising `McpRoutedToolCallTimedOut`) -- that failure is the
intended signal to update this file, not a flake to retry.
"""

from __future__ import annotations

import json
import platform
import tempfile
import time
from pathlib import Path

import numpy as np
import pytest
import skrf as rf
from conftest import (
    DIPOLE_GEOMETRY,
    McpRoutedToolCallTimedOut,
    invoke_agent_tool,
    invoke_role_mcp_tool,
    make_fake_executable,
)

from orchestration.design_loop import start_design_loop

# Finding 3 (module docstring above) is confirmed Windows-specific, not a
# general mcp/anyio defect -- see the tests that reference this constant for
# how each one adapts to a platform where the hang does not reproduce.
_IS_WINDOWS = platform.system() == "Windows"


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
# AC1 (issue #319): a representative sample spanning a plain-schema tool, a
# strict_mode=False geometry/circuit-dict tool, and a strict_mode=False
# design-loop-state tool, through both paths.
# ---------------------------------------------------------------------------


def _make_touchstone_file() -> str:
    """Mirrors `tests/test_calculation_tool_recording.py`'s helper of the
    same name/shape exactly -- a real, tiny 2-port .s2p file on disk, not a
    hand-built dict, so `analyze_touchstone_file` exercises its actual
    skrf.Network file-reading path on both sides of the comparison."""
    tmp_dir = Path(tempfile.mkdtemp())
    f = rf.Frequency(1, 3, 3, unit="ghz")
    s = np.zeros((3, 2, 2), dtype=complex)
    s[:, 0, 0] = 10 ** (-20 / 20)
    s[:, 1, 0] = 10 ** (-3 / 20)
    ntwk = rf.Network(frequency=f, s=s, z0=50)
    path = tmp_dir / "parity_fixture.s2p"
    ntwk.write_touchstone(path.with_suffix(""))
    return str(path)


def test_plain_schema_simulator_tool_agrees_on_the_analyzed_result():
    """analyze_touchstone_file: AC1's "plain-schema simulator tool" bucket
    -- plain-schema (strict_mode default True; `path`/`design_id` are a
    `str`/`int | None`, no free-form dict), and squarely in the simulator/
    measurement domain (a real .s2p network-parameter file, the kind of
    output NEC2++/openEMS/HFSS/a real bench measurement all produce), on
    the "microwave"/"antenna"/"test" roles. No `design_id` here, so no
    database write either side needs to agree on -- see the error-surfacing
    test below for this same tool's failure-path comparison."""
    path = _make_touchstone_file()

    old_raw = invoke_agent_tool("analyze_touchstone_file", path=path)
    new_raw = invoke_role_mcp_tool("microwave", "analyze_touchstone_file", path=path)

    assert isinstance(old_raw, dict)
    assert isinstance(new_raw, dict) and new_raw.get("type") == "text"
    assert _decode_mcp_tool_output(new_raw) == old_raw


def test_plain_schema_tool_agrees_on_the_computed_value():
    """calculate_wavelength: a second, minimal plain-schema (strict_mode
    default True) example, on the "systems" role -- OLD path returns a
    bare Python float; NEW path returns a JSON-encoded string wrapped in a
    `{"type": "text", ...}` envelope -- different SHAPE, same decoded
    VALUE. Kept alongside analyze_touchstone_file above (this file's
    canonical "plain-schema simulator tool" per AC1) because it shows the
    bare-scalar shape difference most crisply -- analyze_touchstone_file's
    dict-shaped result looks the same story as inspect_design_loop_state's
    below at a glance; a caller returning a plain number sees a more
    visibly different Python type (`float` vs. `dict`) on each path."""
    old_raw = invoke_agent_tool("calculate_wavelength", frequency_hz=1e9)
    new_raw = invoke_role_mcp_tool("systems", "calculate_wavelength", frequency_hz=1e9)

    assert isinstance(old_raw, float)
    assert new_raw == {"type": "text", "text": "0.299792458"}

    assert _decode_mcp_tool_output(old_raw) == pytest.approx(0.299792458)
    assert _decode_mcp_tool_output(new_raw) == pytest.approx(old_raw)


def test_design_loop_state_tool_agrees_on_the_full_state(tmp_path: Path):
    """inspect_design_loop_state: a strict_mode=False tool (its `state`
    param is a free-form dict) on the "principal" role's direct tools.
    Built with no `design_id` (orchestration.design_loop.start_design_loop
    is the pure, no-database constructor `start_new_design_loop`/
    `start_design_loop`'s tool wrapper itself calls after creating a real
    `designs` row -- calling it directly here keeps this comparison
    database-free, matching the tool's own documented "without a design_id,
    this never touches the database" behavior)."""
    state = start_design_loop({"gain_dbi": {"threshold": 5.0, "unit": "dBi"}}).to_dict()

    old_raw = invoke_agent_tool("inspect_design_loop_state", state=state)
    new_raw = invoke_role_mcp_tool("principal", "inspect_design_loop_state", state=state)

    assert isinstance(old_raw, dict)
    assert isinstance(new_raw, dict) and new_raw.get("type") == "text"

    assert _decode_mcp_tool_output(new_raw) == old_raw


def _write_fake_nec2pp_exit_0(tmp_path: Path) -> Path:
    body = "import sys\nsys.exit(0)\n"
    return make_fake_executable(tmp_path, body, name="fast_nec2pp")


def test_geometry_dict_tool_known_hung_on_windows_over_the_new_path(tmp_path, monkeypatch):
    """run_nec2_simulation: a strict_mode=False tool (its `geometry` param
    is a free-form dict) on the "antenna" role, which shells out to a real
    subprocess (`simulation.nec2pp.Nec2ppSimulator.run`'s own
    `subprocess.run()` call against whatever `NEC2PP_BIN` names -- faked
    out here exactly as `tests/test_nec2pp.py` already does, per this
    repo's own solver-adapter-test convention).

    On Windows, this is finding 3 from this file's module docstring,
    reproduced concretely: the OLD path succeeds normally; the SAME call
    over the NEW path does not return within `invoke_role_mcp_tool`'s bound
    at all, even for a fake "solver" that exits immediately with no output
    and no sleep -- this is not about how long the tool takes, it is about
    shelling out to a subprocess AT ALL from inside mcp_server.server's own
    stdio-transport subprocess on this platform. See the module docstring
    for the raw `mcp`-SDK-only reproduction that rules out the OpenAI
    Agents SDK and this repo's own agent/mcp_roles.py as the cause.

    THE WINDOWS BRANCH PASSES TODAY BY CAPTURING THAT HANG, NOT BY AVOIDING
    IT -- if it starts failing, that means the NEW path now completes in
    time on Windows too, which is the update signal for this file, not a
    flake. On every other platform (confirmed Linux -- see the module
    docstring), the call genuinely completes, so this runs the SAME
    value-level comparison every non-hanging tool in this file runs, giving
    AC1's "strict_mode=False geometry/circuit-dict tool" bucket a real,
    completed answer on the platform CI actually runs on
    (`.github/workflows/ci.yml` is `ubuntu-latest`-only)."""
    script = _write_fake_nec2pp_exit_0(tmp_path)
    monkeypatch.setenv("NEC2PP_BIN", str(script))

    old_result = invoke_agent_tool(
        "run_nec2_simulation", geometry=DIPOLE_GEOMETRY, frequency_hz=300e6, timeout_s=10
    )
    assert old_result["provenance"] == "SIMULATED"
    assert old_result["status"] == "COMPLETED"

    if _IS_WINDOWS:
        with pytest.raises(McpRoutedToolCallTimedOut):
            invoke_role_mcp_tool(
                "antenna",
                "run_nec2_simulation",
                harness_timeout_s=20,
                geometry=DIPOLE_GEOMETRY,
                frequency_hz=300e6,
                timeout_s=10,
            )
        return

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
    # `workdir`/`input_file` are `tempfile.mkdtemp()`-generated paths --
    # Nec2ppSimulator.run makes a fresh one on every call, on both paths, so
    # they are expected to differ between the OLD and NEW invocations above
    # even when everything else agrees. Excluded from the exact-match
    # comparison for that reason, not because a real mismatch there would be
    # acceptable.
    volatile_keys = {"workdir", "input_file"}
    assert {k: v for k, v in old_result.items() if k not in volatile_keys} == {
        k: v for k, v in new_result.items() if k not in volatile_keys
    }


# ---------------------------------------------------------------------------
# AC2 (issue #319): error-surfacing behavior, for a tool that can genuinely
# raise. Split into two cases -- a clean, non-subprocess exception (which
# DOES complete, and answers ADR-0032's original "isError=true text result,
# not a raised Python exception" question directly) and the subprocess-
# based SimulatorError case (which hits finding 3 above before the isError
# question is even reachable) -- rather than only the latter, so the
# narrower error-surfacing question this ticket also asks about has a real,
# completed answer on record, not just "everything about this tool hangs."
# ---------------------------------------------------------------------------


def test_error_surfacing_for_a_clean_non_subprocess_exception():
    """analyze_touchstone_file with a nonexistent path: rf_tools.touchstone.
    analyze_touchstone raises a plain `FileNotFoundError`, no subprocess
    involved, so this completes on both paths (unlike the geometry/circuit-
    dict case above) and gives a clean answer to ADR-0032's own question:
    "a server-side exception becomes an isError=true text result on the new
    path, not a raised Python exception" -- confirmed EQUIVALENT IN EFFECT,
    not equivalent in exact wording or shape:

    - Neither path lets the exception propagate out of `on_invoke_tool()`
      to the caller. `agent/main.py`'s own `@function_tool` wrappers never
      set `failure_error_function=None` (confirmed by grepping agent/
      main.py -- no override exists anywhere), so the OpenAI Agents SDK's
      own default failure handling (`agents.tool.default_tool_error_
      function`, the SAME machinery a `to_function_tool`-derived MCP tool
      uses) already catches the exception and returns a formatted string
      on the OLD path too -- ADR-0032's assumption that today's direct
      call raises all the way through was not correct for this repo's
      actual tool construction, not because anything in this ticket
      changed that, but because agent/main.py never opted out of the SDK's
      own default handling. This is itself worth recording plainly rather
      than silently updating the assumption without saying so.
    - The exact WORDING differs: the OLD path's text carries the Agents
      SDK's own generic prefix ("An error occurred while running the tool.
      Please try again. Error: ..."); the NEW path's text is FastMCP's own
      "Error executing tool <name>: ..." (mcp/server/fastmcp/tools/base.py's
      `ToolError` message), with no SDK-generic wrapper at all -- a
      genuinely different string a model or a caller pattern-matching on
      exact wording would see differently.
    - The SHAPE differs: the OLD path returns a bare `str`; the NEW path
      returns the same `{"type": "text", "text": ...}` envelope as every
      other NEW-path result (see `_decode_mcp_tool_output`)."""
    bad_path = "C:/this/path/does/not/exist/on/purpose.s2p"

    old_raw = invoke_agent_tool("analyze_touchstone_file", path=bad_path)
    new_raw = invoke_role_mcp_tool("microwave", "analyze_touchstone_file", path=bad_path)

    assert isinstance(old_raw, str)
    assert (
        old_raw == f"An error occurred while running the tool. Please try again. Error: {bad_path}"
    )

    assert isinstance(new_raw, dict) and new_raw.get("type") == "text"
    assert new_raw["text"] == f"Error executing tool analyze_touchstone_file: {bad_path}"

    # Equivalent IN EFFECT: both are plain text containing the bad path,
    # neither is a raised exception a Python caller could catch by type.
    assert bad_path in old_raw
    assert bad_path in new_raw["text"]


def _write_fake_nec2pp_exit_1(tmp_path: Path) -> Path:
    body = 'import sys\nsys.stderr.write("boom: bad geometry card\\n")\nsys.exit(1)\n'
    return make_fake_executable(tmp_path, body, name="failing_nec2pp")


def test_error_surfacing_for_a_genuine_simulator_error_known_hung_on_windows(tmp_path, monkeypatch):
    """run_nec2_simulation with a fake solver that fails (nonzero exit) --
    the concrete `SimulatorError` scenario ADR-0032's acceptance criteria
    names by example. `simulation.nec2pp.Nec2ppSimulator.run` raises
    `SimulatorError(f"NEC2++ failed ({code}): {stderr}")`, exercised here
    exactly as `tests/test_nec2pp.py::test_run_nec2_simulation_propagates_
    simulator_error_on_failure` already does for the underlying function.

    On the OLD path, this SimulatorError is caught and formatted by the
    Agents SDK's own default_tool_error_function, same as the clean
    non-subprocess case above -- a plain, promptly-returned text string.

    On Windows, the NEW path hits finding 3 (the module docstring's
    Windows-specific stdio-transport + nested-subprocess hang) before ever
    reaching the isError=true-vs-raised-exception question at all: the call
    never returns, error or otherwise. ADR-0032's specific error-surfacing
    question therefore has NO answer for this tool category on that
    platform -- not "equivalent", not "different wording" -- the more
    fundamental transport-level finding preempts it entirely, and the
    Windows branch's job is to say exactly that, not to paper over it with
    a narrower claim that platform cannot actually support.

    On every other platform (confirmed Linux -- see the module docstring),
    the call completes, and ADR-0032's error-surfacing question DOES have
    an answer for this tool category there: equivalent in effect to
    `test_error_surfacing_for_a_clean_non_subprocess_exception` above (a
    plain text result on both paths containing the same failure detail,
    neither path raising a catchable-by-type exception), with the same
    wording/shape differences already documented there."""
    script = _write_fake_nec2pp_exit_1(tmp_path)
    monkeypatch.setenv("NEC2PP_BIN", str(script))

    old_raw = invoke_agent_tool(
        "run_nec2_simulation", geometry=DIPOLE_GEOMETRY, frequency_hz=300e6, timeout_s=10
    )
    assert isinstance(old_raw, str)
    assert "NEC2++ failed (1)" in old_raw
    assert "boom: bad geometry card" in old_raw

    if _IS_WINDOWS:
        with pytest.raises(McpRoutedToolCallTimedOut):
            invoke_role_mcp_tool(
                "antenna",
                "run_nec2_simulation",
                harness_timeout_s=20,
                geometry=DIPOLE_GEOMETRY,
                frequency_hz=300e6,
                timeout_s=10,
            )
        return

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
# just enough to rule out a gross regression from the added MCP transport
# hop, for tools that do complete (calculate_wavelength and inspect_design_
# loop_state above, both proven equivalent already -- reused here rather
# than a third tool, since the finding this check cares about is the
# transport hop's cost, which is the same regardless of which non-hanging
# tool is called).
# ---------------------------------------------------------------------------


def test_latency_sanity_new_path_per_call_cost_is_not_a_gross_regression():
    """Per-call cost only -- deliberately excludes the one-time subprocess
    connect+list_tools cost (measured and reported separately below,
    unasserted): a real Agent session in production connects one
    MCPServerStdio per role ONCE and reuses it for every tool call within
    that run (see agent/mcp_roles.py's own docstring), so the one-time
    setup cost is amortized across a whole session, not paid per call --
    asserting a tight bound on it here would be sanity-checking the wrong
    thing. What actually matters for "is the added transport hop a gross
    regression" is the cost of each individual call once connected, which
    this measures directly by re-using ONE connection across N calls,
    mirroring real usage.

    Bounds are deliberately generous (sanity, not a formal benchmark, per
    the ticket's own wording) -- this only needs to catch a hop that got,
    say, 100x slower than a bare in-process call, not to hold this repo to
    a strict SLA on a shared, variably-loaded CI/dev machine."""
    import asyncio

    from agents import RunContextWrapper
    from agents.tool_context import ToolContext

    from agent.mcp_roles import build_role_agent

    n_calls = 5

    old_start = time.perf_counter()
    for _ in range(n_calls):
        invoke_agent_tool("calculate_wavelength", frequency_hz=1e9)
    old_per_call_s = (time.perf_counter() - old_start) / n_calls

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
        f"\nlatency sanity: OLD per-call={old_per_call_s * 1000:.2f}ms, "
        f"NEW per-call={new_per_call_s * 1000:.2f}ms, "
        f"NEW one-time connect+list_tools={connect_s * 1000:.1f}ms (unasserted, "
        "amortized across a session in real usage)"
    )

    # Sanity thresholds, not a benchmark: catch a gross regression, not a
    # normal, expected added-hop cost (stdio JSON-RPC round trip vs. a bare
    # in-process function call).
    assert new_per_call_s < 2.0, (
        f"NEW path per-call cost {new_per_call_s:.3f}s looks like a hang, not overhead"
    )
    assert new_per_call_s < max(old_per_call_s * 200, 0.5), (
        f"NEW path ({new_per_call_s:.4f}s/call) is more than 200x the OLD path "
        f"({old_per_call_s:.4f}s/call) -- looks like a gross regression, not the expected "
        "transport-hop overhead"
    )


# ---------------------------------------------------------------------------
# Root-cause isolation for finding 3 (module docstring): the raw `mcp`
# package's own client, with NO OpenAI Agents SDK import at all, to rule
# out agent/mcp_roles.py's own construction (or the Agents SDK's MCPUtil
# conversion layer) as the cause. Bounded the same way as every hang-prone
# test above. Windows-only (see the skipif below): unlike the two tests
# above, this one has no non-Windows branch, because its entire point is
# isolating a hang that platform does not have -- there is nothing here to
# prove on a platform where the raw mcp SDK just returns normally.
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _IS_WINDOWS,
    reason=(
        "finding 3 (module docstring) is confirmed Windows-specific -- the "
        "raw mcp SDK call this test makes completes normally on Linux (run "
        "against this exact code during code review, see the module "
        "docstring). This test's whole purpose is isolating a Windows-only "
        "hang from the OpenAI Agents SDK, so it has nothing to prove on a "
        "platform with no hang to isolate."
    ),
)
def test_raw_mcp_sdk_reproduces_the_hang_independent_of_the_agents_sdk(tmp_path, monkeypatch):
    """Proves finding 3 is a `mcp`/`anyio` stdio-transport limitation on
    this platform, not a bug this ticket's own `agent/mcp_roles.py`
    changes introduced or could fix: talks to the exact same `python -m
    mcp_server.server` subprocess using ONLY the `mcp` package's own
    `stdio_client`/`ClientSession` -- no `agents` import anywhere in this
    test. `read_timeout_seconds=None` mirrors this ticket's own
    `client_session_timeout_seconds=None` fix (finding 2) so the SAME
    absence of a client-side timeout applies here too -- if this hangs, it
    is not because of a timeout config this test forgot to raise, it is the
    same underlying non-completion finding 1/2's fixes were unable to
    resolve on their own.

    The `asyncio.wait_for` bound is caught INSIDE the two `async with`
    blocks, not around them: cancelling `session.call_tool()` mid-flight
    (the only way to bound a call that never returns) leaves the stdio
    reader/writer task group in a state where exiting `stdio_client`'s own
    `async with` afterward can itself raise an `anyio.BrokenResourceError`
    wrapped in an `ExceptionGroup` -- a real, observed artifact of
    cancelling a stuck call, not a second, independent finding, and not
    the thing this test exists to prove. That secondary exception is
    swallowed on the way out for exactly that reason."""
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
    timed_out = False

    async def _call():
        nonlocal timed_out
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write, read_timeout_seconds=None) as session:
                await session.initialize()
                try:
                    await asyncio.wait_for(
                        session.call_tool(
                            "run_nec2_simulation",
                            {
                                "geometry": DIPOLE_GEOMETRY,
                                "frequency_hz": 300e6,
                                "timeout_s": 10,
                            },
                        ),
                        timeout=20,
                    )
                except TimeoutError:
                    timed_out = True

    with contextlib.suppress(BaseExceptionGroup, BrokenResourceError):
        asyncio.run(_call())

    assert timed_out, (
        "expected the raw mcp SDK call to time out, same as the Agents-SDK-routed path"
    )
