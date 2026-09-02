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
    _ALL_TOOLS,
    _SPEC_BY_KEY,
    DELEGATION_TOOLS,
    ROLE_SPECS,
    ROLES,
    _specialist_output_tag,
    principal,
)
from orchestration.policy import assert_all_tools_categorized


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
    # 11 pre-#36 calculation/knowledge tools, the 35 Phase 1-2 tools added
    # by issue #36, the search_design_records tool added by issue #37, the
    # run_nec2_simulation tool added by issue #38, the run_openems_simulation
    # tool added by issue #39, the run_hfss_simulation tool added by issue
    # #40, the optimize_patch_length_for_target_frequency tool added by
    # issue #41, the request_vna_measurement_approval and
    # measure_vna_s_parameters tools added by issue #43, the 6 spectrum
    # analyzer/signal generator/power meter approval+measure/actuate tools
    # added by issue #44, the correlate_simulated_and_measured tool added
    # by issue #45, the 3 design-iteration-loop tools (start_design_loop,
    # advance_design_loop_step, inspect_design_loop_state) added by issue
    # #46, the 4 design-lifecycle tools (create_design, read_design,
    # record_decision, verify_requirement) from a separately-merged PR
    # (#15, docs/adr/0005-0007) reconciled into this branch's specialist-role
    # tool set, the run_openparem_simulation tool added by issue #62, plus 5
    # consult_<role>_role delegation tools (issue #35), one per non-principal
    # specialist.
    assert len(names) == 73


def test_principal_module_alias_matches_registry():
    assert principal is ROLES["principal"]


def test_every_tool_in_all_tools_is_categorized_in_tool_policy():
    # Mirrors the import-time assert_all_tools_categorized() call right
    # after _ALL_TOOLS is built in agent/main.py -- this test makes the
    # same guarantee explicit and independently re-checkable here.
    assert_all_tools_categorized([tool.name for tool in _ALL_TOOLS])


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
    # issue #45: quantifying simulated-vs-measured trust is test-engineering work
    assert "correlate_simulated_and_measured" in names
    # test role validates hardware, it doesn't author the knowledge base
    assert "ingest_document" not in names
    assert "extract_components" not in names


def test_verification_role_gets_knowledge_auditing_tools():
    names = _tool_names(ROLES["verification"])
    assert "read_document" in names
    assert "extract_components" in names
    # verification audits documented claims, it does not run RF arithmetic
    assert "calculate_wavelength" not in names
    assert "correlate_simulated_and_measured" not in names
    # authoring belongs to systems, not verification
    assert "ingest_document" not in names


def test_search_design_records_is_scoped_to_principal_and_verification():
    # issue #37: precedent lookup is a knowledge-audit concern, same family
    # as read_document/extract_components -- narrower than search_knowledge,
    # which every role shares.
    assert "search_design_records" in _tool_names(ROLES["principal"])
    assert "search_design_records" in _tool_names(ROLES["verification"])
    for key in ("systems", "microwave", "antenna", "test"):
        assert "search_design_records" not in _tool_names(ROLES[key])


# ---------------------------------------------------------------------------
# Issue #36: Phase 1-2 calculation/Touchstone tools' role scoping.
#
# These tests check role-tool-list coverage only, per the ticket's own
# testing decision -- the underlying tool wiring (each new tool calls
# through to its rf_tools function correctly) is exercised in
# test_mcp_server.py, and the tools' own math is covered by
# test_calculations.py/test_touchstone.py.
# ---------------------------------------------------------------------------


def test_systems_role_gets_link_budget_and_ip3_and_unit_converters():
    names = _tool_names(ROLES["systems"])
    assert "calculate_free_space_path_loss" in names
    assert "calculate_link_budget_margin" in names
    assert "calculate_cascade_output_ip3" in names
    assert "convert_db_to_linear" in names
    assert "convert_linear_to_db" in names
    # network-parameter conversions and stability/matching are microwave's job
    assert "convert_s_to_z" not in names
    assert "calculate_rollett_k_factor" not in names
    # antenna synthesis is the antenna role's job
    assert "calculate_aperture_gain" not in names


def test_microwave_role_gets_conversions_stability_and_matching():
    names = _tool_names(ROLES["microwave"])
    for tool_name in (
        "convert_s_to_z",
        "convert_z_to_s",
        "convert_s_to_y",
        "convert_y_to_s",
        "convert_s_to_abcd",
        "convert_abcd_to_s",
    ):
        assert tool_name in names, f"missing {tool_name!r} from microwave role"
    assert "calculate_rollett_k_factor" in names
    assert "calculate_stability_verdict" in names
    assert "calculate_output_stability_circle" in names
    assert "calculate_input_stability_circle" in names
    assert "calculate_stability_delta" in names
    assert "calculate_quarter_wave_transformer_impedance" in names
    assert "calculate_l_network_match" in names
    # shared with systems: linearity budgeting is both chain- and
    # component-level, same overlap already established for noise figure
    assert "calculate_cascade_output_ip3" in names
    # link budget and antenna synthesis are not microwave's job
    assert "calculate_link_budget_margin" not in names
    assert "calculate_aperture_gain" not in names


def test_antenna_role_gets_antenna_synthesis_tools():
    names = _tool_names(ROLES["antenna"])
    for tool_name in (
        "calculate_patch_effective_permittivity",
        "calculate_patch_length_extension",
        "calculate_patch_resonant_frequency",
        "calculate_fractional_bandwidth_from_q",
        "calculate_quality_factor_from_fractional_bandwidth",
        "calculate_curvature_length_correction_factor",
        "calculate_curvature_shifted_resonant_frequency",
        "calculate_maxwell_garnett_effective_permeability",
        "calculate_aperture_gain",
    ):
        assert tool_name in names, f"missing {tool_name!r} from antenna role"
    # S/Z/Y/ABCD conversions and stability/matching are microwave's job
    assert "convert_s_to_z" not in names
    assert "calculate_rollett_k_factor" not in names
    # link budget is systems' job
    assert "calculate_link_budget_margin" not in names


def test_antenna_and_test_roles_get_nec2_simulation():
    # issue #38: simulating a wire-antenna structure is antenna-element
    # work, and its SIMULATED-provenance result is something a measured
    # result gets validated against in test engineering.
    assert "run_nec2_simulation" in _tool_names(ROLES["antenna"])
    assert "run_nec2_simulation" in _tool_names(ROLES["test"])
    # not systems/microwave/verification's job
    assert "run_nec2_simulation" not in _tool_names(ROLES["systems"])
    assert "run_nec2_simulation" not in _tool_names(ROLES["microwave"])
    assert "run_nec2_simulation" not in _tool_names(ROLES["verification"])


def test_antenna_and_test_roles_get_openems_simulation():
    # issue #39: openEMS FDTD simulation is the antenna-element counterpart
    # to NEC2++ for conformal/metamaterial geometry NEC2++ can't adequately
    # model, and (like run_nec2_simulation) its SIMULATED-provenance result
    # is something a measured result gets validated against in test
    # engineering.
    assert "run_openems_simulation" in _tool_names(ROLES["antenna"])
    assert "run_openems_simulation" in _tool_names(ROLES["test"])
    # not systems/microwave/verification's job
    assert "run_openems_simulation" not in _tool_names(ROLES["systems"])
    assert "run_openems_simulation" not in _tool_names(ROLES["microwave"])
    assert "run_openems_simulation" not in _tool_names(ROLES["verification"])


def test_antenna_and_test_roles_get_hfss_simulation():
    # issue #40: full-wave HFSS/PyAEDT simulation, confined to a controlled
    # licensed workstation, is the same antenna-element/test-reference-
    # result family as run_nec2_simulation/run_openems_simulation.
    assert "run_hfss_simulation" in _tool_names(ROLES["antenna"])
    assert "run_hfss_simulation" in _tool_names(ROLES["test"])
    # not systems/microwave/verification's job
    assert "run_hfss_simulation" not in _tool_names(ROLES["systems"])
    assert "run_hfss_simulation" not in _tool_names(ROLES["microwave"])
    assert "run_hfss_simulation" not in _tool_names(ROLES["verification"])


def test_antenna_role_gets_patch_length_optimization_tool():
    # issue #41: searching patch length against a target resonant frequency
    # via the generic optimization/ package composes with the Phase 1
    # antenna-synthesis tool this role already owns.
    assert "optimize_patch_length_for_target_frequency" in _tool_names(ROLES["antenna"])
    assert "optimize_patch_length_for_target_frequency" in _tool_names(ROLES["principal"])
    # not systems/microwave/test/verification's job
    assert "optimize_patch_length_for_target_frequency" not in _tool_names(ROLES["systems"])
    assert "optimize_patch_length_for_target_frequency" not in _tool_names(ROLES["microwave"])
    assert "optimize_patch_length_for_target_frequency" not in _tool_names(ROLES["test"])
    assert "optimize_patch_length_for_target_frequency" not in _tool_names(ROLES["verification"])


def test_test_role_gets_new_touchstone_tools():
    names = _tool_names(ROLES["test"])
    assert "interpolate_touchstone_file" in names
    assert "deembed_touchstone_file" in names
    assert "cascade_touchstone_files" in names
    assert "compare_touchstone_files" in names
    # antenna synthesis and link budget are not test's job
    assert "calculate_aperture_gain" not in names
    assert "calculate_link_budget_margin" not in names


def test_verification_role_gets_no_new_calculation_tools():
    names = _tool_names(ROLES["verification"])
    # verification audits documented claims, it does not run RF arithmetic --
    # none of the issue #36 tools belong here either.
    assert "convert_db_to_linear" not in names
    assert "calculate_aperture_gain" not in names
    assert "interpolate_touchstone_file" not in names


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
