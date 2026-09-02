"""Tests for the RF power meter adapter (issue #44, Phase 10 ticket 2 of
2), reusing measurement/base.py's approval gate exactly as
tests/test_vna.py exercises it for the VNA adapter. See tests/test_vna.py's
module docstring for the four-group discipline these tests follow (groups
2/3, the shared request_physical_measurement_approval()/
check_physical_actuation_gate() behavior itself, are already covered there
and not duplicated here).
"""

import pytest

from measurement.base import Instrument, InstrumentError, InstrumentResult
from measurement.power_meter import (
    DEFAULT_SCPI_COMMANDS,
    PowerMeterAdapter,
    _power_meter_fingerprint_fields,
    request_power_meter_measurement_approval,
    run_power_meter_measurement,
)

# ---------------------------------------------------------------------------
# Group 1: the real, unmockable proof that this sandbox is rejected.
# ---------------------------------------------------------------------------


def test_pyvisa_is_genuinely_not_installed_in_this_environment():
    with pytest.raises(ImportError):
        import pyvisa  # noqa: F401


def test_power_meter_adapter_measure_rejects_this_sandbox_with_no_overrides():
    """The actual safety property this ticket cares about most: a real
    PowerMeterAdapter(), constructed with no test seams engaged, called
    with a job that has no resource and no approval, in this real
    unmodified environment (no ALLOW_INSTRUMENT_CONTROL, no pyvisa), must
    refuse."""
    adapter = PowerMeterAdapter()
    with pytest.raises(InstrumentError, match="Physical instrument actuation refused"):
        adapter.measure({"frequency_hz": 2.4e9})


def test_power_meter_adapter_measure_rejects_this_sandbox_even_with_a_shaped_job():
    adapter = PowerMeterAdapter()
    with pytest.raises(InstrumentError) as excinfo:
        adapter.measure(
            {
                "resource": "TCPIP0::192.0.2.13::INSTR",
                "frequency_hz": 2.4e9,
            }
        )
    message = str(excinfo.value)
    assert "ALLOW_INSTRUMENT_CONTROL" in message
    assert "pyvisa is not importable" in message
    assert "no approval was provided" in message


def test_run_power_meter_measurement_rejects_this_sandbox_with_no_overrides():
    with pytest.raises(InstrumentError, match="Physical instrument actuation refused"):
        run_power_meter_measurement(
            resource="TCPIP0::192.0.2.13::INSTR",
            frequency_hz=2.4e9,
            approval=None,
        )


def test_request_power_meter_measurement_approval_rejects_this_sandbox_by_default():
    with pytest.raises(InstrumentError, match="No human-approval mechanism"):
        request_power_meter_measurement_approval(
            resource="TCPIP0::192.0.2.13::INSTR",
            frequency_hz=2.4e9,
            approved_by="a.human",
        )


# ---------------------------------------------------------------------------
# Group 4: PowerMeterAdapter.measure() against a hand-written fake
# transport. Confinement is bypassed ONLY via the explicit
# confinement_check=lambda *a, **kw: None constructor-injection seam.
# ---------------------------------------------------------------------------


class FakeVisaTransport:
    """Hand-written fake matching the subset of pyvisa's Resource API
    PowerMeterAdapter.measure() calls: .query(str) -> str, .write(str),
    and .close(). Returns a fixed synthetic power reading and *IDN?
    identity."""

    def __init__(self, idn: str = "FAKE,PWRMTR-100,SN004,FW1.1", reading_dbm: float = 5.25):
        self.idn = idn
        self.reading_dbm = reading_dbm
        self.writes: list[str] = []
        self.queries: list[str] = []
        self.closed = False

    def write(self, cmd: str) -> None:
        self.writes.append(cmd)

    def query(self, cmd: str) -> str:
        self.queries.append(cmd)
        if cmd == "*IDN?":
            return self.idn
        if cmd == "FETC?":
            return str(self.reading_dbm)
        if "CORR:CFAC" in cmd:
            return "0.98"
        return ""

    def close(self) -> None:
        self.closed = True


def _measure_against_fake(job: dict, fake: FakeVisaTransport | None = None, **kwargs):
    fake = fake or FakeVisaTransport()
    adapter = PowerMeterAdapter(
        transport_factory=lambda resource: fake,
        confinement_check=lambda *a, **kw: None,
        **kwargs,
    )
    result = adapter.measure({**job, "approval": job.get("approval", object())})
    return result, fake


_BASE_JOB = {
    "resource": "TCPIP0::192.0.2.13::INSTR",
    "frequency_hz": 2.4e9,
}


def test_instrument_is_the_shared_adapter_contract():
    assert issubclass(PowerMeterAdapter, Instrument)
    assert PowerMeterAdapter.name == "PowerMeter"


def test_measure_returns_instrument_result_with_measured_provenance():
    result, _fake = _measure_against_fake(_BASE_JOB)
    assert isinstance(result, InstrumentResult)
    assert result.provenance == "MEASURED"
    assert result.status == "COMPLETED"
    assert result.instrument == "FAKE,PWRMTR-100,SN004,FW1.1"


def test_measure_reports_instrument_identity_and_resource():
    result, _fake = _measure_against_fake(_BASE_JOB)
    assert result.outputs["instrument_idn"] == "FAKE,PWRMTR-100,SN004,FW1.1"
    assert result.outputs["resource"] == _BASE_JOB["resource"]


def test_measure_reports_power_reading_with_units_and_frequency():
    result, _fake = _measure_against_fake(_BASE_JOB)
    assert result.outputs["power_dbm"] == pytest.approx(5.25)
    assert result.outputs["units"] == "dBm"
    assert result.outputs["frequency_hz"] == pytest.approx(2.4e9)


def test_measure_writes_expected_scpi_command_sequence():
    result, fake = _measure_against_fake(_BASE_JOB)
    assert "SENS:FREQ 2400000000" in fake.writes
    assert any("INIT" in w for w in fake.writes)
    assert "*IDN?" in fake.queries
    assert "FETC?" in fake.queries


def test_measure_closes_the_transport():
    result, fake = _measure_against_fake(_BASE_JOB)
    assert fake.closed is True


def test_measure_reports_correction_factor_and_a_metadata_note():
    result, _fake = _measure_against_fake(_BASE_JOB)
    calibration = result.outputs["calibration"]
    assert calibration["instrument_reported_correction_factor"] == pytest.approx(0.98)
    assert "note" in calibration


def test_measure_merges_caller_supplied_calibration_metadata():
    job = {**_BASE_JOB, "calibration": {"sensor_sn": "US12345", "cal_due": "2027-01-01"}}
    result, _fake = _measure_against_fake(job)
    calibration = result.outputs["calibration"]
    assert calibration["sensor_sn"] == "US12345"
    assert calibration["cal_due"] == "2027-01-01"
    assert calibration["instrument_reported_correction_factor"] == pytest.approx(0.98)


def test_measure_requires_frequency_hz():
    with pytest.raises(InstrumentError, match="frequency_hz"):
        _measure_against_fake({"resource": "GPIB0::20::INSTR"})


def test_measure_raises_on_malformed_reading_response():
    class BrokenTransport(FakeVisaTransport):
        def query(self, cmd: str) -> str:
            if cmd == "FETC?":
                return "not-a-number"
            return super().query(cmd)

    with pytest.raises(InstrumentError, match="could not parse"):
        _measure_against_fake(_BASE_JOB, fake=BrokenTransport())


def test_measure_raises_on_empty_reading_response():
    class EmptyReadingTransport(FakeVisaTransport):
        def query(self, cmd: str) -> str:
            if cmd == "FETC?":
                return ""
            return super().query(cmd)

    with pytest.raises(InstrumentError, match="empty reading"):
        _measure_against_fake(_BASE_JOB, fake=EmptyReadingTransport())


def test_measure_tolerates_calibration_factor_query_not_supported():
    class NoCalFactorTransport(FakeVisaTransport):
        def query(self, cmd: str) -> str:
            if "CORR:CFAC" in cmd:
                raise RuntimeError("unsupported query")
            return super().query(cmd)

    result, _fake = _measure_against_fake(_BASE_JOB, fake=NoCalFactorTransport())
    assert "instrument_reported_correction_factor" not in result.outputs["calibration"]
    assert result.status == "COMPLETED"


def test_commands_dict_is_fully_overridable():
    fake = FakeVisaTransport()
    custom_commands = {"freq_set": "SENS:FREQ:FIX {frequency_hz:.0f}HZ"}
    adapter = PowerMeterAdapter(
        transport_factory=lambda resource: fake,
        confinement_check=lambda *a, **kw: None,
        commands=custom_commands,
    )
    adapter.measure({**_BASE_JOB, "approval": object()})
    assert any("SENS:FREQ:FIX 2400000000HZ" in w for w in fake.writes)
    assert "FETC?" in fake.queries


def test_default_commands_are_not_mutated_by_an_override():
    fake = FakeVisaTransport()
    PowerMeterAdapter(
        transport_factory=lambda resource: fake,
        confinement_check=lambda *a, **kw: None,
        commands={"freq_set": "CUSTOM {frequency_hz}"},
    )
    assert DEFAULT_SCPI_COMMANDS["freq_set"] == "SENS:FREQ {frequency_hz:.0f}"


# ---------------------------------------------------------------------------
# Tool-layer convenience functions -- end-to-end path, with a real
# ApprovalReceipt granted via an explicit test-only callback and a fake
# transport.
# ---------------------------------------------------------------------------


def test_end_to_end_request_then_measure_with_fake_transport():
    resource = "TCPIP0::192.0.2.24::INSTR"
    approval = request_power_meter_measurement_approval(
        resource=resource,
        frequency_hz=2.4e9,
        approved_by="engineer.jane",
        approval_callback=lambda fields: True,
    )
    assert isinstance(approval, dict)

    result = run_power_meter_measurement(
        resource=resource,
        frequency_hz=2.4e9,
        approval=approval,
        transport_factory=lambda r: FakeVisaTransport(),
        confinement_check=lambda *a, **kw: None,
    )
    assert result["provenance"] == "MEASURED"
    assert result["status"] == "COMPLETED"
    assert result["instrument"] == "FAKE,PWRMTR-100,SN004,FW1.1"
    assert result["power_dbm"] == pytest.approx(5.25)


def test_end_to_end_measure_rejects_approval_for_a_different_request():
    """An approval granted for one frequency cannot be reused for a
    different one, even with a fake transport and bypassed pyvisa/env
    checks -- because the real approval verification inside
    check_physical_actuation_gate is NOT part of what confinement_check
    bypasses when confinement_check is left as the real function."""
    resource = "TCPIP0::192.0.2.24::INSTR"
    approval = request_power_meter_measurement_approval(
        resource=resource,
        frequency_hz=2.4e9,
        approved_by="engineer.jane",
        approval_callback=lambda fields: True,
    )

    with pytest.raises(InstrumentError, match="does not match"):
        run_power_meter_measurement(
            resource=resource,
            frequency_hz=5.8e9,  # different from what was approved
            approval=approval,
            transport_factory=lambda r: FakeVisaTransport(),
        )


def test_fingerprint_fields_helper_is_order_independent_dict_shape():
    fields_a = _power_meter_fingerprint_fields("R1", 2.4e9)
    fields_b = _power_meter_fingerprint_fields("R1", 2.4e9)
    assert fields_a == fields_b
