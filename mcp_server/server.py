from mcp.server.fastmcp import FastMCP

from rf_tools.calculations import (
    cascade_gain_db,
    friis_noise_factor,
    noise_factor_to_db,
    return_loss_db,
    vswr_from_gamma,
    wavelength,
)
from rf_tools.touchstone import analyze_touchstone

mcp = FastMCP("principal-rf-engineer")


@mcp.tool()
def calculate_wavelength(frequency_hz: float) -> float:
    """Calculate free-space wavelength in meters."""
    return wavelength(frequency_hz)


@mcp.tool()
def calculate_vswr(reflection_coefficient_magnitude: float) -> float:
    """Calculate VSWR from |Gamma|."""
    return vswr_from_gamma(reflection_coefficient_magnitude)


@mcp.tool()
def calculate_return_loss(reflection_coefficient_magnitude: float) -> float:
    """Calculate return loss in dB from |Gamma|."""
    return return_loss_db(reflection_coefficient_magnitude)


@mcp.tool()
def calculate_cascade_gain(gains_db: list[float]) -> float:
    """Calculate cascaded gain in dB."""
    return cascade_gain_db(gains_db)


@mcp.tool()
def calculate_noise_figure(
    noise_factors: list[float], gains_linear: list[float]
) -> dict:
    """Calculate cascaded noise factor and noise figure."""
    f_total = friis_noise_factor(noise_factors, gains_linear)
    return {
        "noise_factor": f_total,
        "noise_figure_db": noise_factor_to_db(f_total),
        "provenance": "CALCULATED",
    }


@mcp.tool()
def analyze_touchstone_file(path: str) -> dict:
    """Analyze a local Touchstone network file."""
    result = analyze_touchstone(path)
    result["provenance"] = "CALCULATED"
    return result


if __name__ == "__main__":
    mcp.run()
