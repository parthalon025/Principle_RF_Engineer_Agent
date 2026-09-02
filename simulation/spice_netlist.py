"""Shared SPICE3F5-style netlist-card generation for simulation/ngspice.py and
simulation/xyce.py (issue #57).

FACTORING NOTE: simulation/base.py deliberately supplies no shared
netlist/CLI helpers today (Nec2ppSimulator and OpenemsSimulator each own
their own `_fmt_num`-style formatting and card generation independently --
their file formats, NEC2 cards and openEMS FDTD-XML, share nothing). This
module exists because, once both simulation/ngspice.py and simulation/
xyce.py were actually written for issue #57, the R/L/C/V/I basic
two-terminal-element instance-card syntax turned out to be byte-for-byte
identical between them (both trace to the same SPICE3F5 lineage) -- see the
per-element citations below, each confirmed independently against ngspice's
and Xyce's own primary documentation, not assumed from the other. Only that
genuinely-duplicated subset is factored here; each adapter's own module
still owns everything that differs (ngspice's `.control`/`wrdata` batch-
output mechanics vs. Xyce's `.PRINT`/`.LIN` dot-command output mechanics,
and each simulator's own CLI invocation contract).

PRIMARY SOURCES CONSULTED for the element forms below:
  - Resistor/Capacitor/Inductor/Independent-source basic instance-card
    shape (`R<name> n+ n- value`, `C<name> n+ n- value`,
    `L<name> n+ n- value`, `V<name>/I<name> n+ n- [DC value]
    [AC magnitude phase]`): confirmed independently against (a) the ngspice
    manual's own "Circuit elements (device instances)" page and
    "Independent Sources for Voltage or Current" page
    (nmg.gitlab.io/ngspice-manual, mirroring the official
    ngspice.sourceforge.io HTML/PDF manual), and (b) the Xyce Reference
    Guide (Sandia SAND2023-13759, xyce.sandia.gov/files/xyce/
    Xyce_Reference_Guide_7.8.pdf), sections 2.3.4 (Capacitor), 2.3.5
    (Inductor), 2.3.7 (Resistor), and 2.3.10 (Independent Voltage Source) --
    both documents independently show the same base positional form, which
    is what this module generates (a bare numeric value, no optional
    model-name/device-parameter extensions from either tool's own
    superset).
  - `.SUBCKT`/`.ENDS`/`X<name>` subcircuit-instantiation form: confirmed
    against the same two sources (ngspice manual's ".SUBCKT Subcircuits"
    page; Xyce Reference Guide's `.PRINT` example netlist at section
    2.1.31, which itself demonstrates an `X1 1 2 3 MySubcircuit` instance
    line against a `.SUBCKT`/`.ENDS` pair) -- not independently generated
    by this module (see SCOPE below), only documented here since a caller
    building `raw_cards` needs this exact form.

SCOPE: this module generates ONLY the well-established passive/source
two-terminal element cards (R, L, C, V, I) needed for a matching network,
filter, or linear amplifier bias/termination network. It deliberately does
NOT generate semiconductor-device instance cards (diode/BJT/JFET/MOSFET) or
`.MODEL`/`.SUBCKT` text -- SPICE model-parameter sets vary enormously by
model level/vintage and guessing at their field layout would be exactly the
"plausible-but-wrong CLI flag" failure mode this codebase's discipline
exists to prevent. A nonlinear amplifier sub-circuit is instead supplied by
the caller as already-valid raw SPICE text via each adapter's `raw_cards`
job-dict key (see simulation/ngspice.py's and simulation/xyce.py's module
docstrings), inserted verbatim -- this module and its callers do not
validate or generate that text.
"""

from __future__ import annotations

from typing import Any


def format_number(value: float) -> str:
    """Format a float as a compact free-format SPICE decimal field (plain
    decimal/scientific notation, 6 significant digits -- both ngspice and
    Xyce accept plain numeric literals for every field this module emits;
    neither tool's SI-suffix shorthand, e.g. "1k"/"1meg", is required or
    used here)."""
    return f"{float(value):.6g}"


_REQUIRED_TWO_TERMINAL_FIELDS = ("name", "n1", "n2", "value")


def _two_terminal_card(component: dict[str, Any], prefix: str) -> str:
    missing = [f for f in _REQUIRED_TWO_TERMINAL_FIELDS if f not in component]
    if missing:
        raise ValueError(f"{prefix} component missing required field(s): {missing}")
    name = str(component["name"])
    if not name.upper().startswith(prefix):
        raise ValueError(
            f"{prefix} component 'name' must start with {prefix!r} "
            f"(the element-type letter both ngspice and Xyce dispatch on), got {name!r}"
        )
    return f"{name} {component['n1']} {component['n2']} {format_number(component['value'])}"


def format_resistor(component: dict[str, Any]) -> str:
    """`R<name> n+ n- value` -- resistance in ohms."""
    return _two_terminal_card(component, "R")


def format_capacitor(component: dict[str, Any]) -> str:
    """`C<name> n+ n- value` -- capacitance in farads."""
    return _two_terminal_card(component, "C")


def format_inductor(component: dict[str, Any]) -> str:
    """`L<name> n+ n- value` -- inductance in henries."""
    return _two_terminal_card(component, "L")


def _source_card(component: dict[str, Any], prefix: str) -> str:
    required = ("name", "n1", "n2")
    missing = [f for f in required if f not in component]
    if missing:
        raise ValueError(f"{prefix} source component missing required field(s): {missing}")
    name = str(component["name"])
    if not name.upper().startswith(prefix):
        raise ValueError(
            f"{prefix} source component 'name' must start with {prefix!r}, got {name!r}"
        )
    fields = [name, str(component["n1"]), str(component["n2"])]
    if "dc" in component:
        fields += ["DC", format_number(component["dc"])]
    if "ac_mag" in component:
        fields += ["AC", format_number(component["ac_mag"])]
        if "ac_phase" in component:
            fields.append(format_number(component["ac_phase"]))
    return " ".join(fields)


def format_voltage_source(component: dict[str, Any]) -> str:
    """`V<name> n+ n- [DC value] [AC magnitude [phase]]` -- volts/degrees.
    At least one of "dc"/"ac_mag" should normally be given (a source with
    neither is a 0V short, valid SPICE but rarely intentional)."""
    return _source_card(component, "V")


def format_current_source(component: dict[str, Any]) -> str:
    """`I<name> n+ n- [DC value] [AC magnitude [phase]]` -- amps/degrees."""
    return _source_card(component, "I")


_FORMATTERS = {
    "R": format_resistor,
    "C": format_capacitor,
    "L": format_inductor,
    "V": format_voltage_source,
    "I": format_current_source,
}


def format_components(components: list[dict[str, Any]]) -> list[str]:
    """Render a structured `components` list (see this module's docstring
    for the supported R/L/C/V/I shapes) into SPICE card lines, in order.
    Each dict must carry a "type" key naming one of R/L/C/V/I."""
    lines: list[str] = []
    for idx, component in enumerate(components):
        component_type = component.get("type")
        formatter = _FORMATTERS.get(component_type)
        if formatter is None:
            raise ValueError(
                f"components[{idx}]['type'] must be one of {sorted(_FORMATTERS)}, "
                f"got {component_type!r} -- an active/nonlinear device (diode, BJT, "
                "MOSFET, etc.) or a subcircuit is not generated here; supply it as "
                "already-valid SPICE text via the job dict's 'raw_cards' instead "
                "(see this module's docstring SCOPE note)"
            )
        lines.append(formatter(component))
    return lines
