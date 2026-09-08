"""Tests for MEEP FDTD simulation (issue #60) -- an independent-method
cross-check against openEMS.

CRITICAL DIFFERENCE FROM tests/test_nec2pp.py / tests/test_openems.py:
those adapters shell a real binary out via subprocess, so their fake
executables are small shell/CLI scripts. MEEP is used as a Python LIBRARY
(`import meep as mp`), so this file instead follows tests/test_hfss.py's
constructor-injection pattern: a hand-written FakeMeepModule stands in for
`meep_module` on MeepSimulator/run_meep_simulation, matching the subset of
Meep's real Python API simulation/meep.py actually calls (Vector3, Medium,
Block, Cylinder, PML, GaussianSource, Source, FluxRegion, Simulation,
get_fluxes, get_flux_freqs, stop_when_fields_decayed, metal, inf -- each
verified against Meep's own primary documentation, see simulation/meep.py's
module docstring for the full citation list).

This file's tests fall into three groups:
  1. Unit/geometry translation helpers (_m_to_meep/_hz_to_meep_freq/
     _meep_freq_to_hz/_primitive_to_meep) -- pure functions, no Meep needed.
  2. End-to-end orchestration against FakeMeepModule -- geometry/port
     translation, the two-run reference/full flux-subtraction sequence
     (add_flux/run/get_flux_data/load_minus_flux_data/reset_meep, in the
     exact order simulation/meep.py's module docstring cites to Meep's own
     documented reflectance-tutorial technique), and the final numeric
     reflectance/|S11| result against a SCRIPTED, closed-form-known-answer
     flux spectrum -- the same "hand-computable answer, not real FDTD
     physics" approach tests/test_openems.py already uses for its own
     FFT/S-parameter tests.
  3. The real, unmockable proof that Meep is not installed in this
     environment, and that MeepSimulator()/run_meep_simulation() refuse to
     run (raising SimulatorError, not crashing some other way) when no
     `meep_module` is injected.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from simulation.base import SimulationResult, SimulatorError
from simulation.meep import (
    _SPEED_OF_LIGHT_M_S,
    MeepSimulator,
    _hz_to_meep_freq,
    _import_meep,
    _m_to_meep,
    _meep_freq_to_hz,
    _primitive_to_meep,
    run_meep_simulation,
)

# ---------------------------------------------------------------------------
# Group 1: unit/geometry translation helpers.
# ---------------------------------------------------------------------------


def test_m_to_meep_divides_by_characteristic_length():
    assert _m_to_meep(3e-3, 1e-3) == pytest.approx(3.0)
    assert _m_to_meep(0.5e-3, 1e-3) == pytest.approx(0.5)


def test_hz_to_meep_freq_matches_a_over_lambda():
    # frequency_meep = a / lambda = frequency_hz * a / c -- module docstring
    # citation (meep.readthedocs.io/en/latest/Introduction/).
    a_m = 1e-3
    frequency_hz = 2.45e9
    expected = frequency_hz * a_m / _SPEED_OF_LIGHT_M_S
    assert _hz_to_meep_freq(frequency_hz, a_m) == pytest.approx(expected)


def test_meep_freq_to_hz_is_the_exact_inverse_of_hz_to_meep_freq():
    a_m = 2.5e-3
    frequency_hz = 5.8e9
    f_meep = _hz_to_meep_freq(frequency_hz, a_m)
    assert _meep_freq_to_hz(f_meep, a_m) == pytest.approx(frequency_hz)


class _FakeMediumForUnitTests:
    def __init__(self, epsilon=1.0, mu=1.0):
        self.epsilon = epsilon
        self.mu = mu


class _MinimalFakeMeepForPrimitives:
    """Just enough of the real meep API for _primitive_to_meep's own unit
    tests, independent of the fuller FakeMeepModule used in Group 2."""

    inf = float("inf")

    def Vector3(self, x=0.0, y=0.0, z=0.0):
        return (x, y, z)

    def Block(self, material=None, center=None, size=None):
        return {"kind": "block", "material": material, "center": center, "size": size}

    def Cylinder(self, material=None, center=None, radius=1.0, height=None, axis=None):
        return {
            "kind": "cylinder",
            "material": material,
            "center": center,
            "radius": radius,
            "height": height,
            "axis": axis,
        }


def test_primitive_to_meep_box_converts_corners_to_center_and_size():
    mp_fake = _MinimalFakeMeepForPrimitives()
    material = _FakeMediumForUnitTests(epsilon=4.4)
    prim = {"shape": "box", "p1_m": [0.0, 0.0, 0.0], "p2_m": [2e-3, 4e-3, 0.0]}
    block = _primitive_to_meep(mp_fake, prim, a_m=1e-3, material=material)
    assert block["kind"] == "block"
    assert block["material"] is material
    assert block["center"] == pytest.approx((1.0, 2.0, 0.0))
    assert block["size"] == pytest.approx((2.0, 4.0, 0.0))


def test_primitive_to_meep_box_missing_corner_raises_value_error():
    mp_fake = _MinimalFakeMeepForPrimitives()
    with pytest.raises(ValueError, match="p2_m"):
        _primitive_to_meep(mp_fake, {"shape": "box", "p1_m": [0, 0, 0]}, a_m=1e-3, material=None)


def test_primitive_to_meep_cylinder_converts_radius_and_defaults_height_to_inf():
    mp_fake = _MinimalFakeMeepForPrimitives()
    prim = {"shape": "cylinder", "center_m": [1e-3, 1e-3, 0.0], "radius_m": 0.5e-3}
    cyl = _primitive_to_meep(mp_fake, prim, a_m=1e-3, material=None)
    assert cyl["kind"] == "cylinder"
    assert cyl["radius"] == pytest.approx(0.5)
    assert cyl["height"] == float("inf")
    assert cyl["axis"] == pytest.approx((0.0, 0.0, 1.0))  # default axis


def test_primitive_to_meep_unknown_shape_raises_value_error():
    mp_fake = _MinimalFakeMeepForPrimitives()
    with pytest.raises(ValueError, match="shape"):
        _primitive_to_meep(mp_fake, {"shape": "sphere"}, a_m=1e-3, material=None)


# ---------------------------------------------------------------------------
# Group 2: end-to-end orchestration against FakeMeepModule.
# ---------------------------------------------------------------------------


class FakeMedium:
    def __init__(self, epsilon=1.0, mu=1.0):
        self.epsilon = epsilon
        self.mu = mu


class FakeFlux:
    def __init__(self, freqs, values):
        self.freqs = list(freqs)
        self.values = list(values)


class FakeSimulation:
    def __init__(self, module: FakeMeepModule, **kwargs):
        self._module = module
        self.kwargs = kwargs
        self.flux_calls: list[dict[str, Any]] = []
        self.run_calls: list[dict[str, Any]] = []
        self.load_minus_calls: list[tuple[Any, Any]] = []
        self.get_flux_data_calls: list[Any] = []
        self.reset_called = False

    def add_flux(self, fcen, df, nfreq, region):
        self.flux_calls.append({"fcen": fcen, "df": df, "nfreq": nfreq, "region": region})
        return self._module._next_flux()

    def run(self, *step_funcs, **kwargs):
        self.run_calls.append(kwargs)

    def get_flux_data(self, flux):
        self.get_flux_data_calls.append(flux)
        return {"saved_from": flux}

    def load_minus_flux_data(self, flux, data):
        self.load_minus_calls.append((flux, data))

    def reset_meep(self):
        self.reset_called = True


class FakeMeepModule:
    """Stand-in for `import meep as mp` -- see simulation/meep.py's module
    docstring for each real-API fact's primary-source citation."""

    def __init__(self, flux_script: list[tuple[list[float], list[float]]]):
        # Consumed in add_flux() call order: this module's own
        # _run_reflectance_cross_check always calls add_flux exactly three
        # times, in this fixed order: (0) the reference run's reflection
        # monitor, (1) the reference run's baseline/transmission monitor,
        # (2) the full run's reflection monitor.
        self._flux_script = list(flux_script)
        self._flux_index = 0
        self.simulations: list[FakeSimulation] = []
        self.inf = float("inf")
        self.metal = FakeMedium(epsilon=-1e20)
        for name in ("Ex", "Ey", "Ez", "Hx", "Hy", "Hz"):
            setattr(self, name, name)

    def _next_flux(self) -> FakeFlux:
        freqs, values = self._flux_script[self._flux_index]
        self._flux_index += 1
        return FakeFlux(freqs, values)

    def Vector3(self, x=0.0, y=0.0, z=0.0):
        return (x, y, z)

    def Medium(self, epsilon=1.0, mu=1.0, **kwargs):
        return FakeMedium(epsilon=epsilon, mu=mu)

    def Block(self, material=None, center=None, size=None, **kwargs):
        return {"kind": "block", "material": material, "center": center, "size": size}

    def Cylinder(self, material=None, center=None, radius=1.0, height=None, axis=None, **kwargs):
        return {
            "kind": "cylinder",
            "material": material,
            "center": center,
            "radius": radius,
            "height": height,
            "axis": axis,
        }

    def PML(self, thickness, **kwargs):
        return {"kind": "pml", "thickness": thickness}

    def GaussianSource(self, frequency, fwidth=0.0, **kwargs):
        return {"kind": "gaussian_source", "frequency": frequency, "fwidth": fwidth}

    def Source(self, src, component=None, center=None, size=None, **kwargs):
        return {
            "kind": "source",
            "src": src,
            "component": component,
            "center": center,
            "size": size,
        }

    def FluxRegion(self, center=None, size=None, **kwargs):
        return {"kind": "flux_region", "center": center, "size": size}

    def Simulation(self, **kwargs):
        sim = FakeSimulation(self, **kwargs)
        self.simulations.append(sim)
        return sim

    def get_fluxes(self, flux: FakeFlux):
        return list(flux.values)

    def get_flux_freqs(self, flux: FakeFlux):
        return list(flux.freqs)

    def stop_when_fields_decayed(self, dt, component, pt, decay_by):
        return {
            "kind": "stop_when_fields_decayed",
            "dt": dt,
            "component": component,
            "pt": pt,
            "decay_by": decay_by,
        }


# Closed-form scenario: baseline (reference-run transmitted) flux = 2.0 at
# every one of 3 frequency points; the full run's post-subtraction
# reflected flux is scripted so that reflectance = -reflected/baseline
# comes out to exactly 0.25 / 0.16 / 0.09 -> s11_magnitude = 0.5 / 0.4 / 0.3
# (nice round numbers, hand-checkable, matching the closed-form-known-
# answer approach tests/test_openems.py already uses).
_FREQS_MEEP = [0.1, 0.12, 0.14]
_BASELINE_FLUX = [2.0, 2.0, 2.0]
_REFLECTED_FLUX = [-0.5, -0.32, -0.18]  # -reflectance * baseline
_EXPECTED_REFLECTANCE = [0.25, 0.16, 0.09]
_EXPECTED_S11_MAGNITUDE = [0.5, 0.4, 0.3]


def _flux_script():
    return [
        (_FREQS_MEEP, [0.0, 0.0, 0.0]),  # (0) reference reflection monitor -- unused numerically
        (_FREQS_MEEP, _BASELINE_FLUX),  # (1) reference baseline/transmission monitor
        (_FREQS_MEEP, _REFLECTED_FLUX),  # (2) full-run reflection monitor (post-subtraction)
    ]


PATCH_GEOMETRY = {
    "cell_size_m": [30e-3, 20e-3, 10e-3],
    "pml_thickness_m": 1e-3,
    "mesh_cell_size_m": 0.5e-3,
    "materials": [
        {
            "name": "substrate",
            "shape": "box",
            "p1_m": [0, 0, 0],
            "p2_m": [30e-3, 20e-3, 1.6e-3],
            "epsilon_r": 4.4,
        }
    ],
    "conductors": [
        {"name": "ground", "shape": "box", "p1_m": [0, 0, 0], "p2_m": [30e-3, 20e-3, 0]},
        {
            "name": "patch",
            "shape": "box",
            "p1_m": [5e-3, 5e-3, 1.6e-3],
            "p2_m": [25e-3, 15e-3, 1.6e-3],
        },
    ],
    "port": {
        "center_m": [-10e-3, 10e-3, 0.8e-3],
        "size_m": [0, 20e-3, 1.6e-3],
        "direction": "x",
        "frequency_hz": 2.45e9,
    },
    "reflection_monitor_center_m": [-8e-3, 10e-3, 0.8e-3],
    "reference_monitor_center_m": [12e-3, 10e-3, 0.8e-3],
}


def _run_against_fake(geometry=None, flux_script=None, **kwargs):
    fake = FakeMeepModule(flux_script if flux_script is not None else _flux_script())
    result = run_meep_simulation(
        geometry=geometry if geometry is not None else PATCH_GEOMETRY,
        meep_module=fake,
        **kwargs,
    )
    return result, fake


def test_run_meep_simulation_end_to_end_against_fake():
    result, fake = _run_against_fake()

    assert result["provenance"] == "SIMULATED"
    assert result["simulator"] == "MEEP"
    assert result["status"] == "COMPLETED"
    assert result["s_parameters"]["computed"] is True
    assert result["s_parameters"]["reflectance"] == pytest.approx(_EXPECTED_REFLECTANCE)
    assert result["s_parameters"]["s11_magnitude"] == pytest.approx(_EXPECTED_S11_MAGNITUDE)
    assert "touchstone_file" not in result
    assert result["far_field"]["computed"] is False
    assert result["gain_dbi"] is None


def test_frequency_hz_output_matches_hz_to_meep_freq_inverse():
    result, _ = _run_against_fake()
    a_m = 1e-3  # default characteristic length
    expected_hz = [_meep_freq_to_hz(f, a_m) for f in _FREQS_MEEP]
    assert result["s_parameters"]["frequency_hz"] == pytest.approx(expected_hz)


def test_two_simulations_are_built_reference_then_full():
    _, fake = _run_against_fake()
    assert len(fake.simulations) == 2
    ref_sim, full_sim = fake.simulations
    assert ref_sim.reset_called is True
    assert full_sim.reset_called is True


def test_conductors_are_excluded_from_reference_run_and_included_in_full_run():
    _, fake = _run_against_fake()
    ref_sim, full_sim = fake.simulations

    def _material_epsilons(sim):
        return {obj["material"].epsilon for obj in sim.kwargs["geometry"]}

    # reference run: only the substrate (epsilon_r=4.4) -- no PEC (-1e20)
    assert _material_epsilons(ref_sim) == {4.4}
    # full run: substrate plus the PEC conductors (mp.metal, epsilon=-1e20)
    assert _material_epsilons(full_sim) == {4.4, -1e20}
    assert len(full_sim.kwargs["geometry"]) == 3  # substrate + ground + patch
    assert len(ref_sim.kwargs["geometry"]) == 1  # substrate only


def test_source_frequency_is_converted_to_meep_units():
    _, fake = _run_against_fake()
    ref_sim = fake.simulations[0]
    source = ref_sim.kwargs["sources"][0]
    expected_fcen = _hz_to_meep_freq(2.45e9, 1e-3)
    assert source["src"]["frequency"] == pytest.approx(expected_fcen)
    # default fractional_bandwidth is 0.2
    assert source["src"]["fwidth"] == pytest.approx(expected_fcen * 0.2)
    assert source["component"] == "Ez"  # default component


def test_flux_monitors_added_in_documented_order_with_correct_geometry():
    _, fake = _run_against_fake()
    ref_sim, full_sim = fake.simulations
    assert len(ref_sim.flux_calls) == 2
    assert len(full_sim.flux_calls) == 1
    # reflection monitor center (converted to meep units, a=1mm default)
    assert ref_sim.flux_calls[0]["region"]["center"] == pytest.approx((-8.0, 10.0, 0.8))
    # reference/baseline monitor center
    assert ref_sim.flux_calls[1]["region"]["center"] == pytest.approx((12.0, 10.0, 0.8))
    # full run's reflection monitor is at the SAME location as the
    # reference run's reflection monitor
    assert full_sim.flux_calls[0]["region"]["center"] == pytest.approx((-8.0, 10.0, 0.8))


def test_load_minus_flux_data_subtracts_the_saved_reference_reflection_data():
    _, fake = _run_against_fake()
    ref_sim, full_sim = fake.simulations
    assert len(ref_sim.get_flux_data_calls) == 1
    assert len(full_sim.load_minus_calls) == 1
    flux_arg, data_arg = full_sim.load_minus_calls[0]
    assert data_arg == {"saved_from": ref_sim.get_flux_data_calls[0]}


def test_pml_thickness_and_resolution_are_converted():
    _, fake = _run_against_fake()
    ref_sim = fake.simulations[0]
    assert ref_sim.kwargs["boundary_layers"][0]["thickness"] == pytest.approx(1.0)  # 1mm / 1mm a
    # resolution = a_m / mesh_cell_size_m = 1e-3 / 0.5e-3 = 2
    assert ref_sim.kwargs["resolution"] == pytest.approx(2.0)


def test_custom_characteristic_length_changes_unit_conversion():
    result, fake = _run_against_fake(characteristic_length_m=2e-3)
    ref_sim = fake.simulations[0]
    # cell_size_m[0] = 30e-3 / 2e-3 = 15
    assert ref_sim.kwargs["cell_size"] == pytest.approx((15.0, 10.0, 5.0))
    expected_hz = [_meep_freq_to_hz(f, 2e-3) for f in _FREQS_MEEP]
    assert result["s_parameters"]["frequency_hz"] == pytest.approx(expected_hz)


def test_nfreq_is_forwarded_to_add_flux():
    _, fake = _run_against_fake(nfreq=7)
    for sim in fake.simulations:
        for call in sim.flux_calls:
            assert call["nfreq"] == 7


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_missing_geometry_raises_simulator_error():
    simulator = MeepSimulator(meep_module=FakeMeepModule(_flux_script()))
    with pytest.raises(SimulatorError, match="geometry"):
        simulator.run({})


def test_missing_top_level_geometry_key_raises_simulator_error():
    geometry = {k: v for k, v in PATCH_GEOMETRY.items() if k != "pml_thickness_m"}
    simulator = MeepSimulator(meep_module=FakeMeepModule(_flux_script()))
    with pytest.raises(SimulatorError, match="pml_thickness_m"):
        simulator.run({"geometry": geometry})


def test_missing_port_field_raises_value_error():
    geometry = {
        **PATCH_GEOMETRY,
        "port": {k: v for k, v in PATCH_GEOMETRY["port"].items() if k != "frequency_hz"},
    }
    simulator = MeepSimulator(meep_module=FakeMeepModule(_flux_script()))
    with pytest.raises(ValueError, match="frequency_hz"):
        simulator.run({"geometry": geometry})


def test_port_invalid_direction_raises_value_error():
    geometry = {**PATCH_GEOMETRY, "port": {**PATCH_GEOMETRY["port"], "direction": "diagonal"}}
    simulator = MeepSimulator(meep_module=FakeMeepModule(_flux_script()))
    with pytest.raises(ValueError, match="direction"):
        simulator.run({"geometry": geometry})


def test_port_nonzero_size_along_direction_raises_value_error():
    geometry = {
        **PATCH_GEOMETRY,
        "port": {**PATCH_GEOMETRY["port"], "size_m": [1e-3, 20e-3, 1.6e-3]},  # nonzero along x
    }
    simulator = MeepSimulator(meep_module=FakeMeepModule(_flux_script()))
    with pytest.raises(ValueError, match="size_m"):
        simulator.run({"geometry": geometry})


def test_port_invalid_component_raises_value_error():
    geometry = {**PATCH_GEOMETRY, "port": {**PATCH_GEOMETRY["port"], "component": "Zz"}}
    simulator = MeepSimulator(meep_module=FakeMeepModule(_flux_script()))
    with pytest.raises(ValueError, match="component"):
        simulator.run({"geometry": geometry})


def test_zero_baseline_flux_is_honestly_reported_as_not_computed():
    script = [
        (_FREQS_MEEP, [0.0, 0.0, 0.0]),
        (_FREQS_MEEP, [0.0, 0.0, 0.0]),  # baseline is all zero
        (_FREQS_MEEP, _REFLECTED_FLUX),
    ]
    result, _ = _run_against_fake(flux_script=script)
    assert result["s_parameters"]["computed"] is False
    assert "note" in result["s_parameters"]


def test_material_missing_corner_raises_value_error():
    geometry = {**PATCH_GEOMETRY, "materials": [{"shape": "box", "p1_m": [0, 0, 0]}]}
    simulator = MeepSimulator(meep_module=FakeMeepModule(_flux_script()))
    with pytest.raises(ValueError, match="p2_m"):
        simulator.run({"geometry": geometry})


# ---------------------------------------------------------------------------
# Simulator contract
# ---------------------------------------------------------------------------


def test_meep_simulator_returns_simulation_result_instance():
    simulator = MeepSimulator(meep_module=FakeMeepModule(_flux_script()))
    result = simulator.run({"geometry": PATCH_GEOMETRY})
    assert isinstance(result, SimulationResult)
    assert result.simulator == "MEEP"
    assert result.status == "COMPLETED"
    assert result.provenance == "SIMULATED"
    assert isinstance(result.workdir, Path)


# ---------------------------------------------------------------------------
# Group 3: the real, unmockable proof that Meep is not installed here.
# ---------------------------------------------------------------------------


def test_meep_is_genuinely_not_installed_in_this_environment():
    """Confirms the premise directly: this is not a mock pretending meep is
    absent, it actually is, in the interpreter running this test suite --
    matching tests/test_hfss.py's own
    test_pyaedt_is_genuinely_not_installed_in_this_environment."""
    with pytest.raises(ImportError):
        import meep  # noqa: F401


def test_meep_simulator_run_raises_simulator_error_with_no_injected_module():
    """A real MeepSimulator() constructed with no meep_module override must
    fail with a clear SimulatorError (naming how to install Meep), not some
    other exception, when meep genuinely isn't importable here."""
    simulator = MeepSimulator()
    with pytest.raises(SimulatorError, match="meep is not installed"):
        simulator.run({"geometry": PATCH_GEOMETRY})


def test_run_meep_simulation_raises_simulator_error_with_no_injected_module():
    with pytest.raises(SimulatorError, match="meep is not installed"):
        run_meep_simulation(geometry=PATCH_GEOMETRY)


def test_missing_meep_names_the_interpreter_mismatch_when_meep_python_is_set(monkeypatch):
    """The Dockerfile installs pymeep into its own conda env and exports
    MEEP_PYTHON. This adapter imports meep in-process, so that interpreter is
    unreachable -- and the old message claimed meep was not installed, which
    in a container is simply false and sends the reader looking for the wrong
    problem."""
    monkeypatch.setenv("MEEP_PYTHON", "/opt/conda/envs/mp/bin/python3")
    with pytest.raises(SimulatorError) as excinfo:
        _import_meep()
    message = str(excinfo.value)
    assert "not in THIS interpreter" in message
    assert "/opt/conda/envs/mp/bin/python3" in message
    assert "gprmax" in message.lower()


def test_missing_meep_keeps_the_install_message_when_meep_python_is_unset(monkeypatch):
    monkeypatch.delenv("MEEP_PYTHON", raising=False)
    with pytest.raises(SimulatorError) as excinfo:
        _import_meep()
    assert "meep is not installed" in str(excinfo.value)
