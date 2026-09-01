import pytest

from designs.provenance import provenance_for_tool


@pytest.mark.parametrize(
    "tool_name",
    [
        "calculate_wavelength",
        "calculate_vswr",
        "calculate_return_loss",
        "calculate_cascade_gain",
        "calculate_noise_figure",
        "analyze_touchstone_file",
    ],
)
def test_calculation_and_touchstone_tools_are_calculated(tool_name):
    assert provenance_for_tool(tool_name) == "CALCULATED"


@pytest.mark.parametrize("tool_name", ["run_nec", "run_openems", "run_hfss"])
def test_simulation_tools_are_simulated(tool_name):
    assert provenance_for_tool(tool_name) == "SIMULATED"


def test_unknown_tool_raises():
    with pytest.raises(ValueError):
        provenance_for_tool("not_a_real_tool")
