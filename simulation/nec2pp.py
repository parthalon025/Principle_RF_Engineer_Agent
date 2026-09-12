import math
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .base import SimulationResult, Simulator, SimulatorError


class Nec2ppSimulator(Simulator):
    name = "NEC2++"

    def __init__(self, executable: str | None = None):
        self.executable = executable or os.getenv("NEC2PP_BIN") or "nec2++"

    def run(self, job: dict) -> SimulationResult:
        input_file = Path(job["input_file"]).resolve()
        workdir = Path(job.get("workdir", input_file.parent)).resolve()
        if not input_file.exists():
            raise SimulatorError(f"Input file not found: {input_file}")

        # nec2++'s own argument parser (see nec2cpp.cpp's main(), upstream at
        # github.com/tmolteno/necpp/blob/master/src/nec2cpp.cpp) requires an
        # explicit "-i <file>" -- a bare positional filename is rejected with
        # "nec2++: -i input_filename is required" and a nonzero exit. Without
        # "-o -" it also writes the full results to "<input-without-ext>.out"
        # instead of stdout. Both flags are required for this adapter to work
        # against a real binary; verified by reading necpp's own source (see
        # simulation/nec2pp.py module docstring below for the fuller citation).
        timeout_s = int(job.get("timeout_s", 600))
        try:
            completed = subprocess.run(
                [self.executable, "-i", str(input_file), "-o", "-"],
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise SimulatorError(f"NEC2++ timed out after {timeout_s}s: {exc}") from exc
        if completed.returncode != 0:
            raise SimulatorError(
                f"NEC2++ failed ({completed.returncode}): {completed.stderr[-4000:]}"
            )

        # Unlike the openEMS adapter (whose stdout is diagnostic chatter),
        # nec2++'s stdout (via "-o -") *is* the full results text this
        # module's parser below reads impedance/pattern/gain out of, so it is
        # kept in full rather than tail-truncated to 4000 chars -- a
        # radiation-pattern table alone can exceed that for a modest sweep.
        return SimulationResult(
            simulator=self.name,
            status="COMPLETED",
            workdir=workdir,
            outputs={"stdout": completed.stdout},
        )


# ---------------------------------------------------------------------------
# NEC2++ deck generation, execution, and result parsing (issue #38).
#
# Card format verified against the primary NEC-2 documentation source: "NEC-2
# Manual, Part III: User's Guide" (WDBN version 0.92, 9/24/96), fetched from
# https://www.nec2.org/other/nec2prt3.pdf. Cards used here and their
# confirmed field layout/units (mnemonic, then I1-I4 integer fields, then
# F1-F6 decimal fields, all free-format/whitespace-tokenized -- see below):
#   - CM/CE (p.15): comment block; CE terminates it, next card must be
#     geometry.
#   - GW (p.26): wire -- ITG(tag) NS(segments) XW1 YW1 ZW1 XW2 YW2 ZW2 RAD,
#     "structure dimensions must be in units of meters".
#   - GE (p.17): end geometry -- gpflag (0 = no ground plane, nonzero =
#     ground plane present per a following GN card).
#   - GN (p.55): ground -- IPERF (-1 free space / 0 finite reflection-
#     coefficient approx / 1 perfect), NRADL, EPSR, SIG.
#   - EX (p.48-49): excitation -- I1=0 voltage source, I2=source segment's
#     tag, I3=segment position within that tag's set, F1/F2=volts real/imag.
#     I1=1 is an incident plane wave, linear polarization (I1=2/3 are
#     right/left circular -- not emitted by this module, see issue #271):
#     I2/I3=number of theta/phi angles, F1=first theta (deg), F2=first phi
#     (deg), F3=eta -- the polarization angle between the theta unit vector
#     and the E-field direction (deg), F4=theta step (deg), F5=phi step
#     (deg). Confirmed against the ex_card() doc comment in necpp's
#     nec_context.h (github.com/tmolteno/necpp) -- the same upstream source
#     already cited above for the "-i"/"-o -" CLI contract -- since the
#     locally-available NEC-2 Manual excerpt for this repo does not itself
#     transcribe the plane-wave field list.
#   - FR (p.52): frequency -- IFRQ(0=linear) NFRQ FMHZ DELFRQ, "Frequency in
#     MegaHertz".
#   - RP (p.69-72): radiation pattern request -- I1=0 normal mode, NTH, NPH,
#     XNDA, THETS PHIS DTH DPH (degrees); "will initiate program execution".
#   - EN (p.47): end of run, no parameters.
# Free-format (whitespace/comma tokenized, not strict Fortran columns) input
# is what every modern NEC2-compatible reader (necpp included) actually
# accepts -- confirmed against necpp's own upstream source and its `nec2++.1`
# man page (github.com/tmolteno/necpp), which also gave the "-i"/"-o -" CLI
# contract used in Nec2ppSimulator.run() above.
#
# Output section format (ANTENNA INPUT PARAMETERS, RADIATION PATTERNS) is
# taken from "Example 1" in the same Part III guide (p.83-86), the only
# worked example in that document showing full program output text.
#
# HONEST CAVEAT: the real nec2++ binary is not installed in this environment
# (confirmed via `which nec2++`, exit 1) and was not available to actually
# run against these generated decks. Deck generation and output parsing
# below are built to the letter of the documented/verified format above, and
# exercised in tests only against a small fake "nec2++" script that mimics
# that documented output shape (see tests/test_nec2pp.py) -- NOT against a
# real nec2++ binary's actual output. Treat this as unverified end-to-end
# until it has been run against the real tool at least once.
# ---------------------------------------------------------------------------


def _fmt_num(value: float) -> str:
    """Format a float as a compact free-format NEC2 decimal field."""
    return f"{float(value):.6g}"


def _fmt_int(value: int) -> str:
    return str(int(value))


def generate_nec2_deck(
    geometry: dict[str, Any],
    frequency_hz: float,
    comment: str = "Generated by run_nec2_simulation",
) -> str:
    """Generate a NEC2++ free-format card deck from structured geometry.

    `geometry` shape:
        {
          "wires": [
              {
                "tag": int (optional, defaults to 1-based wire index),
                "segments": int,
                "x1_m", "y1_m", "z1_m": float,
                "x2_m", "y2_m", "z2_m": float,
                "radius_m": float,
              },
              ...
          ],
          "ground_condition": "free_space" (default) | "perfect"
              | {"type": "finite", "epsilon_r": float, "conductivity_s_m": float},
          "excitation": {          # optional
              "type": "voltage" (default) | "plane_wave",
              # "voltage" fields (fed antenna, today's only behavior):
              "wire_tag": int, "segment": int,
              "voltage_real": float, "voltage_imag": float,
              # "plane_wave" fields (incident linear-polarized illumination,
              # for reading back a passive structure's reflection phase --
              # see this module's header comment for the EX I1=1 field
              # layout; right/left circular (I1=2/3) are out of scope):
              "theta_start_deg", "theta_step_deg": float, "theta_count": int,
              "phi_start_deg", "phi_step_deg": float, "phi_count": int,
              "eta_deg": float,
          },
          "pattern": {             # optional
              "theta_start_deg", "theta_step_deg": float, "theta_count": int,
              "phi_start_deg", "phi_step_deg": float, "phi_count": int,
          },
        }

    Geometry is in meters and frequency_hz in Hz (converted to the MHz the
    FR card requires) -- both confirmed against the primary source cited in
    this module's header comment. A "voltage" excitation (the default)
    feeds a 1+0j volt source on the first wire's middle segment unless
    overridden; a "plane_wave" excitation illuminates the structure with an
    incident linear-polarized wave instead and has no feed segment to
    default (theta/phi angle count default to 1, all angles/steps default
    to 0 deg). Pattern defaults to a single phi=0 deg elevation cut, theta
    0-180 deg in 10 deg steps.
    """
    wires = geometry.get("wires")
    if not wires:
        raise ValueError("geometry['wires'] must be a non-empty list")

    lines: list[str] = ["CM " + comment, "CE"]

    required_wire_fields = (
        "segments",
        "x1_m",
        "y1_m",
        "z1_m",
        "x2_m",
        "y2_m",
        "z2_m",
        "radius_m",
    )
    for idx, wire in enumerate(wires):
        missing = [f for f in required_wire_fields if f not in wire]
        if missing:
            raise ValueError(f"wire {idx} missing required field(s): {missing}")
        tag = int(wire.get("tag", idx + 1))
        lines.append(
            "GW "
            + " ".join(
                [
                    _fmt_int(tag),
                    _fmt_int(wire["segments"]),
                    _fmt_num(wire["x1_m"]),
                    _fmt_num(wire["y1_m"]),
                    _fmt_num(wire["z1_m"]),
                    _fmt_num(wire["x2_m"]),
                    _fmt_num(wire["y2_m"]),
                    _fmt_num(wire["z2_m"]),
                    _fmt_num(wire["radius_m"]),
                ]
            )
        )

    ground_condition = geometry.get("ground_condition", "free_space")
    gn_line: str | None = None
    if ground_condition == "free_space" or ground_condition is None:
        gpflag = 0
    elif ground_condition == "perfect":
        gpflag = 1
        gn_line = "GN " + " ".join([_fmt_int(1), _fmt_int(0)])
    elif isinstance(ground_condition, dict) and ground_condition.get("type") == "finite":
        gpflag = 1
        epsr = ground_condition["epsilon_r"]
        sig = ground_condition["conductivity_s_m"]
        gn_line = "GN " + " ".join([_fmt_int(0), _fmt_int(0), _fmt_num(epsr), _fmt_num(sig)])
    else:
        raise ValueError(
            "ground_condition must be 'free_space', 'perfect', or "
            "{'type': 'finite', 'epsilon_r': ..., 'conductivity_s_m': ...}, "
            f"got {ground_condition!r}"
        )

    lines.append("GE " + _fmt_int(gpflag))
    if gn_line is not None:
        lines.append(gn_line)

    excitation = geometry.get("excitation", {})
    excitation_type = excitation.get("type", "voltage")
    if excitation_type == "voltage":
        # Feed-segment defaulting only makes sense for a driven antenna --
        # a plane wave has no feed segment, so this must not run for that
        # path (issue #271 AC). first_wire["segments"] was already checked
        # present by required_wire_fields above.
        first_wire = wires[0]
        default_tag = int(first_wire.get("tag", 1))
        default_segment = max(1, math.ceil(int(first_wire["segments"]) / 2))
        ex_tag = int(excitation.get("wire_tag", default_tag))
        ex_segment = int(excitation.get("segment", default_segment))
        v_real = excitation.get("voltage_real", 1.0)
        v_imag = excitation.get("voltage_imag", 0.0)
        lines.append(
            "EX "
            + " ".join(
                [
                    _fmt_int(0),
                    _fmt_int(ex_tag),
                    _fmt_int(ex_segment),
                    _fmt_int(0),
                    _fmt_num(v_real),
                    _fmt_num(v_imag),
                ]
            )
        )
    elif excitation_type == "plane_wave":
        # Incident plane wave, linear polarization (I1=1; necpp's
        # EXCITATION_LINEAR, see this module's header comment for the full
        # field-layout citation). Right/left circular (I1=2/3) are out of
        # scope for this ticket.
        theta_start = excitation.get("theta_start_deg", 0.0)
        phi_start = excitation.get("phi_start_deg", 0.0)
        eta = excitation.get("eta_deg", 0.0)
        theta_step = excitation.get("theta_step_deg", 0.0)
        phi_step = excitation.get("phi_step_deg", 0.0)
        theta_count = int(excitation.get("theta_count", 1))
        phi_count = int(excitation.get("phi_count", 1))
        lines.append(
            "EX "
            + " ".join(
                [
                    _fmt_int(1),
                    _fmt_int(theta_count),
                    _fmt_int(phi_count),
                    _fmt_int(0),
                    _fmt_num(theta_start),
                    _fmt_num(phi_start),
                    _fmt_num(eta),
                    _fmt_num(theta_step),
                    _fmt_num(phi_step),
                ]
            )
        )
    else:
        raise ValueError(
            f"excitation['type'] must be 'voltage' or 'plane_wave', got {excitation_type!r}"
        )

    freq_mhz = frequency_hz / 1e6
    fr_fields = [_fmt_int(0), _fmt_int(1), _fmt_int(0), _fmt_int(0), _fmt_num(freq_mhz)]
    lines.append("FR " + " ".join(fr_fields))

    pattern = geometry.get("pattern", {})
    theta_start = pattern.get("theta_start_deg", 0.0)
    theta_step = pattern.get("theta_step_deg", 10.0)
    theta_count = int(pattern.get("theta_count", 19))
    phi_start = pattern.get("phi_start_deg", 0.0)
    phi_step = pattern.get("phi_step_deg", 0.0)
    phi_count = int(pattern.get("phi_count", 1))
    lines.append(
        "RP "
        + " ".join(
            [
                _fmt_int(0),
                _fmt_int(theta_count),
                _fmt_int(phi_count),
                _fmt_int(0),
                _fmt_num(theta_start),
                _fmt_num(phi_start),
                _fmt_num(theta_step),
                _fmt_num(phi_step),
            ]
        )
    )

    lines.append("EN")
    return "\n".join(lines) + "\n"


# Matches a NEC2 fixed-field decimal number, e.g. "9.20585E-03", "-999.99",
# ".00000" -- deliberately permissive about a missing leading digit before
# the decimal point (NEC2 prints e.g. ".00000" with no leading zero) and
# about adjacent numbers being printed with no separating space when the
# next one starts with '-' (a classic Fortran fixed-field artifact visible
# e.g. in "9.20585E-03-5.15474E-03" in the guide's own Example 1 output).
_NUM_RE = re.compile(r"[+-]?\d*\.\d+(?:[Ee][+-]?\d+)?")


def _extract_numbers(line: str) -> list[float]:
    return [float(tok) for tok in _NUM_RE.findall(line)]


def parse_nec2_output(raw_output: str) -> dict[str, Any]:
    """Parse a NEC2++ results text (as produced by `nec2++ -i ... -o -`) into
    structured impedance/pattern/gain data.

    Section formats (ANTENNA INPUT PARAMETERS, RADIATION PATTERNS) are taken
    from "Example 1" of the primary source cited in this module's header
    comment. See that comment for the honest caveat: this has been verified
    against the *documented* output format, not against real nec2++ output,
    since no real binary was available in this environment.
    """
    lines = raw_output.splitlines()

    impedance: dict[str, Any] | None = None
    for i, line in enumerate(lines):
        if "ANTENNA INPUT PARAMETERS" in line:
            # Header line, then a "TAG SEG. ..." column-label line, then a
            # units line ("NO. NO. REAL IMAG. ..."), then one data row per
            # excited segment -- take the first, per this function's
            # single-source/single-frequency contract.
            for data_line in lines[i + 3 : i + 3 + 5]:
                nums = _extract_numbers(data_line)
                if len(nums) == 9:
                    tag_seg = re.match(r"\s*(-?\d+)\s+(-?\d+)\s", data_line)
                    impedance = {
                        "tag": int(tag_seg.group(1)) if tag_seg else None,
                        "segment": int(tag_seg.group(2)) if tag_seg else None,
                        "voltage_real_v": nums[0],
                        "voltage_imag_v": nums[1],
                        "current_real_a": nums[2],
                        "current_imag_a": nums[3],
                        "resistance_ohms": nums[4],
                        "reactance_ohms": nums[5],
                        "admittance_real_mhos": nums[6],
                        "admittance_imag_mhos": nums[7],
                        "power_w": nums[8],
                    }
                    break
            break

    pattern: list[dict[str, Any]] = []
    for i, line in enumerate(lines):
        if "RADIATION PATTERNS" in line:
            # Header line, then three more label/units lines ("- - ANGLES
            # - -...", "THETA PHI...", "DEGREES DEGREES..."), then data rows
            # until a line that doesn't parse as an 11-number pattern row
            # (e.g. a blank line or the trailing "AVERAGE POWER GAIN=" line).
            for data_line in lines[i + 4 :]:
                nums = _extract_numbers(data_line)
                if len(nums) != 11:
                    break
                pattern.append(
                    {
                        "theta_deg": nums[0],
                        "phi_deg": nums[1],
                        "vertical_gain_db": nums[2],
                        "horizontal_gain_db": nums[3],
                        "total_gain_db": nums[4],
                        "axial_ratio": nums[5],
                        "tilt_deg": nums[6],
                        "e_theta_v_per_m": nums[7],
                        "e_theta_phase_deg": nums[8],
                        "e_phi_v_per_m": nums[9],
                        "e_phi_phase_deg": nums[10],
                    }
                )
            break

    gain_dbi = None
    valid_totals = [row["total_gain_db"] for row in pattern if row["total_gain_db"] > -999.0]
    if valid_totals:
        gain_dbi = max(valid_totals)

    avg_gain_match = re.search(r"AVERAGE POWER GAIN=\s*([+-]?\d*\.\d+E[+-]\d+)", raw_output)
    average_power_gain_linear = float(avg_gain_match.group(1)) if avg_gain_match else None

    return {
        "impedance": impedance,
        "pattern": pattern,
        "gain_dbi": gain_dbi,
        "average_power_gain_linear": average_power_gain_linear,
    }


def run_nec2_simulation(
    geometry: dict[str, Any],
    frequency_hz: float,
    timeout_s: int = 600,
    executable: str | None = None,
    workdir: str | None = None,
) -> dict[str, Any]:
    """Generate a NEC2++ deck from structured geometry, run it via
    Nec2ppSimulator, and parse the result into structured impedance/pattern/
    gain data tagged with SIMULATED provenance.

    See this module's header comment for the honest caveat: deck generation
    and parsing are built to the documented NEC2 card/output format (cited
    there), not verified against a real nec2++ binary run in this
    environment.
    """
    work_dir = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="nec2pp_"))
    work_dir.mkdir(parents=True, exist_ok=True)
    input_file = work_dir / "model.nec"
    input_file.write_text(generate_nec2_deck(geometry, frequency_hz))

    simulator = Nec2ppSimulator(executable=executable)
    result = simulator.run(
        {"input_file": str(input_file), "workdir": str(work_dir), "timeout_s": timeout_s}
    )
    parsed = parse_nec2_output(result.outputs.get("stdout", ""))

    return {
        "provenance": result.provenance,
        "impedance": parsed["impedance"],
        "pattern": parsed["pattern"],
        "gain_dbi": parsed["gain_dbi"],
        "average_power_gain_linear": parsed["average_power_gain_linear"],
        "simulator": result.simulator,
        "status": result.status,
        "workdir": str(result.workdir),
        "input_file": str(input_file),
    }
