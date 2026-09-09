"""Thin wiring tests for the specialist-role split (issue #34) and the
principal's routing mechanism (issue #35, redesigned).

These tests confirm each role is constructible and that its tool list is
scoped to its stated domain. They deliberately do NOT re-test the tools'
own logic -- that is already covered by test_calculations.py,
test_touchstone.py, and the knowledge test suite.

The routing mechanism was originally built on `Agent.as_tool()` (a nested
Runner.run() call per delegated question, with a deterministic
`custom_output_extractor` stamping a "[Role Name] ..." citation onto each
specialist's result so the principal could synthesize multiple
contributions into one cited answer). It was replaced with
`Agent(handoffs=[...])` after live testing against a real local model
(qwen3.8:27b via Ollama) reproduced a real, repeatable failure specific to
the nested shape -- see agent/main.py's routing section for the full
account and the upstream bug reports it traces to (Qwen3.8's official chat
template hard-crashing on a message sequence with no genuine `user` turn,
which is exactly what `.as_tool()`'s nested call constructs). Handoffs
transfer control within the SAME Runner.run() call instead, sidestepping
that failure mode structurally -- at the cost of the old citation-synthesis
behavior: the principal now routes to ONE specialist per question, and that
specialist's own answer becomes the run's final output directly, with no
principal-side re-synthesis step.

These tests exercise the routing mechanism's wiring at the level that is
genuinely testable without a configured OPENAI_API_KEY / local LLM backend
in this environment (see test_literature_corpus.py for the same
missing-credential constraint elsewhere in this repo). A full live routed
query through Runner.run_sync is NOT exercised here for that reason --
the real, live re-test (against real Ollama/qwen3.8) that validated this
redesign in the first place lives outside this repo's automated suite (see
this session's own record, not a file in this tree). What IS verified:
the principal role has exactly one handoff registered per specialist role,
each handoff targets the correct specialist Agent, and the principal's own
direct tool list holds only what's genuinely principal-exclusive.
"""

from types import SimpleNamespace

import pytest

from agent.main import (
    _ALL_TOOLS,
    _SPEC_BY_KEY,
    ROLE_SPECS,
    ROLES,
    SPECIALIST_HANDOFFS,
    ProvenanceIntegrityError,
    _assert_calculated_provenance_is_tool_backed,
    principal,
    run_meep_simulation,
)
from orchestration.policy import assert_all_tools_categorized, category_for


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


def test_principal_role_is_scoped_not_broad():
    """Superseded by this repo's own real-world local-model testing: giving
    one agent all 86 calculation/simulation tools at once (the "principal is
    deliberately unscoped" design this test used to assert, and the
    docstring history below this comment used to track fact-by-fact)
    measurably breaks tool-selection reliability on a local model -- a
    91-tool principal (86 + 5 delegation tools) never called a real tool at
    all in live testing against qwen3.8:27b/Ollama, claiming tools it
    plainly had didn't exist. This matches Anthropic's own published tool
    design guidance ("fewer, higher-leverage tools beat many overlapping
    ones") and DeepSeek Harness's production tool registry, which stays
    explicitly *scoped* per agent even at thousands-of-plugins scale.

    The fix: the principal now holds only tools with no other home (the
    design-record/lifecycle tools and the design-iteration-loop tools,
    genuinely principal-exclusive -- no specialist role holds them) plus
    the two search tools it already shared, plus 5 `route_to_<role>_role`
    handoffs (`agent.handoffs`, not `agent.tools` -- see
    test_principal_has_one_handoff_per_specialist_role for why this moved
    off `Agent.as_tool()` entirely, not just a smaller tool list). Every
    specialist calculation/simulation tool is still fully reachable, just
    through a handoff rather than directly -- nothing lost, only routed
    through a smaller, more reliable per-call tool surface. See
    agent/main.py's `_PRINCIPAL_DIRECT_TOOLS` for the exact, reasoned
    list."""
    names = _tool_names(ROLES["principal"])
    # Specialist-domain tools are reachable only via handoff now, not directly.
    assert "calculate_wavelength" not in names
    assert "ingest_document" not in names
    assert "ingest_arxiv_paper" not in names
    assert "ingest_3gpp_spec" not in names
    assert "ingest_etsi_standard" not in names
    assert "ingest_etsi_ipr_declaration" not in names
    assert "ingest_fcc_rule" not in names
    assert "ingest_patent" not in names
    assert "extract_components" not in names
    assert "analyze_touchstone_file" not in names
    # Design-record/lifecycle tools: still principal-exclusive, still direct.
    for tool_name in (
        "create_design",
        "read_design",
        "record_decision",
        "verify_requirement",
        "advance_design_status",
        "propose_requirement_target",
        "mark_requirement_unscoreable",
        "confirm_requirement_target",
    ):
        assert tool_name in names
    # Shared search tools: still direct.
    assert "search_knowledge" in names
    assert "search_design_records" in names
    # Design-iteration-loop tools (issue #46/#94/#95): still principal-exclusive, still direct.
    for tool_name in (
        "start_design_loop",
        "advance_design_loop_step",
        "inspect_design_loop_state",
        "compile_lab_test_plan",
        "run_candidate_search",
    ):
        assert tool_name in names
    # 8 design-record + 2 search + 5 design-loop = 15 direct tools. The 5
    # specialist handoffs are NOT in .tools -- see the handoff-specific
    # tests below for those.
    assert len(names) == 15


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
    assert "ingest_arxiv_paper" in names
    assert "ingest_patent" in names
    # network-level (not systems-level) tool
    assert "analyze_touchstone_file" not in names
    # knowledge-auditing tool belongs to verification, not systems
    assert "extract_components" not in names


def test_systems_role_gets_standards_body_sourcing_tools():
    # issue #215: 3GPP/ETSI/FCC-eCFR standards ingestion is the same
    # knowledge-authoring concern as ingest_document/ingest_arxiv_paper --
    # "bring an external document into the knowledge base", each with its
    # own fetch/extraction step ahead of it.
    names = _tool_names(ROLES["systems"])
    assert "ingest_3gpp_spec" in names
    assert "ingest_etsi_standard" in names
    assert "ingest_fcc_rule" in names
    for key in ("microwave", "antenna", "test", "verification"):
        role_names = _tool_names(ROLES[key])
        assert "ingest_3gpp_spec" not in role_names
        assert "ingest_etsi_standard" not in role_names
        assert "ingest_fcc_rule" not in role_names


def test_systems_role_gets_etsi_ipr_declaration_sourcing_tool():
    # issue #284: ingest_etsi_ipr_declaration (the SR 000 314 IPR/FRAND-
    # declaration register client) is the same knowledge-authoring concern
    # as its ingest_etsi_standard sibling -- same bucket, same reasoning.
    names = _tool_names(ROLES["systems"])
    assert "ingest_etsi_ipr_declaration" in names
    for key in ("microwave", "antenna", "test", "verification"):
        role_names = _tool_names(ROLES[key])
        assert "ingest_etsi_ipr_declaration" not in role_names
    # Not principal-direct either -- reachable via the systems handoff only.
    assert "ingest_etsi_ipr_declaration" not in _tool_names(ROLES["principal"])


def test_systems_role_gets_patent_sourcing_tool():
    # issue #219: fetching a USPTO patent grant/publication is the same
    # knowledge-authoring concern as ingest_arxiv_paper/ingest_3gpp_spec/
    # ingest_etsi_standard/ingest_fcc_rule -- same bucket, same reasoning.
    names = _tool_names(ROLES["systems"])
    assert "ingest_patent" in names
    for key in ("microwave", "antenna", "test", "verification"):
        role_names = _tool_names(ROLES[key])
        assert "ingest_patent" not in role_names


def test_systems_role_gets_arxiv_discovery_search_tool():
    # issue #257-T2: search_arxiv_papers (topic/keyword discovery, issue
    # #257-T1's knowledge/sourcing/arxiv.py addition) is wired onto the same
    # role as its sibling ingest_arxiv_paper -- both are the same "bring
    # arXiv into reach of the design loop" knowledge-sourcing concern,
    # discovery finding candidates ahead of the deliberate ingest step.
    names = _tool_names(ROLES["systems"])
    assert "search_arxiv_papers" in names
    for key in ("microwave", "antenna", "test", "verification"):
        role_names = _tool_names(ROLES[key])
        assert "search_arxiv_papers" not in role_names
    # Not principal-direct either -- reachable via the systems handoff only,
    # same as ingest_arxiv_paper (see test_principal_role_is_scoped_not_broad).
    assert "search_arxiv_papers" not in _tool_names(ROLES["principal"])


def test_search_arxiv_papers_is_categorized_ingestion_auto():
    # Matches ingest_arxiv_paper's category: a knowledge/sourcing operation,
    # not a calculation -- see policies/tool_policy.yaml's ingestion_auto
    # comment on why a credential-free arXiv sourcing call belongs here even
    # though this particular tool, unlike its ingest_arxiv_paper sibling,
    # never itself writes a document.
    assert category_for("search_arxiv_papers") == category_for("ingest_arxiv_paper")
    assert category_for("search_arxiv_papers") == "ingestion_auto"


def test_systems_role_gets_component_sourcing_tools():
    # ticket #67: sourcing a datasheet straight from a distributor and
    # reconciling it into one components row is the same knowledge-
    # authoring concern as ingest_document/index_document.
    names = _tool_names(ROLES["systems"])
    assert "lookup_digikey_component" in names
    assert "lookup_mouser_component" in names
    assert "lookup_nexar_component" in names
    assert "reconcile_component_sources" in names
    for key in ("microwave", "antenna", "test", "verification"):
        role_names = _tool_names(ROLES[key])
        assert "lookup_digikey_component" not in role_names
        assert "lookup_mouser_component" not in role_names
        assert "lookup_nexar_component" not in role_names
        assert "reconcile_component_sources" not in role_names


def test_microwave_role_gets_network_and_component_analysis():
    names = _tool_names(ROLES["microwave"])
    assert "analyze_touchstone_file" in names
    assert "calculate_vswr" in names
    # system-chain concern, not a single component/network concern
    assert "calculate_cascade_gain" not in names
    # knowledge authoring is out of the microwave domain
    assert "ingest_document" not in names
    assert "ingest_arxiv_paper" not in names
    assert "ingest_patent" not in names


def test_antenna_role_gets_antenna_relevant_tools():
    names = _tool_names(ROLES["antenna"])
    assert "calculate_wavelength" in names
    assert "analyze_touchstone_file" in names
    # receiver-chain concerns, not the antenna element itself
    assert "calculate_noise_figure" not in names
    assert "ingest_document" not in names
    assert "ingest_arxiv_paper" not in names
    assert "ingest_patent" not in names


def test_test_role_gets_verification_and_measurement_tools():
    names = _tool_names(ROLES["test"])
    assert "analyze_touchstone_file" in names
    assert "calculate_cascade_gain" in names
    # issue #45: quantifying simulated-vs-measured trust is test-engineering work
    assert "correlate_simulated_and_measured" in names
    # test role validates hardware, it doesn't author the knowledge base
    assert "ingest_document" not in names
    assert "ingest_arxiv_paper" not in names
    assert "ingest_patent" not in names
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


def test_antenna_and_test_roles_get_elmer_simulation():
    # issue #64: Elmer FEM's VectorHelmholtz module is a general,
    # multiphysics-ready EM cross-check kept available for a future
    # coupled-physics need -- same antenna-element/test-reference-result
    # family as run_nec2_simulation/run_openems_simulation/run_hfss_
    # simulation, despite having no native S-parameter/far-field/gain
    # post-processing of its own (see simulation/elmer.py).
    assert "run_elmer_simulation" in _tool_names(ROLES["antenna"])
    assert "run_elmer_simulation" in _tool_names(ROLES["test"])
    # not systems/microwave/verification's job
    assert "run_elmer_simulation" not in _tool_names(ROLES["systems"])
    assert "run_elmer_simulation" not in _tool_names(ROLES["microwave"])
    assert "run_elmer_simulation" not in _tool_names(ROLES["verification"])


def test_antenna_and_test_roles_get_openparem_simulation():
    # issue #62: OpenParEM3D full-wave FEM simulation, computing antenna
    # far-field gain/directivity/radiation-efficiency from the same solve
    # as its S-parameters, is the same antenna-element/test-reference-
    # result family as run_nec2_simulation/run_openems_simulation/run_hfss_
    # simulation.
    assert "run_openparem_simulation" in _tool_names(ROLES["antenna"])
    assert "run_openparem_simulation" in _tool_names(ROLES["test"])
    # not systems/microwave/verification's job
    assert "run_openparem_simulation" not in _tool_names(ROLES["systems"])
    assert "run_openparem_simulation" not in _tool_names(ROLES["microwave"])
    assert "run_openparem_simulation" not in _tool_names(ROLES["verification"])


def test_antenna_and_test_roles_get_kicad_gerber2ems_simulation():
    # issue #65: deriving PCB signal-integrity simulation geometry from a
    # real, as-laid-out KiCad PCB design (trace impedance, via/stackup
    # S-parameters) is antenna-feed-network geometry-prep/reference-result
    # work, same family as run_nec2_simulation/run_openems_simulation.
    assert "run_kicad_gerber2ems_simulation" in _tool_names(ROLES["antenna"])
    assert "run_kicad_gerber2ems_simulation" in _tool_names(ROLES["test"])
    # not systems/microwave/verification's job
    assert "run_kicad_gerber2ems_simulation" not in _tool_names(ROLES["systems"])
    assert "run_kicad_gerber2ems_simulation" not in _tool_names(ROLES["microwave"])
    assert "run_kicad_gerber2ems_simulation" not in _tool_names(ROLES["verification"])


def test_antenna_and_test_roles_get_palace_simulation():
    # issue #61: Palace's native Floquet/periodic-boundary full-wave
    # simulation of a periodic metamaterial unit cell is the same
    # antenna-element/test-reference-result family as run_nec2_simulation/
    # run_openems_simulation/run_hfss_simulation.
    assert "run_palace_simulation" in _tool_names(ROLES["antenna"])
    assert "run_palace_simulation" in _tool_names(ROLES["test"])
    # not systems/microwave/verification's job
    assert "run_palace_simulation" not in _tool_names(ROLES["systems"])
    assert "run_palace_simulation" not in _tool_names(ROLES["microwave"])
    assert "run_palace_simulation" not in _tool_names(ROLES["verification"])


def test_microwave_and_test_roles_get_qucs_simulation():
    # issue #58: Qucs-S/qucsator_rf native multi-port S-parameter circuit
    # simulation is component/network-level work, not antenna-element
    # work -- like run_ltspice_simulation/run_ngspice_simulation/
    # run_xyce_simulation, it belongs with microwave (not antenna), and
    # (like the full-wave simulators) with test as a SIMULATED-provenance
    # reference result to validate hardware against.
    assert "run_qucs_simulation" in _tool_names(ROLES["microwave"])
    assert "run_qucs_simulation" in _tool_names(ROLES["test"])
    # not systems/antenna/verification's job
    assert "run_qucs_simulation" not in _tool_names(ROLES["systems"])
    assert "run_qucs_simulation" not in _tool_names(ROLES["antenna"])
    assert "run_qucs_simulation" not in _tool_names(ROLES["verification"])


def test_microwave_and_test_roles_get_ltspice_simulation():
    # issue #59: LTspice circuit simulation is component/network-level
    # (SPICE) work, not antenna-element work -- unlike run_nec2_simulation/
    # run_openems_simulation/run_hfss_simulation, it belongs with microwave
    # (not antenna), and (like the other three simulators) with test as a
    # SIMULATED-provenance reference result to validate hardware against.
    assert "run_ltspice_simulation" in _tool_names(ROLES["microwave"])
    assert "run_ltspice_simulation" in _tool_names(ROLES["test"])
    # not systems/antenna/verification's job
    assert "run_ltspice_simulation" not in _tool_names(ROLES["systems"])
    assert "run_ltspice_simulation" not in _tool_names(ROLES["antenna"])
    assert "run_ltspice_simulation" not in _tool_names(ROLES["verification"])


def test_microwave_and_test_roles_get_ngspice_and_xyce_simulation():
    # issue #57: free/open circuit-level SPICE simulation of a matching
    # network, filter, or amplifier sub-circuit is microwave/network-level
    # component-analysis work, and (like run_nec2_simulation/
    # run_openems_simulation/run_hfss_simulation) its SIMULATED-provenance
    # result is something a measured result gets validated against in test
    # engineering.
    for tool_name in ("run_ngspice_simulation", "run_xyce_simulation"):
        assert tool_name in _tool_names(ROLES["microwave"])
        assert tool_name in _tool_names(ROLES["test"])
        # principal reaches this via a route_to_microwave_role/route_to_test_role
        # handoff now, not directly -- see test_principal_role_is_scoped_not_broad.
        # not systems/antenna/verification's job
        assert tool_name not in _tool_names(ROLES["systems"])
        assert tool_name not in _tool_names(ROLES["antenna"])
        assert tool_name not in _tool_names(ROLES["verification"])


def test_antenna_and_test_roles_get_gprmax_simulation():
    # issue #63: gprMax FDTD simulation is the ground-coupled/lossy-half-
    # space counterpart to NEC2++/openEMS, for a host surface (soil,
    # concrete, a vehicle hull) neither of those can represent, and (like
    # run_nec2_simulation/run_openems_simulation) its SIMULATED-provenance
    # result is something a measured result gets validated against in test
    # engineering.
    assert "run_gprmax_simulation" in _tool_names(ROLES["antenna"])
    assert "run_gprmax_simulation" in _tool_names(ROLES["test"])
    # not systems/microwave/verification's job
    assert "run_gprmax_simulation" not in _tool_names(ROLES["systems"])
    assert "run_gprmax_simulation" not in _tool_names(ROLES["microwave"])
    assert "run_gprmax_simulation" not in _tool_names(ROLES["verification"])


def test_antenna_and_test_roles_get_meep_simulation():
    # issue #60: MEEP FDTD simulation is a second, independent full-wave
    # solver for cross-checking a design decision against
    # run_openems_simulation's own output -- same antenna-element/test-
    # reference-result family as run_nec2_simulation/run_openems_simulation/
    # run_hfss_simulation.
    assert "run_meep_simulation" in _tool_names(ROLES["antenna"])
    assert "run_meep_simulation" in _tool_names(ROLES["test"])
    # not systems/microwave/verification's job
    assert "run_meep_simulation" not in _tool_names(ROLES["systems"])
    assert "run_meep_simulation" not in _tool_names(ROLES["microwave"])
    assert "run_meep_simulation" not in _tool_names(ROLES["verification"])


def test_run_meep_simulation_tool_description_reflects_far_field_support():
    """agent/main.py's own @function_tool-wrapped run_meep_simulation (the
    surface an agent driven through this module -- as opposed to the MCP
    server -- actually sees) carries a FOURTH, independently-maintained copy
    of this tool's docstring, alongside simulation/meep.py's module
    docstring, mcp_server/server.py's tool docstring, and docs/tools/meep.md
    -- issue #270 named the first three as needing to change together and
    missed this one. `@function_tool`-wrapped functions expose their
    docstring text to the SDK via the `.description` attribute (see
    agents.tool.FunctionTool), not `.__doc__` on the wrapped callable, so
    this reads that attribute -- the same text an agent calling this tool
    surface is actually shown. Regression guard: an agent told outright "NO
    far-field/gain" never learns geometry['far_field_monitor'] exists."""
    description = run_meep_simulation.description
    assert "NO far-field/gain" not in description
    assert "far_field_monitor" in description
    assert "gain_dbi" in description


def test_antenna_role_gets_patch_length_optimization_tool():
    # issue #41: searching patch length against a target resonant frequency
    # via the generic optimization/ package composes with the Phase 1
    # antenna-synthesis tool this role already owns.
    assert "optimize_patch_length_for_target_frequency" in _tool_names(ROLES["antenna"])
    # principal reaches this via a route_to_antenna_role handoff now, not
    # directly -- see test_principal_role_is_scoped_not_broad.
    # not systems/microwave/test/verification's job
    assert "optimize_patch_length_for_target_frequency" not in _tool_names(ROLES["systems"])
    assert "optimize_patch_length_for_target_frequency" not in _tool_names(ROLES["microwave"])
    assert "optimize_patch_length_for_target_frequency" not in _tool_names(ROLES["test"])
    assert "optimize_patch_length_for_target_frequency" not in _tool_names(ROLES["verification"])


def test_antenna_role_gets_freecad_curved_geometry_tool():
    # issue #66: mapping a flat unit-cell/array layout onto a curved host
    # surface is a geometry-prep step that feeds run_openems_simulation's/
    # run_palace_simulation's own geometry dict -- same antenna-geometry-
    # generator family as optimize_patch_length_for_target_frequency, not a
    # SIMULATED-provenance reference result test would validate hardware
    # against.
    assert "generate_freecad_curved_geometry" in _tool_names(ROLES["antenna"])
    # principal reaches this via a route_to_antenna_role handoff now, not
    # directly -- see test_principal_role_is_scoped_not_broad.
    # not systems/microwave/test/verification's job
    assert "generate_freecad_curved_geometry" not in _tool_names(ROLES["systems"])
    assert "generate_freecad_curved_geometry" not in _tool_names(ROLES["microwave"])
    assert "generate_freecad_curved_geometry" not in _tool_names(ROLES["test"])
    assert "generate_freecad_curved_geometry" not in _tool_names(ROLES["verification"])


def test_test_role_gets_new_touchstone_tools():
    names = _tool_names(ROLES["test"])
    assert "interpolate_touchstone_file" in names
    assert "deembed_touchstone_file" in names
    assert "cascade_touchstone_files" in names
    assert "compare_touchstone_files" in names
    # antenna synthesis and link budget are not test's job
    assert "calculate_aperture_gain" not in names
    assert "calculate_link_budget_margin" not in names


def test_test_and_principal_roles_get_lab_test_plan_tool():
    # issue #94: read-only (no mutation, no approval) -- shared with test
    # (which owns lab-test-plan work day to day), unlike the mutating
    # design-loop tools (start_design_loop/advance_design_loop_step/
    # inspect_design_loop_state), which stay principal-only.
    assert "compile_lab_test_plan" in _tool_names(ROLES["principal"])
    assert "compile_lab_test_plan" in _tool_names(ROLES["test"])
    for key in ("systems", "microwave", "antenna", "verification"):
        assert "compile_lab_test_plan" not in _tool_names(ROLES[key])
    for key in ("systems", "microwave", "antenna", "test", "verification"):
        assert "start_design_loop" not in _tool_names(ROLES[key])
        assert "advance_design_loop_step" not in _tool_names(ROLES[key])
        assert "inspect_design_loop_state" not in _tool_names(ROLES[key])


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
    # Was `_tool_names(ROLES["principal"])` -- valid back when the principal
    # held every tool, no longer valid now that it's deliberately scoped
    # (see test_principal_role_is_scoped_not_broad). The true superset is
    # just _ALL_TOOLS now: every specialist's tools are drawn from it, and
    # the principal's route_to_<role>_role handoffs live in .handoffs, not
    # .tools, so they're a separate namespace this check doesn't need to
    # include (see test_principal_has_one_handoff_per_specialist_role for
    # that half).
    all_wired = {tool.name for tool in _ALL_TOOLS}
    for spec in ROLE_SPECS:
        role_names = _tool_names(ROLES[spec.key])
        assert role_names <= all_wired, f"role {spec.key!r} has an unexpected tool"


# ---------------------------------------------------------------------------
# Issue #35: principal routing (redesigned from delegation -- see this
# file's module docstring and agent/main.py's routing section for the full
# account of why).
#
# `Agent(handoffs=[...])` transfers control to the target agent within the
# SAME Runner.run() call -- there is no nested Runner.run(), so there is no
# live-model-call requirement to work around the way `Agent.as_tool()`
# testing had to (see this file's git history for that prior constraint).
# What's tested here is still just the wiring: each handoff targets the
# correct specialist Agent, with the right tool name and description. A
# full live routed query through Runner.run/Runner.run_sync is still not
# exercised in this automated suite (same missing-credential constraint as
# ever in this environment) -- that verification happened live against a
# real Ollama/qwen3.8 backend outside this repo's test suite.
# ---------------------------------------------------------------------------

_SPECIALIST_KEYS = ["systems", "microwave", "antenna", "test", "verification"]


def test_principal_has_one_handoff_per_specialist_role():
    handoff_tool_names = {h.tool_name for h in ROLES["principal"].handoffs}
    for key in _SPECIALIST_KEYS:
        assert f"route_to_{key}_role" in handoff_tool_names, f"missing handoff for {key!r}"
    assert "route_to_principal_role" not in handoff_tool_names
    # Handoffs are NOT tools -- confirm they don't leak into .tools too.
    assert not (handoff_tool_names & _tool_names(ROLES["principal"]))


def test_specialist_handoffs_registry_matches_specialist_keys():
    assert set(SPECIALIST_HANDOFFS.keys()) == set(_SPECIALIST_KEYS)


def test_each_handoff_targets_the_correct_specialist_agent():
    for key in _SPECIALIST_KEYS:
        h = SPECIALIST_HANDOFFS[key]
        assert h.tool_name == f"route_to_{key}_role"
        assert h.agent_name == ROLES[key].name
        assert h.agent_name == _SPEC_BY_KEY[key].display_name


def test_handoff_description_names_its_role():
    for key in _SPECIALIST_KEYS:
        h = SPECIALIST_HANDOFFS[key]
        display_name = _SPEC_BY_KEY[key].display_name
        assert display_name in h.tool_description


def test_principal_instructions_direct_it_to_route_not_delegate():
    instructions = ROLES["principal"].instructions
    assert "hand" in instructions.lower()
    # The old citation-synthesis framing is gone -- routing hands off
    # control entirely, there is no principal-side re-synthesis step.
    assert "specialist role(s) contributed" not in instructions


def test_principal_instructions_never_claim_reasoned_out_values_as_calculated():
    # Issue #158: the principal's own routing instructions must say, in
    # its own words, not to reach for CALCULATED on a value it reasoned out
    # itself rather than getting from a calculation tool/specialist.
    instructions = ROLES["principal"].instructions
    assert "CALCULATED" in instructions
    assert "INFERRED" in instructions


# ---------------------------------------------------------------------------
# Issue #158: a CALCULATED claim with no backing calculation-tool call is a
# provenance-integrity violation, not a labeling nuance -- CONTEXT.md's
# Provenance entry and prompts/principal_engineer.md's "Mandatory
# provenance" section both define CALCULATED as "deterministic
# calculation", specifically the kind the "Numerical discipline" section
# says to get from a tool instead of mental arithmetic. A live-reproduced
# failure (issue #158's own repro) showed the principal skipping both
# specialist routing and its own calculation tools, hand-computing a
# cascaded noise figure, and still labeling the answer (CALCULATED) --
# indistinguishable, to a reader, from a genuinely tool-verified result.
#
# `_assert_calculated_provenance_is_tool_backed` is the "cheap runtime
# guard" the issue's own suggested next steps floated: it inspects a
# RunResult's new_items for a `calculation`-category tool_call_item (see
# policies/tool_policy.yaml and orchestration/policy.py's `category_for`)
# and raises ProvenanceIntegrityError if none is found -- fail closed, the
# same idiom orchestration/policy.py's PolicyError already establishes for
# a policy violation, rather than silently letting a mislabeled claim
# through. Tested here with plain SimpleNamespace stand-ins for RunResult
# (matching this file's existing no-live-model-credential constraint, see
# module docstring) since the guard only reads `.final_output` and
# `.new_items[*].type`/`.new_items[*].tool_name`.
#
# ONLY A run()-LEVEL GUARD, NO SEPARATE SPECIALIST-SIDE HOOK: this branch's
# prior version (see git history) also guarded each specialist's nested
# result via the `Agent.as_tool()` `custom_output_extractor` hook. That
# hook doesn't exist post-#165 -- routing is now `Agent(handoffs=[...])`,
# which keeps a specialist's own tool calls in the SAME top-level
# RunResult.new_items the run()-level guard below already inspects (see
# agent/main.py's own module comment right above `run()` for how this was
# concretely verified against this repo's installed SDK, not assumed). The
# tests below exercise the guard function directly against synthetic
# new_items shaped like what a real routed run's accumulated new_items
# looks like post-handoff (a handoff_call_item/handoff_output_item pair
# followed by the specialist's own tool_call_item), to document that this
# one guard is sufficient for a handed-off answer too.
# ---------------------------------------------------------------------------


def test_calculated_claim_backed_by_a_calculation_tool_call_is_accepted():
    stub_result = SimpleNamespace(
        final_output="Cascaded noise figure: 3.47 dB (CALCULATED).",
        new_items=[SimpleNamespace(type="tool_call_item", tool_name="calculate_cascade_gain")],
    )
    _assert_calculated_provenance_is_tool_backed(stub_result)  # must not raise


def test_calculated_claim_with_no_tool_call_is_rejected():
    stub_result = SimpleNamespace(
        # issue #158's own live repro text.
        final_output="**3.47 dB** (CALCULATED)\n\nFriis Cascaded Noise Figure Breakdown: ...",
        new_items=[SimpleNamespace(type="message_output_item")],
    )
    with pytest.raises(ProvenanceIntegrityError):
        _assert_calculated_provenance_is_tool_backed(stub_result)


def test_calculated_claim_with_empty_item_list_is_rejected():
    stub_result = SimpleNamespace(
        final_output="Cascaded noise figure: 3.47 dB (CALCULATED).",
        new_items=[],
    )
    with pytest.raises(ProvenanceIntegrityError):
        _assert_calculated_provenance_is_tool_backed(stub_result)


def test_handoff_call_item_alone_does_not_back_a_calculated_claim():
    # A handoff transfers control to another agent; it is not itself a
    # deterministic calculation, so it must not satisfy the guard on its
    # own (mirrors issue #158's own "no handoff_call_item and no
    # tool_call_item" observation).
    stub_result = SimpleNamespace(
        final_output="3.47 dB (CALCULATED).",
        new_items=[SimpleNamespace(type="handoff_call_item", tool_name="route_to_systems_role")],
    )
    with pytest.raises(ProvenanceIntegrityError):
        _assert_calculated_provenance_is_tool_backed(stub_result)


def test_non_calculated_claim_needs_no_tool_call():
    # INFERRED/ASSUMED/etc. never claimed a tool verified them, so the
    # guard has nothing to enforce here.
    stub_result = SimpleNamespace(
        final_output="Rough order-of-magnitude estimate: ~3 dB (INFERRED), not tool-verified.",
        new_items=[],
    )
    _assert_calculated_provenance_is_tool_backed(stub_result)  # must not raise


def test_calculated_claim_with_a_non_tool_item_present_is_still_rejected():
    # A message or reasoning item in new_items must not be mistaken for a
    # tool call -- only an actual calculation-category tool_call_item backs
    # the label.
    stub_result = SimpleNamespace(
        final_output="3.47 dB (CALCULATED).",
        new_items=[
            SimpleNamespace(type="message_output_item"),
            SimpleNamespace(type="reasoning_item"),
        ],
    )
    with pytest.raises(ProvenanceIntegrityError):
        _assert_calculated_provenance_is_tool_backed(stub_result)


def test_calculated_claim_backed_by_an_unrelated_tool_call_is_still_rejected():
    # The real spec gap a reviewer of this branch's prior version found:
    # calling SOME tool during the run does not license labeling an
    # unrelated hand-computed value CALCULATED. search_knowledge is a real,
    # legitimate tool_call_item -- categorized read_only, not calculation
    # (policies/tool_policy.yaml) -- so it must not satisfy this guard.
    stub_result = SimpleNamespace(
        final_output="Cascaded noise figure: 3.47 dB (CALCULATED).",
        new_items=[SimpleNamespace(type="tool_call_item", tool_name="search_knowledge")],
    )
    with pytest.raises(ProvenanceIntegrityError):
        _assert_calculated_provenance_is_tool_backed(stub_result)


def test_calculated_claim_backed_by_a_calculation_call_among_unrelated_calls_is_accepted():
    # A run that legitimately calls an unrelated tool AND a real
    # calculation tool in the same turn should still pass -- the guard
    # looks for at least one calculation-category call, not that every
    # call is one.
    stub_result = SimpleNamespace(
        final_output="Wavelength: 12.24 cm (CALCULATED).",
        new_items=[
            SimpleNamespace(type="tool_call_item", tool_name="search_knowledge"),
            SimpleNamespace(type="tool_call_item", tool_name="calculate_wavelength"),
        ],
    )
    _assert_calculated_provenance_is_tool_backed(stub_result)  # must not raise


def test_calculated_claim_backed_by_an_uncategorized_tool_name_is_rejected():
    # A tool_call_item whose name isn't in policies/tool_policy.yaml at all
    # (category_for returns None) must not accidentally satisfy the guard.
    stub_result = SimpleNamespace(
        final_output="3.47 dB (CALCULATED).",
        new_items=[SimpleNamespace(type="tool_call_item", tool_name="not_a_real_tool_name")],
    )
    with pytest.raises(ProvenanceIntegrityError):
        _assert_calculated_provenance_is_tool_backed(stub_result)


def test_calculated_claim_accepted_across_a_simulated_handoff():
    # Documents the post-#165 architecture fact this guard relies on:
    # native handoffs keep the WHOLE routed exchange in one top-level
    # RunResult, so new_items looks like [handoff_call_item,
    # handoff_output_item, <specialist's own tool_call_item>, ...] by the
    # time run() sees it -- not a separate nested RunResult the run()-level
    # guard can't see into. Shaped after this repo's own scripted-fake-
    # model verification of that fact against the installed SDK (see
    # agent/main.py's module comment above run()).
    stub_result = SimpleNamespace(
        final_output="Cascaded noise figure: 3.47 dB (CALCULATED).",
        new_items=[
            SimpleNamespace(type="handoff_call_item", tool_name="route_to_systems_role"),
            SimpleNamespace(type="handoff_output_item", tool_name=None),
            SimpleNamespace(type="tool_call_item", tool_name="calculate_cascade_gain"),
            SimpleNamespace(type="message_output_item", tool_name=None),
        ],
    )
    _assert_calculated_provenance_is_tool_backed(stub_result)  # must not raise
