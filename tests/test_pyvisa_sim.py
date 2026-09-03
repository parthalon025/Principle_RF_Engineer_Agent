"""End-to-end tests for measurement/vna.py, measurement/spectrum_analyzer.py,
measurement/signal_generator.py, and measurement/power_meter.py against a
real pyvisa-sim simulated instrument backend (issue #56) -- NOT a mock of
pyvisa itself, and NOT the confinement_check=lambda *a, **kw: None bypass
seam tests/test_vna.py's Group 4 uses. This file exercises the REAL,
UNMODIFIED code path: a real `pyvisa.ResourceManager()` call (see each
adapter's `_real_transport_factory`), talking real SCPI text over pyvisa-sim's
simulated transport, through the REAL measurement.base.
check_physical_actuation_gate (not overridden) against this repo-specific
fixture at tests/fixtures/pyvisa_sim_instruments.yaml, whose dialogues and
properties match each adapter's own DEFAULT_SCPI_COMMANDS -- so a passing
test here is genuine evidence the real SCPI parsing/formatting logic works,
not evidence that pyvisa-sim's own generic bundled example instrument works.

Why this can run at all without real lab hardware: pyvisa-sim (selected via
the `@sim` ResourceManager specification, or the `PYVISA_LIBRARY` env var
pyvisa's own `pyvisa.highlevel.open_visa_library` falls back to when no
explicit specification is given -- verified directly against pyvisa's GitHub
`main` branch, see tests/fixtures/pyvisa_sim_instruments.yaml's own header
comment for the full citation) requires no real VISA backend and no
physical instrument at all, unlike bare pyvisa. `pyvisa`, `pyvisa-sim`, and
`pyvisa-py` are all pip-installable, license-free packages now in this
project's `measurement` optional extra (pyproject.toml) -- install with
`uv sync --extra measurement` to run this file for real; under a bare
`uv sync` (no extra) these tests SKIP via `pytest.importorskip` below,
leaving tests/test_vna.py's/test_spectrum_analyzer.py's/etc. own "pyvisa is
genuinely not installed in this sandbox" proofs undisturbed (this file adds
new, additive coverage; it does not change what those tests assert about
the DEFAULT/bare-sync environment).

CRITICAL, NON-NEGOTIABLE PROJECT CONSTRAINT, unaffected by this ticket: this
file explicitly does NOT construct any adapter with a bypassed
confinement_check, and every `run_*` call below goes through the real,
unmodified measurement.base.check_physical_actuation_gate -- including its
`ALLOW_INSTRUMENT_CONTROL` env-var check and its real ApprovalReceipt
verification. `sim_env` (below) opts a test INTO
`ALLOW_INSTRUMENT_CONTROL=true` for its own duration only (via monkeypatch,
never touching the real environment permanently), and every approval used
here is a genuine one minted by measurement.base.
request_physical_measurement_approval() with an explicit, test-only
`approval_callback` -- never a bare boolean/string standing in for one (see
measurement/base.py's module docstring on why that path is the ONLY way to
obtain one). See test_approval_gate_still_requires_a_callback_against_the_
sim_backend and test_run_vna_measurement_still_rejected_without_allow_
instrument_control below for the direct proof that this ticket did not
weaken that gate in any way, even against a genuine @sim resource with
pyvisa genuinely importable.
"""

from pathlib import Path

import pytest

pytest.importorskip("pyvisa")
pytest.importorskip("pyvisa_sim")

from measurement.base import InstrumentError  # noqa: E402
from measurement.power_meter import (  # noqa: E402
    request_power_meter_measurement_approval,
    run_power_meter_measurement,
)
from measurement.signal_generator import (  # noqa: E402
    request_signal_generator_output_approval,
    run_signal_generator_output,
)
from measurement.spectrum_analyzer import (  # noqa: E402
    request_spectrum_analyzer_measurement_approval,
    run_spectrum_analyzer_measurement,
)
from measurement.vna import (  # noqa: E402
    request_vna_measurement_approval,
    run_vna_measurement,
)

FIXTURE_PATH = (Path(__file__).parent / "fixtures" / "pyvisa_sim_instruments.yaml").resolve()


@pytest.fixture
def sim_env(monkeypatch):
    """Point a bare `pyvisa.ResourceManager()` (exactly what every
    adapter's `_real_transport_factory` calls, unmodified) at this repo's
    fixture over the @sim backend, and satisfy the OTHER independent
    ALLOW_INSTRUMENT_CONTROL gate signal -- both via monkeypatch, so
    neither touches the real environment beyond this test's duration, and
    neither is a substitute for a genuine ApprovalReceipt (still required
    separately -- see this module's docstring)."""
    monkeypatch.setenv("PYVISA_LIBRARY", f"{FIXTURE_PATH}@sim")
    monkeypatch.setenv("ALLOW_INSTRUMENT_CONTROL", "true")


# ---------------------------------------------------------------------------
# VNA
# ---------------------------------------------------------------------------


def test_run_vna_measurement_against_sim_backend(sim_env):
    approval = request_vna_measurement_approval(
        resource="ASRL1::INSTR",
        start_hz=2.4e9,
        stop_hz=2.5e9,
        points=3,
        sparams=["S11", "S12", "S21", "S22"],
        approved_by="engineer.jane",
        approval_callback=lambda fields: True,
    )
    assert isinstance(approval, dict)

    result = run_vna_measurement(
        resource="ASRL1::INSTR",
        start_hz=2.4e9,
        stop_hz=2.5e9,
        approval=approval,
        points=3,
        sparams=["S11", "S12", "S21", "S22"],
    )

    assert result["provenance"] == "MEASURED"
    assert result["status"] == "COMPLETED"
    assert result["instrument"] == "SIMFIXTURE,VNA-SIM-1,SN-VNA-0001,FW1.0"
    assert result["resource"] == "ASRL1::INSTR"

    freqs = result["frequency_hz"]
    assert len(freqs) == 3
    assert freqs[0] == pytest.approx(2.4e9)
    assert freqs[-1] == pytest.approx(2.5e9)

    assert result["ports"] == 2
    assert set(result["s_parameters"].keys()) == {"S11", "S12", "S21", "S22"}
    s11 = result["s_parameters"]["S11"]
    assert len(s11) == 3
    assert complex(s11[0]) == pytest.approx(0.1 + 0.01j)
    assert complex(s11[1]) == pytest.approx(0.2 + 0.02j)
    assert complex(s11[2]) == pytest.approx(0.3 + 0.03j)

    assert result["calibration"]["instrument_reported_correction_state"] == "1"
    assert result["touchstone_file"] is None


def test_run_vna_measurement_writes_an_analyzable_touchstone_file_against_sim_backend(
    sim_env, tmp_path: Path
):
    """The MEASURED result from a real @sim run is structurally compatible
    with this project's existing Touchstone tooling (rf_tools/touchstone.py)
    -- not merely Touchstone-shaped in isolation -- mirroring
    tests/test_vna.py's own fake-transport version of this same proof."""
    from rf_tools.touchstone import analyze_touchstone

    approval = request_vna_measurement_approval(
        resource="ASRL1::INSTR",
        start_hz=2.4e9,
        stop_hz=2.5e9,
        points=3,
        sparams=["S11"],
        approved_by="engineer.jane",
        approval_callback=lambda fields: True,
    )
    result = run_vna_measurement(
        resource="ASRL1::INSTR",
        start_hz=2.4e9,
        stop_hz=2.5e9,
        approval=approval,
        points=3,
        sparams=["S11"],
        touchstone_path=str(tmp_path / "sim_meas.s1p"),
    )

    analyzed = analyze_touchstone(result["touchstone_file"])
    assert analyzed["ports"] == 1
    assert analyzed["points"] == 3


# ---------------------------------------------------------------------------
# Spectrum analyzer
# ---------------------------------------------------------------------------


def test_run_spectrum_analyzer_measurement_against_sim_backend(sim_env):
    approval = request_spectrum_analyzer_measurement_approval(
        resource="ASRL2::INSTR",
        center_hz=1.0e9,
        span_hz=2.0e8,
        res_bw_hz=1.0e5,
        points=4,
        approved_by="engineer.jane",
        approval_callback=lambda fields: True,
    )
    assert isinstance(approval, dict)

    result = run_spectrum_analyzer_measurement(
        resource="ASRL2::INSTR",
        center_hz=1.0e9,
        span_hz=2.0e8,
        approval=approval,
        res_bw_hz=1.0e5,
        points=4,
    )

    assert result["provenance"] == "MEASURED"
    assert result["status"] == "COMPLETED"
    assert result["instrument"] == "SIMFIXTURE,SA-SIM-1,SN-SA-0001,FW1.0"
    assert result["resource"] == "ASRL2::INSTR"
    assert result["center_hz"] == pytest.approx(1.0e9)
    assert result["span_hz"] == pytest.approx(2.0e8)
    assert result["resolution_bandwidth_hz"] == pytest.approx(1.0e5)

    freqs = result["frequency_hz"]
    assert len(freqs) == 4
    assert freqs[0] == pytest.approx(9.0e8)
    assert freqs[-1] == pytest.approx(1.1e9)

    assert result["amplitude_dbm"] == pytest.approx([-50.0, -42.5, -15.25, -60.0])
    assert result["peak_amplitude_dbm"] == pytest.approx(-15.25)
    assert result["peak_frequency_hz"] == pytest.approx(freqs[2])


# ---------------------------------------------------------------------------
# Signal generator
# ---------------------------------------------------------------------------


def test_run_signal_generator_output_against_sim_backend(sim_env):
    approval = request_signal_generator_output_approval(
        resource="ASRL3::INSTR",
        frequency_hz=2.45e9,
        power_dbm=5.0,
        output_on=True,
        approved_by="engineer.jane",
        approval_callback=lambda fields: True,
    )
    assert isinstance(approval, dict)

    result = run_signal_generator_output(
        resource="ASRL3::INSTR",
        frequency_hz=2.45e9,
        power_dbm=5.0,
        approval=approval,
        output_on=True,
    )

    assert result["provenance"] == "MEASURED"
    assert result["status"] == "COMPLETED"
    assert result["instrument"] == "SIMFIXTURE,SIGGEN-SIM-1,SN-SG-0001,FW1.0"
    assert result["resource"] == "ASRL3::INSTR"
    assert result["frequency_hz"] == pytest.approx(2.45e9)
    assert result["power_dbm"] == pytest.approx(5.0)
    assert result["output_on"] is True

    # Genuine instrument-side state round-trip: the simulated device's
    # `frequency`/`power` properties (see the fixture) are actually set by
    # the freq_set/power_set writes above, then read back here via
    # freq_query/power_query -- not merely echoed back from the job dict on
    # the Python side.
    assert result["frequency_hz_readback"] == pytest.approx(2.45e9)
    assert result["power_dbm_readback"] == pytest.approx(5.0)
    assert result["output_state_readback"] == "1"


# ---------------------------------------------------------------------------
# Power meter
# ---------------------------------------------------------------------------


def test_run_power_meter_measurement_against_sim_backend(sim_env):
    approval = request_power_meter_measurement_approval(
        resource="ASRL4::INSTR",
        frequency_hz=1.5e9,
        approved_by="engineer.jane",
        approval_callback=lambda fields: True,
    )
    assert isinstance(approval, dict)

    result = run_power_meter_measurement(
        resource="ASRL4::INSTR",
        frequency_hz=1.5e9,
        approval=approval,
    )

    assert result["provenance"] == "MEASURED"
    assert result["status"] == "COMPLETED"
    assert result["instrument"] == "SIMFIXTURE,PWRMTR-SIM-1,SN-PM-0001,FW1.0"
    assert result["resource"] == "ASRL4::INSTR"
    assert result["frequency_hz"] == pytest.approx(1.5e9)
    assert result["power_dbm"] == pytest.approx(-12.34)
    assert result["units"] == "dBm"
    assert result["calibration"]["instrument_reported_correction_factor"] == pytest.approx(0.98)


# ---------------------------------------------------------------------------
# The approval gate itself is untouched by this ticket -- even against a
# genuine @sim resource with pyvisa genuinely importable (acceptance
# criterion). See this module's docstring.
# ---------------------------------------------------------------------------


def test_approval_gate_still_requires_a_callback_against_the_sim_backend(sim_env):
    with pytest.raises(InstrumentError, match="No human-approval mechanism"):
        request_vna_measurement_approval(
            resource="ASRL1::INSTR",
            start_hz=2.4e9,
            stop_hz=2.5e9,
            points=3,
            sparams=["S11"],
            approved_by="a.human",
        )


def test_run_vna_measurement_still_rejected_without_allow_instrument_control(monkeypatch):
    """Same gate, the OTHER independent signal: a real @sim resource and
    pyvisa genuinely importable are not, by themselves, enough --
    ALLOW_INSTRUMENT_CONTROL defaulting off (this test deliberately leaves
    it unset) still refuses, proving the sim backend does not implicitly
    satisfy or bypass that check."""
    monkeypatch.setenv("PYVISA_LIBRARY", f"{FIXTURE_PATH}@sim")
    monkeypatch.delenv("ALLOW_INSTRUMENT_CONTROL", raising=False)

    approval = request_vna_measurement_approval(
        resource="ASRL1::INSTR",
        start_hz=2.4e9,
        stop_hz=2.5e9,
        points=3,
        sparams=["S11"],
        approved_by="engineer.jane",
        approval_callback=lambda fields: True,
    )

    with pytest.raises(InstrumentError, match="ALLOW_INSTRUMENT_CONTROL"):
        run_vna_measurement(
            resource="ASRL1::INSTR",
            start_hz=2.4e9,
            stop_hz=2.5e9,
            approval=approval,
            points=3,
            sparams=["S11"],
        )
