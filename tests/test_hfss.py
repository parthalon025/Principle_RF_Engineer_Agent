"""Tests for HFSS/PyAEDT simulation (issue #40) -- the last simulation-phase
ticket (Phases 6-8 complete after this).

CRITICAL DIFFERENCE FROM tests/test_nec2pp.py / tests/test_openems.py: those
modules' "the real binary just isn't installed here" caveat does NOT apply
to HFSS. HFSS is commercial, licensed software that genuinely cannot run in
this environment even in principle -- no license, no AEDT installation, and
(by design) this sandboxed container fails the workstation-confinement gate
on every one of its four required signals. See simulation/hfss.py's module
docstring for the full pyaedt API citation list (GitHub source, fetched
directly from ansys/pyaedt's `main` branch) and its own honest caveat.

This file's tests fall into three groups, per the ticket's own testing
guidance:
  1. The workstation-confinement gate against THIS real, unmodified
     environment -- a real, meaningful, non-mockable test of the actual
     security property this ticket cares about most.
  2. The confinement gate's individual branch logic, via explicit env-dict
     and pyaedt_importable overrides passed directly to
     check_hfss_workstation_confinement() -- these do NOT touch real
     os.environ or a real pyaedt install; they test the gate's own
     decision logic in isolation.
  3. Project-creation/geometry/solve/report-extraction/archival/Touchstone-
     export logic, against a hand-written fake object matching the subset
     of pyaedt's Hfss API simulation/hfss.py actually calls, via
     HfssSimulator's/run_hfss_simulation's `hfss_factory`/
     `confinement_check` constructor-injection seams (documented on
     HfssSimulator.__init__) -- this is the "Simulator.run() seam with
     PyAEDT/HFSS invocation substituted by a fake for CI" the ticket calls
     for. NONE of this group is run against a real HFSS/AEDT installation.
"""

import json
from pathlib import Path

import pytest

from simulation.base import SimulationResult, SimulatorError
from simulation.hfss import (
    HfssSimulator,
    check_hfss_workstation_confinement,
    run_hfss_simulation,
)

# ---------------------------------------------------------------------------
# Group 1: the real, unmockable proof that this sandbox is rejected.
# ---------------------------------------------------------------------------


def test_check_hfss_workstation_confinement_rejects_this_sandbox():
    """The actual security property this ticket cares about most: called
    with NO overrides at all (real os.environ, a real pyaedt import
    attempt), the gate must refuse to treat this container as the
    designated licensed HFSS workstation."""
    with pytest.raises(SimulatorError) as excinfo:
        check_hfss_workstation_confinement()
    message = str(excinfo.value)
    # All four signals are expected to fail in this real sandbox.
    assert "HFSS_ENABLED" in message
    assert "HFSS_WORKSTATION_ID" in message
    assert "pyaedt is not importable" in message
    assert "ANSYSEM_ROOT" in message


def test_hfss_simulator_run_rejects_this_sandbox_with_no_overrides():
    """Same property, exercised through the public Simulator.run() seam
    with zero test seams engaged -- a real HfssSimulator() constructed with
    no hfss_factory/confinement_check override must refuse to run here."""
    simulator = HfssSimulator()
    with pytest.raises(SimulatorError, match="HFSS execution refused"):
        simulator.run({"geometry": {}, "frequency_hz": 2.45e9})


def test_run_hfss_simulation_rejects_this_sandbox_with_no_overrides():
    with pytest.raises(SimulatorError, match="HFSS execution refused"):
        run_hfss_simulation(geometry={}, frequency_hz=2.45e9)


def test_pyaedt_is_genuinely_not_installed_in_this_environment():
    """Confirms the premise directly: this is not a mock pretending pyaedt
    is absent, it actually is, in the interpreter running this test suite."""
    with pytest.raises(ImportError):
        import ansys.aedt.core  # noqa: F401


# ---------------------------------------------------------------------------
# Group 2: the confinement gate's own branch logic, via explicit overrides.
# ---------------------------------------------------------------------------

_FULLY_SATISFIED_ENV = {
    "HFSS_ENABLED": "true",
    "HFSS_WORKSTATION_ID": "bench-3",
    "HFSS_ALLOWED_WORKSTATION_ID": "bench-3",
    "ANSYSEM_ROOT251": r"C:\Program Files\AnsysEM\v251\ANSYS",
}


def test_confinement_passes_when_all_four_signals_present():
    # Does not raise.
    check_hfss_workstation_confinement(env=_FULLY_SATISFIED_ENV, pyaedt_importable=True)


def test_confinement_fails_when_hfss_enabled_is_false():
    env = {**_FULLY_SATISFIED_ENV, "HFSS_ENABLED": "false"}
    with pytest.raises(SimulatorError, match="HFSS_ENABLED"):
        check_hfss_workstation_confinement(env=env, pyaedt_importable=True)


def test_confinement_fails_when_hfss_enabled_missing():
    env = {k: v for k, v in _FULLY_SATISFIED_ENV.items() if k != "HFSS_ENABLED"}
    with pytest.raises(SimulatorError, match="HFSS_ENABLED"):
        check_hfss_workstation_confinement(env=env, pyaedt_importable=True)


def test_confinement_fails_when_workstation_id_missing():
    env = {k: v for k, v in _FULLY_SATISFIED_ENV.items() if k != "HFSS_WORKSTATION_ID"}
    with pytest.raises(SimulatorError, match="HFSS_WORKSTATION_ID is not set"):
        check_hfss_workstation_confinement(env=env, pyaedt_importable=True)


def test_confinement_fails_when_allowed_workstation_id_not_configured():
    env = {k: v for k, v in _FULLY_SATISFIED_ENV.items() if k != "HFSS_ALLOWED_WORKSTATION_ID"}
    with pytest.raises(SimulatorError, match="HFSS_ALLOWED_WORKSTATION_ID is not configured"):
        check_hfss_workstation_confinement(env=env, pyaedt_importable=True)


def test_confinement_fails_when_workstation_id_does_not_match_allowed():
    env = {**_FULLY_SATISFIED_ENV, "HFSS_WORKSTATION_ID": "some-other-host"}
    with pytest.raises(SimulatorError, match="does not match"):
        check_hfss_workstation_confinement(env=env, pyaedt_importable=True)


def test_confinement_fails_when_pyaedt_not_importable():
    with pytest.raises(SimulatorError, match="pyaedt is not importable"):
        check_hfss_workstation_confinement(env=_FULLY_SATISFIED_ENV, pyaedt_importable=False)


def test_confinement_fails_when_no_ansysem_root_marker():
    env = {k: v for k, v in _FULLY_SATISFIED_ENV.items() if not k.startswith("ANSYSEM_ROOT")}
    with pytest.raises(SimulatorError, match="ANSYSEM_ROOT"):
        check_hfss_workstation_confinement(env=env, pyaedt_importable=True)


def test_confinement_error_lists_every_missing_signal_at_once():
    # Structurally impossible to fix by flipping one boolean: with every
    # signal missing, the error names all four, not just the first found.
    with pytest.raises(SimulatorError) as excinfo:
        check_hfss_workstation_confinement(env={}, pyaedt_importable=False)
    message = str(excinfo.value)
    assert "HFSS_ENABLED" in message
    assert "HFSS_WORKSTATION_ID" in message
    assert "pyaedt is not importable" in message
    assert "ANSYSEM_ROOT" in message


# ---------------------------------------------------------------------------
# Group 3: build/solve/report/archive/Touchstone-export logic against a
# hand-written fake matching the pyaedt Hfss API subset simulation/hfss.py
# calls. The confinement gate is bypassed here ONLY via the explicit,
# visible confinement_check=lambda: None constructor-injection seam
# documented on HfssSimulator.__init__ -- never by monkeypatching internals
# -- so this never contradicts Group 1/2's "the real gate rejects this
# sandbox" finding.
# ---------------------------------------------------------------------------


class FakeMesh:
    def __init__(self):
        self.assigned = []

    def assign_length_mesh(self, **kwargs):
        self.assigned.append(kwargs)
        return object()


class FakeModeler:
    def __init__(self):
        self.created = []

    def create_box(self, origin, sizes, name=None, **kwargs):
        self.created.append({"name": name, "origin": list(origin), "sizes": list(sizes)})
        return name


class FakeSolutionData:
    def __init__(self, freqs_ghz, magnitude, phase_rad):
        self.primary_sweep_values = list(freqs_ghz)
        self.full_matrix_mag_phase = (
            {"S(1,1)": list(magnitude)},
            {"S(1,1)": list(phase_rad)},
        )


class FakePost:
    def __init__(self, solution_data):
        self._solution_data = solution_data
        self.calls = []

    def get_solution_data(self, **kwargs):
        self.calls.append(kwargs)
        return self._solution_data


class FakeHfss:
    """Hand-written fake matching the subset of pyaedt.Hfss's real API
    simulation/hfss.py calls (create_box/assign_material/lumped_port/
    mesh.assign_length_mesh/create_setup/create_linear_count_sweep/analyze/
    post.get_solution_data/export_touchstone/save_project/release_desktop
    -- each verified against primary source, see simulation/hfss.py's
    module docstring)."""

    def __init__(self, project, design, solution_type=None, version=None, **kwargs):
        self.project = project
        self.design = design
        self.modeler = FakeModeler()
        self.mesh = FakeMesh()
        self.post = FakePost(
            FakeSolutionData(
                freqs_ghz=[2.2, 2.45, 2.7],
                magnitude=[0.15, 0.03, 0.22],
                phase_rad=[0.1, 1.4, -0.5],
            )
        )
        self.material_assignments: dict[str, str] = {}
        self.ports: list[dict] = []
        self.setups: list[dict] = []
        self.sweeps: list[dict] = []
        self.analyze_calls: list[dict] = []
        self.export_calls: list[dict] = []
        self.saved = False
        self.released = False
        self.release_kwargs = None

    def assign_material(self, assignment, material):
        self.material_assignments[assignment] = material
        return True

    def lumped_port(self, **kwargs):
        self.ports.append(kwargs)
        return object()

    def create_setup(self, **kwargs):
        self.setups.append(kwargs)
        return object()

    def create_linear_count_sweep(self, **kwargs):
        self.sweeps.append(kwargs)
        return object()

    def analyze(self, **kwargs):
        self.analyze_calls.append(kwargs)

    def export_touchstone(self, **kwargs):
        self.export_calls.append(kwargs)
        Path(kwargs["output_file"]).write_text("! fake touchstone export\n")
        return kwargs["output_file"]

    def save_project(self):
        self.saved = True
        Path(self.project).write_text("fake .aedt project contents\n")
        return True

    def release_desktop(self, **kwargs):
        self.released = True
        self.release_kwargs = kwargs
        return True


PATCH_GEOMETRY = {
    "materials": [
        {
            "name": "substrate",
            "p1_m": [0.0, 0.0, 0.0],
            "p2_m": [0.03, 0.02, 0.0016],
            "material": "FR4_epoxy",
        }
    ],
    "conductors": [
        {"name": "ground", "p1_m": [0.0, 0.0, 0.0], "p2_m": [0.03, 0.02, 0.0]},
        {"name": "patch", "p1_m": [0.005, 0.005, 0.0016], "p2_m": [0.025, 0.015, 0.0016]},
    ],
    "port": {
        "name": "feed",
        "sheet": {"p1_m": [0.015, 0.005, 0.0], "p2_m": [0.015, 0.005, 0.0016]},
        "impedance_ohms": 50.0,
    },
    "mesh": {"max_length_mm": 0.5},
}


def _run_against_fake(tmp_path: Path, geometry=None, **kwargs):
    created_fakes: list[FakeHfss] = []

    def factory(**fkwargs):
        fake = FakeHfss(**fkwargs)
        created_fakes.append(fake)
        return fake

    result = run_hfss_simulation(
        geometry=geometry if geometry is not None else PATCH_GEOMETRY,
        frequency_hz=2.45e9,
        archive_dir=str(tmp_path),
        hfss_factory=factory,
        confinement_check=lambda: None,
        **kwargs,
    )
    return result, created_fakes[0]


def test_run_hfss_simulation_end_to_end_against_fake(tmp_path: Path):
    result, fake = _run_against_fake(tmp_path)

    assert result["provenance"] == "SIMULATED"
    assert result["simulator"] == "HFSS"
    assert result["status"] == "COMPLETED"
    assert result["s_parameters"]["computed"] is True
    assert result["s_parameters"]["frequency_ghz"] == [2.2, 2.45, 2.7]
    assert result["s_parameters"]["magnitude_linear"] == [0.15, 0.03, 0.22]
    assert set(result["conductor_names"]) == {"ground", "patch"}
    assert result["port_name"] == "feed"


def test_geometry_creates_boxes_and_assigns_materials(tmp_path: Path):
    _, fake = _run_against_fake(tmp_path)
    created_names = {c["name"] for c in fake.modeler.created}
    assert "substrate" in created_names
    assert "ground" in created_names
    assert "patch" in created_names
    assert "feed_sheet" in created_names
    assert fake.material_assignments["substrate"] == "FR4_epoxy"
    assert fake.material_assignments["ground"] == "copper"
    assert fake.material_assignments["patch"] == "copper"


def test_geometry_converts_meters_to_millimeters(tmp_path: Path):
    _, fake = _run_against_fake(tmp_path)
    ground = next(c for c in fake.modeler.created if c["name"] == "ground")
    assert ground["origin"] == pytest.approx([0.0, 0.0, 0.0])
    assert ground["sizes"] == pytest.approx([30.0, 20.0, 0.0])


def test_port_reference_defaults_to_last_conductor(tmp_path: Path):
    _, fake = _run_against_fake(tmp_path)
    assert len(fake.ports) == 1
    port_call = fake.ports[0]
    assert port_call["assignment"] == "feed_sheet"
    assert port_call["reference"] == "patch"  # last conductor created
    assert port_call["impedance"] == 50.0
    assert port_call["name"] == "feed"


def test_port_reference_explicit_override_is_honored(tmp_path: Path):
    geometry = {
        **PATCH_GEOMETRY,
        "port": {**PATCH_GEOMETRY["port"], "reference": "ground"},
    }
    _, fake = _run_against_fake(tmp_path, geometry=geometry)
    assert fake.ports[0]["reference"] == "ground"


def test_mesh_defaults_to_conductor_names(tmp_path: Path):
    _, fake = _run_against_fake(tmp_path)
    assert len(fake.mesh.assigned) == 1
    assignment = fake.mesh.assigned[0]["assignment"]
    assert set(assignment) == {"ground", "patch"}
    assert fake.mesh.assigned[0]["maximum_length"] == 0.5


def test_missing_port_raises_value_error(tmp_path: Path):
    geometry = {k: v for k, v in PATCH_GEOMETRY.items() if k != "port"}
    with pytest.raises(ValueError, match="port"):
        _run_against_fake(tmp_path, geometry=geometry)


def test_missing_material_field_raises_value_error(tmp_path: Path):
    geometry = {**PATCH_GEOMETRY, "materials": [{"name": "bad", "p1_m": [0, 0, 0]}]}
    with pytest.raises(ValueError, match="p2_m"):
        _run_against_fake(tmp_path, geometry=geometry)


def test_setup_and_sweep_and_analyze_are_called(tmp_path: Path):
    _, fake = _run_against_fake(tmp_path)
    assert len(fake.setups) == 1
    assert fake.setups[0]["name"] == "Setup1"
    assert "2.45" in fake.setups[0]["Frequency"]
    assert len(fake.sweeps) == 1
    assert fake.sweeps[0]["setup"] == "Setup1"
    assert fake.sweeps[0]["unit"] == "GHz"
    assert len(fake.analyze_calls) == 1


def test_custom_sweep_range_is_honored(tmp_path: Path):
    result, fake = _run_against_fake(
        tmp_path, sweep={"start_hz": 2.0e9, "stop_hz": 3.0e9, "points": 21}
    )
    sweep_call = fake.sweeps[0]
    assert sweep_call["start_frequency"] == pytest.approx(2.0)
    assert sweep_call["stop_frequency"] == pytest.approx(3.0)
    assert sweep_call["num_of_freq_points"] == 21


# ---------------------------------------------------------------------------
# Touchstone export shape
# ---------------------------------------------------------------------------


def test_touchstone_export_is_invoked_and_file_is_written(tmp_path: Path):
    result, fake = _run_against_fake(tmp_path)
    assert len(fake.export_calls) == 1
    touchstone_path = Path(result["touchstone_file"])
    assert touchstone_path.exists()
    assert touchstone_path.suffix == ".s1p"
    assert touchstone_path.read_text().startswith("!")


# ---------------------------------------------------------------------------
# Archival: solved project + extracted report, for later reproducibility.
# ---------------------------------------------------------------------------


def test_project_is_saved_before_archival(tmp_path: Path):
    _, fake = _run_against_fake(tmp_path)
    assert fake.saved is True


def test_archive_directory_contains_project_file_and_report_json(tmp_path: Path):
    result, fake = _run_against_fake(tmp_path)
    archive_dir = Path(result["archive_dir"])
    assert archive_dir.is_dir()
    assert archive_dir.parent == tmp_path

    project_files = list(archive_dir.glob("*.aedt"))
    assert len(project_files) == 1
    assert project_files[0].read_text() == "fake .aedt project contents\n"

    report_path = archive_dir / "report.json"
    assert report_path.exists()
    report = json.loads(report_path.read_text())
    assert report["provenance"] == "SIMULATED"
    assert report["simulator"] == "HFSS"
    assert report["s_parameters"]["computed"] is True
    assert "touchstone_file" in report


def test_archive_directory_name_is_prefixed_by_project_name(tmp_path: Path):
    result, _ = _run_against_fake(tmp_path, project_name="patch_test_run")
    archive_dir = Path(result["archive_dir"])
    assert archive_dir.name.startswith("patch_test_run_")


def test_desktop_is_released_after_a_successful_run(tmp_path: Path):
    _, fake = _run_against_fake(tmp_path)
    assert fake.released is True


def test_desktop_is_released_even_if_solve_raises(tmp_path: Path):
    """release_desktop() must still be called on failure -- the run()
    method wraps geometry/solve/extract/archive in try/finally."""

    class RaisingHfss(FakeHfss):
        def analyze(self, **kwargs):
            raise RuntimeError("solver diverged")

    fakes: list[RaisingHfss] = []

    def factory(**kwargs):
        fake = RaisingHfss(**kwargs)
        fakes.append(fake)
        return fake

    with pytest.raises(RuntimeError, match="solver diverged"):
        run_hfss_simulation(
            geometry=PATCH_GEOMETRY,
            frequency_hz=2.45e9,
            archive_dir=str(tmp_path),
            hfss_factory=factory,
            confinement_check=lambda: None,
        )
    assert fakes[0].released is True


# ---------------------------------------------------------------------------
# Simulator contract / job validation
# ---------------------------------------------------------------------------


def test_hfss_simulator_returns_simulation_result_instance(tmp_path: Path):
    def factory(**kwargs):
        return FakeHfss(**kwargs)

    simulator = HfssSimulator(
        hfss_factory=factory, confinement_check=lambda: None, archive_dir=str(tmp_path)
    )
    result = simulator.run({"geometry": PATCH_GEOMETRY, "frequency_hz": 2.45e9})
    assert isinstance(result, SimulationResult)
    assert result.simulator == "HFSS"
    assert result.status == "COMPLETED"
    assert result.provenance == "SIMULATED"


def test_missing_geometry_raises_simulator_error(tmp_path: Path):
    simulator = HfssSimulator(confinement_check=lambda: None, archive_dir=str(tmp_path))
    with pytest.raises(SimulatorError, match="geometry"):
        simulator.run({"frequency_hz": 2.45e9})


def test_missing_frequency_raises_simulator_error(tmp_path: Path):
    simulator = HfssSimulator(confinement_check=lambda: None, archive_dir=str(tmp_path))
    with pytest.raises(SimulatorError, match="frequency_hz"):
        simulator.run({"geometry": PATCH_GEOMETRY})
