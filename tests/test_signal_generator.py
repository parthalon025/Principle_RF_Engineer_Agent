"""Tests for the signal generator adapter (issue #44, Phase 10 ticket 2 of
2), reusing measurement/base.py's approval gate exactly as
tests/test_vna.py exercises it for the VNA adapter. This is the one
adapter in this ticket that WRITES to the physical world (see
measurement/signal_generator.py's module docstring), so its approval-gate
usage is held to be AT LEAST as strict as VnaAdapter's -- the extra tests
in the "fingerprint specificity" section below are the direct proof this
ticket's design guidance calls for: an approval granted for one power
level/frequency/output-on-off combination must be rejected if applied to a
different one, not merely a different resource/frequency pair as
tests/test_vna.py already covers for the VNA.

See tests/test_vna.py's module docstring for the four-group discipline
these tests otherwise follow (groups 2/3, the shared
request_physical_measurement_approval()/check_physical_actuation_gate()
behavior itself, are already covered there and not duplicated here).
"""

import pytest

from measurement.base import Instrument, InstrumentError, InstrumentResult
from measurement.signal_generator import (
    DEFAULT_SCPI_COMMANDS,
    SignalGeneratorAdapter,
    _siggen_fingerprint_fields,
    request_signal_generator_output_approval,
    run_signal_generator_output,
)

# ---------------------------------------------------------------------------
# Group 1: the real, unmockable proof that this sandbox is rejected.
# ---------------------------------------------------------------------------


def test_pyvisa_is_genuinely_not_installed_in_this_environment():
    with pytest.raises(ImportError):
        import pyvisa  # noqa: F401


def test_signal_generator_adapter_measure_rejects_this_sandbox_with_no_overrides():
    """The actual safety property this ticket cares about most -- doubly so
    here, since this adapter actively outputs RF power: a real
    SignalGeneratorAdapter(), constructed with no test seams engaged,
    called with a job that has no resource and no approval, in this real
    unmodified environment (no ALLOW_INSTRUMENT_CONTROL, no pyvisa), must
    refuse."""
    adapter = SignalGeneratorAdapter()
    with pytest.raises(InstrumentError, match="Physical instrument actuation refused"):
        adapter.measure({"frequency_hz": 2.4e9, "power_dbm": 10.0})


def test_signal_generator_adapter_measure_rejects_this_sandbox_even_with_a_shaped_job():
    adapter = SignalGeneratorAdapter()
    with pytest.raises(InstrumentError) as excinfo:
        adapter.measure(
            {
                "resource": "TCPIP0::192.0.2.12::INSTR",
                "frequency_hz": 2.4e9,
                "power_dbm": 10.0,
                "output_on": True,
            }
        )
    message = str(excinfo.value)
    assert "ALLOW_INSTRUMENT_CONTROL" in message
    assert "pyvisa is not importable" in message
    assert "no approval was provided" in message


def test_run_signal_generator_output_rejects_this_sandbox_with_no_overrides():
    with pytest.raises(InstrumentError, match="Physical instrument actuation refused"):
        run_signal_generator_output(
            resource="TCPIP0::192.0.2.12::INSTR",
            frequency_hz=2.4e9,
            power_dbm=10.0,
            approval=None,
        )


def test_request_signal_generator_output_approval_rejects_this_sandbox_by_default():
    with pytest.raises(InstrumentError, match="No human-approval mechanism"):
        request_signal_generator_output_approval(
            resource="TCPIP0::192.0.2.12::INSTR",
            frequency_hz=2.4e9,
            power_dbm=10.0,
            approved_by="a.human",
        )


# ---------------------------------------------------------------------------
# Group 4: SignalGeneratorAdapter.measure() against a hand-written fake
# transport. Confinement is bypassed ONLY via the explicit
# confinement_check=lambda *a, **kw: None constructor-injection seam.
# ---------------------------------------------------------------------------


class FakeVisaTransport:
    """Hand-written fake matching the subset of pyvisa's Resource API
    SignalGeneratorAdapter.measure() calls: .query(str) -> str,
    .write(str), and .close(). Tracks the last frequency/power/output
    state written so readback queries can echo them back, and a fixed
    synthetic *IDN? identity."""

    def __init__(self, idn: str = "FAKE,SIGGEN-500,SN003,FW1.0"):
        self.idn = idn
        self.writes: list[str] = []
        self.queries: list[str] = []
        self.closed = False
        self._frequency_hz = 0.0
        self._power_dbm = 0.0
        self._output_on = False

    def write(self, cmd: str) -> None:
        self.writes.append(cmd)
        if cmd.startswith("FREQ "):
            self._frequency_hz = float(cmd.split()[-1])
        elif cmd.startswith("POW "):
            self._power_dbm = float(cmd.split()[-1])
        elif cmd == "OUTP:STAT ON":
            self._output_on = True
        elif cmd == "OUTP:STAT OFF":
            self._output_on = False

    def query(self, cmd: str) -> str:
        self.queries.append(cmd)
        if cmd == "*IDN?":
            return self.idn
        if cmd == "FREQ?":
            return str(self._frequency_hz)
        if cmd == "POW?":
            return str(self._power_dbm)
        if cmd == "OUTP:STAT?":
            return "1" if self._output_on else "0"
        return ""

    def close(self) -> None:
        self.closed = True


def _measure_against_fake(job: dict, fake: FakeVisaTransport | None = None, **kwargs):
    fake = fake or FakeVisaTransport()
    adapter = SignalGeneratorAdapter(
        transport_factory=lambda resource: fake,
        confinement_check=lambda *a, **kw: None,
        **kwargs,
    )
    result = adapter.measure({**job, "approval": job.get("approval", object())})
    return result, fake


_BASE_JOB = {
    "resource": "TCPIP0::192.0.2.12::INSTR",
    "frequency_hz": 2.4e9,
    "power_dbm": 10.0,
    "output_on": True,
}


def test_instrument_is_the_shared_adapter_contract():
    assert issubclass(SignalGeneratorAdapter, Instrument)
    assert SignalGeneratorAdapter.name == "SignalGenerator"


def test_measure_returns_instrument_result_with_measured_provenance():
    result, _fake = _measure_against_fake(_BASE_JOB)
    assert isinstance(result, InstrumentResult)
    assert result.provenance == "MEASURED"
    assert result.status == "COMPLETED"
    assert result.instrument == "FAKE,SIGGEN-500,SN003,FW1.0"


def test_measure_reports_actuated_state():
    result, _fake = _measure_against_fake(_BASE_JOB)
    assert result.outputs["frequency_hz"] == pytest.approx(2.4e9)
    assert result.outputs["power_dbm"] == pytest.approx(10.0)
    assert result.outputs["output_on"] is True


def test_measure_reports_instrument_readback():
    result, _fake = _measure_against_fake(_BASE_JOB)
    assert result.outputs["frequency_hz_readback"] == pytest.approx(2.4e9)
    assert result.outputs["power_dbm_readback"] == pytest.approx(10.0)
    assert result.outputs["output_state_readback"] == "1"


def test_measure_writes_expected_scpi_command_sequence():
    result, fake = _measure_against_fake(_BASE_JOB)
    assert "FREQ 2400000000" in fake.writes
    assert "POW 10.0" in fake.writes
    assert "OUTP:STAT ON" in fake.writes
    assert "*IDN?" in fake.queries


def test_measure_writes_output_off_when_requested():
    job = {**_BASE_JOB, "output_on": False}
    result, fake = _measure_against_fake(job)
    assert "OUTP:STAT OFF" in fake.writes
    assert "OUTP:STAT ON" not in fake.writes
    assert result.outputs["output_on"] is False


def test_measure_defaults_output_on_to_true_when_omitted():
    job = {k: v for k, v in _BASE_JOB.items() if k != "output_on"}
    result, fake = _measure_against_fake(job)
    assert result.outputs["output_on"] is True
    assert "OUTP:STAT ON" in fake.writes


def test_measure_closes_the_transport():
    result, fake = _measure_against_fake(_BASE_JOB)
    assert fake.closed is True


def test_measure_requires_frequency_and_power():
    with pytest.raises(InstrumentError, match="frequency_hz"):
        _measure_against_fake({"resource": "GPIB0::19::INSTR"})


def test_measure_tolerates_readback_not_supported():
    class NoReadbackTransport(FakeVisaTransport):
        def query(self, cmd: str) -> str:
            if cmd in {"FREQ?", "POW?", "OUTP:STAT?"}:
                raise RuntimeError("unsupported query")
            return super().query(cmd)

    result, _fake = _measure_against_fake(_BASE_JOB, fake=NoReadbackTransport())
    assert result.outputs["frequency_hz_readback"] is None
    assert result.outputs["power_dbm_readback"] is None
    assert result.outputs["output_state_readback"] is None
    assert result.status == "COMPLETED"


def test_commands_dict_is_fully_overridable():
    fake = FakeVisaTransport()
    custom_commands = {"freq_set": "FREQ:CW {frequency_hz:.0f}Hz"}
    adapter = SignalGeneratorAdapter(
        transport_factory=lambda resource: fake,
        confinement_check=lambda *a, **kw: None,
        commands=custom_commands,
    )
    adapter.measure({**_BASE_JOB, "approval": object()})
    assert any("FREQ:CW 2400000000Hz" in w for w in fake.writes)
    assert any(w.startswith("POW ") for w in fake.writes)


def test_default_commands_are_not_mutated_by_an_override():
    fake = FakeVisaTransport()
    SignalGeneratorAdapter(
        transport_factory=lambda resource: fake,
        confinement_check=lambda *a, **kw: None,
        commands={"freq_set": "CUSTOM {frequency_hz}"},
    )
    assert DEFAULT_SCPI_COMMANDS["freq_set"] == "FREQ {frequency_hz:.0f}"


# ---------------------------------------------------------------------------
# Tool-layer convenience functions -- end-to-end path, with a real
# ApprovalReceipt granted via an explicit test-only callback and a fake
# transport.
# ---------------------------------------------------------------------------


def test_end_to_end_request_then_measure_with_fake_transport():
    resource = "TCPIP0::192.0.2.22::INSTR"
    approval = request_signal_generator_output_approval(
        resource=resource,
        frequency_hz=2.4e9,
        power_dbm=10.0,
        output_on=True,
        approved_by="engineer.jane",
        approval_callback=lambda fields: True,
    )
    assert isinstance(approval, dict)

    result = run_signal_generator_output(
        resource=resource,
        frequency_hz=2.4e9,
        power_dbm=10.0,
        output_on=True,
        approval=approval,
        transport_factory=lambda r: FakeVisaTransport(),
        confinement_check=lambda *a, **kw: None,
    )
    assert result["provenance"] == "MEASURED"
    assert result["status"] == "COMPLETED"
    assert result["instrument"] == "FAKE,SIGGEN-500,SN003,FW1.0"
    assert result["power_dbm"] == pytest.approx(10.0)


# ---------------------------------------------------------------------------
# Fingerprint-specificity: the design-guidance-mandated proof that an
# approval granted for "10 dBm at 2.4 GHz" cannot be silently reused/
# misapplied to a different power level, a different frequency, or a
# flipped output on/off state. Each test grants a real approval for one
# combination, via the real (unmocked) request_physical_measurement_
# approval/check_physical_actuation_gate verification path (confinement_
# check is intentionally left as the real function here, exactly like
# tests/test_vna.py's test_end_to_end_measure_rejects_approval_for_a_
# different_request -- only pyvisa/env are irrelevant because a fake
# transport is supplied and the real gate's OTHER checks would also fail in
# this sandbox regardless; what actually proves the point is that the
# fingerprint-mismatch error is what's raised).
# ---------------------------------------------------------------------------

_RESOURCE = "TCPIP0::192.0.2.23::INSTR"


def _approved_for(frequency_hz: float, power_dbm: float, output_on: bool = True) -> dict:
    return request_signal_generator_output_approval(
        resource=_RESOURCE,
        frequency_hz=frequency_hz,
        power_dbm=power_dbm,
        output_on=output_on,
        approved_by="engineer.jane",
        approval_callback=lambda fields: True,
    )


def test_end_to_end_measure_rejects_approval_for_a_different_frequency():
    approval = _approved_for(frequency_hz=2.4e9, power_dbm=10.0)
    with pytest.raises(InstrumentError, match="does not match"):
        run_signal_generator_output(
            resource=_RESOURCE,
            frequency_hz=900e6,  # different from what was approved
            power_dbm=10.0,
            approval=approval,
            transport_factory=lambda r: FakeVisaTransport(),
        )


def test_end_to_end_measure_rejects_approval_for_a_different_power_level():
    """The specific scenario named in this ticket's design guidance: an
    approval for "10 dBm at 2.4 GHz" must not be reusable for "30 dBm at
    2.4 GHz"."""
    approval = _approved_for(frequency_hz=2.4e9, power_dbm=10.0)
    with pytest.raises(InstrumentError, match="does not match"):
        run_signal_generator_output(
            resource=_RESOURCE,
            frequency_hz=2.4e9,
            power_dbm=30.0,  # different from what was approved
            approval=approval,
            transport_factory=lambda r: FakeVisaTransport(),
        )


def test_end_to_end_measure_rejects_approval_for_a_different_power_and_frequency_combination():
    """The exact scenario the design guidance names by example: an
    approval for "10 dBm at 2.4 GHz" cannot be silently reused/misapplied
    to "30 dBm at 900 MHz"."""
    approval = _approved_for(frequency_hz=2.4e9, power_dbm=10.0)
    with pytest.raises(InstrumentError, match="does not match"):
        run_signal_generator_output(
            resource=_RESOURCE,
            frequency_hz=900e6,
            power_dbm=30.0,
            approval=approval,
            transport_factory=lambda r: FakeVisaTransport(),
        )


def test_end_to_end_measure_rejects_approval_for_a_flipped_output_state():
    """An approval granted with output_on=True cannot be replayed to
    silently flip the output OFF (or vice versa) -- output_on is part of
    the fingerprinted request, not merely a side effect."""
    approval = _approved_for(frequency_hz=2.4e9, power_dbm=10.0, output_on=True)
    with pytest.raises(InstrumentError, match="does not match"):
        run_signal_generator_output(
            resource=_RESOURCE,
            frequency_hz=2.4e9,
            power_dbm=10.0,
            output_on=False,  # different from what was approved
            approval=approval,
            transport_factory=lambda r: FakeVisaTransport(),
        )


def test_end_to_end_measure_rejects_approval_for_a_different_resource():
    approval = _approved_for(frequency_hz=2.4e9, power_dbm=10.0)
    with pytest.raises(InstrumentError, match="does not match"):
        run_signal_generator_output(
            resource="TCPIP0::192.0.2.99::INSTR",  # different from approved
            frequency_hz=2.4e9,
            power_dbm=10.0,
            approval=approval,
            transport_factory=lambda r: FakeVisaTransport(),
        )


def test_end_to_end_measure_accepts_approval_for_the_exact_approved_combination():
    """Positive control for the fingerprint-specificity tests above: the
    EXACT same combination that was approved is accepted (still refused
    here only because the real gate's ALLOW_INSTRUMENT_CONTROL/pyvisa
    checks genuinely fail in this sandbox -- proving the fingerprint match
    itself succeeded and it is a DIFFERENT signal that raises)."""
    approval = _approved_for(frequency_hz=2.4e9, power_dbm=10.0, output_on=True)
    with pytest.raises(InstrumentError) as excinfo:
        run_signal_generator_output(
            resource=_RESOURCE,
            frequency_hz=2.4e9,
            power_dbm=10.0,
            output_on=True,
            approval=approval,
            transport_factory=lambda r: FakeVisaTransport(),
        )
    message = str(excinfo.value)
    assert "does not match" not in message
    assert "ALLOW_INSTRUMENT_CONTROL" in message


def test_fingerprint_fields_include_power_and_output_state_not_just_frequency():
    """Direct unit-level proof that _siggen_fingerprint_fields captures
    power_dbm and output_on, not just resource/frequency_hz -- the
    property the design guidance asks to be verified explicitly rather
    than assumed."""
    base = _siggen_fingerprint_fields("R1", 2.4e9, 10.0, True)
    assert base != _siggen_fingerprint_fields("R1", 2.4e9, 30.0, True)
    assert base != _siggen_fingerprint_fields("R1", 900e6, 10.0, True)
    assert base != _siggen_fingerprint_fields("R1", 2.4e9, 10.0, False)


def test_fingerprint_fields_helper_is_order_independent_dict_shape():
    fields_a = _siggen_fingerprint_fields("R1", 2.4e9, 10.0, True)
    fields_b = _siggen_fingerprint_fields("R1", 2.4e9, 10.0, True)
    assert fields_a == fields_b
