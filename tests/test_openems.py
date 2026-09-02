# ruff: noqa: E501 -- this file transcribes openEMS log text with long
# progress lines verbatim from the sources cited below; reflowing it would
# obscure the exact format the parser under test reads.
"""Tests for openEMS FDTD-XML generation, execution, and result parsing
(issue #39).

The real `openEMS` binary is NOT installed in this environment (confirmed
via `which openEMS` during implementation) so `OpenemsSimulator.run()` is
exercised here only against small fake "openEMS" scripts checked in below
(via `tmp_path`), per the same Phase 6-8 testing decision ticket #38 used
for NEC2++: subprocess plumbing (argument shape, nonzero exit, timeout) and
result parsing are tested; the physics itself is out of scope for automated
tests.

The FDTD-XML element/attribute format and the openEMS CLI contract were
verified against the primary openEMS/CSXCAD GitHub source -- see the header
comment in simulation/openems.py for the full, per-fact citation list. The
sample console-log text used in test_parse_openems_output_* below is
transcribed from third-party openEMS/pyEMS run logs (a public run-log gist
and GitHub discussion threads, cited in simulation/openems.py's header
comment) cross-referenced against openEMS's own documented endCriteria/NrTS
convergence semantics -- it has NOT been produced by, or checked against, a
real openEMS run, and (per that module's honest caveat) its exact wording
is not guaranteed byte-for-byte, which is why the parser under test matches
it with tolerant regexes rather than a fixed string.
"""

import os
import stat
import sys
from pathlib import Path

import pytest

from simulation.base import SimulatorError
from simulation.openems import (
    OpenemsSimulator,
    generate_openems_xml,
    parse_openems_output,
    run_openems_simulation,
)

# Transcribed (whitespace normalized) from real openEMS/pyEMS run-log
# excerpts -- see this file's module docstring and simulation/openems.py's
# header comment for the citation. A converged run: energy decays past the
# (here, -50dB) end criteria before NrTS is reached.
CONVERGED_LOG = """
[@        4s] Timestep:          500 || Speed:   88.8 MC/s (3.040e-03 s/TS) || Energy: ~7.06e-03 (- 5.00dB)
[@        8s] Timestep:         1326 || Speed:   88.8 MC/s (3.040e-03 s/TS) || Energy: ~7.06e-17 (- 50.00dB)
Time for 1326 iterations with 269780.00 cells : 32.41 sec
Speed: 118.02 MCells/s
"""

# A run that hits NrTS (max timesteps) before the energy decays to the end
# criteria -- includes openEMS's own logged warning for this case.
MAX_TIMESTEPS_LOG = """
[@       60s] Timestep:        30000 || Speed:   53.3 MC/s (8.732e-02 s/TS) || Energy: ~1.00e-03 (- 30.00dB)
Max. number of timesteps was reached before the end-criteria of -50dB was reached
Time for 30000 iterations with 500000.00 cells : 120.00 sec
Speed: 55.00 MCells/s
"""


def _make_fake_openems(tmp_path: Path, body: str) -> Path:
    """Write a small fake 'openEMS' shell script and make it executable."""
    script = tmp_path / "fake_openems.sh"
    script.write_text("#!/bin/sh\n" + body)
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return script


PATCH_GEOMETRY = {
    "materials": [
        {
            "name": "substrate",
            "shape": "box",
            "p1_m": [0.0, 0.0, 0.0],
            "p2_m": [0.03, 0.02, 0.0016],
            "epsilon_r": 3.5,
        }
    ],
    "conductors": [
        {
            "name": "patch",
            "shape": "box",
            "p1_m": [0.005, 0.005, 0.0016],
            "p2_m": [0.025, 0.015, 0.0016],
        },
        {
            "name": "ground",
            "shape": "box",
            "p1_m": [0.0, 0.0, 0.0],
            "p2_m": [0.03, 0.02, 0.0],
        },
    ],
    "ports": [
        {
            "name": "feed",
            "p1_m": [0.015, 0.005, 0.0],
            "p2_m": [0.015, 0.005, 0.0016],
            "direction": "z",
            "resistance_ohms": 50.0,
        }
    ],
    "mesh": {
        "x_lines_m": [0.0, 0.01, 0.02, 0.03],
        "y_lines_m": [0.0, 0.01, 0.02],
        "z_lines_m": [0.0, 0.0016],
    },
    "frequency_hz": 2.45e9,
}


# ---------------------------------------------------------------------------
# FDTD-XML generation
# ---------------------------------------------------------------------------


def test_generate_openems_xml_root_structure():
    xml_text = generate_openems_xml(PATCH_GEOMETRY, {"max_timesteps": 30000, "end_criteria": 1e-5})
    assert xml_text.startswith("<openEMS>")
    assert xml_text.rstrip().endswith("</openEMS>")
    assert '<FDTD NumberOfTimesteps="30000" endCriteria="1e-05">' in xml_text
    assert '<ContinuousStructure CoordSystem="0">' in xml_text


def test_generate_openems_xml_is_well_formed():
    import xml.etree.ElementTree as ET

    xml_text = generate_openems_xml(PATCH_GEOMETRY)
    root = ET.fromstring(xml_text)
    assert root.tag == "openEMS"
    assert root.find("FDTD") is not None
    assert root.find("ContinuousStructure") is not None


def test_generate_openems_xml_mesh_lines():
    xml_text = generate_openems_xml(PATCH_GEOMETRY)
    assert '<XLines Qty="4">0,0.01,0.02,0.03</XLines>' in xml_text
    assert '<YLines Qty="3">0,0.01,0.02</YLines>' in xml_text
    assert '<ZLines Qty="2">0,0.0016</ZLines>' in xml_text


def test_generate_openems_xml_material_property():
    xml_text = generate_openems_xml(PATCH_GEOMETRY)
    assert '<Material Name="substrate">' in xml_text
    assert '<Epsilon X="3.5" Y="3.5" Z="3.5"/>' in xml_text


def test_generate_openems_xml_conductors_as_metal_properties():
    xml_text = generate_openems_xml(PATCH_GEOMETRY)
    assert '<Metal Name="patch">' in xml_text
    assert '<Metal Name="ground">' in xml_text


def test_generate_openems_xml_port_excitation_and_lumped_element():
    xml_text = generate_openems_xml(PATCH_GEOMETRY)
    assert '<Excitation Name="feed_exc" Type="0" Frequency="2.45e+09" Delay="0">' in xml_text
    assert '<Excite X="0" Y="0" Z="1"/>' in xml_text  # z-directed port
    assert '<LumpedElement Name="feed_R" Direction="2" Caps="0" R="50" C="0" L="0" LEtype="0">' in xml_text


def test_generate_openems_xml_cylinder_primitive():
    geometry = {
        **PATCH_GEOMETRY,
        "conductors": [
            {
                "name": "post",
                "shape": "cylinder",
                "p1_m": [0.015, 0.01, 0.0],
                "p2_m": [0.015, 0.01, 0.0016],
                "radius_m": 0.001,
            }
        ],
    }
    xml_text = generate_openems_xml(geometry)
    assert '<Cylinder Radius="0.001">' in xml_text


def test_generate_openems_xml_second_port_not_excited_by_default():
    geometry = {
        **PATCH_GEOMETRY,
        "ports": [
            PATCH_GEOMETRY["ports"][0],
            {
                "name": "thru",
                "p1_m": [0.025, 0.005, 0.0],
                "p2_m": [0.025, 0.005, 0.0016],
                "direction": "z",
                "resistance_ohms": 50.0,
            },
        ],
    }
    xml_text = generate_openems_xml(geometry)
    assert '<Excitation Name="feed_exc"' in xml_text
    assert '<Excitation Name="thru_exc"' not in xml_text
    # Both ports still get a termination resistor.
    assert '<LumpedElement Name="feed_R"' in xml_text
    assert '<LumpedElement Name="thru_R"' in xml_text


def test_generate_openems_xml_no_ports_raises():
    with pytest.raises(ValueError, match="ports"):
        generate_openems_xml({**PATCH_GEOMETRY, "ports": []})


def test_generate_openems_xml_no_mesh_raises():
    geometry = {k: v for k, v in PATCH_GEOMETRY.items() if k != "mesh"}
    with pytest.raises(ValueError, match="mesh"):
        generate_openems_xml(geometry)


def test_generate_openems_xml_active_port_without_frequency_raises():
    geometry = {
        "materials": [],
        "conductors": [],
        "ports": [
            {
                "name": "feed",
                "p1_m": [0.0, 0.0, 0.0],
                "p2_m": [0.0, 0.0, 0.001],
                "direction": "z",
            }
        ],
        "mesh": PATCH_GEOMETRY["mesh"],
    }
    with pytest.raises(ValueError, match="frequency_hz"):
        generate_openems_xml(geometry)


def test_generate_openems_xml_missing_material_field_raises():
    geometry = {**PATCH_GEOMETRY, "materials": [{"name": "bad", "shape": "box", "p1_m": [0, 0, 0]}]}
    with pytest.raises(ValueError, match="p2_m"):
        generate_openems_xml(geometry)


def test_generate_openems_xml_invalid_shape_raises():
    geometry = {
        **PATCH_GEOMETRY,
        "conductors": [
            {"name": "bad", "shape": "sphere", "p1_m": [0, 0, 0], "p2_m": [1, 1, 1]}
        ],
    }
    with pytest.raises(ValueError, match="shape"):
        generate_openems_xml(geometry)


# ---------------------------------------------------------------------------
# Output parsing (against transcribed sample logs -- see module docstring
# for the honest not-verified-against-a-real-binary caveat).
# ---------------------------------------------------------------------------


def test_parse_openems_output_converged_run():
    result = parse_openems_output(CONVERGED_LOG, end_criteria=1e-5, max_timesteps=30000)
    conv = result["convergence"]
    assert conv["terminated_reason"] == "end_criteria"
    assert conv["final_timestep"] == 1326
    assert conv["final_energy_db"] == pytest.approx(-50.0)
    assert conv["total_cells"] == pytest.approx(269780.0)
    assert conv["elapsed_s"] == pytest.approx(32.41)
    assert conv["speed_mcells_per_s"] == pytest.approx(118.02)


def test_parse_openems_output_max_timesteps_run():
    result = parse_openems_output(MAX_TIMESTEPS_LOG, end_criteria=1e-5, max_timesteps=30000)
    conv = result["convergence"]
    assert conv["terminated_reason"] == "max_timesteps"
    assert conv["final_timestep"] == 30000


def test_parse_openems_output_max_timesteps_detected_without_warning_text():
    # Fallback signal: final timestep >= max_timesteps even if the warning
    # text itself doesn't match (format not guaranteed byte-exact, see
    # module docstring).
    log = (
        "[@ 1s] Timestep: 30000 || Speed: 50.0 MC/s (1e-2 s/TS) || Energy: ~1.0e-02 (- 20.00dB)\n"
        "Time for 30000 iterations with 1000.00 cells : 10.0 sec\nSpeed: 100.0 MCells/s\n"
    )
    result = parse_openems_output(log, end_criteria=1e-5, max_timesteps=30000)
    assert result["convergence"]["terminated_reason"] == "max_timesteps"


def test_parse_openems_output_missing_data_returns_unknown_and_none():
    result = parse_openems_output("NOTHING USEFUL HERE\n")
    conv = result["convergence"]
    assert conv["terminated_reason"] == "unknown"
    assert conv["final_timestep"] is None
    assert conv["final_energy_db"] is None


def test_parse_openems_output_s_parameters_and_far_field_are_stubbed():
    result = parse_openems_output(CONVERGED_LOG)
    assert result["s_parameters"]["computed"] is False
    assert "note" in result["s_parameters"]
    assert result["far_field"]["computed"] is False
    assert "note" in result["far_field"]
    assert result["gain_dbi"] is None


# ---------------------------------------------------------------------------
# OpenemsSimulator.run() subprocess plumbing, against fake executables.
# ---------------------------------------------------------------------------


def test_openems_simulator_invokes_xml_file_positionally_with_disable_dumps(tmp_path: Path):
    """Confirm the real openEMS CLI contract (a single positional XML file
    argument, then flags -- see module docstring citation) is what actually
    gets shelled out, and that --disable-dumps is passed by default."""
    script = _make_fake_openems(tmp_path, 'echo "$@"\n')
    xml_file = tmp_path / "model.xml"
    xml_file.write_text("<openEMS/>")

    simulator = OpenemsSimulator(executable=str(script))
    result = simulator.run({"xml_file": str(xml_file), "timeout_s": 10})

    tokens = result.outputs["stdout"].split()
    assert tokens == [str(xml_file), "--disable-dumps"]
    assert result.status == "COMPLETED"
    assert result.provenance == "SIMULATED"


def test_openems_simulator_custom_extra_args(tmp_path: Path):
    script = _make_fake_openems(tmp_path, 'echo "$@"\n')
    xml_file = tmp_path / "model.xml"
    xml_file.write_text("<openEMS/>")

    simulator = OpenemsSimulator(executable=str(script))
    result = simulator.run(
        {"xml_file": str(xml_file), "timeout_s": 10, "extra_args": ["--numThreads=4"]}
    )
    assert result.outputs["stdout"].split() == [str(xml_file), "--numThreads=4"]


def test_openems_simulator_nonzero_exit_raises_simulator_error(tmp_path: Path):
    script = _make_fake_openems(
        tmp_path, 'echo "boom: invalid mesh" >&2\nexit 1\n'
    )
    xml_file = tmp_path / "model.xml"
    xml_file.write_text("<openEMS/>")

    simulator = OpenemsSimulator(executable=str(script))
    with pytest.raises(SimulatorError, match="boom"):
        simulator.run({"xml_file": str(xml_file), "timeout_s": 10})


def test_openems_simulator_timeout_raises_simulator_error(tmp_path: Path):
    script = _make_fake_openems(tmp_path, "sleep 5\n")
    xml_file = tmp_path / "model.xml"
    xml_file.write_text("<openEMS/>")

    simulator = OpenemsSimulator(executable=str(script))
    with pytest.raises(SimulatorError, match="timed out"):
        simulator.run({"xml_file": str(xml_file), "timeout_s": 1})


def test_openems_simulator_missing_xml_file_raises(tmp_path: Path):
    simulator = OpenemsSimulator(executable="openEMS")
    with pytest.raises(SimulatorError, match="not found"):
        simulator.run({"xml_file": str(tmp_path / "does_not_exist.xml")})


def test_openems_simulator_picks_up_executable_from_env_var(tmp_path: Path, monkeypatch):
    script = _make_fake_openems(tmp_path, "exit 0\n")
    monkeypatch.setenv("OPENEMS_BIN", str(script))
    simulator = OpenemsSimulator()
    assert simulator.executable == str(script)


# ---------------------------------------------------------------------------
# run_openems_simulation end to end, against a fake executable that mimics
# the documented log shape (per the ticket's fake-executable testing
# approach). This is plumbing + parsing coverage only -- see module
# docstring for the not-verified-against-a-real-binary caveat.
# ---------------------------------------------------------------------------

_FAKE_OPENEMS_PY = '''#!{python}
import sys

OUTPUT = """{sample}"""

args = sys.argv[1:]
assert args[0].endswith(".xml"), args
assert "--disable-dumps" in args, args
sys.stdout.write(OUTPUT)
sys.exit(0)
'''


def _make_fake_openems_py(tmp_path: Path, sample_output: str) -> Path:
    script = tmp_path / "fake_openems_realistic.py"
    script.write_text(_FAKE_OPENEMS_PY.format(python=sys.executable, sample=sample_output))
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return script


def test_run_openems_simulation_end_to_end_converged(tmp_path: Path):
    script = _make_fake_openems_py(tmp_path, CONVERGED_LOG)

    result = run_openems_simulation(
        geometry=PATCH_GEOMETRY,
        fdtd={"max_timesteps": 30000, "end_criteria": 1e-5},
        timeout_s=10,
        executable=str(script),
        workdir=str(tmp_path / "run"),
    )

    assert result["provenance"] == "SIMULATED"
    assert result["simulator"] == "openEMS"
    assert result["status"] == "COMPLETED"
    assert result["convergence"]["terminated_reason"] == "end_criteria"
    assert result["convergence"]["final_timestep"] == 1326
    assert result["s_parameters"]["computed"] is False
    assert result["far_field"]["computed"] is False
    assert os.path.exists(result["xml_file"])
    xml_text = Path(result["xml_file"]).read_text()
    assert xml_text.startswith("<openEMS>")


def test_run_openems_simulation_end_to_end_max_timesteps(tmp_path: Path):
    script = _make_fake_openems_py(tmp_path, MAX_TIMESTEPS_LOG)

    result = run_openems_simulation(
        geometry=PATCH_GEOMETRY,
        fdtd={"max_timesteps": 30000, "end_criteria": 1e-5},
        timeout_s=10,
        executable=str(script),
        workdir=str(tmp_path / "run2"),
    )
    assert result["convergence"]["terminated_reason"] == "max_timesteps"


def test_run_openems_simulation_propagates_simulator_error_on_failure(tmp_path: Path):
    script = _make_fake_openems(tmp_path, 'echo "mesh error" >&2\nexit 1\n')
    with pytest.raises(SimulatorError):
        run_openems_simulation(
            geometry=PATCH_GEOMETRY,
            timeout_s=10,
            executable=str(script),
            workdir=str(tmp_path / "run3"),
        )
