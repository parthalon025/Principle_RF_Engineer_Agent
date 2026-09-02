"""Thin wiring tests for the specialist-role split (issue #34) and the
principal's delegation/synthesis mechanism (issue #35).

These tests confirm each role is constructible and that its tool list is
scoped to its stated domain. They deliberately do NOT re-test the tools'
own logic -- that is already covered by test_calculations.py,
test_touchstone.py, and the knowledge test suite.

The issue #35 tests exercise the delegation mechanism (Agent.as_tool()
wiring and the deterministic role-citation tag) at the level that is
genuinely testable without a configured OPENAI_API_KEY / local LLM backend
in this environment (see test_literature_corpus.py for the same
missing-credential constraint elsewhere in this repo). A full live
multi-domain query through Runner.run_sync is NOT exercised here -- there
is no model credential in this environment to run it against, and no
existing test in this repo calls Runner/Agent against a real model to use
as precedent. What IS verified: the principal role has a delegation tool
registered per specialist role, each tool wraps the correct specialist
Agent, and the deterministic output-tagging function produces the
documented "[Role Name] ..." citation format the principal is instructed
to carry through into its final answer.
"""

from types import SimpleNamespace

from agent.main import (
    _SPEC_BY_KEY,
    DELEGATION_TOOLS,
    ROLE_SPECS,
    ROLES,
    _specialist_output_tag,
    principal,
)


def _tool_names(agent) -> set[str]:
    return {tool.name for tool in agent.tools}


def test_all_six_roles_are_constructible():
    expected_keys = {"principal", "systems", "microwave", "antenna", "test", "verification"}
    assert set(ROLES.keys()) == expected_keys
    for key in expected_keys:
        assert ROLES[key] is not None


def test_every_role_has_a_non_empty_tool_list():
    for spec in ROLE_SPECS:
        assert len(spec.tools) > 0, f"role {spec.key!r} has no tools"
        assert len(ROLES[spec.key].tools) > 0, f"role {spec.key!r} has no tools"


def test_principal_role_has_broad_access():
    names = _tool_names(ROLES["principal"])
    assert "calculate_wavelength" in names
    assert "ingest_document" in names
    assert "extract_components" in names
    assert "analyze_touchstone_file" in names
    # principal is the coordinating role and is deliberately unscoped: the
    # 11 calculation/knowledge tools plus 5 consult_<role>_role delegation
    # tools (issue #35), one per non-principal specialist.
    assert len(names) == 16


def test_principal_module_alias_matches_registry():
    assert principal is ROLES["principal"]


def test_systems_role_gets_calculations_and_knowledge_authoring():
    names = _tool_names(ROLES["systems"])
    assert "calculate_cascade_gain" in names
    assert "ingest_document" in names
    # network-level (not systems-level) tool
    assert "analyze_touchstone_file" not in names
    # knowledge-auditing tool belongs to verification, not systems
    assert "extract_components" not in names


def test_microwave_role_gets_network_and_component_analysis():
    names = _tool_names(ROLES["microwave"])
    assert "analyze_touchstone_file" in names
    assert "calculate_vswr" in names
    # system-chain concern, not a single component/network concern
    assert "calculate_cascade_gain" not in names
    # knowledge authoring is out of the microwave domain
    assert "ingest_document" not in names


def test_antenna_role_gets_antenna_relevant_tools():
    names = _tool_names(ROLES["antenna"])
    assert "calculate_wavelength" in names
    assert "analyze_touchstone_file" in names
    # receiver-chain concerns, not the antenna element itself
    assert "calculate_noise_figure" not in names
    assert "ingest_document" not in names


def test_test_role_gets_verification_and_measurement_tools():
    names = _tool_names(ROLES["test"])
    assert "analyze_touchstone_file" in names
    assert "calculate_cascade_gain" in names
    # test role validates hardware, it doesn't author the knowledge base
    assert "ingest_document" not in names
    assert "extract_components" not in names


def test_verification_role_gets_knowledge_auditing_tools():
    names = _tool_names(ROLES["verification"])
    assert "read_document" in names
    assert "extract_components" in names
    # verification audits documented claims, it does not run RF arithmetic
    assert "calculate_wavelength" not in names
    # authoring belongs to systems, not verification
    assert "ingest_document" not in names


def test_search_knowledge_is_shared_by_every_role():
    for spec in ROLE_SPECS:
        assert "search_knowledge" in _tool_names(ROLES[spec.key]), (
            f"role {spec.key!r} should share search_knowledge"
        )


def test_no_role_has_a_tool_outside_all_currently_wired_tools():
    all_wired = _tool_names(ROLES["principal"])
    for spec in ROLE_SPECS:
        role_names = _tool_names(ROLES[spec.key])
        assert role_names <= all_wired, f"role {spec.key!r} has an unexpected tool"


# ---------------------------------------------------------------------------
# Issue #35: principal delegation and synthesis.
#
# `Agent.as_tool()` runs the nested specialist agent through `Runner.run`,
# which requires a live model call -- not feasible in this environment (no
# OPENAI_API_KEY, no LOCAL_LLM_BASE_URL; see module docstring). These tests
# instead verify the delegation mechanism's wiring and its deterministic,
# non-LLM-dependent piece: the role-citation tag every delegated result is
# stamped with before it can reach the principal's synthesis.
# ---------------------------------------------------------------------------

_SPECIALIST_KEYS = ["systems", "microwave", "antenna", "test", "verification"]


def test_principal_has_one_delegation_tool_per_specialist_role():
    names = _tool_names(ROLES["principal"])
    for key in _SPECIALIST_KEYS:
        assert f"consult_{key}_role" in names, f"missing delegation tool for {key!r}"
    # principal does not delegate to itself
    assert "consult_principal_role" not in names


def test_delegation_tools_registry_matches_specialist_keys():
    assert set(DELEGATION_TOOLS.keys()) == set(_SPECIALIST_KEYS)


def test_each_delegation_tool_wraps_the_correct_specialist_agent():
    for key in _SPECIALIST_KEYS:
        tool = DELEGATION_TOOLS[key]
        assert tool.name == f"consult_{key}_role"
        # Agent.as_tool() stamps the wrapped Agent instance on the FunctionTool
        # it returns -- confirm each delegation tool actually wraps *that*
        # specialist's Agent, not some other role's.
        assert tool._agent_instance is ROLES[key]
        assert tool._agent_instance.name == _SPEC_BY_KEY[key].display_name


def test_delegation_tool_description_names_its_role_and_citation_format():
    for key in _SPECIALIST_KEYS:
        tool = DELEGATION_TOOLS[key]
        display_name = _SPEC_BY_KEY[key].display_name
        assert display_name in tool.description
        assert f"[{display_name}]" in tool.description


def test_principal_instructions_direct_it_to_delegate_and_cite_roles():
    instructions = ROLES["principal"].instructions
    assert "consult_<role>_role" in instructions
    assert "specialist role(s) contributed" in instructions


def test_specialist_output_tag_produces_the_documented_citation_format():
    spec = _SPEC_BY_KEY["antenna"]
    stub_run_result = SimpleNamespace(final_output="Resonant length: 12.4 mm (CALCULATED).")
    tagged = _specialist_output_tag(spec, stub_run_result)
    assert tagged == "[Antenna Engineer] Resonant length: 12.4 mm (CALCULATED)."
    assert tagged.startswith(f"[{spec.display_name}]")


def test_multi_domain_query_synthesis_cites_both_contributing_roles():
    """Representative multi-domain scenario from the ticket: an antenna-
    sizing question that also needs a stability check (test/verification-
    adjacent). Exercises the same tagging function `Agent.as_tool()`'s
    `custom_output_extractor` calls for each delegated result, then confirms
    a synthesized answer built from both tagged results attributes each
    contribution to its own specialist role -- without invoking a live
    model."""
    antenna_spec = _SPEC_BY_KEY["antenna"]
    test_spec = _SPEC_BY_KEY["test"]

    antenna_result = SimpleNamespace(
        final_output=(
            "For 2.45 GHz, a half-wave dipole is ~61.2 mm "
            "(wavelength=122.4 mm, CALCULATED)."
        )
    )
    stability_result = SimpleNamespace(
        final_output=(
            "Measured VSWR=1.42 at the antenna port is within the 2:1 spec "
            "(CALCULATED); no stability concern from this Touchstone data."
        )
    )

    antenna_contribution = _specialist_output_tag(antenna_spec, antenna_result)
    test_contribution = _specialist_output_tag(test_spec, stability_result)

    # This mirrors what the principal's synthesis step composes from its two
    # consult_<role>_role tool calls: each specialist's citation-tagged
    # contribution, concatenated into one answer.
    synthesized_answer = f"{antenna_contribution}\n\n{test_contribution}"

    assert "[Antenna Engineer]" in synthesized_answer
    assert "[Test Engineer]" in synthesized_answer
    assert "61.2 mm" in synthesized_answer
    assert "VSWR=1.42" in synthesized_answer
    # Each specialist's own text stays out of the other's citation block.
    antenna_block, test_block = synthesized_answer.split("\n\n")
    assert "VSWR" not in antenna_block
    assert "wavelength" not in test_block
