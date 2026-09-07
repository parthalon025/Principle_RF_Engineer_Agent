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

S-PARAMETER EXTRACTION TESTS (code-review fix against issue #39's own
acceptance criterion): the port_probe_* helpers below construct SYNTHETIC
port voltage/current time-domain data with a closed-form, hand-computable
answer -- a frequency-independent reflection/transmission coefficient (see
_matched_pulse_port_signals' docstring) -- rather than anything resembling
real FDTD physics, and write it in the plain two-column ASCII format
simulation/openems.py's module docstring cites to openEMS's own ReadUI.m.
This validates this module's FFT/incident-reflected-wave/S_ij arithmetic
against a known answer; it is NOT a claim that this synthetic data
resembles a real openEMS run's port probe output byte-for-byte (see that
module's honest caveat).
"""

import os
from pathlib import Path

import numpy as np
import pytest
from conftest import make_fake_executable

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
    """Write a small fake 'openEMS' executable (a Python script body,
    launched cross-platform -- see conftest.make_fake_executable)."""
    return make_fake_executable(tmp_path, body, name="fake_openems")


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
# Synthetic port ProbeBox time-domain data with a closed-form, hand-
# computable S-parameter answer, for the S-parameter extraction tests
# below. See simulation/openems.py's module docstring for the
# v_inc=(V+Z0*I)/2, v_ref=(V-Z0*I)/2, S_ij=v_ref_i/v_inc_j citation this
# construction is checked against.
# ---------------------------------------------------------------------------

_PROBE_Z0 = 50.0
_PROBE_N = 256
_PROBE_DT_S = 2e-12
_PROBE_T0_S = 80e-12
_PROBE_SIGMA_S = 12e-12


def _gaussian_pulse() -> np.ndarray:
    t = np.arange(_PROBE_N) * _PROBE_DT_S
    return np.exp(-((t - _PROBE_T0_S) ** 2) / (2 * _PROBE_SIGMA_S**2))


def _matched_pulse_port_signals(gamma: float = 0.0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Total voltage/current time series for a single port driven by a pure
    incident Gaussian pulse v_inc(t), reflected with a FREQUENCY-INDEPENDENT
    real coefficient `gamma`: V(t) = (1+gamma)*v_inc(t), I(t) =
    (1-gamma)*v_inc(t)/Z0.

    By construction (v_inc=(V+Z0*I)/2, v_ref=(V-Z0*I)/2, see module
    docstring citation): v_inc(t) recovers the pure pulse and
    v_ref(t)=gamma*v_inc(t), so S11(f)=v_ref(f)/v_inc(f)=gamma at every
    frequency -- a hand-computable closed form independent of the FFT
    itself. gamma=0 (the default) is the matched case, S11 should come back
    ~0 (a perfectly matched port has no reflection)."""
    v_inc = _gaussian_pulse()
    t = np.arange(_PROBE_N) * _PROBE_DT_S
    v = (1 + gamma) * v_inc
    i = (1 - gamma) * v_inc / _PROBE_Z0
    return t, v, i


def _thru_pulse_port_signals(tau: float = 1.0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Total voltage/current time series for a passively-terminated
    (matched, no local reflection) SECOND port receiving a transmitted
    copy of the same Gaussian pulse, scaled by a FREQUENCY-INDEPENDENT
    real transmission coefficient `tau`: V(t) = tau*v_inc(t), I(t) =
    -tau*v_inc(t)/Z0 (current sign flipped -- see module docstring's
    calcLumpedPort.m citation on port current-direction convention).

    By construction: v_inc2(t)=0 (nothing incident from outside this
    port), v_ref2(t)=tau*v_inc(t), so S21(f) = v_ref2(f)/v_inc1(f) = tau
    at every frequency -- tau=1.0 (the default) is the lossless, fully-
    transmitting case, S21 should come back ~1."""
    v_inc = _gaussian_pulse()
    t = np.arange(_PROBE_N) * _PROBE_DT_S
    v = tau * v_inc
    i = -tau * v_inc / _PROBE_Z0
    return t, v, i


def _port_probe_ascii(t: np.ndarray, val: np.ndarray) -> str:
    """Render (t, val) as the plain two-column ASCII openEMS port probe
    dump format this project's parser reads (see simulation/openems.py's
    module docstring's ReadUI.m citation) -- a '%' comment header line,
    then one 'time value' row per sample."""
    lines = ["% t val"]
    lines.extend(f"{tt:.9e} {vv:.9e}" for tt, vv in zip(t, val, strict=True))
    return "\n".join(lines) + "\n"


def _write_port_probe_files(
    directory: Path, port_name: str, t: np.ndarray, v: np.ndarray, i: np.ndarray
) -> None:
    (directory / f"{port_name}_ut").write_text(_port_probe_ascii(t, v))
    (directory / f"{port_name}_it").write_text(_port_probe_ascii(t, i))


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
    assert (
        '<LumpedElement Name="feed_R" Direction="2" Caps="0" R="50" C="0" L="0" LEtype="0">'
        in xml_text
    )


def test_generate_openems_xml_port_probe_boxes():
    """The code-review fix (issue #39): each port now also gets Type=0
    (voltage) and Type=1 (current) ProbeBox properties, whose Name is the
    dump filename parse_openems_output()'s S-parameter extraction reads --
    see module docstring citation."""
    xml_text = generate_openems_xml(PATCH_GEOMETRY)
    assert '<ProbeBox Name="feed_ut" Type="0" Weight="-1">' in xml_text
    assert '<ProbeBox Name="feed_it" Type="1" Weight="1" NormDir="2">' in xml_text


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


def test_generate_openems_xml_polygon_primitive():
    """Issue #55: a Polygon conductor primitive -- e.g. a metamaterial
    unit-cell element -- matching CSXCAD's own <Polygon Elevation="..."
    NormDir="..." QtyVertices="N"><Vertex X1="..." X2="..."/>...</Polygon>
    shape (see module docstring citation)."""
    geometry = {
        **PATCH_GEOMETRY,
        "conductors": [
            {
                "name": "srr_element",
                "shape": "polygon",
                "points_m": [[0.0, 0.0], [0.002, 0.0], [0.002, 0.002], [0.0, 0.002]],
                "normal_axis": "z",
                "elevation_m": 0.0016,
            }
        ],
    }
    xml_text = generate_openems_xml(geometry)
    assert '<Metal Name="srr_element">' in xml_text
    assert '<Polygon Elevation="0.0016" NormDir="2" QtyVertices="4">' in xml_text
    assert '<Vertex X1="0" X2="0"/>' in xml_text
    assert '<Vertex X1="0.002" X2="0.002"/>' in xml_text


def test_generate_openems_xml_polygon_primitive_is_well_formed():
    import xml.etree.ElementTree as ET

    geometry = {
        **PATCH_GEOMETRY,
        "conductors": [
            {
                "name": "jerusalem_cross",
                "shape": "polygon",
                "points_m": [[0.0, 0.0], [0.001, 0.0], [0.001, 0.001], [0.0, 0.001]],
            }
        ],
    }
    xml_text = generate_openems_xml(geometry)
    root = ET.fromstring(xml_text)
    polygons = root.findall(".//Polygon")
    assert len(polygons) == 1
    assert polygons[0].get("NormDir") == "2"  # default normal_axis="z"
    vertices = polygons[0].findall("Vertex")
    assert len(vertices) == 4


def test_generate_openems_xml_polygon_missing_points_raises():
    geometry = {
        **PATCH_GEOMETRY,
        "conductors": [{"name": "bad", "shape": "polygon"}],
    }
    with pytest.raises(ValueError, match="points_m"):
        generate_openems_xml(geometry)


def test_generate_openems_xml_polygon_too_few_points_raises():
    geometry = {
        **PATCH_GEOMETRY,
        "conductors": [{"name": "bad", "shape": "polygon", "points_m": [[0.0, 0.0], [1.0, 1.0]]}],
    }
    with pytest.raises(ValueError, match="at least 3"):
        generate_openems_xml(geometry)


def test_generate_openems_xml_polygon_invalid_normal_axis_raises():
    geometry = {
        **PATCH_GEOMETRY,
        "conductors": [
            {
                "name": "bad",
                "shape": "polygon",
                "points_m": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0]],
                "normal_axis": "w",
            }
        ],
    }
    with pytest.raises(ValueError, match="normal_axis"):
        generate_openems_xml(geometry)


def test_generate_openems_xml_polygon_material_uses_points_m_not_p1_p2():
    """A polygon material primitive must not be rejected for lacking the
    box/cylinder-only p1_m/p2_m fields (issue #55 shape-aware validation)."""
    geometry = {
        **PATCH_GEOMETRY,
        "materials": [
            {
                "name": "polygon_dielectric",
                "shape": "polygon",
                "points_m": [[0.0, 0.0], [0.01, 0.0], [0.01, 0.01], [0.0, 0.01]],
                "epsilon_r": 2.2,
            }
        ],
    }
    xml_text = generate_openems_xml(geometry)
    assert '<Material Name="polygon_dielectric">' in xml_text
    assert "<Polygon " in xml_text


def test_generate_openems_xml_existing_box_cylinder_unaffected_by_polygon_support():
    """Additive-not-breaking check (issue #55 acceptance criterion): the
    pre-existing box/cylinder path still works unchanged alongside the new
    polygon path."""
    geometry = {
        **PATCH_GEOMETRY,
        "conductors": [
            *PATCH_GEOMETRY["conductors"],
            {
                "name": "post",
                "shape": "cylinder",
                "p1_m": [0.015, 0.01, 0.0],
                "p2_m": [0.015, 0.01, 0.0016],
                "radius_m": 0.001,
            },
            {
                "name": "srr",
                "shape": "polygon",
                "points_m": [[0.0, 0.0], [0.001, 0.0], [0.001, 0.001]],
            },
        ],
    }
    xml_text = generate_openems_xml(geometry)
    assert '<Metal Name="patch">' in xml_text
    assert '<Cylinder Radius="0.001">' in xml_text
    assert "<Polygon " in xml_text


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
        "conductors": [{"name": "bad", "shape": "sphere", "p1_m": [0, 0, 0], "p2_m": [1, 1, 1]}],
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


def test_parse_openems_output_s_parameters_and_far_field_are_stubbed_without_port_data():
    # No workdir/ports given -- nothing to read port probe dumps from, so
    # this stays honestly uncomputed (far_field always does, see module
    # docstring "SCOPE").
    result = parse_openems_output(CONVERGED_LOG)
    assert result["s_parameters"]["computed"] is False
    assert "note" in result["s_parameters"]
    assert result["far_field"]["computed"] is False
    assert "note" in result["far_field"]
    assert result["gain_dbi"] is None


# ---------------------------------------------------------------------------
# Real S-parameter extraction from port ProbeBox time-domain data (code
# review fix against issue #39's own acceptance criterion). See this
# file's module docstring and the _matched_pulse_port_signals/
# _thru_pulse_port_signals helpers above for the closed-form construction
# these are checked against.
# ---------------------------------------------------------------------------


def test_parse_openems_output_computes_real_s11_for_matched_one_port(tmp_path: Path):
    t, v, i = _matched_pulse_port_signals(gamma=0.0)
    _write_port_probe_files(tmp_path, "feed", t, v, i)

    ports = [{"name": "feed", "resistance_ohms": _PROBE_Z0, "excite": True}]
    result = parse_openems_output(CONVERGED_LOG, workdir=tmp_path, ports=ports)
    s_params = result["s_parameters"]

    assert s_params["computed"] is True
    assert s_params["excited_port"] == "feed"
    assert s_params["z0_ohms"] == _PROBE_Z0
    assert len(s_params["frequency_hz"]) > 0
    s11 = [complex(re, im) for re, im in s_params["values"]["S11"]]
    assert all(abs(v) < 1e-6 for v in s11)  # matched port: S11 ~= 0 exactly


def test_parse_openems_output_computes_real_s11_s21_for_matched_two_port_thru(tmp_path: Path):
    t1, v1, i1 = _matched_pulse_port_signals(gamma=0.0)
    t2, v2, i2 = _thru_pulse_port_signals(tau=1.0)
    _write_port_probe_files(tmp_path, "feed", t1, v1, i1)
    _write_port_probe_files(tmp_path, "thru", t2, v2, i2)

    ports = [
        {"name": "feed", "resistance_ohms": _PROBE_Z0, "excite": True},
        {"name": "thru", "resistance_ohms": _PROBE_Z0, "excite": False},
    ]
    result = parse_openems_output(CONVERGED_LOG, workdir=tmp_path, ports=ports)
    s_params = result["s_parameters"]

    assert s_params["computed"] is True
    assert s_params["excited_port"] == "feed"
    s11 = [complex(re, im) for re, im in s_params["values"]["S11"]]
    s21 = [complex(re, im) for re, im in s_params["values"]["S21"]]
    assert len(s11) == len(s21) == len(s_params["frequency_hz"])
    assert all(abs(v) < 1e-6 for v in s11)  # matched excited port: S11 ~= 0
    assert all(abs(v - 1.0) < 1e-6 for v in s21)  # lossless thru: S21 ~= 1
    # Only the excited port's own column was obtainable from one run.
    assert set(s_params["values"]) == {"S11", "S21"}


def test_parse_openems_output_computes_nonzero_s11_for_mismatched_port(tmp_path: Path):
    # A real, frequency-independent reflection coefficient (a mismatched,
    # but still purely resistive, port) -- time-domain voltage/current are
    # real signals, so gamma itself must be real here (see
    # _matched_pulse_port_signals' docstring).
    gamma = 0.3
    t, v, i = _matched_pulse_port_signals(gamma=gamma)
    _write_port_probe_files(tmp_path, "feed", t, v, i)

    ports = [{"name": "feed", "resistance_ohms": _PROBE_Z0, "excite": True}]
    result = parse_openems_output(CONVERGED_LOG, workdir=tmp_path, ports=ports)
    s11 = [complex(re, im) for re, im in result["s_parameters"]["values"]["S11"]]
    assert all(abs(v - gamma) < 1e-6 for v in s11)


def test_parse_openems_output_1port_computed_writes_touchstone_file(tmp_path: Path):
    t, v, i = _matched_pulse_port_signals(gamma=0.0)
    _write_port_probe_files(tmp_path, "feed", t, v, i)

    ports = [{"name": "feed", "resistance_ohms": _PROBE_Z0, "excite": True}]
    result = parse_openems_output(CONVERGED_LOG, workdir=tmp_path, ports=ports)
    s_params = result["s_parameters"]

    touchstone_file = s_params.get("touchstone_file")
    assert touchstone_file is not None
    assert Path(touchstone_file).exists()

    import skrf as rf

    network = rf.Network(touchstone_file)
    assert network.nports == 1
    assert np.max(np.abs(network.s[:, 0, 0])) < 1e-6


def test_parse_openems_output_2port_does_not_write_touchstone_file(tmp_path: Path):
    t1, v1, i1 = _matched_pulse_port_signals(gamma=0.0)
    t2, v2, i2 = _thru_pulse_port_signals(tau=1.0)
    _write_port_probe_files(tmp_path, "feed", t1, v1, i1)
    _write_port_probe_files(tmp_path, "thru", t2, v2, i2)

    ports = [
        {"name": "feed", "resistance_ohms": _PROBE_Z0, "excite": True},
        {"name": "thru", "resistance_ohms": _PROBE_Z0, "excite": False},
    ]
    result = parse_openems_output(CONVERGED_LOG, workdir=tmp_path, ports=ports)
    # A full 2-port network needs S12/S22 too (a second, separately-excited
    # run) -- not fabricated, so no touchstone file is written here.
    assert "touchstone_file" not in result["s_parameters"]


def test_parse_openems_output_s_parameters_computed_false_when_probe_files_missing(tmp_path: Path):
    ports = [{"name": "feed", "resistance_ohms": 50.0, "excite": True}]
    result = parse_openems_output(CONVERGED_LOG, workdir=tmp_path, ports=ports)
    s_params = result["s_parameters"]
    assert s_params["computed"] is False
    assert "feed" in s_params["note"]


def test_parse_openems_output_s_parameters_computed_false_on_mismatched_port_impedances(
    tmp_path: Path,
):
    t1, v1, i1 = _matched_pulse_port_signals(gamma=0.0)
    t2, v2, i2 = _thru_pulse_port_signals(tau=1.0)
    _write_port_probe_files(tmp_path, "feed", t1, v1, i1)
    _write_port_probe_files(tmp_path, "thru", t2, v2, i2)

    ports = [
        {"name": "feed", "resistance_ohms": 50.0, "excite": True},
        {"name": "thru", "resistance_ohms": 75.0, "excite": False},
    ]
    result = parse_openems_output(CONVERGED_LOG, workdir=tmp_path, ports=ports)
    s_params = result["s_parameters"]
    assert s_params["computed"] is False
    assert "resistance_ohms" in s_params["note"]


# ---------------------------------------------------------------------------
# OpenemsSimulator.run() subprocess plumbing, against fake executables.
# ---------------------------------------------------------------------------


def test_openems_simulator_invokes_xml_file_positionally_with_disable_dumps(tmp_path: Path):
    """Confirm the real openEMS CLI contract (a single positional XML file
    argument, then flags -- see module docstring citation) is what actually
    gets shelled out, and that --disable-dumps is passed by default."""
    script = _make_fake_openems(tmp_path, "import sys\nsys.stdout.write(' '.join(sys.argv[1:]))\n")
    xml_file = tmp_path / "model.xml"
    xml_file.write_text("<openEMS/>")

    simulator = OpenemsSimulator(executable=str(script))
    result = simulator.run({"xml_file": str(xml_file), "timeout_s": 10})

    tokens = result.outputs["stdout"].split()
    assert tokens == [str(xml_file), "--disable-dumps"]
    assert result.status == "COMPLETED"
    assert result.provenance == "SIMULATED"


def test_openems_simulator_custom_extra_args(tmp_path: Path):
    script = _make_fake_openems(tmp_path, "import sys\nsys.stdout.write(' '.join(sys.argv[1:]))\n")
    xml_file = tmp_path / "model.xml"
    xml_file.write_text("<openEMS/>")

    simulator = OpenemsSimulator(executable=str(script))
    result = simulator.run(
        {"xml_file": str(xml_file), "timeout_s": 10, "extra_args": ["--numThreads=4"]}
    )
    assert result.outputs["stdout"].split() == [str(xml_file), "--numThreads=4"]


def test_openems_simulator_nonzero_exit_raises_simulator_error(tmp_path: Path):
    script = _make_fake_openems(
        tmp_path, 'import sys\nsys.stderr.write("boom: invalid mesh\\n")\nsys.exit(1)\n'
    )
    xml_file = tmp_path / "model.xml"
    xml_file.write_text("<openEMS/>")

    simulator = OpenemsSimulator(executable=str(script))
    with pytest.raises(SimulatorError, match="boom"):
        simulator.run({"xml_file": str(xml_file), "timeout_s": 10})


def test_openems_simulator_timeout_raises_simulator_error(tmp_path: Path):
    script = _make_fake_openems(tmp_path, "import time\ntime.sleep(5)\n")
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
    script = _make_fake_openems(tmp_path, "import sys\nsys.exit(0)\n")
    monkeypatch.setenv("OPENEMS_BIN", str(script))
    simulator = OpenemsSimulator()
    assert simulator.executable == str(script)


# ---------------------------------------------------------------------------
# run_openems_simulation end to end, against a fake executable that mimics
# the documented log shape (per the ticket's fake-executable testing
# approach). This is plumbing + parsing coverage only -- see module
# docstring for the not-verified-against-a-real-binary caveat.
# ---------------------------------------------------------------------------

_FAKE_OPENEMS_PY = '''
import sys

OUTPUT = """{sample}"""

args = sys.argv[1:]
assert args[0].endswith(".xml"), args
assert "--disable-dumps" in args, args
sys.stdout.write(OUTPUT)
sys.exit(0)
'''


def _make_fake_openems_py(tmp_path: Path, sample_output: str) -> Path:
    body = _FAKE_OPENEMS_PY.format(sample=sample_output)
    return make_fake_executable(tmp_path, body, name="fake_openems_realistic")


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
    script = _make_fake_openems(
        tmp_path, 'import sys\nsys.stderr.write("mesh error\\n")\nsys.exit(1)\n'
    )
    with pytest.raises(SimulatorError):
        run_openems_simulation(
            geometry=PATCH_GEOMETRY,
            timeout_s=10,
            executable=str(script),
            workdir=str(tmp_path / "run3"),
        )


# ---------------------------------------------------------------------------
# run_openems_simulation end to end with a fake executable EXTENDED to also
# emit port ProbeBox time-domain dump files (as a real openEMS run would --
# see simulation/openems.py's module docstring citations), so the real
# FFT-based S-parameter path is exercised through the full run_openems_
# simulation() -> parse_openems_output() -> _compute_s_parameters_from_
# probes() call chain, not just parse_openems_output() directly.
# ---------------------------------------------------------------------------

_FAKE_OPENEMS_WITH_PORTS_PY = '''
import sys

PORT_FILES = {port_files!r}
for _name, _content in PORT_FILES.items():
    with open(_name, "w") as _f:
        _f.write(_content)

OUTPUT = """{sample}"""

args = sys.argv[1:]
assert args[0].endswith(".xml"), args
assert "--disable-dumps" in args, args
sys.stdout.write(OUTPUT)
sys.exit(0)
'''


def _make_fake_openems_with_ports_py(
    tmp_path: Path, sample_output: str, port_files: dict[str, str]
) -> Path:
    """Like _make_fake_openems_py, but the fake script ALSO writes
    `port_files` (dump filename -> full ASCII content) into its cwd before
    printing OUTPUT -- mimicking a real openEMS run's ProbeBox dumps."""
    body = _FAKE_OPENEMS_WITH_PORTS_PY.format(sample=sample_output, port_files=port_files)
    return make_fake_executable(tmp_path, body, name="fake_openems_with_ports")


def test_run_openems_simulation_end_to_end_computes_real_s_parameters(tmp_path: Path):
    t, v, i = _matched_pulse_port_signals(gamma=0.0)
    port_files = {
        "feed_ut": _port_probe_ascii(t, v),
        "feed_it": _port_probe_ascii(t, i),
    }
    script = _make_fake_openems_with_ports_py(tmp_path, CONVERGED_LOG, port_files)

    result = run_openems_simulation(
        geometry=PATCH_GEOMETRY,
        fdtd={"max_timesteps": 30000, "end_criteria": 1e-5},
        timeout_s=10,
        executable=str(script),
        workdir=str(tmp_path / "run"),
    )

    assert result["provenance"] == "SIMULATED"
    assert result["convergence"]["terminated_reason"] == "end_criteria"
    s_params = result["s_parameters"]
    assert s_params["computed"] is True
    s11 = [complex(re, im) for re, im in s_params["values"]["S11"]]
    assert all(abs(v) < 1e-6 for v in s11)  # matched patch feed: S11 ~= 0
    # far-field genuinely still needs the separate nf2ff tool.
    assert result["far_field"]["computed"] is False
    # 1-port + computed -> a real Touchstone file, surfaced at top level
    # for rf_tools.correlation integration (mirrors simulation/hfss.py).
    assert "touchstone_file" in result
    assert os.path.exists(result["touchstone_file"])

    import skrf as rf

    network = rf.Network(result["touchstone_file"])
    assert network.nports == 1
    assert np.max(np.abs(network.s[:, 0, 0])) < 1e-6


def test_run_openems_simulation_end_to_end_without_port_dumps_stays_uncomputed(tmp_path: Path):
    # The pre-existing fake executable (no ProbeBox dumps) still leaves
    # S-parameters honestly uncomputed -- confirms this pass didn't quietly
    # start fabricating results when the port data just isn't there.
    script = _make_fake_openems_py(tmp_path, CONVERGED_LOG)

    result = run_openems_simulation(
        geometry=PATCH_GEOMETRY,
        fdtd={"max_timesteps": 30000, "end_criteria": 1e-5},
        timeout_s=10,
        executable=str(script),
        workdir=str(tmp_path / "run"),
    )
    assert result["s_parameters"]["computed"] is False
    assert "touchstone_file" not in result
