"""MCP-native role/tool-filter construction (issue #318, ADR-0032).

ADR-0032 decided that `mcp_server/server.py` should eventually become the
ONLY place a tool is ever registered, with every role's `Agent` consuming it
through the OpenAI Agents SDK's own `mcp_servers=[server]` adapter plus a
per-role `create_static_tool_filter` allow-list, instead of `agent/main.py`'s
hand-built `@function_tool` wrapper layer and `ROLES` dict. That ADR also
says plainly: *"This is a real rewrite, not a patch... A tracking issue for
the migration itself should be filed separately and scoped/staged rather
than attempted in one pass."* Issue #318 is that first staged step, scoped
narrowly on purpose: build the new construction ALONGSIDE `agent/main.py`'s
existing one, prove its per-role tool-filter allow-lists exactly match what
`ROLES`/`_PRINCIPAL_DIRECT_TOOLS` already grant today, and give issue #158's
provenance-integrity guardrail a working home in the new shape -- WITHOUT
touching a single line of `agent/main.py`'s own construction. As of issue
#318 (and until #377 below), nothing here was wired into `agent/main.py`'s
`run()`, `ROLES`, or `SPECIALIST_HANDOFFS`; those stayed exactly as they were
before this file existed.

WHAT THIS DID NOT DO AS OF #318 (see ADR-0032's own "Consequences" section --
these were explicitly future work, not gaps that ticket silently left): it
did not migrate production traffic onto this path, it did not delete or
deprecate any of `agent/main.py`'s 87+ wrappers, and it had not been
live-tested end to end against a real model the way `agent/main.py`'s
`.as_tool()` -> `handoffs=[...]` redesign was (see `agent/main.py`'s own
routing-section comment for that history) -- the ADR's own "Needs a live
behavior check before it ships" consequence was still open. What WAS proven
there, by test: each role's `create_static_tool_filter` allow-list is
BYTE-FOR-BYTE the same tool-name set `agent/main.py` already grants that
role today (derived from the same source objects, not hand-copied --
copying the list a second time here would just recreate the exact
two-places-must-agree problem ADR-0032 exists to eliminate), including a
real MCP-protocol round trip proving the filter actually restricts
`tools/list` to that set over the wire (not just as a config literal); and
the provenance guardrail fires under exactly the same condition
`agent/main.py`'s `_assert_calculated_provenance_is_tool_backed` does today.

ISSUE #377 (this update): `build_role_agent()` is now wired into a REAL,
LIVE `agent/main.py::run()` for exactly three roles -- principal, systems,
verification (see `agent/main.py`'s own module comment above `run()` for the
full account, and issue #376 for why microwave/antenna/test stay on the OLD
`agent/main.py::ROLES` construction: they hold every Windows-hanging
subprocess-shelling tool, #372). `build_role_agent()` gained three new,
all-optional keyword parameters to make this possible WITHOUT changing its
existing signature's observable behavior for any current caller
(`tests/test_mcp_roles.py`, `tests/test_mcp_tool_call_parity.py`):

  - `mcp_server`: an already-CONNECTED `MCPServerStdio` to attach instead of
    building (and leaving unconnected) a fresh one via
    `build_role_mcp_server(role_key)`. `run()` needs this because connecting
    a server is `async` (`MCPServerManager.connect_all()`), and this
    function itself is not -- the caller connects first, this function just
    wires the already-live instance onto the `Agent`. Omitted (the default,
    `None`): unchanged behavior, a fresh unconnected server every call, same
    as before this parameter existed.
  - `handoffs`: this role's own `route_to_<role>_role` targets. Needed
    because the LIVE principal's handoffs are a MIXED list -- the two other
    NEW-style Agents this same function just built (systems, verification)
    plus the three EXISTING, unchanged `agent/main.py::ROLES` Agent objects
    for microwave/antenna/test (old-style, `tools=[...]`, no MCP server at
    all) -- something no single per-role call to this function could express
    on its own. Omitted (the default, `None`): unchanged behavior, no
    handoffs, same as `Agent`'s own default.
  - `extra_instructions`: text inserted between the shared `## Role scope`
    domain note and the local-reasoning output tail. Needed because the
    LIVE principal carries an extra "## Routing to a specialist" section
    (`agent/main.py::_PRINCIPAL_ROUTING_INSTRUCTIONS`) that no other role's
    `domain_note` needs. Omitted (the default, `""`): unchanged instructions
    text, same as before this parameter existed.

Confirmed directly against `agents/run.py`'s own turn loop (not assumed):
`get_all_tools(execution_agent, ...)` is called inside the `while True:`
per-turn loop, rebound to whatever `current_agent` is that iteration, every
single turn -- including the turn immediately after a handoff. This is WHY
mixing an old-style (no MCP server) and a new-style (`mcp_servers=[server]`)
handoff target on the same principal is safe: an old-style target is never
asked for MCP tools at all (`Agent.get_mcp_tools()` only iterates
`self.mcp_servers`, which is empty for `agent/main.py::ROLES[...]`), and a
new-style target's server only needs to already be connected by the time
ITS OWN turn arrives -- which eager connect-everything-up-front at `run()`
start (via `agents.mcp.MCPServerManager`, `strict=True`) guarantees for
every query, regardless of which role the query actually reaches.

THE PROVENANCE-GUARDRAIL GAP THIS MIXING CREATES, AND WHY IT'S NOT A
REGRESSION: `provenance_integrity_guardrail` (below) is an
`Agent.output_guardrails` entry -- it only ever runs when the AGENT IT IS
ATTACHED TO produces the run's final output. An old-style specialist
(microwave/antenna/test) has no `output_guardrails` and no
`_ProvenanceTrackingHooks` wired onto it at all (unchanged, per #376's own
scope), so if the principal hands off to one and IT calls a real
calculation tool and produces the final answer, this module's own guardrail
never runs for that turn -- it was never attached to that agent. This is not
a gap `run()` silently accepts: `agent/main.py`'s existing, OLDER
`_assert_calculated_provenance_is_tool_backed(result)` reads the whole
finished `RunResult.new_items` regardless of which agent in the handoff
chain produced which item, so it already covers this path (and every other
handoff path, old-style or new) correctly -- it does not care whether the
tool-calling agent had a guardrail wired onto it, only whether a real
calculation-category `tool_call_item` exists anywhere in the run. `run()`
keeps calling it, unconditionally, on every run's `RunResult`, as the
authoritative enforcement point; this module's own guardrail is an
additional, EARLIER line of defense for the NEW-style agents it is actually
attached to (principal/systems/verification answering directly), not a
replacement for the post-hoc check. See
`tests/test_agent_roles.py::test_calculated_claim_backed_by_a_real_tool_call_through_an_old_style_specialist_handoff_is_accepted`
and its sibling `..._mislabeled_..._still_trips` for the scripted-fake-model
proof of both halves of this claim.

WHY SIX MCPServerStdio INSTANCES, NOT ONE SHARED SERVER WITH A CALLABLE
FILTER: the Agents SDK also supports a dynamic/callable `tool_filter` keyed
off `ToolFilterContext.agent` (see `docs/llm-tool-registry-completeness-
patterns.md` section 2), which would let one shared server connection serve
every role. Issue #318's own acceptance criteria ask specifically for a
`create_static_tool_filter(allowed_tool_names=[...])` PER role, and reading
the installed SDK's own `MCPServer._apply_static_tool_filter` directly
confirms why that forces six server instances: a static `ToolFilterStatic`
dict is applied to the whole server connection it is attached to, with no
per-requesting-agent branching at all (`agent`/`run_context` aren't even
read on that code path) -- so six roles needing six DIFFERENT static
allow-lists need six separate `MCPServerStdio` connections, each launching
the same `python -m mcp_server.server` stdio subprocess (`mcp_server/
server.py`'s real entry point -- the same one
`tests/test_mcp_server_protocol.py` already spawns for its own wire-level
tests) but filtered to one role's own tool set.
"""

import os
import sys
from dataclasses import dataclass

from agents import Agent, GuardrailFunctionOutput, Handoff, RunContextWrapper, output_guardrail
from agents.lifecycle import AgentHooks
from agents.mcp import MCPServerStdio, ToolFilterStatic, create_static_tool_filter
from agents.mcp.server import MCPServerStdioParams

# These five names are module-private to agent/main.py (leading underscore
# applied by that module's own author) rather than the "import a public name
# and re-alias it _locally" pattern used elsewhere in this repo (e.g.
# `from designs.service import create_design as _create_design`). Reaching
# into them directly is deliberate: they ARE the single source of truth this
# ticket exists to reuse rather than re-derive (see this module's own
# docstring, "derived from the same source objects, not hand-copied"), and
# `agent/main.py` cannot be touched to re-export them publicly without
# violating issue #318's own scope. The failure mode if agent/main.py ever
# renames one of these is loud, not silent: this import raises `ImportError`
# at collection/import time, well before any test assertion runs -- there is
# no linter warning, but there is also no way to miss it.
from agent.main import (
    _PRINCIPAL_DIRECT_TOOLS,
    _SPEC_BY_KEY,
    SYSTEM_PROMPT,
    _local_reasoning_output_tail,
    _resolve_agent_model,
    _resolve_agent_model_settings,
)
from orchestration.policy import category_for

# Every role this construction covers -- the same six agent/main.py's ROLES
# dict has, principal included.
ROLE_KEYS: tuple[str, ...] = (
    "principal",
    "systems",
    "microwave",
    "antenna",
    "test",
    "verification",
)


def _allowed_tool_names_for_role(role_key: str) -> list[str]:
    """The exact tool-name allow-list for one role, DERIVED from
    `agent/main.py`'s current construction rather than a second, hand-typed
    copy of it: `_PRINCIPAL_DIRECT_TOOLS` for the principal, never
    `ROLE_SPECS`'s own dead `principal.tools = list(_ALL_TOOLS)` entry (89
    tools) -- using that dead entry here would silently reproduce the
    already-fixed 91-tool-principal reliability bug this repo's own testing
    found (see `agent/main.py`'s `_PRINCIPAL_DIRECT_TOOLS` comment and
    `tests/test_agent_roles.py::test_principal_role_is_scoped_not_broad`).
    Every specialist's allow-list comes from `ROLE_SPECS[key].tools`
    (`_SPEC_BY_KEY[key].tools`) directly -- the same list `agent/main.py`'s
    own `ROLES[key] = Agent(..., tools=list(_SPEC_BY_KEY[key].tools))`
    already builds each specialist Agent from.
    """
    if role_key == "principal":
        return [tool.name for tool in _PRINCIPAL_DIRECT_TOOLS]
    return [tool.name for tool in _SPEC_BY_KEY[role_key].tools]


# One `create_static_tool_filter(allowed_tool_names=[...])` per role --
# issue #318's own acceptance criteria, sourced from `_allowed_tool_names_for_role`
# above rather than hand-copied. `tests/test_mcp_roles.py` verifies each of
# these matches `agent/main.py`'s current `ROLES[key].tools`/
# `_PRINCIPAL_DIRECT_TOOLS` name-for-name.
ROLE_MCP_TOOL_FILTERS: dict[str, ToolFilterStatic] = {
    role_key: create_static_tool_filter(allowed_tool_names=_allowed_tool_names_for_role(role_key))
    for role_key in ROLE_KEYS
}

# The real stdio entry point every role's MCPServerStdio launches -- the
# exact same subprocess command (`python -m mcp_server.server`) test_mcp_
# server_protocol.py's SERVER_PARAMS already spawns, run once per role with
# that role's own static tool_filter attached (see this module's docstring
# for why one shared connection can't serve six different static filters).
_MCP_SERVER_PARAMS: MCPServerStdioParams = {
    "command": sys.executable,
    "args": ["-m", "mcp_server.server"],
}


def build_role_mcp_server(role_key: str) -> MCPServerStdio:
    """A fresh `MCPServerStdio` scoped to one role's tool-filter allow-list.

    Constructing this does NOT spawn the subprocess -- `MCPServerStdio`
    only stores its params/filter at `__init__` time (confirmed by reading
    the installed SDK's own `MCPServerStdio.__init__` directly: no
    `create_subprocess`/`connect()` call happens there) and connects lazily
    on `await server.connect()` (or `async with server:`), same lifecycle
    `tests/test_mcp_server_protocol.py` already relies on for the plain,
    unfiltered server. Returns a NEW instance on every call rather than a
    cached singleton, since each call site (a live run, or a test) owns its
    own connect/cleanup lifecycle and two callers sharing one `MCPServerStdio`
    would also share one underlying subprocess and session.

    WHY `env=dict(os.environ)` IS REQUIRED, NOT OPTIONAL (issue #319's own
    Verify-phase finding): confirmed directly against the installed MCP
    client's own source (`mcp/client/stdio/__init__.py`) that
    `MCPServerStdio`'s underlying `stdio_client()` defaults an unset `env`
    to `get_default_environment()` -- a small, security-motivated allowlist
    (`PATH`/`HOME`/`USER`/etc. on POSIX, `PATH`/`APPDATA`/etc. on Windows)
    that does NOT include `DATABASE_URL` or any other `.env`-loaded
    configuration this repo's tools read from the environment. Without this,
    every tool the spawned subprocess runs that touches Postgres
    (`designs.db.get_connection` reads `os.environ["DATABASE_URL"]` -- true
    of nearly every tool in this repo) would fail inside the subprocess with
    a bare `KeyError`, for a reason that has nothing to do with MCP-routing
    parity -- see `tests/test_mcp_tool_call_parity.py` for the live proof.
    Captured FRESH on every call (not once at `_MCP_SERVER_PARAMS`'s module-
    import time) so a caller's own `monkeypatch.setenv` (e.g. `NEC2PP_BIN`
    pointed at a fake executable, this repo's own solver-adapter-test
    convention -- see `tests/conftest.py`'s `make_fake_executable`) reaches
    the subprocess too.

    WHY `client_session_timeout_seconds=None` IS REQUIRED, NOT OPTIONAL
    (found while building issue #319's own verification harness):
    `MCPServerStdio.__init__`'s own default (`client_session_timeout_
    seconds: float | None = 5`, confirmed directly against the installed
    SDK) means an un-overridden server aborts ANY tool call still running
    after 5 seconds with a client-side "Timed out while waiting for
    response to ClientRequest" error, regardless of the tool's own
    `timeout_s` argument -- confirmed live before this fix (a fake solver
    that legitimately takes 6s, well within its own `timeout_s=30`, was
    aborted at exactly 5.0s over this path while succeeding normally on the
    OLD direct-call path, which has no external timeout at all -- only the
    tool's own `timeout_s`-bounded `subprocess.run()` call applies there).
    This repo's real EM/circuit solvers default `timeout_s` to 600-3600
    seconds specifically because real solves take that long
    (`run_hfss_simulation`, `run_openems_simulation`, `run_elmer_
    simulation`, etc.) -- left at the SDK default, EVERY one of them would
    silently and unconditionally fail over the new path the moment a real
    solve took more than 5 seconds, independent of anything else this
    ticket compared. `None` is a documented, supported way to disable the
    ClientSession read timeout entirely (see `MCPServerStdio`'s own
    docstring), restoring parity: the tool's own internal `timeout_s`
    becomes the only bound again, exactly as it is on the OLD path.

    This fix alone does NOT make subprocess-shelling tools (every `run_*_
    simulation` tool) work over this path on native Windows -- see
    `tests/test_mcp_tool_call_parity.py`'s module docstring for a THIRD,
    NOT-fixed finding this ticket surfaced and documented instead: those
    tools hang indefinitely over this transport regardless of this fix,
    for a reason traced to the `mcp` package itself, not to anything
    `client_session_timeout_seconds` or `env` controls.
    """
    return MCPServerStdio(
        params={**_MCP_SERVER_PARAMS, "env": dict(os.environ)},
        name=f"principal-rf-engineer-mcp-{role_key}",
        tool_filter=ROLE_MCP_TOOL_FILTERS[role_key],
        client_session_timeout_seconds=None,
    )


# ---------------------------------------------------------------------------
# Issue #158's provenance-integrity guardrail, given a new, concrete home in
# this construction (issue #318's own acceptance criteria).
#
# WHY A CONTEXT + AgentHooks PAIR, NOT A DIRECT PORT: agent/main.py's
# `_assert_calculated_provenance_is_tool_backed` runs AFTER `Runner.run_sync`
# returns, reading the finished `RunResult.new_items` for a calculation-
# category `tool_call_item`. An `Agent.output_guardrails` entry is different
# in a way that matters here: its `OutputGuardrail.guardrail_function` is
# called `(context: RunContextWrapper, agent: Agent, agent_output: Any)` --
# confirmed by reading `agents.OutputGuardrail.run` directly -- with no
# `new_items`/tool-call-history parameter at all, because it runs DURING the
# run, before any `RunResult` exists to inspect. `RunContextWrapper` was also
# read directly to confirm it keeps no general, public tool-call-history
# list either: its `_tool_invocations` bookkeeping exists, but is private
# and scoped to approval status, not a call log a guardrail can read.
#
# `AgentHooks.on_tool_end(context, agent, tool, result)` -- called once per
# real tool execution, with access to the SAME `RunContextWrapper.context`
# object an output guardrail later reads -- is the SDK-supported bridge:
# `_ProvenanceTrackingHooks` sets a flag on that shared context the first
# time a calculation-category tool actually runs, and
# `provenance_integrity_guardrail` reads that flag instead of a `new_items`
# list. The category check itself (`orchestration.policy.category_for`) is
# identical to `agent/main.py`'s -- same policy file, same "calculation"
# category, same reasoning for why a `search_knowledge` call must not
# satisfy this (see `agent/main.py`'s own module comment above `run()` for
# the fuller account of that specific gap and why it matters).
# ---------------------------------------------------------------------------


@dataclass
class ProvenanceTrackingContext:
    """The `Runner.run(..., context=...)` payload `provenance_integrity_
    guardrail` and `_ProvenanceTrackingHooks` share for one run. Pass a
    fresh instance per run (like `agent/main.py`'s `run()` gets a fresh,
    implicit accounting per call) -- reusing one instance across runs would
    let an earlier run's calculation-tool call satisfy a later run's
    guardrail check.
    """

    calculation_tool_called: bool = False


class MissingProvenanceTrackingContextError(TypeError):
    """Raised when `provenance_integrity_guardrail` runs against a
    `RunContextWrapper` whose `.context` isn't a `ProvenanceTrackingContext`
    -- i.e. `Runner.run`/`run_sync` wasn't called with
    `context=ProvenanceTrackingContext()`, the pairing `build_role_agent`'s
    own docstring requires so `_ProvenanceTrackingHooks.on_tool_end` has
    somewhere to record a calculation-tool call for this guardrail to later
    read. Matches this repo's fail-closed style (see
    `orchestration.design_loop.DesignLoopValidationError`,
    `geometry.unit_cell.SymbolNotFoundError`,
    `optimization.combinatorial.EmptyCandidateShelfError`) -- silently
    treating a missing/wrong context as "no calculation tool was called"
    would trip the guardrail for the wrong reason instead of surfacing the
    real mistake: this Agent's context was never wired up.
    """


class _ProvenanceTrackingHooks(AgentHooks[ProvenanceTrackingContext]):
    """Sets `context.context.calculation_tool_called = True` the first time
    this agent's run executes a calculation-category tool (`policies/
    tool_policy.yaml`, via `orchestration.policy.category_for` -- the exact
    category check `agent/main.py`'s own
    `_run_result_has_calculation_tool_call` makes against a finished
    RunResult's `new_items`, just fed from a live hook instead). A handoff
    is not a tool call and never reaches `on_tool_end` at all, so (matching
    `agent/main.py`'s own guard) handing off control alone can never satisfy
    this on its own.
    """

    async def on_tool_end(self, context, agent, tool, result) -> None:
        if category_for(getattr(tool, "name", None)) == "calculation":
            context.context.calculation_tool_called = True


@output_guardrail
def provenance_integrity_guardrail(
    context: RunContextWrapper[ProvenanceTrackingContext],
    agent: Agent,
    agent_output: str,
) -> GuardrailFunctionOutput:
    """Trips (`tripwire_triggered=True`, which raises
    `OutputGuardrailTripwireTriggered` once this is actually wired via
    `Agent(output_guardrails=[...])` and run through `Runner.run`/
    `run_sync`) under EXACTLY the condition `agent/main.py`'s
    `_assert_calculated_provenance_is_tool_backed` raises
    `ProvenanceIntegrityError` for today: a CALCULATED claim in the final
    answer with no calculation-category tool call anywhere in this run. Does
    nothing for any other provenance label (INFERRED/ASSUMED/etc. never
    claimed a tool verified them) and does nothing when a CALCULATED claim
    genuinely is tool-backed -- see issue #158 and this module's own
    "provenance-integrity guardrail" section comment above for why this
    needs `_ProvenanceTrackingHooks` paired onto the same Agent to have
    anything to read.
    """
    tracked = context.context
    if not isinstance(tracked, ProvenanceTrackingContext):
        raise MissingProvenanceTrackingContextError(
            "provenance_integrity_guardrail requires Runner.run(..., "
            "context=ProvenanceTrackingContext()) -- got "
            f"{type(tracked).__name__} instead. Every Agent built via "
            "build_role_agent must be run with a ProvenanceTrackingContext "
            "so _ProvenanceTrackingHooks has somewhere to record a "
            "calculation-tool call for this guardrail to read."
        )
    tripped = "CALCULATED" in agent_output and not tracked.calculation_tool_called
    return GuardrailFunctionOutput(
        output_info={"calculation_tool_called": tracked.calculation_tool_called},
        tripwire_triggered=tripped,
    )


def build_role_agent(
    role_key: str,
    *,
    mcp_server: MCPServerStdio | None = None,
    handoffs: list[Agent | Handoff] | None = None,
    extra_instructions: str = "",
) -> Agent:
    """One role's `Agent`, built the ADR-0032 way: `mcp_servers=[server]`
    instead of a hand-built `tools=[...]` list, that role's own
    `create_static_tool_filter` allow-list doing the subsetting `agent/
    main.py`'s `ROLES` dict does by hand today, and issue #158's
    provenance-integrity guardrail wired directly via `output_guardrails`
    (its new home per issue #318) paired with `_ProvenanceTrackingHooks` so
    that guardrail has something to read. Reuses `agent/main.py`'s own
    model/instructions helpers (`SYSTEM_PROMPT`, `_resolve_agent_model`,
    `_resolve_agent_model_settings`, `_local_reasoning_output_tail`,
    `_SPEC_BY_KEY[key].domain_note`) so this construction's agents carry the
    same reasoning/prompt behavior `ROLES` does today -- only the tool-
    registration MECHANISM differs, per this ticket's scope.

    Independent of, and never compared against by identity to,
    `agent.main.ROLES` -- nothing in `agent/main.py` changes or is read back
    into by this function.

    Three all-optional keyword-only parameters, added for issue #377's live
    `run()` wiring, each defaulting to exactly the pre-#377 behavior so no
    existing caller (`tests/test_mcp_roles.py`, `tests/test_mcp_tool_call_
    parity.py`) sees any change when it doesn't pass them -- see this
    module's own docstring, "ISSUE #377 (this update)", for the full
    rationale on why each one exists:

    mcp_server: an already-connected `MCPServerStdio` to attach instead of
        building (and leaving unconnected) a fresh one. `None` (default):
        calls `build_role_mcp_server(role_key)`, unchanged.
    handoffs: this Agent's own `route_to_<role>_role` targets -- a mix of
        old- and new-style Agents is fine (see this module's docstring for
        why). `None` (default): no handoffs, matching `Agent`'s own default.
    extra_instructions: appended after the shared domain note and before
        the local-reasoning output tail. `""` (default): no change to the
        instructions text.
    """
    spec = _SPEC_BY_KEY[role_key]
    server = mcp_server if mcp_server is not None else build_role_mcp_server(role_key)
    return Agent(
        name=spec.display_name,
        model=_resolve_agent_model(),
        model_settings=_resolve_agent_model_settings(),
        instructions=(
            f"{SYSTEM_PROMPT}\n\n## Role scope\n\n{spec.domain_note}"
            f"{extra_instructions}"
            f"{_local_reasoning_output_tail()}"
        ),
        mcp_servers=[server],
        output_guardrails=[provenance_integrity_guardrail],
        hooks=_ProvenanceTrackingHooks(),
        handoffs=list(handoffs) if handoffs is not None else [],
    )
