"""Tests for agent/mcp_roles.py -- the MCP-native role/tool-filter
construction (issue #318, ADR-0032).

This is a NEW module, built entirely alongside agent/main.py's existing
@function_tool/ROLES construction -- see agent/mcp_roles.py's own module
docstring for the full rationale. `tests/test_agent_roles.py` stays scoped
to `agent.main`'s existing construction (its own module docstring says so
explicitly); this file is the equivalent coverage for the new one, matching
this repo's one-test-file-per-module convention.

Two kinds of proof are used here, deliberately:

1. Plain, synchronous, no-I/O tests that the new construction's per-role
   `create_static_tool_filter` allow-lists are DERIVED from (not a second,
   hand-typed copy of) agent/main.py's current `ROLES[key].tools`/
   `_PRINCIPAL_DIRECT_TOOLS` -- the literal wording of issue #318's own
   acceptance criteria.
2. A REAL MCP-protocol round trip (spawning `mcp_server/server.py` as a
   genuine subprocess, exactly like `tests/test_mcp_server_protocol.py`
   already does for the unfiltered server) proving the filter isn't just a
   config literal that happens to match -- it actually restricts a real
   `tools/list` response to that exact set, for every one of the six roles.
   This is the stronger of the two proofs and is what actually exercises
   `agents.mcp.MCPServerStdio`'s own `_apply_static_tool_filter` code path
   this repo now depends on.
"""

import asyncio
import sys

import pytest
from agents import Agent, RunContextWrapper

from agent.main import _PRINCIPAL_DIRECT_TOOLS, ROLE_SPECS, ROLES
from agent.mcp_roles import (
    ROLE_KEYS,
    ROLE_MCP_TOOL_FILTERS,
    MissingProvenanceTrackingContextError,
    ProvenanceTrackingContext,
    _ProvenanceTrackingHooks,
    build_role_agent,
    build_role_mcp_server,
    provenance_integrity_guardrail,
)

_SPECIALIST_KEYS = ["systems", "microwave", "antenna", "test", "verification"]
_ROLE_SPECS_BY_KEY = {spec.key: spec for spec in ROLE_SPECS}


# ---------------------------------------------------------------------------
# Tool-filter allow-list equivalence (issue #318's own acceptance criteria).
# ---------------------------------------------------------------------------


def test_role_keys_cover_all_six_roles():
    assert set(ROLE_KEYS) == {
        "principal",
        "systems",
        "microwave",
        "antenna",
        "test",
        "verification",
    }


def test_every_role_has_a_static_allow_list_filter():
    for role_key in ROLE_KEYS:
        tool_filter = ROLE_MCP_TOOL_FILTERS[role_key]
        assert isinstance(tool_filter, dict)
        assert "allowed_tool_names" in tool_filter
        assert "blocked_tool_names" not in tool_filter
        assert len(tool_filter["allowed_tool_names"]) > 0, f"role {role_key!r} has no tools"


def test_principal_filter_matches_principal_direct_tools_exactly():
    # The ticket's own headline regression: the principal's filter must be
    # sourced from _PRINCIPAL_DIRECT_TOOLS (15 tools), never from
    # ROLE_SPECS's own dead `principal.tools = _ALL_TOOLS` entry (89 tools)
    # -- getting this wrong reproduces the already-fixed 91-tool-principal
    # reliability bug (see agent/main.py's _PRINCIPAL_DIRECT_TOOLS comment).
    principal_allowed = set(ROLE_MCP_TOOL_FILTERS["principal"]["allowed_tool_names"])
    expected = {tool.name for tool in _PRINCIPAL_DIRECT_TOOLS}
    assert principal_allowed == expected
    assert len(principal_allowed) == 15


def test_principal_filter_does_not_match_role_specs_dead_entry():
    # ROLE_SPECS's own "principal" entry still carries the dead
    # `tools=list(_ALL_TOOLS)` assignment (agent/main.py never reads it back
    # for the real ROLES["principal"] Agent -- that gets overwritten right
    # after ROLES is built, using _PRINCIPAL_DIRECT_TOOLS instead). Confirm
    # the new construction's filter deliberately does NOT match that dead,
    # much-larger entry, so a future refactor that accidentally re-sources
    # this from ROLE_SPECS instead of _PRINCIPAL_DIRECT_TOOLS fails loudly
    # here.
    dead_entry_names = {tool.name for tool in _ROLE_SPECS_BY_KEY["principal"].tools}
    principal_allowed = set(ROLE_MCP_TOOL_FILTERS["principal"]["allowed_tool_names"])
    assert len(dead_entry_names) > len(principal_allowed)
    assert principal_allowed != dead_entry_names
    assert principal_allowed < dead_entry_names  # every principal-direct tool is also in _ALL_TOOLS


@pytest.mark.parametrize("role_key", _SPECIALIST_KEYS)
def test_specialist_filter_matches_role_specs_tools_exactly(role_key):
    allowed = set(ROLE_MCP_TOOL_FILTERS[role_key]["allowed_tool_names"])
    expected = {tool.name for tool in _ROLE_SPECS_BY_KEY[role_key].tools}
    assert allowed == expected


@pytest.mark.parametrize("role_key", _SPECIALIST_KEYS)
def test_specialist_filter_matches_the_live_roles_dict_tools(role_key):
    # Belt-and-suspenders: also compare against agent.main.ROLES[key].tools
    # directly (the actual constructed Agent's tool list), not only
    # ROLE_SPECS (the RoleSpec data ROLES is built from) -- these are
    # expected to always agree, but the acceptance criterion names
    # ROLES[key].tools specifically.
    allowed = set(ROLE_MCP_TOOL_FILTERS[role_key]["allowed_tool_names"])
    expected = {tool.name for tool in ROLES[role_key].tools}
    assert allowed == expected


# ---------------------------------------------------------------------------
# MCPServerStdio factory (agent/mcp_roles.build_role_mcp_server).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("role_key", ROLE_KEYS)
def test_build_role_mcp_server_carries_that_roles_filter(role_key):
    server = build_role_mcp_server(role_key)
    assert server.tool_filter == ROLE_MCP_TOOL_FILTERS[role_key]
    assert role_key in server.name


def test_build_role_mcp_server_returns_a_fresh_instance_each_call():
    first = build_role_mcp_server("verification")
    second = build_role_mcp_server("verification")
    assert first is not second


# ---------------------------------------------------------------------------
# build_role_agent: the construction is callable independently of ROLES,
# and SPECIALIST_HANDOFFS is untouched by this ticket.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("role_key", ROLE_KEYS)
def test_build_role_agent_is_constructible_for_every_role(role_key):
    agent = build_role_agent(role_key)
    assert agent.name == _ROLE_SPECS_BY_KEY[role_key].display_name
    assert len(agent.mcp_servers) == 1
    assert agent.mcp_servers[0].tool_filter == ROLE_MCP_TOOL_FILTERS[role_key]
    assert provenance_integrity_guardrail in agent.output_guardrails
    assert isinstance(agent.hooks, _ProvenanceTrackingHooks)
    # This construction is independent of ROLES -- it must not reuse or
    # mutate the existing Agent objects agent/main.py already built.
    assert agent is not ROLES[role_key]


def test_building_new_construction_agents_does_not_touch_specialist_handoffs():
    from agent.main import SPECIALIST_HANDOFFS as handoffs_before

    before = dict(handoffs_before)
    for role_key in ROLE_KEYS:
        build_role_agent(role_key)
    from agent.main import SPECIALIST_HANDOFFS as handoffs_after

    assert handoffs_after == before
    assert set(handoffs_after.keys()) == set(_SPECIALIST_KEYS)


# ---------------------------------------------------------------------------
# Issue #158's provenance-integrity guardrail, in its new home. Exercised
# through the REAL agents.OutputGuardrail.run() code path (not just calling
# the bare Python function), the same way agent/main.py's own guard is
# exercised through direct calls in tests/test_agent_roles.py -- this file's
# no-live-model-credential constraint (see test_agent_roles.py's module
# docstring) applies here too, so a full live Runner.run through a real
# model is not attempted.
# ---------------------------------------------------------------------------

_DUMMY_AGENT = Agent(name="mcp-roles-test-dummy")


def _run_guardrail(context: RunContextWrapper, agent_output: str):
    return asyncio.run(provenance_integrity_guardrail.run(context, _DUMMY_AGENT, agent_output))


def test_calculated_claim_backed_by_a_calculation_tool_call_is_accepted():
    context = RunContextWrapper(context=ProvenanceTrackingContext(calculation_tool_called=True))
    result = _run_guardrail(context, "Cascaded noise figure: 3.47 dB (CALCULATED).")
    assert result.output.tripwire_triggered is False


def test_calculated_claim_with_no_tool_call_is_rejected():
    context = RunContextWrapper(context=ProvenanceTrackingContext())
    result = _run_guardrail(
        context, "**3.47 dB** (CALCULATED)\n\nFriis Cascaded Noise Figure Breakdown: ..."
    )
    assert result.output.tripwire_triggered is True


def test_non_calculated_claim_needs_no_tool_call():
    context = RunContextWrapper(context=ProvenanceTrackingContext())
    result = _run_guardrail(context, "Rough order-of-magnitude estimate: ~3 dB (INFERRED).")
    assert result.output.tripwire_triggered is False


def test_guardrail_requires_a_provenance_tracking_context():
    # A run started without context=ProvenanceTrackingContext() must fail
    # loudly, not silently treat "wrong context type" as "no calculation
    # tool was called" -- see MissingProvenanceTrackingContextError's own
    # docstring for why that distinction matters.
    context = RunContextWrapper(context=None)
    with pytest.raises(MissingProvenanceTrackingContextError):
        _run_guardrail(context, "3.47 dB (CALCULATED).")


class _FakeTool:
    def __init__(self, name):
        self.name = name


def test_hooks_set_the_flag_on_a_calculation_category_tool_call():
    hooks = _ProvenanceTrackingHooks()
    context = RunContextWrapper(context=ProvenanceTrackingContext())
    asyncio.run(hooks.on_tool_end(context, _DUMMY_AGENT, _FakeTool("calculate_wavelength"), None))
    assert context.context.calculation_tool_called is True


def test_hooks_do_not_set_the_flag_on_a_non_calculation_tool_call():
    # Mirrors agent/main.py's own
    # test_calculated_claim_backed_by_an_unrelated_tool_call_is_still_rejected:
    # a real, legitimate tool call to a non-calculation tool must not
    # satisfy this guard.
    hooks = _ProvenanceTrackingHooks()
    context = RunContextWrapper(context=ProvenanceTrackingContext())
    asyncio.run(hooks.on_tool_end(context, _DUMMY_AGENT, _FakeTool("search_knowledge"), None))
    assert context.context.calculation_tool_called is False


def test_hooks_do_not_set_the_flag_for_an_uncategorized_tool_name():
    hooks = _ProvenanceTrackingHooks()
    context = RunContextWrapper(context=ProvenanceTrackingContext())
    asyncio.run(hooks.on_tool_end(context, _DUMMY_AGENT, _FakeTool("not_a_real_tool"), None))
    assert context.context.calculation_tool_called is False


def test_guardrail_end_to_end_through_hooks_then_guardrail():
    # A tiny integration of the two halves this construction actually pairs
    # on one Agent (build_role_agent wires both onto the same Agent, and
    # Runner.run would share one RunContextWrapper across both): the hook
    # records a calculation-tool call, and the guardrail -- reading the SAME
    # context object afterward -- accepts the CALCULATED claim as a result.
    context = RunContextWrapper(context=ProvenanceTrackingContext())
    hooks = _ProvenanceTrackingHooks()
    asyncio.run(hooks.on_tool_end(context, _DUMMY_AGENT, _FakeTool("calculate_cascade_gain"), None))
    result = _run_guardrail(context, "Cascaded noise figure: 3.47 dB (CALCULATED).")
    assert result.output.tripwire_triggered is False


# ---------------------------------------------------------------------------
# Real MCP-protocol round trip: for every one of the six roles, spawn the
# real mcp_server/server.py subprocess (same entry point tests/test_mcp_
# server_protocol.py already spawns) with that role's tool_filter attached,
# and confirm the actual wire-level tools/list response is restricted to
# exactly that role's allow-list -- not just that the config literal says
# so. This is what actually exercises agents.mcp.MCPServerStdio's own
# _apply_static_tool_filter code path this repo now depends on.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("role_key", ROLE_KEYS)
async def test_role_scoped_mcp_server_lists_exactly_that_roles_tools(role_key):
    server = build_role_mcp_server(role_key)
    async with server:
        tools = await server.list_tools()
    names = {tool.name for tool in tools}
    assert names == set(ROLE_MCP_TOOL_FILTERS[role_key]["allowed_tool_names"])


@pytest.mark.asyncio
async def test_verification_role_server_never_lists_a_principal_only_tool():
    # A concrete negative check alongside the exact-set check above: a tool
    # genuinely absent from a narrow role's allow-list (verification, 4
    # tools) must never leak through over the real wire protocol.
    server = build_role_mcp_server("verification")
    async with server:
        tools = await server.list_tools()
    names = {tool.name for tool in tools}
    assert "create_design" not in names
    assert "run_candidate_search" not in names


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
