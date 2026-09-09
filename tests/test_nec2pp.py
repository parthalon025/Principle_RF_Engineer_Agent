# ruff: noqa: E501 -- this file transcribes fixed-column NEC2 output text
# verbatim from the primary source cited below; reflowing it would break
# the exact fixed-column shape the parser under test reads.
"""Tests for NEC2++ deck generation, execution, and result parsing
(issue #38).

The real `nec2++` binary is NOT installed in this environment (confirmed
via `which nec2++` during implementation) so `Nec2ppSimulator.run()` is
exercised here only against small fake "nec2++" scripts checked in below
(via `tmp_path`), per the Phase 6-8 testing decision cited in the ticket:
subprocess plumbing (argument shape, nonzero exit, timeout) and result
parsing are tested; the physics itself is out of scope for automated tests.

The deck card format and the "ANTENNA INPUT PARAMETERS"/"RADIATION
PATTERNS" output section format were verified against the primary NEC-2
documentation source -- see the header comment in simulation/nec2pp.py for
the exact citation (NEC-2 Manual, Part III: User's Guide, WDBN v0.92,
https://www.nec2.org/other/nec2prt3.pdf) -- and the "-i"/"-o -" CLI
contract against necpp's own upstream source
(github.com/tmolteno/necpp/blob/master/src/nec2cpp.cpp). The sample output
text used in test_parse_nec2_output_* below is transcribed from that
guide's own worked "Example 1" (impedance) and a "RADIATION PATTERNS"
excerpt from the same document -- it has NOT been produced by, or checked
against, a real nec2++ run.
"""

import os
from pathlib import Path

import pytest
from conftest import make_fake_executable

from simulation.base import SimulatorError
from simulation.nec2pp import (
    Nec2ppSimulator,
    generate_nec2_deck,
    parse_nec2_output,
    run_nec2_simulation,
)

# Transcribed verbatim (aside from surrounding indentation) from "Example 1.
# Center fed linear antenna" in the NEC-2 User's Guide (see module docstring
# for the citation) -- the ANTENNA INPUT PARAMETERS section, plus a
# RADIATION PATTERNS excerpt from later in the same document.
GUIDE_SAMPLE_OUTPUT = """
                                          - - - ANTENNA INPUT PARAMETERS - - -
   TAG   SEG.    VOLTAGE (VOLTS)         CURRENT (AMPS)         IMPEDANCE (OHMS)        ADMITTANCE (MHOS)      POWER
   NO.   NO.    REAL        IMAG.       REAL        IMAG.       REAL        IMAG.       REAL        IMAG.     (WATTS)
     0     4 1.00000E+00 0.00000E+00 9.20585E-03-5.15474E-03 8.26979E+01 4.63060E+01 9.20585E-03-5.15474E-03 4.60292E-03
                                                - - - RADIATION PATTERNS - - -
  - - ANGLES - -           - POWER GAINS -       - - - POLARIZATION - - -    - - - E(THETA) - - -    - - - E(PHI) - - -
  THETA     PHI        VERT.   HOR.    TOTAL      AXIAL     TILT   SENSE     MAGNITUDE    PHASE     MAGNITUDE    PHASE
 DEGREES  DEGREES       DB      DB      DB        RATIO     DEG.              VOLTS/M    DEGREES      VOLTS/M    DEGREES
     .00      .00    -999.99 -999.99 -999.99     .00000      .00            0.00000E-01      .00    0.00000E-01      .00
   10.00      .00      -9.87 -999.99   -9.87     .00000      .00  LINEAR    1.69640E-01  -114.38    0.00000E-01      .00
   20.00      .00      -4.20 -999.99   -4.20     .00000      .00  LINEAR    3.25649E-01  -114.64    0.00000E-01      .00
   90.00      .00       8.52 -999.99    8.52     .00000      .00  LINEAR    1.40967E+00    62.47    0.00000E-01      .00
   AVERAGE POWER GAIN= 2.02793E+00       SOLID ANGLE USED IN AVERAGING=(  .5000)*PI STERADIANS.
"""


def _make_fake_nec2pp(tmp_path: Path, body: str) -> Path:
    """Write a small fake 'nec2++' executable (a Python script body,
    launched cross-platform -- see conftest.make_fake_executable)."""
    return make_fake_executable(tmp_path, body, name="fake_nec2pp")


DIPOLE_GEOMETRY = {
    "wires": [
        {
            "tag": 1,
            "segments": 7,
            "x1_m": 0.0,
            "y1_m": 0.0,
            "z1_m": -0.25,
            "x2_m": 0.0,
            "y2_m": 0.0,
            "z2_m": 0.25,
            "radius_m": 0.001,
        }
    ],
}


# ---------------------------------------------------------------------------
# Deck generation
# ---------------------------------------------------------------------------


def test_generate_nec2_deck_basic_dipole_card_order_and_fields():
    deck = generate_nec2_deck(DIPOLE_GEOMETRY, frequency_hz=300e6)
    lines = deck.strip("\n").split("\n")

    assert lines[0].startswith("CM ")
    assert lines[1] == "CE"
    assert lines[2] == "GW 1 7 0 0 -0.25 0 0 0.25 0.001"
    assert lines[3] == "GE 0"
    assert lines[4].startswith("EX 0 1 4 0 1 0")  # middle of 7 segments = 4
    assert lines[5].startswith("FR 0 1 0 0 300")
    assert lines[6].startswith("RP 0 ")
    assert lines[-1] == "EN"
    # No GN card in the free-space (default) case.
    assert not any(line.startswith("GN") for line in lines)


def test_generate_nec2_deck_frequency_converted_hz_to_mhz():
    deck = generate_nec2_deck(DIPOLE_GEOMETRY, frequency_hz=2.45e9)
    fr_line = next(line for line in deck.split("\n") if line.startswith("FR "))
    assert "2450" in fr_line  # 2.45 GHz -> 2450 MHz


def test_generate_nec2_deck_perfect_ground_sets_gpflag_and_gn_card():
    geometry = {**DIPOLE_GEOMETRY, "ground_condition": "perfect"}
    deck = generate_nec2_deck(geometry, frequency_hz=300e6)
    lines = deck.split("\n")
    assert "GE 1" in lines
    assert "GN 1 0" in lines


def test_generate_nec2_deck_finite_ground_card():
    geometry = {
        **DIPOLE_GEOMETRY,
        "ground_condition": {
            "type": "finite",
            "epsilon_r": 13.0,
            "conductivity_s_m": 0.005,
        },
    }
    deck = generate_nec2_deck(geometry, frequency_hz=300e6)
    gn_line = next(line for line in deck.split("\n") if line.startswith("GN"))
    assert gn_line == "GN 0 0 13 0.005"


def test_generate_nec2_deck_invalid_ground_condition_raises():
    geometry = {**DIPOLE_GEOMETRY, "ground_condition": "not_a_real_condition"}
    with pytest.raises(ValueError):
        generate_nec2_deck(geometry, frequency_hz=300e6)


def test_generate_nec2_deck_explicit_excitation_and_pattern():
    geometry = {
        "wires": [
            {
                "tag": 5,
                "segments": 11,
                "x1_m": 0.0,
                "y1_m": 0.0,
                "z1_m": 0.0,
                "x2_m": 0.1,
                "y2_m": 0.0,
                "z2_m": 0.0,
                "radius_m": 0.0005,
            }
        ],
        "excitation": {"wire_tag": 5, "segment": 3, "voltage_real": 2.0, "voltage_imag": -1.0},
        "pattern": {
            "theta_start_deg": 0.0,
            "theta_step_deg": 5.0,
            "theta_count": 37,
            "phi_start_deg": 0.0,
            "phi_step_deg": 0.0,
            "phi_count": 1,
        },
    }
    deck = generate_nec2_deck(geometry, frequency_hz=1e9)
    lines = deck.split("\n")
    assert "EX 0 5 3 0 2 -1" in lines
    assert "RP 0 37 1 0 0 0 5 0" in lines


def test_generate_nec2_deck_plane_wave_excitation_ex_card():
    """A plane_wave excitation must emit 'EX 1 ...' (linear polarization,
    necpp's EXCITATION_LINEAR=1 per src/common.h) instead of the voltage
    source's 'EX 0 ...', with I2/I3 set from theta/phi angle counts and the
    decimal fields set from first-theta, first-phi, polarization angle eta,
    theta step, and phi step -- per the ex_card() doc comment in necpp's
    nec_context.h cited in issue #271."""
    geometry = {
        **DIPOLE_GEOMETRY,
        "excitation": {
            "type": "plane_wave",
            "theta_start_deg": 30.0,
            "phi_start_deg": 45.0,
            "eta_deg": 90.0,
            "theta_step_deg": 10.0,
            "phi_step_deg": 5.0,
            "theta_count": 1,
            "phi_count": 1,
        },
    }
    deck = generate_nec2_deck(geometry, frequency_hz=300e6)
    lines = deck.strip("\n").split("\n")
    ex_line = next(line for line in lines if line.startswith("EX "))
    assert ex_line.startswith("EX 1 ")
    assert ex_line == "EX 1 1 1 0 30 45 90 10 5"
    # RP/EN cards are unaffected by the excitation type.
    assert any(line.startswith("RP 0 ") for line in lines)
    assert lines[-1] == "EN"


def test_generate_nec2_deck_plane_wave_default_voltage_type_unchanged():
    """Omitting excitation['type'] entirely still produces today's
    voltage-source-only output (AC: byte-identical for every existing
    caller/test)."""
    deck_no_type = generate_nec2_deck(DIPOLE_GEOMETRY, frequency_hz=300e6)
    geometry_explicit_voltage = {
        **DIPOLE_GEOMETRY,
        "excitation": {"type": "voltage"},
    }
    deck_explicit_voltage = generate_nec2_deck(geometry_explicit_voltage, frequency_hz=300e6)
    assert deck_no_type == deck_explicit_voltage
    assert "EX 0 " in deck_no_type


def test_generate_nec2_deck_plane_wave_ignores_feed_segment_fields():
    """A plane wave has no feed segment, so its EX line must not depend on
    the wire's 'tag'/'segments' -- the fields the voltage path's
    default_tag/default_segment computation reads.

    Note: this can't be proven by handing generate_nec2_deck() a wire
    *missing* 'segments' and checking it doesn't crash -- that scenario is
    unreachable. required_wire_fields (simulation/nec2pp.py) requires
    'segments' on every wire, for both excitation types, before the
    excitation branch is ever reached, so a wire missing it always raises
    ValueError there regardless of excitation type; the voltage path's
    default_tag/default_segment computation is never the thing that would
    fail. Instead, this proves non-invocation the way it's actually
    observable: two wires with different 'tag'/'segments' values, otherwise
    identical, must produce byte-identical plane_wave EX lines."""
    base_wire = {
        "tag": 1,
        "segments": 7,
        "x1_m": 0.0,
        "y1_m": 0.0,
        "z1_m": -0.25,
        "x2_m": 0.0,
        "y2_m": 0.0,
        "z2_m": 0.25,
        "radius_m": 0.001,
    }
    other_wire = {**base_wire, "tag": 99, "segments": 4}
    excitation = {"type": "plane_wave"}
    deck_a = generate_nec2_deck(
        {"wires": [base_wire], "excitation": excitation}, frequency_hz=300e6
    )
    deck_b = generate_nec2_deck(
        {"wires": [other_wire], "excitation": excitation}, frequency_hz=300e6
    )
    ex_a = next(line for line in deck_a.split("\n") if line.startswith("EX "))
    ex_b = next(line for line in deck_b.split("\n") if line.startswith("EX "))
    assert ex_a == ex_b == "EX 1 1 1 0 0 0 0 0 0"


def test_generate_nec2_deck_invalid_excitation_type_raises():
    geometry = {**DIPOLE_GEOMETRY, "excitation": {"type": "not_a_real_type"}}
    with pytest.raises(ValueError, match="excitation"):
        generate_nec2_deck(geometry, frequency_hz=300e6)


def test_generate_nec2_deck_empty_wires_raises():
    with pytest.raises(ValueError):
        generate_nec2_deck({"wires": []}, frequency_hz=300e6)


def test_generate_nec2_deck_missing_wire_field_raises():
    with pytest.raises(ValueError, match="radius_m"):
        generate_nec2_deck(
            {
                "wires": [
                    {
                        "tag": 1,
                        "segments": 7,
                        "x1_m": 0.0,
                        "y1_m": 0.0,
                        "z1_m": -0.25,
                        "x2_m": 0.0,
                        "y2_m": 0.0,
                        "z2_m": 0.25,
                        # radius_m deliberately omitted
                    }
                ]
            },
            frequency_hz=300e6,
        )


def test_generate_nec2_deck_multiple_wires_auto_assigns_tags():
    geometry = {
        "wires": [
            {
                "segments": 5,
                "x1_m": 0.0,
                "y1_m": 0.0,
                "z1_m": 0.0,
                "x2_m": 0.0,
                "y2_m": 0.0,
                "z2_m": 0.1,
                "radius_m": 0.001,
            },
            {
                "segments": 5,
                "x1_m": 0.1,
                "y1_m": 0.0,
                "z1_m": 0.0,
                "x2_m": 0.1,
                "y2_m": 0.0,
                "z2_m": 0.1,
                "radius_m": 0.001,
            },
        ]
    }
    deck = generate_nec2_deck(geometry, frequency_hz=300e6)
    gw_lines = [line for line in deck.split("\n") if line.startswith("GW")]
    assert gw_lines[0].startswith("GW 1 ")
    assert gw_lines[1].startswith("GW 2 ")


# ---------------------------------------------------------------------------
# Output parsing (against the guide-transcribed sample -- see module
# docstring for the honest not-verified-against-a-real-binary caveat).
# ---------------------------------------------------------------------------


def test_parse_nec2_output_extracts_impedance():
    result = parse_nec2_output(GUIDE_SAMPLE_OUTPUT)
    impedance = result["impedance"]
    assert impedance is not None
    assert impedance["tag"] == 0
    assert impedance["segment"] == 4
    assert impedance["resistance_ohms"] == pytest.approx(82.6979)
    assert impedance["reactance_ohms"] == pytest.approx(46.3060)
    assert impedance["current_real_a"] == pytest.approx(9.20585e-03)
    assert impedance["current_imag_a"] == pytest.approx(-5.15474e-03)


def test_parse_nec2_output_extracts_pattern_rows():
    result = parse_nec2_output(GUIDE_SAMPLE_OUTPUT)
    pattern = result["pattern"]
    assert len(pattern) == 4
    assert pattern[0]["theta_deg"] == pytest.approx(0.0)
    assert pattern[1]["theta_deg"] == pytest.approx(10.0)
    assert pattern[1]["total_gain_db"] == pytest.approx(-9.87)
    assert pattern[3]["theta_deg"] == pytest.approx(90.0)
    assert pattern[3]["total_gain_db"] == pytest.approx(8.52)


def test_parse_nec2_output_gain_dbi_excludes_sentinel_and_takes_max():
    result = parse_nec2_output(GUIDE_SAMPLE_OUTPUT)
    # -999.99 (undefined boresight polarization) must not win the max.
    assert result["gain_dbi"] == pytest.approx(8.52)


def test_parse_nec2_output_average_power_gain():
    result = parse_nec2_output(GUIDE_SAMPLE_OUTPUT)
    assert result["average_power_gain_linear"] == pytest.approx(2.02793)


def test_parse_nec2_output_missing_sections_returns_none_and_empty():
    result = parse_nec2_output("NOTHING USEFUL HERE\n")
    assert result["impedance"] is None
    assert result["pattern"] == []
    assert result["gain_dbi"] is None
    assert result["average_power_gain_linear"] is None


# ---------------------------------------------------------------------------
# Nec2ppSimulator.run() subprocess plumbing, against fake executables.
# ---------------------------------------------------------------------------


def test_nec2pp_simulator_invokes_dash_i_and_dash_o_dash(tmp_path: Path):
    """Confirm the real necpp CLI contract (-i <file> -o -, see module
    docstring citation) is what actually gets shelled out -- the previous
    invocation shape (a bare positional filename) is rejected by real
    nec2++ with 'nec2++: -i input_filename is required'."""
    script = _make_fake_nec2pp(tmp_path, 'import sys\nsys.stdout.write(" ".join(sys.argv[1:]))\n')
    input_file = tmp_path / "model.nec"
    input_file.write_text("CM test\nCE\nEN\n")

    simulator = Nec2ppSimulator(executable=str(script))
    result = simulator.run({"input_file": str(input_file), "timeout_s": 10})

    tokens = result.outputs["stdout"].split()
    assert tokens == ["-i", str(input_file), "-o", "-"]
    assert result.status == "COMPLETED"
    assert result.provenance == "SIMULATED"


def test_nec2pp_simulator_nonzero_exit_raises_simulator_error(tmp_path: Path):
    script = _make_fake_nec2pp(
        tmp_path, 'import sys\nsys.stderr.write("boom: bad geometry card\\n")\nsys.exit(1)\n'
    )
    input_file = tmp_path / "model.nec"
    input_file.write_text("CM test\nCE\nEN\n")

    simulator = Nec2ppSimulator(executable=str(script))
    with pytest.raises(SimulatorError, match="boom"):
        simulator.run({"input_file": str(input_file), "timeout_s": 10})


def test_nec2pp_simulator_timeout_raises_simulator_error(tmp_path: Path):
    script = _make_fake_nec2pp(tmp_path, "import time\ntime.sleep(5)\n")
    input_file = tmp_path / "model.nec"
    input_file.write_text("CM test\nCE\nEN\n")

    simulator = Nec2ppSimulator(executable=str(script))
    with pytest.raises(SimulatorError, match="timed out"):
        simulator.run({"input_file": str(input_file), "timeout_s": 1})


def test_nec2pp_simulator_missing_input_file_raises(tmp_path: Path):
    simulator = Nec2ppSimulator(executable="nec2++")
    with pytest.raises(SimulatorError, match="not found"):
        simulator.run({"input_file": str(tmp_path / "does_not_exist.nec")})


def test_nec2pp_simulator_picks_up_executable_from_env_var(tmp_path: Path, monkeypatch):
    script = _make_fake_nec2pp(tmp_path, "import sys\nsys.exit(0)\n")
    monkeypatch.setenv("NEC2PP_BIN", str(script))
    simulator = Nec2ppSimulator()
    assert simulator.executable == str(script)


# ---------------------------------------------------------------------------
# run_nec2_simulation end to end, against a fake executable that mimics the
# documented output shape (per the ticket's fake-executable testing
# approach). This is plumbing + parsing coverage only -- see module
# docstring for the not-verified-against-a-real-binary caveat.
# ---------------------------------------------------------------------------

_FAKE_NEC2PP_PY = '''
import sys

OUTPUT = """{sample}"""

args = sys.argv[1:]
assert "-i" in args, args
assert args[args.index("-o") + 1] == "-", args
sys.stdout.write(OUTPUT)
sys.exit(0)
'''


def _make_fake_nec2pp_py(tmp_path: Path, sample_output: str) -> Path:
    body = _FAKE_NEC2PP_PY.format(sample=sample_output)
    return make_fake_executable(tmp_path, body, name="fake_nec2pp_realistic")


def test_run_nec2_simulation_end_to_end_with_fake_executable(tmp_path: Path):
    script = _make_fake_nec2pp_py(tmp_path, GUIDE_SAMPLE_OUTPUT)

    result = run_nec2_simulation(
        geometry=DIPOLE_GEOMETRY,
        frequency_hz=300e6,
        timeout_s=10,
        executable=str(script),
        workdir=str(tmp_path / "run"),
    )

    assert result["provenance"] == "SIMULATED"
    assert result["simulator"] == "NEC2++"
    assert result["status"] == "COMPLETED"
    assert result["impedance"]["resistance_ohms"] == pytest.approx(82.6979)
    assert len(result["pattern"]) == 4
    assert result["gain_dbi"] == pytest.approx(8.52)
    assert os.path.exists(result["input_file"])
    # The generated deck itself is on disk and readable/inspectable.
    deck_text = Path(result["input_file"]).read_text()
    assert deck_text.startswith("CM ")
    assert "EN" in deck_text


def test_run_nec2_simulation_end_to_end_with_plane_wave_excitation(tmp_path: Path):
    """A plane_wave excitation geometry runs end to end (deck generation ->
    fake nec2++ -> parsing) and the far-field phase readback a
    reflection-phase measurement needs (e_theta_phase_deg/e_phi_phase_deg)
    is still present and unchanged -- confirming plane-wave illumination
    plus far-field phase readback is now producible from a single
    run_nec2_simulation() call (issue #271)."""
    script = _make_fake_nec2pp_py(tmp_path, GUIDE_SAMPLE_OUTPUT)
    geometry = {
        **DIPOLE_GEOMETRY,
        "excitation": {
            "type": "plane_wave",
            "theta_start_deg": 0.0,
            "phi_start_deg": 0.0,
            "eta_deg": 0.0,
            "theta_step_deg": 10.0,
            "phi_step_deg": 0.0,
            "theta_count": 19,
            "phi_count": 1,
        },
    }

    result = run_nec2_simulation(
        geometry=geometry,
        frequency_hz=300e6,
        timeout_s=10,
        executable=str(script),
        workdir=str(tmp_path / "run_plane_wave"),
    )

    assert result["provenance"] == "SIMULATED"
    assert result["status"] == "COMPLETED"
    deck_text = Path(result["input_file"]).read_text()
    assert "EX 1 " in deck_text
    assert len(result["pattern"]) == 4
    assert result["pattern"][1]["e_theta_phase_deg"] == pytest.approx(-114.38)
    assert result["pattern"][1]["e_phi_phase_deg"] == pytest.approx(0.0)


def test_run_nec2_simulation_propagates_simulator_error_on_failure(tmp_path: Path):
    script = _make_fake_nec2pp(
        tmp_path, 'import sys\nsys.stderr.write("geometry error\\n")\nsys.exit(1)\n'
    )
    with pytest.raises(SimulatorError):
        run_nec2_simulation(
            geometry=DIPOLE_GEOMETRY,
            frequency_hz=300e6,
            timeout_s=10,
            executable=str(script),
            workdir=str(tmp_path / "run2"),
        )
