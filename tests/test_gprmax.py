"""Tests for gprMax .in deck generation, execution, and .out (HDF5) result
parsing (issue #63: ground-coupled / lossy-half-space EM simulation).

gprMax genuinely cannot be installed in this environment: it is not
pip-installable at all (confirmed via direct PyPI JSON-API queries during
implementation, both HTTP 404 -- see simulation/gprmax.py's module
docstring "CORRECTION" section) and requires a conda environment plus a C
compiler with OpenMP support to build its Cython extensions. So this file
exercises `GprmaxSimulator.run()`'s subprocess-invocation contract against
small fake "python -m gprMax" scripts (mirroring tests/test_nec2pp.py's/
tests/test_openems.py's own fake-executable pattern, adjusted for gprMax
having no standalone binary -- see that module's docstring), and
`parse_gprmax_output()` against synthetic .out HDF5 files hand-built with
h5py to match the documented schema -- NOT against a real gprMax run's
actual output. The .in command syntax and .out HDF5 structure themselves
were verified against gprMax's own primary documentation (docs.gprmax.com/
github.com/gprMax/gprMax's `master` branch) -- see simulation/gprmax.py's
module docstring for the full per-fact citation list.
"""

import sys
from pathlib import Path

import h5py
import numpy as np
import pytest
from conftest import make_fake_executable

from simulation.base import SimulatorError
from simulation.gprmax import (
    GprmaxSimulator,
    generate_gprmax_input,
    parse_gprmax_output,
    run_gprmax_simulation,
)

BASIC_GEOMETRY = {
    "domain_m": [0.1, 0.1, 0.1],
    "resolution_m": 0.002,
    "port": {
        "polarization": "z",
        "position_m": [0.05, 0.05, 0.05],
        "center_frequency_hz": 1.0e9,
    },
}


# ---------------------------------------------------------------------------
# .in deck generation
# ---------------------------------------------------------------------------


def test_generate_gprmax_input_basic_cards_and_order():
    deck = generate_gprmax_input(BASIC_GEOMETRY, fdtd={"time_window_s": 6e-8})
    lines = deck.strip("\n").split("\n")

    assert lines[0].startswith("#title:")
    assert lines[1] == "#domain: 0.1 0.1 0.1"
    assert lines[2] == "#dx_dy_dz: 0.002 0.002 0.002"
    assert lines[3] == "#time_window: 6e-08"
    # No half-space, materials, or conductors in the minimal geometry.
    assert not any(line.startswith("#material") for line in lines)
    assert not any(line.startswith("#box") for line in lines)
    assert "#waveform: gaussian 1 1e+09 gprmax_adapter_src" in lines
    assert "#transmission_line: z 0.05 0.05 0.05 50 gprmax_adapter_src" in lines


def test_generate_gprmax_input_time_window_iterations_form():
    deck = generate_gprmax_input(BASIC_GEOMETRY, fdtd={"time_window_iterations": 5000})
    lines = deck.split("\n")
    assert "#time_window: 5000" in lines


def test_generate_gprmax_input_requires_exactly_one_time_window_field():
    with pytest.raises(ValueError, match="time_window"):
        generate_gprmax_input(BASIC_GEOMETRY, fdtd={})
    with pytest.raises(ValueError, match="time_window"):
        generate_gprmax_input(
            BASIC_GEOMETRY, fdtd={"time_window_s": 1e-8, "time_window_iterations": 100}
        )


def test_generate_gprmax_input_missing_domain_raises():
    geometry = {"resolution_m": 0.001, "port": BASIC_GEOMETRY["port"]}
    with pytest.raises(ValueError, match="domain_m"):
        generate_gprmax_input(geometry, fdtd={"time_window_s": 1e-8})


def test_generate_gprmax_input_missing_resolution_raises():
    geometry = {"domain_m": [0.1, 0.1, 0.1], "port": BASIC_GEOMETRY["port"]}
    with pytest.raises(ValueError, match="resolution_m"):
        generate_gprmax_input(geometry, fdtd={"time_window_s": 1e-8})


def test_generate_gprmax_input_resolution_as_uniform_float():
    deck = generate_gprmax_input(BASIC_GEOMETRY, fdtd={"time_window_s": 1e-8})
    assert "#dx_dy_dz: 0.002 0.002 0.002" in deck.split("\n")


def test_generate_gprmax_input_resolution_as_per_axis_list():
    geometry = {**BASIC_GEOMETRY, "resolution_m": [0.001, 0.002, 0.003]}
    deck = generate_gprmax_input(geometry, fdtd={"time_window_s": 1e-8})
    assert "#dx_dy_dz: 0.001 0.002 0.003" in deck.split("\n")


def test_generate_gprmax_input_pml_cells_and_num_threads():
    deck = generate_gprmax_input(
        BASIC_GEOMETRY, fdtd={"time_window_s": 1e-8, "pml_cells": 8, "num_threads": 4}
    )
    lines = deck.split("\n")
    assert "#pml_cells: 8" in lines
    assert "#num_threads: 4" in lines


def test_generate_gprmax_input_pml_cells_six_sides():
    deck = generate_gprmax_input(
        BASIC_GEOMETRY, fdtd={"time_window_s": 1e-8, "pml_cells": [1, 2, 3, 4, 5, 6]}
    )
    assert "#pml_cells: 1 2 3 4 5 6" in deck.split("\n")


def test_generate_gprmax_input_half_space_material_and_box_ordering():
    geometry = {
        **BASIC_GEOMETRY,
        "half_space": {"z_m": 0.04, "epsilon_r": 6.0, "conductivity_s_m": 0.02},
    }
    deck = generate_gprmax_input(geometry, fdtd={"time_window_s": 1e-8})
    lines = deck.split("\n")
    material_idx = next(i for i, line in enumerate(lines) if line.startswith("#material:"))
    box_idx = next(i for i, line in enumerate(lines) if line.startswith("#box:"))
    assert lines[material_idx] == "#material: 6 0.02 1 0 ground"
    assert lines[box_idx] == "#box: 0 0 0 0.1 0.1 0.04 ground"
    # The half-space's #material/#box must both precede the #transmission_line
    # excitation -- and, more importantly for the "layered canvas" ordering
    # (see module docstring citation), any of the caller's own materials/
    # conductors below it in this test file's other cases.
    tl_idx = next(i for i, line in enumerate(lines) if line.startswith("#transmission_line:"))
    assert material_idx < tl_idx and box_idx < tl_idx


def test_generate_gprmax_input_half_space_missing_field_raises():
    geometry = {**BASIC_GEOMETRY, "half_space": {"z_m": 0.04, "epsilon_r": 6.0}}
    with pytest.raises(ValueError, match="conductivity_s_m"):
        generate_gprmax_input(geometry, fdtd={"time_window_s": 1e-8})


def test_generate_gprmax_input_materials_and_conductors_after_half_space():
    geometry = {
        **BASIC_GEOMETRY,
        "half_space": {"z_m": 0.04, "epsilon_r": 6.0, "conductivity_s_m": 0.02},
        "materials": [
            {
                "name": "substrate",
                "shape": "box",
                "p1_m": [0.03, 0.03, 0.04],
                "p2_m": [0.07, 0.07, 0.042],
                "epsilon_r": 3.5,
                "conductivity_s_m": 0.0,
            }
        ],
        "conductors": [
            {"shape": "box", "p1_m": [0.035, 0.035, 0.042], "p2_m": [0.065, 0.065, 0.042]}
        ],
    }
    deck = generate_gprmax_input(geometry, fdtd={"time_window_s": 1e-8})
    lines = deck.split("\n")

    ground_box_idx = next(
        i for i, line in enumerate(lines) if "ground" in line and line.startswith("#box")
    )
    substrate_material_idx = next(
        i for i, line in enumerate(lines) if line.startswith("#material:") and "substrate" in line
    )
    substrate_box_idx = next(
        i for i, line in enumerate(lines) if line.startswith("#box:") and "substrate" in line
    )
    pec_box_idx = next(i for i, line in enumerate(lines) if line.endswith(" pec"))

    # "Layered canvas" ordering (module docstring citation): ground fill
    # first, caller's own dielectric next, PEC conductor last -- so PEC
    # correctly overrides substrate which correctly overrides ground where
    # they overlap.
    assert ground_box_idx < substrate_material_idx < substrate_box_idx < pec_box_idx
    assert lines[substrate_material_idx] == "#material: 3.5 0 1 0 substrate"


def test_generate_gprmax_input_material_dispersion_debye_line_follows_material(
    tmp_path: Path,
):
    # Reproduces gprMax's own documented worked example verbatim (docs/
    # source/input.rst, "#add_dispersion_debye:" section): a single-pole
    # Debye water model with eps_r_infinity=4.9 in #material and
    # delta_eps_r=75.2, tau=9.231e-12s in #add_dispersion_debye -- the
    # exact numbers gprMax's own docs use for
    # "#material: 4.9 0 1 0 my_water" / "#add_dispersion_debye: 1 75.2
    # 9.231e-12 my_water" (material named "water" here, not "my_water", to
    # keep this test's material distinct from the doc's own identifier).
    geometry = {
        **BASIC_GEOMETRY,
        "materials": [
            {
                "name": "water",
                "shape": "box",
                "p1_m": [0.0, 0.0, 0.0],
                "p2_m": [0.01, 0.01, 0.01],
                "epsilon_r": 4.9,
                "conductivity_s_m": 0.0,
                "dispersion": {
                    "model": "debye",
                    "poles": [{"delta_epsilon_r": 75.2, "tau_s": 9.231e-12}],
                },
            }
        ],
    }
    deck = generate_gprmax_input(geometry, fdtd={"time_window_s": 1e-8})
    lines = deck.split("\n")

    material_idx = next(
        i for i, line in enumerate(lines) if line.startswith("#material:") and "water" in line
    )
    assert lines[material_idx] == "#material: 4.9 0 1 0 water"
    assert lines[material_idx + 1] == "#add_dispersion_debye: 1 75.2 9.231e-12 water"


def test_generate_gprmax_input_material_dispersion_lorentz_line_follows_material():
    geometry = {
        **BASIC_GEOMETRY,
        "materials": [
            {
                "name": "fss_resonator",
                "shape": "box",
                "p1_m": [0.0, 0.0, 0.0],
                "p2_m": [0.01, 0.01, 0.01],
                "epsilon_r": 2.0,
                "conductivity_s_m": 0.0,
                "dispersion": {
                    "model": "lorentz",
                    "poles": [{"delta_epsilon_r": 2.0, "omega_hz": 5e9, "delta_hz": 1e8}],
                },
            }
        ],
    }
    deck = generate_gprmax_input(geometry, fdtd={"time_window_s": 1e-8})
    lines = deck.split("\n")

    material_idx = next(
        i
        for i, line in enumerate(lines)
        if line.startswith("#material:") and "fss_resonator" in line
    )
    assert lines[material_idx + 1] == "#add_dispersion_lorentz: 1 2 5e+09 1e+08 fss_resonator"


def test_generate_gprmax_input_half_space_dispersion_drude_line_follows_material():
    geometry = {
        **BASIC_GEOMETRY,
        "half_space": {
            "z_m": 0.04,
            "epsilon_r": 1.0,
            "conductivity_s_m": 0.0,
            "dispersion": {
                "model": "drude",
                "poles": [{"omega_hz": 1.37e16, "gamma_hz": 4.06e13}],
            },
        },
    }
    deck = generate_gprmax_input(geometry, fdtd={"time_window_s": 1e-8})
    lines = deck.split("\n")

    material_idx = next(
        i for i, line in enumerate(lines) if line.startswith("#material:") and "ground" in line
    )
    assert lines[material_idx + 1] == "#add_dispersion_drude: 1 1.37e+16 4.06e+13 ground"
    # The dispersion line must precede the ground's #box (and everything
    # else downstream) exactly like the #material line it modifies.
    box_idx = next(i for i, line in enumerate(lines) if line.startswith("#box:"))
    assert material_idx + 1 < box_idx


def test_generate_gprmax_input_dispersion_multi_pole():
    # #add_dispersion_lorentz's own syntax ("i1 f1 f2 f3 f4 f5 f6 ... str1")
    # repeats a (delta_epsilon_r, omega_hz, delta_hz) triplet per pole, with
    # i1 counting how many -- verify two poles round-trip correctly.
    geometry = {
        **BASIC_GEOMETRY,
        "materials": [
            {
                "name": "two_pole",
                "shape": "box",
                "p1_m": [0.0, 0.0, 0.0],
                "p2_m": [0.01, 0.01, 0.01],
                "epsilon_r": 2.0,
                "conductivity_s_m": 0.0,
                "dispersion": {
                    "model": "lorentz",
                    "poles": [
                        {"delta_epsilon_r": 1.0, "omega_hz": 3e9, "delta_hz": 5e7},
                        {"delta_epsilon_r": 0.5, "omega_hz": 8e9, "delta_hz": 2e8},
                    ],
                },
            }
        ],
    }
    deck = generate_gprmax_input(geometry, fdtd={"time_window_s": 1e-8})
    assert "#add_dispersion_lorentz: 2 1 3e+09 5e+07 0.5 8e+09 2e+08 two_pole" in deck.split("\n")


def test_generate_gprmax_input_dispersion_unrecognized_model_raises():
    geometry = {
        **BASIC_GEOMETRY,
        "materials": [
            {
                "name": "bad",
                "shape": "box",
                "p1_m": [0.0, 0.0, 0.0],
                "p2_m": [0.01, 0.01, 0.01],
                "epsilon_r": 2.0,
                "conductivity_s_m": 0.0,
                "dispersion": {"model": "cole_cole", "poles": [{"delta_epsilon_r": 1.0}]},
            }
        ],
    }
    with pytest.raises(ValueError, match="debye.*lorentz.*drude"):
        generate_gprmax_input(geometry, fdtd={"time_window_s": 1e-8})


def test_generate_gprmax_input_dispersion_missing_field_raises():
    geometry = {
        **BASIC_GEOMETRY,
        "materials": [
            {
                "name": "bad",
                "shape": "box",
                "p1_m": [0.0, 0.0, 0.0],
                "p2_m": [0.01, 0.01, 0.01],
                "epsilon_r": 2.0,
                "conductivity_s_m": 0.0,
                "dispersion": {"model": "debye"},
            }
        ],
    }
    with pytest.raises(ValueError, match="poles"):
        generate_gprmax_input(geometry, fdtd={"time_window_s": 1e-8})


def test_generate_gprmax_input_dispersion_pole_missing_field_raises():
    geometry = {
        **BASIC_GEOMETRY,
        "materials": [
            {
                "name": "bad",
                "shape": "box",
                "p1_m": [0.0, 0.0, 0.0],
                "p2_m": [0.01, 0.01, 0.01],
                "epsilon_r": 2.0,
                "conductivity_s_m": 0.0,
                "dispersion": {"model": "debye", "poles": [{"delta_epsilon_r": 75.2}]},
            }
        ],
    }
    with pytest.raises(ValueError, match="tau_s"):
        generate_gprmax_input(geometry, fdtd={"time_window_s": 1e-8})


def test_generate_gprmax_input_no_dispersion_key_unchanged():
    # Acceptance criterion (issue #277): omitting `dispersion` -- the call
    # shape every OTHER test in this file already uses -- must produce
    # output identical to before this field existed, i.e. no
    # #add_dispersion_* line appears anywhere, for either a `materials`
    # entry or `half_space`.
    geometry = {
        **BASIC_GEOMETRY,
        "half_space": {"z_m": 0.04, "epsilon_r": 6.0, "conductivity_s_m": 0.02},
        "materials": [
            {
                "name": "substrate",
                "shape": "box",
                "p1_m": [0.03, 0.03, 0.04],
                "p2_m": [0.07, 0.07, 0.042],
                "epsilon_r": 3.5,
                "conductivity_s_m": 0.0,
            }
        ],
    }
    deck = generate_gprmax_input(geometry, fdtd={"time_window_s": 1e-8})
    assert not any(line.startswith("#add_dispersion") for line in deck.split("\n"))


def test_generate_gprmax_input_material_missing_field_raises():
    geometry = {
        **BASIC_GEOMETRY,
        "materials": [
            {"shape": "box", "p1_m": [0, 0, 0], "p2_m": [0.01, 0.01, 0.01], "epsilon_r": 3.0}
        ],
    }
    with pytest.raises(ValueError, match="conductivity_s_m"):
        generate_gprmax_input(geometry, fdtd={"time_window_s": 1e-8})


def test_generate_gprmax_input_cylinder_primitive_requires_radius():
    geometry = {
        **BASIC_GEOMETRY,
        "conductors": [{"shape": "cylinder", "p1_m": [0, 0, 0], "p2_m": [0, 0, 0.01]}],
    }
    with pytest.raises(ValueError, match="radius_m"):
        generate_gprmax_input(geometry, fdtd={"time_window_s": 1e-8})


def test_generate_gprmax_input_cylinder_primitive_renders_radius():
    geometry = {
        **BASIC_GEOMETRY,
        "conductors": [
            {
                "shape": "cylinder",
                "p1_m": [0.01, 0.01, 0],
                "p2_m": [0.01, 0.01, 0.02],
                "radius_m": 0.0015,
            }
        ],
    }
    deck = generate_gprmax_input(geometry, fdtd={"time_window_s": 1e-8})
    assert "#cylinder: 0.01 0.01 0 0.01 0.01 0.02 0.0015 pec" in deck.split("\n")


def test_generate_gprmax_input_invalid_shape_raises():
    geometry = {
        **BASIC_GEOMETRY,
        "conductors": [{"shape": "sphere", "p1_m": [0, 0, 0], "p2_m": [1, 1, 1]}],
    }
    with pytest.raises(ValueError, match="shape"):
        generate_gprmax_input(geometry, fdtd={"time_window_s": 1e-8})


def test_generate_gprmax_input_missing_port_raises():
    geometry = {"domain_m": [0.1, 0.1, 0.1], "resolution_m": 0.002}
    with pytest.raises(ValueError, match="port"):
        generate_gprmax_input(geometry, fdtd={"time_window_s": 1e-8})


def test_generate_gprmax_input_invalid_polarization_raises():
    geometry = {**BASIC_GEOMETRY, "port": {**BASIC_GEOMETRY["port"], "polarization": "w"}}
    with pytest.raises(ValueError, match="polarization"):
        generate_gprmax_input(geometry, fdtd={"time_window_s": 1e-8})


def test_generate_gprmax_input_resistance_out_of_bounds_raises():
    # gprMax's own documented #transmission_line bound (module docstring
    # citation): strictly between 0 and 376.73 Ohms (free-space impedance).
    geometry = {**BASIC_GEOMETRY, "port": {**BASIC_GEOMETRY["port"], "resistance_ohms": 400.0}}
    with pytest.raises(ValueError, match="376.73"):
        generate_gprmax_input(geometry, fdtd={"time_window_s": 1e-8})


def test_generate_gprmax_input_missing_center_frequency_raises():
    geometry = {
        "domain_m": [0.1, 0.1, 0.1],
        "resolution_m": 0.002,
        "port": {"polarization": "z", "position_m": [0.05, 0.05, 0.05]},
    }
    with pytest.raises(ValueError, match="center_frequency_hz"):
        generate_gprmax_input(geometry, fdtd={"time_window_s": 1e-8})


def test_generate_gprmax_input_frequency_hz_fallback_on_geometry():
    geometry = {
        "domain_m": [0.1, 0.1, 0.1],
        "resolution_m": 0.002,
        "frequency_hz": 2.45e9,
        "port": {"polarization": "z", "position_m": [0.05, 0.05, 0.05]},
    }
    deck = generate_gprmax_input(geometry, fdtd={"time_window_s": 1e-8})
    assert "#waveform: gaussian 1 2.45e+09 gprmax_adapter_src" in deck.split("\n")


def test_generate_gprmax_input_receivers():
    geometry = {
        **BASIC_GEOMETRY,
        "receivers": [
            {"name": "probe1", "position_m": [0.06, 0.05, 0.05], "components": "Ez Hy"},
            {"position_m": [0.07, 0.05, 0.05]},
        ],
    }
    deck = generate_gprmax_input(geometry, fdtd={"time_window_s": 1e-8})
    lines = deck.split("\n")
    assert "#rx: 0.06 0.05 0.05 probe1 Ez Hy" in lines
    assert "#rx: 0.07 0.05 0.05 rx2" in lines


def test_generate_gprmax_input_receiver_missing_position_raises():
    geometry = {**BASIC_GEOMETRY, "receivers": [{"name": "probe1"}]}
    with pytest.raises(ValueError, match="position_m"):
        generate_gprmax_input(geometry, fdtd={"time_window_s": 1e-8})


# ---------------------------------------------------------------------------
# .out (HDF5) result parsing
# ---------------------------------------------------------------------------


def _gaussian_pulse(n: int, dt: float, t0: float, tau: float) -> np.ndarray:
    t = np.arange(n) * dt
    return np.exp(-(((t - t0) / tau) ** 2))


def write_fake_out_file(
    path: Path,
    vinc: np.ndarray,
    vtotal: np.ndarray,
    itotal: np.ndarray,
    dt: float,
    receivers: dict[str, dict[str, np.ndarray]] | None = None,
) -> None:
    """Hand-build a gprMax .out HDF5 file matching the documented schema
    (module docstring citation): root attribute `dt`, a `/tls/tl1/` group
    with Vinc/Vtotal/Itotal datasets, and optionally `/rxs/rxN/` groups
    with named field-component datasets."""
    with h5py.File(path, "w") as f:
        f.attrs["dt"] = dt
        f.attrs["Iterations"] = len(vinc)
        tl = f.create_group("tls/tl1")
        tl.create_dataset("Vinc", data=vinc)
        tl.create_dataset("Vtotal", data=vtotal)
        tl.create_dataset("Itotal", data=itotal)
        for idx, (_name, components) in enumerate(sorted((receivers or {}).items()), start=1):
            rx_group = f.create_group(f"rxs/rx{idx}")
            for comp, values in components.items():
                rx_group.create_dataset(comp, data=values)


def test_parse_gprmax_output_missing_file_returns_computed_false():
    result = parse_gprmax_output("/does/not/exist.out", port={"resistance_ohms": 50.0})
    assert result["s_parameters"]["computed"] is False
    assert result["impedance"]["computed"] is False
    assert result["receivers"] == {}


def test_parse_gprmax_output_missing_tl_group_returns_computed_false(tmp_path: Path):
    out_path = tmp_path / "model.in.out"
    with h5py.File(out_path, "w") as f:
        f.attrs["dt"] = 1e-11
        f.attrs["Iterations"] = 10

    result = parse_gprmax_output(out_path, port={"resistance_ohms": 50.0})
    assert result["s_parameters"]["computed"] is False
    assert "tls/tl1" in result["s_parameters"]["note"]


def test_parse_gprmax_output_computes_s11_closed_form(tmp_path: Path):
    # Vtotal = (1+GAMMA)*Vinc pointwise in time => Vref = GAMMA*Vinc pointwise
    # => S11(f) = FFT(Vref)/FFT(Vinc) = GAMMA at every frequency -- an exact,
    # frequency-independent closed-form answer (same technique
    # tests/test_openems.py uses for its own FFT-based S-parameter check).
    n, dt = 512, 1e-11
    vinc = _gaussian_pulse(n, dt, t0=n * dt / 4, tau=n * dt / 20)
    gamma = 0.25
    vtotal = (1 + gamma) * vinc
    itotal = vtotal / 50.0  # arbitrary nonzero current, not used by S11 itself

    out_path = tmp_path / "model.in.out"
    write_fake_out_file(out_path, vinc, vtotal, itotal, dt)

    result = parse_gprmax_output(out_path, port={"resistance_ohms": 50.0, "name": "feed"})
    s_params = result["s_parameters"]
    assert s_params["computed"] is True
    assert s_params["port"] == "feed"
    values = s_params["values"]["S11"]
    assert len(values) > 0
    for re, im in values:
        assert re == pytest.approx(gamma, abs=1e-6)
        assert im == pytest.approx(0.0, abs=1e-6)


def test_parse_gprmax_output_impedance_magnitude_closed_form(tmp_path: Path):
    # Itotal = Vtotal / ZIN pointwise in time (a real scalar) => the same
    # scaling holds in the frequency domain (FFT is linear), so
    # |Zin_computed(f)| = |ZIN * delaycorrection(f)| = ZIN exactly, since
    # |delaycorrection| == 1 at every frequency (a pure phase factor) --
    # see simulation/gprmax.py's module docstring for the delaycorrection
    # citation. This sidesteps needing to reproduce the phase term exactly
    # in this test while still being an exact closed-form check.
    n, dt = 512, 1e-11
    vinc = _gaussian_pulse(n, dt, t0=n * dt / 4, tau=n * dt / 20)
    vtotal = 0.6 * vinc
    zin_known = 75.0
    itotal = vtotal / zin_known

    out_path = tmp_path / "model.in.out"
    write_fake_out_file(out_path, vinc, vtotal, itotal, dt)

    result = parse_gprmax_output(out_path, port={"resistance_ohms": 50.0})
    impedance = result["impedance"]
    assert impedance["computed"] is True
    for re, im in zip(impedance["resistance_ohms"], impedance["reactance_ohms"], strict=True):
        magnitude = (re**2 + im**2) ** 0.5
        assert magnitude == pytest.approx(zin_known, rel=1e-6)


def test_parse_gprmax_output_writes_touchstone_file(tmp_path: Path):
    n, dt = 512, 1e-11
    vinc = _gaussian_pulse(n, dt, t0=n * dt / 4, tau=n * dt / 20)
    vtotal = 0.5 * vinc
    itotal = vtotal / 50.0

    out_path = tmp_path / "model.in.out"
    write_fake_out_file(out_path, vinc, vtotal, itotal, dt)

    result = parse_gprmax_output(out_path, port={"resistance_ohms": 50.0})
    touchstone_file = result["s_parameters"].get("touchstone_file")
    assert touchstone_file is not None
    assert Path(touchstone_file).exists()


def test_parse_gprmax_output_zero_incident_spectrum_returns_computed_false(tmp_path: Path):
    n, dt = 128, 1e-11
    zeros = np.zeros(n)
    out_path = tmp_path / "model.in.out"
    write_fake_out_file(out_path, zeros, zeros, zeros, dt)

    result = parse_gprmax_output(out_path, port={"resistance_ohms": 50.0})
    assert result["s_parameters"]["computed"] is False
    assert result["impedance"]["computed"] is False


def test_parse_gprmax_output_reads_receivers(tmp_path: Path):
    n, dt = 64, 1e-11
    vinc = _gaussian_pulse(n, dt, t0=n * dt / 4, tau=n * dt / 20)
    ez_values = np.linspace(0.0, 1.0, n)

    out_path = tmp_path / "model.in.out"
    write_fake_out_file(
        out_path,
        vinc,
        vinc,
        vinc / 50.0,
        dt,
        receivers={"probe1": {"Ez": ez_values}},
    )

    receivers = [{"name": "probe1", "position_m": [0.06, 0.05, 0.05]}]
    result = parse_gprmax_output(out_path, port={"resistance_ohms": 50.0}, receivers=receivers)
    assert "probe1" in result["receivers"]
    assert result["receivers"]["probe1"]["fields"]["Ez"] == pytest.approx(ez_values.tolist())


def test_parse_gprmax_output_receiver_group_missing_is_skipped(tmp_path: Path):
    n, dt = 64, 1e-11
    vinc = _gaussian_pulse(n, dt, t0=n * dt / 4, tau=n * dt / 20)
    out_path = tmp_path / "model.in.out"
    write_fake_out_file(out_path, vinc, vinc, vinc / 50.0, dt)  # no receivers written

    receivers = [{"name": "probe1", "position_m": [0.06, 0.05, 0.05]}]
    result = parse_gprmax_output(out_path, port={"resistance_ohms": 50.0}, receivers=receivers)
    assert result["receivers"] == {}


# ---------------------------------------------------------------------------
# GprmaxSimulator.run() subprocess plumbing, against fake "python -m gprMax"
# scripts.
# ---------------------------------------------------------------------------


def _make_fake_python(tmp_path: Path, body: str) -> Path:
    """Write a small fake "python -m gprMax" executable from a Python
    `body` (cross-platform -- see conftest.make_fake_executable)."""
    return make_fake_executable(tmp_path, body, name="fake_python")


def test_gprmax_simulator_invokes_dash_m_gprmax(tmp_path: Path):
    script = _make_fake_python(tmp_path, "import sys\nsys.stdout.write(' '.join(sys.argv[1:]))\n")
    input_file = tmp_path / "model.in"
    input_file.write_text("#title: test\n")

    simulator = GprmaxSimulator(python_executable=str(script))
    result = simulator.run({"input_file": str(input_file), "timeout_s": 10})

    tokens = result.outputs["stdout"].split()
    assert tokens == ["-m", "gprMax", str(input_file)]
    assert result.status == "COMPLETED"
    assert result.provenance == "SIMULATED"


def test_gprmax_simulator_nonzero_exit_raises_simulator_error(tmp_path: Path):
    script = _make_fake_python(
        tmp_path, 'import sys\nsys.stderr.write("boom: bad command\\n")\nsys.exit(1)\n'
    )
    input_file = tmp_path / "model.in"
    input_file.write_text("#title: test\n")

    simulator = GprmaxSimulator(python_executable=str(script))
    with pytest.raises(SimulatorError, match="boom"):
        simulator.run({"input_file": str(input_file), "timeout_s": 10})


def test_gprmax_simulator_timeout_raises_simulator_error(tmp_path: Path):
    script = _make_fake_python(tmp_path, "import time\ntime.sleep(5)\n")
    input_file = tmp_path / "model.in"
    input_file.write_text("#title: test\n")

    simulator = GprmaxSimulator(python_executable=str(script))
    with pytest.raises(SimulatorError, match="timed out"):
        simulator.run({"input_file": str(input_file), "timeout_s": 1})


def test_gprmax_simulator_missing_input_file_raises(tmp_path: Path):
    simulator = GprmaxSimulator(python_executable=sys.executable)
    with pytest.raises(SimulatorError, match="not found"):
        simulator.run({"input_file": str(tmp_path / "does_not_exist.in")})


def test_gprmax_simulator_picks_up_python_executable_from_env_var(tmp_path: Path, monkeypatch):
    script = _make_fake_python(tmp_path, "import sys\nsys.exit(0)\n")
    monkeypatch.setenv("GPRMAX_PYTHON", str(script))
    simulator = GprmaxSimulator()
    assert simulator.python_executable == str(script)


def test_gprmax_simulator_defaults_to_sys_executable(monkeypatch):
    monkeypatch.delenv("GPRMAX_PYTHON", raising=False)
    simulator = GprmaxSimulator()
    assert simulator.python_executable == sys.executable


# ---------------------------------------------------------------------------
# run_gprmax_simulation end to end, against a fake "python -m gprMax" script
# that writes a synthetic .out file matching gprMax's own documented naming
# convention and HDF5 structure.
# ---------------------------------------------------------------------------

_FAKE_GPRMAX_PY = """
import sys
from pathlib import Path
import h5py

VINC = {vinc!r}
VTOTAL = {vtotal!r}
ITOTAL = {itotal!r}
DT = {dt!r}

args = sys.argv[1:]
assert args[:2] == ["-m", "gprMax"], args
input_file = Path(args[2])
out_path = Path(str(input_file) + ".out")
with h5py.File(out_path, "w") as f:
    f.attrs["dt"] = DT
    f.attrs["Iterations"] = len(VINC)
    tl = f.create_group("tls/tl1")
    tl.create_dataset("Vinc", data=VINC)
    tl.create_dataset("Vtotal", data=VTOTAL)
    tl.create_dataset("Itotal", data=ITOTAL)
sys.exit(0)
"""


def _make_fake_gprmax_python(
    tmp_path: Path, vinc: np.ndarray, vtotal: np.ndarray, itotal: np.ndarray, dt: float
) -> Path:
    body = _FAKE_GPRMAX_PY.format(
        vinc=list(float(v) for v in vinc),
        vtotal=list(float(v) for v in vtotal),
        itotal=list(float(v) for v in itotal),
        dt=float(dt),
    )
    return make_fake_executable(tmp_path, body, name="fake_gprmax_python")


def test_run_gprmax_simulation_end_to_end_with_fake_executable(tmp_path: Path):
    n, dt = 512, 1e-11
    vinc = _gaussian_pulse(n, dt, t0=n * dt / 4, tau=n * dt / 20)
    gamma = -0.4
    vtotal = (1 + gamma) * vinc
    itotal = vtotal / 50.0
    script = _make_fake_gprmax_python(tmp_path, vinc, vtotal, itotal, dt)

    geometry = {
        **BASIC_GEOMETRY,
        "half_space": {"z_m": 0.04, "epsilon_r": 8.0, "conductivity_s_m": 0.015},
    }
    result = run_gprmax_simulation(
        geometry=geometry,
        fdtd={"time_window_s": 6e-9},
        timeout_s=10,
        executable=str(script),
        workdir=str(tmp_path / "run"),
    )

    assert result["provenance"] == "SIMULATED"
    assert result["simulator"] == "gprMax"
    assert result["status"] == "COMPLETED"
    assert result["s_parameters"]["computed"] is True
    for re, _im in result["s_parameters"]["values"]["S11"]:
        assert re == pytest.approx(gamma, abs=1e-6)
    assert result["far_field"]["computed"] is False
    assert Path(result["input_file"]).exists()
    assert Path(result["output_file"]).exists()
    assert result["output_file"].endswith("model.in.out")

    deck_text = Path(result["input_file"]).read_text()
    assert deck_text.startswith("#title:")
    assert "#transmission_line:" in deck_text


def test_run_gprmax_simulation_propagates_simulator_error_on_failure(tmp_path: Path):
    script = _make_fake_python(
        tmp_path, 'import sys\nsys.stderr.write("geometry error\\n")\nsys.exit(1)\n'
    )
    with pytest.raises(SimulatorError):
        run_gprmax_simulation(
            geometry=BASIC_GEOMETRY,
            fdtd={"time_window_s": 1e-8},
            timeout_s=10,
            executable=str(script),
            workdir=str(tmp_path / "run2"),
        )
