"""Thin wiring tests for the specialist-role split (issue #34).

These tests confirm each role is constructible and that its tool list is
scoped to its stated domain. They deliberately do NOT re-test the tools'
own logic -- that is already covered by test_calculations.py,
test_touchstone.py, and the knowledge test suite.
"""

from agent.main import ROLE_SPECS, ROLES, principal


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
    # principal is the coordinating role and is deliberately unscoped
    assert len(names) == 11


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
