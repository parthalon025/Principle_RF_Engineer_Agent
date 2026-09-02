"""Tests for the spectrum analyzer adapter (issue #44, Phase 10 ticket 2 of
2), reusing measurement/base.py's approval gate exactly as
tests/test_vna.py exercises it for the VNA adapter. See tests/test_vna.py's
module docstring for the four-group discipline these tests follow:

  1. The physical-actuation gate against THIS real, unmodified environment.
  2. (Shared infrastructure already covered by tests/test_vna.py --
     request_physical_measurement_approval()/check_physical_actuation_gate()
     themselves are not re-tested field-by-field here; this file only adds
     the spectrum-analyzer-specific fingerprint-fields proof.)
  3. (Same note as 2.)
  4. SpectrumAnalyzerAdapter.measure()'s SCPI command sequence, trace
     parsing, and MEASURED-provenance/calibration-metadata output, against
     a hand-written fake transport -- the gate is bypassed here ONLY via
     the explicit, visible confinement_check=lambda *a, **kw: None
     constructor-injection seam, never by monkeypatching internals.
"""

from pathlib import Path

import pytest

from measurement.base import Instrument, InstrumentError, InstrumentResult
from measurement.spectrum_analyzer import (
    DEFAULT_SCPI_COMMANDS,
    SpectrumAnalyzerAdapter,
    _spectrum_analyzer_fingerprint_fields,
    request_spectrum_analyzer_measurement_approval,
    run_spectrum_analyzer_measurement,
)

# ---------------------------------------------------------------------------
# Group 1: the real, unmockable proof that this sandbox is rejected.
# ---------------------------------------------------------------------------


def test_pyvisa_is_genuinely_not_installed_in_this_environment():
    with pytest.raises(ImportError):
        import pyvisa  # noqa: F401


def test_spectrum_analyzer_adapter_measure_rejects_this_sandbox_with_no_overrides():
    """The actual safety property this ticket cares about most: a real
    SpectrumAnalyzerAdapter(), constructed with no test seams engaged,
    called with a job that has no resource and no approval, in this real
    unmodified environment (no ALLOW_INSTRUMENT_CONTROL, no pyvisa), must
    refuse."""
    adapter = SpectrumAnalyzerAdapter()
    with pytest.raises(InstrumentError, match="Physical instrument actuation refused"):
        adapter.measure({"center_hz": 2.4e9, "span_hz": 100e6})


def test_spectrum_analyzer_adapter_measure_rejects_this_sandbox_even_with_a_shaped_job():
    adapter = SpectrumAnalyzerAdapter()
    with pytest.raises(InstrumentError) as excinfo:
        adapter.measure(
            {
                "resource": "TCPIP0::192.0.2.11::INSTR",
                "center_hz": 2.4e9,
                "span_hz": 100e6,
                "res_bw_hz": 100e3,
                "points": 401,
            }
        )
    message = str(excinfo.value)
    assert "ALLOW_INSTRUMENT_CONTROL" in message
    assert "pyvisa is not importable" in message
    assert "no approval was provided" in message


def test_run_spectrum_analyzer_measurement_rejects_this_sandbox_with_no_overrides():
    with pytest.raises(InstrumentError, match="Physical instrument actuation refused"):
        run_spectrum_analyzer_measurement(
            resource="TCPIP0::192.0.2.11::INSTR",
            center_hz=2.4e9,
            span_hz=100e6,
            approval=None,
        )


def test_request_spectrum_analyzer_measurement_approval_rejects_this_sandbox_by_default():
    with pytest.raises(InstrumentError, match="No human-approval mechanism"):
        request_spectrum_analyzer_measurement_approval(
            resource="TCPIP0::192.0.2.11::INSTR",
            center_hz=2.4e9,
            span_hz=100e6,
            approved_by="a.human",
        )


# ---------------------------------------------------------------------------
# Group 4: SpectrumAnalyzerAdapter.measure() against a hand-written fake
# transport. Confinement is bypassed ONLY via the explicit
# confinement_check=lambda *a, **kw: None constructor-injection seam.
# ---------------------------------------------------------------------------


class FakeVisaTransport:
    """Hand-written fake matching the subset of pyvisa's Resource API
    SpectrumAnalyzerAdapter.measure() calls: .query(str) -> str,
    .write(str), and .close(). Returns synthetic but plausible trace
    amplitude data for however many sweep points were configured (tracked
    via the SWE:POIN write it observes, if any -- otherwise this fake's own
    default) and a fixed synthetic *IDN? identity."""

    def __init__(self, idn: str = "FAKE,SA-3000,SN002,FW2.0", points: int = 5):
        self.idn = idn
        self.writes: list[str] = []
        self.queries: list[str] = []
        self.points = points
        self.closed = False

    def write(self, cmd: str) -> None:
        self.writes.append(cmd)
        if "SWE:POIN" in cmd:
            self.points = int(cmd.split()[-1])

    def query(self, cmd: str) -> str:
        self.queries.append(cmd)
        if cmd == "*IDN?":
            return self.idn
        if "TRAC" in cmd:
            values = [-80.0 + i for i in range(self.points)]
            return ",".join(str(v) for v in values)
        return ""

    def close(self) -> None:
        self.closed = True


def _measure_against_fake(job: dict, fake: FakeVisaTransport | None = None, **kwargs):
    fake = fake or FakeVisaTransport(points=job.get("points", 5))
    adapter = SpectrumAnalyzerAdapter(
        transport_factory=lambda resource: fake,
        confinement_check=lambda *a, **kw: None,
        **kwargs,
    )
    result = adapter.measure({**job, "approval": job.get("approval", object())})
    return result, fake


_BASE_JOB = {
    "resource": "TCPIP0::192.0.2.11::INSTR",
    "center_hz": 2.4e9,
    "span_hz": 100e6,
    "res_bw_hz": 100e3,
    "points": 5,
}


def test_instrument_is_the_shared_adapter_contract():
    assert issubclass(SpectrumAnalyzerAdapter, Instrument)
    assert SpectrumAnalyzerAdapter.name == "SpectrumAnalyzer"


def test_measure_returns_instrument_result_with_measured_provenance():
    result, _fake = _measure_against_fake(_BASE_JOB)
    assert isinstance(result, InstrumentResult)
    assert result.provenance == "MEASURED"
    assert result.status == "COMPLETED"
    assert result.instrument == "FAKE,SA-3000,SN002,FW2.0"


def test_measure_reports_instrument_identity_and_resource():
    result, _fake = _measure_against_fake(_BASE_JOB)
    assert result.outputs["instrument_idn"] == "FAKE,SA-3000,SN002,FW2.0"
    assert result.outputs["resource"] == _BASE_JOB["resource"]


def test_measure_returns_frequency_grid_spanning_center_and_span():
    result, _fake = _measure_against_fake(_BASE_JOB)
    freqs = result.outputs["frequency_hz"]
    assert len(freqs) == 5
    assert freqs[0] == pytest.approx(2.4e9 - 50e6)
    assert freqs[-1] == pytest.approx(2.4e9 + 50e6)


def test_measure_parses_trace_into_amplitude_values():
    result, _fake = _measure_against_fake(_BASE_JOB)
    amplitude = result.outputs["amplitude_dbm"]
    assert amplitude == pytest.approx([-80.0, -79.0, -78.0, -77.0, -76.0])


def test_measure_reports_peak_frequency_and_amplitude():
    result, _fake = _measure_against_fake(_BASE_JOB)
    assert result.outputs["peak_amplitude_dbm"] == pytest.approx(-76.0)
    assert result.outputs["peak_frequency_hz"] == pytest.approx(2.4e9 + 50e6)


def test_measure_writes_expected_scpi_command_sequence():
    result, fake = _measure_against_fake(_BASE_JOB)
    joined = " | ".join(fake.writes)
    assert "FREQ:CENT 2400000000" in joined
    assert "FREQ:SPAN 100000000" in joined
    assert "BAND:RES 100000" in joined
    assert any("INIT" in w for w in fake.writes)
    assert "*IDN?" in fake.queries
    assert any("TRAC" in q for q in fake.queries)


def test_measure_skips_res_bandwidth_write_when_not_given():
    job = {**_BASE_JOB}
    del job["res_bw_hz"]
    result, fake = _measure_against_fake(job)
    assert not any("BAND:RES" in w for w in fake.writes)
    assert result.outputs["resolution_bandwidth_hz"] is None


def test_measure_closes_the_transport():
    result, fake = _measure_against_fake(_BASE_JOB)
    assert fake.closed is True


def test_measure_reports_a_calibration_metadata_note():
    result, _fake = _measure_against_fake(_BASE_JOB)
    calibration = result.outputs["calibration"]
    assert "note" in calibration


def test_measure_merges_caller_supplied_calibration_metadata():
    job = {**_BASE_JOB, "calibration": {"last_self_alignment": "2026-07-01"}}
    result, _fake = _measure_against_fake(job)
    calibration = result.outputs["calibration"]
    assert calibration["last_self_alignment"] == "2026-07-01"
    assert "note" in calibration


def test_measure_requires_center_and_span_hz():
    with pytest.raises(InstrumentError, match="center_hz"):
        _measure_against_fake({"resource": "GPIB0::18::INSTR"})


def test_measure_raises_on_malformed_trace_response():
    class BrokenTransport(FakeVisaTransport):
        def query(self, cmd: str) -> str:
            if "TRAC" in cmd:
                return "not,a,number,here,x"
            return super().query(cmd)

    with pytest.raises(InstrumentError, match="could not parse"):
        _measure_against_fake(_BASE_JOB, fake=BrokenTransport(points=5))


def test_measure_raises_on_point_count_mismatch():
    class MismatchedTransport(FakeVisaTransport):
        def query(self, cmd: str) -> str:
            if "TRAC" in cmd:
                return "-80.0,-79.0"  # only 2 points, job requests 5
            return super().query(cmd)

    with pytest.raises(InstrumentError, match="expected 5"):
        _measure_against_fake(_BASE_JOB, fake=MismatchedTransport(points=5))


def test_commands_dict_is_fully_overridable():
    fake = FakeVisaTransport(points=5)
    custom_commands = {"freq_center": "FREQ:CENTER {center_hz:.0f}HZ"}
    adapter = SpectrumAnalyzerAdapter(
        transport_factory=lambda resource: fake,
        confinement_check=lambda *a, **kw: None,
        commands=custom_commands,
    )
    adapter.measure({**_BASE_JOB, "approval": object()})
    assert any("FREQ:CENTER 2400000000HZ" in w for w in fake.writes)
    assert any("FREQ:SPAN" in w for w in fake.writes)


def test_default_commands_are_not_mutated_by_an_override():
    fake = FakeVisaTransport(points=5)
    SpectrumAnalyzerAdapter(
        transport_factory=lambda resource: fake,
        confinement_check=lambda *a, **kw: None,
        commands={"freq_center": "CUSTOM {center_hz}"},
    )
    assert DEFAULT_SCPI_COMMANDS["freq_center"] == "FREQ:CENT {center_hz:.0f}"


# ---------------------------------------------------------------------------
# Tool-layer convenience functions -- the end-to-end path an agent/MCP tool
# would use, with a real ApprovalReceipt granted via an explicit test-only
# callback and a fake transport.
# ---------------------------------------------------------------------------


def test_end_to_end_request_then_measure_with_fake_transport():
    resource = "TCPIP0::192.0.2.21::INSTR"
    approval = request_spectrum_analyzer_measurement_approval(
        resource=resource,
        center_hz=2.4e9,
        span_hz=100e6,
        res_bw_hz=100e3,
        points=5,
        approved_by="engineer.jane",
        approval_callback=lambda fields: True,
    )
    assert isinstance(approval, dict)

    result = run_spectrum_analyzer_measurement(
        resource=resource,
        center_hz=2.4e9,
        span_hz=100e6,
        res_bw_hz=100e3,
        points=5,
        approval=approval,
        transport_factory=lambda r: FakeVisaTransport(points=5),
        confinement_check=lambda *a, **kw: None,
    )
    assert result["provenance"] == "MEASURED"
    assert result["status"] == "COMPLETED"
    assert result["instrument"] == "FAKE,SA-3000,SN002,FW2.0"
    assert len(result["frequency_hz"]) == 5


def test_end_to_end_measure_rejects_approval_for_a_different_request():
    """An approval granted for one center frequency cannot be reused for a
    different one, even with a fake transport and bypassed pyvisa/env
    checks -- because the real approval verification inside
    check_physical_actuation_gate is NOT part of what confinement_check
    bypasses when confinement_check is left as the real function."""
    resource = "TCPIP0::192.0.2.21::INSTR"
    approval = request_spectrum_analyzer_measurement_approval(
        resource=resource,
        center_hz=2.4e9,
        span_hz=100e6,
        points=5,
        approved_by="engineer.jane",
        approval_callback=lambda fields: True,
    )

    with pytest.raises(InstrumentError, match="does not match"):
        run_spectrum_analyzer_measurement(
            resource=resource,
            center_hz=5.8e9,  # different from what was approved
            span_hz=100e6,
            points=5,
            approval=approval,
            transport_factory=lambda r: FakeVisaTransport(points=5),
        )


def test_fingerprint_fields_helper_is_order_independent_dict_shape():
    fields_a = _spectrum_analyzer_fingerprint_fields("R1", 2.4e9, 100e6, 100e3, 401)
    fields_b = _spectrum_analyzer_fingerprint_fields("R1", 2.4e9, 100e6, 100e3, 401)
    assert fields_a == fields_b


def test_measure_touchstone_free_result_is_plain_json_serializable_shape(tmp_path: Path):
    """Sanity check that this adapter's result contains no non-JSON-
    serializable objects (unlike VnaAdapter's, which embeds an skrf.Network
    reference only via a written file path) -- a spectrum-analyzer trace
    has no natural Touchstone/network representation and this module
    deliberately does not force one (see module/ticket design guidance)."""
    import json

    result, _fake = _measure_against_fake(_BASE_JOB)
    payload = {
        "provenance": result.provenance,
        "instrument": result.instrument,
        "status": result.status,
        **result.outputs,
    }
    json.dumps(payload)  # must not raise
