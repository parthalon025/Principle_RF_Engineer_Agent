"""Tool-name -> `engineering_results.provenance` (pure).

Ticket #19: every `calculate_*`/`analyze_touchstone_file` tool wrapper writes
`CALCULATED`; the not-yet-built `run_nec`/`run_openems`/`run_hfss` simulation
tools will write `SIMULATED`. `provenance` is always looked up from a
tool's own name, never caller-supplied (CONTEXT.md: Engineering result) --
mirrors `knowledge/provenance.py`'s table-driven source-type -> tier mapping.
"""

from __future__ import annotations

from typing import Literal

CALCULATED = "CALCULATED"
SIMULATED = "SIMULATED"

_TOOL_PROVENANCE: dict[str, Literal["CALCULATED", "SIMULATED"]] = {
    "calculate_wavelength": CALCULATED,
    "calculate_vswr": CALCULATED,
    "calculate_return_loss": CALCULATED,
    "calculate_cascade_gain": CALCULATED,
    "calculate_noise_figure": CALCULATED,
    "analyze_touchstone_file": CALCULATED,
    "run_nec": SIMULATED,
    "run_openems": SIMULATED,
    "run_hfss": SIMULATED,
}


def provenance_for_tool(tool_name: str) -> Literal["CALCULATED", "SIMULATED"]:
    """Return the `engineering_results.provenance` value for `tool_name`.

    Raises `ValueError` for a tool name with no mapping -- deliberately not
    a silent default, since a wrong-but-plausible provenance would be worse
    than a loud failure for a value that gets treated as an evidence tier
    downstream.
    """
    try:
        return _TOOL_PROVENANCE[tool_name]
    except KeyError:
        raise ValueError(f"no provenance mapping for tool {tool_name!r}") from None
