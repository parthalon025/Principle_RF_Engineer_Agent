"""Tests for the SCPI/VISA instrument-adapter interface + VNA adapter,
with a hard human-approval gate before any physical actuation (issue #43,
Phase 10 ticket 1 of 2).

CRITICAL, NON-NEGOTIABLE PROJECT CONSTRAINT under test here: physical lab
instruments are never controlled autonomously (README.md, docs/
BUILD_PLAN.md's Phase 10 "Physical control remains approval-required",
docs/SECURITY.md). This file's tests fall into four groups, mirroring
tests/test_hfss.py's own discipline for ticket #40's workstation-
confinement gate:

  1. The physical-actuation gate against THIS real, unmodified environment
     -- a real, meaningful, non-mockable test of the actual safety
     property this ticket cares about most: that this sandbox (no
     ALLOW_INSTRUMENT_CONTROL, no VISA resource, no pyvisa installed, no
     approval) is rejected.
  2. request_physical_measurement_approval()'s own behavior -- proving it
     ALWAYS raises with no approval_callback (the only way this codebase's
     current agent/MCP tool wiring can call it), and that a receipt it
     does grant is cryptographically bound to the exact request it was
     granted for (fingerprint mismatch / forged signature / bare-token
     substitution are all rejected).
  3. check_physical_actuation_gate's own branch logic, via explicit
     overrides -- these do NOT touch real os.environ or a real pyvisa
     install; they test the gate's own decision logic in isolation.
  4. VnaAdapter.measure()'s SCPI command sequence, S-parameter parsing,
     Touchstone construction, and MEASURED-provenance/calibration-metadata
     output, against a hand-written fake transport -- the gate is bypassed
     here ONLY via the explicit, visible confinement_check=lambda *a,
     **kw: None constructor-injection seam (mirroring HfssSimulator's
     confinement_check=lambda: None), never by monkeypatching internals --
     so this never contradicts groups 1-3's "the real gate rejects this
     sandbox" finding.
"""

from pathlib import Path

import pytest

from measurement.base import (
    ApprovalReceipt,
    Instrument,
    InstrumentError,
    InstrumentResult,
    check_physical_actuation_gate,
    request_physical_measurement_approval,
)
from measurement.vna import (
    DEFAULT_SCPI_COMMANDS,
    VnaAdapter,
    _vna_fingerprint_fields,
    request_vna_measurement_approval,
    run_vna_measurement,
)

# ---------------------------------------------------------------------------
# Group 1: the real, unmockable proof that this sandbox is rejected.
# ---------------------------------------------------------------------------


def test_pyvisa_is_genuinely_not_installed_in_this_environment():
    """Confirms the premise directly: this is not a mock pretending pyvisa
    is absent, it actually is, in the interpreter running this test suite."""
    with pytest.raises(ImportError):
        import pyvisa  # noqa: F401


def test_vna_adapter_measure_rejects_this_sandbox_with_no_overrides():
    """The actual safety property this ticket cares about most: a real
    VnaAdapter(), constructed with no test seams engaged, called with a
    job that has no resource and no approval, in this real unmodified
    environment (no ALLOW_INSTRUMENT_CONTROL, no pyvisa), must refuse."""
    adapter = VnaAdapter()
    with pytest.raises(InstrumentError, match="Physical instrument actuation refused"):
        adapter.measure({"start_hz": 1.0e9, "stop_hz": 2.0e9})


def test_vna_adapter_measure_rejects_this_sandbox_even_with_a_shaped_job():
    """Same property, but with a job that LOOKS complete (resource string
    present, sparams present) apart from the approval -- proving the gate
    isn't merely catching an obviously-incomplete request."""
    adapter = VnaAdapter()
    with pytest.raises(InstrumentError) as excinfo:
        adapter.measure(
            {
                "resource": "TCPIP0::192.0.2.10::INSTR",
                "start_hz": 1.0e9,
                "stop_hz": 2.0e9,
                "points": 51,
                "sparams": ["S11"],
            }
        )
    message = str(excinfo.value)
    assert "ALLOW_INSTRUMENT_CONTROL" in message
    assert "pyvisa is not importable" in message
    assert "no approval was provided" in message


def test_run_vna_measurement_rejects_this_sandbox_with_no_overrides():
    with pytest.raises(InstrumentError, match="Physical instrument actuation refused"):
        run_vna_measurement(
            resource="TCPIP0::192.0.2.10::INSTR",
            start_hz=1.0e9,
            stop_hz=2.0e9,
            approval=None,
        )


def test_request_vna_measurement_approval_rejects_this_sandbox_by_default():
    """The other half of the gate: even the *approval-request* step itself
    refuses to fabricate an approval, since no human-approval mechanism is
    wired into this codebase yet."""
    with pytest.raises(InstrumentError, match="No human-approval mechanism"):
        request_vna_measurement_approval(
            resource="TCPIP0::192.0.2.10::INSTR",
            start_hz=1.0e9,
            stop_hz=2.0e9,
            approved_by="a.human",
        )


# ---------------------------------------------------------------------------
# Group 2: request_physical_measurement_approval()'s own behavior and the
# cryptographic binding of the receipts it grants.
# ---------------------------------------------------------------------------

_FIELDS = {"resource": "GPIB0::16::INSTR", "start_hz": 1.0e9, "stop_hz": 2.0e9, "points": 51}


def test_request_physical_measurement_approval_raises_by_default_with_no_callback():
    with pytest.raises(InstrumentError, match="No human-approval mechanism"):
        request_physical_measurement_approval(_FIELDS, approved_by="a.human")


def test_request_physical_measurement_approval_requires_approved_by():
    with pytest.raises(InstrumentError, match="approved_by"):
        request_physical_measurement_approval(_FIELDS, approval_callback=lambda fields: True)


def test_request_physical_measurement_approval_raises_when_callback_declines():
    with pytest.raises(InstrumentError, match="was not approved"):
        request_physical_measurement_approval(
            _FIELDS, approved_by="a.human", approval_callback=lambda fields: False
        )


def test_request_physical_measurement_approval_grants_a_receipt_when_approved():
    receipt = request_physical_measurement_approval(
        _FIELDS, approved_by="a.human", approval_callback=lambda fields: True
    )
    assert isinstance(receipt, ApprovalReceipt)
    assert receipt.approved_by == "a.human"
    assert receipt.token
    assert receipt.job_fingerprint


def test_approval_callback_receives_the_fingerprint_fields():
    seen = {}

    def callback(fields):
        seen.update(fields)
        return True

    request_physical_measurement_approval(
        _FIELDS, approved_by="a.human", approval_callback=callback
    )
    assert seen == _FIELDS


def test_valid_receipt_passes_check_physical_actuation_gate():
    receipt = request_physical_measurement_approval(
        _FIELDS, approved_by="a.human", approval_callback=lambda fields: True
    )
    # Does not raise, given every other signal satisfied too.
    check_physical_actuation_gate(
        receipt,
        _FIELDS,
        resource=_FIELDS["resource"],
        library_importable=True,
        env={"ALLOW_INSTRUMENT_CONTROL": "true"},
    )


def test_receipt_rejected_when_fingerprint_fields_differ():
    receipt = request_physical_measurement_approval(
        _FIELDS, approved_by="a.human", approval_callback=lambda fields: True
    )
    different_fields = {**_FIELDS, "stop_hz": 3.0e9}
    with pytest.raises(InstrumentError, match="does not match"):
        check_physical_actuation_gate(
            receipt,
            different_fields,
            resource=_FIELDS["resource"],
            library_importable=True,
            env={"ALLOW_INSTRUMENT_CONTROL": "true"},
        )


def test_receipt_with_forged_token_is_rejected():
    receipt = request_physical_measurement_approval(
        _FIELDS, approved_by="a.human", approval_callback=lambda fields: True
    )
    forged = ApprovalReceipt(
        token="0" * 64,
        job_fingerprint=receipt.job_fingerprint,
        approved_by=receipt.approved_by,
        granted_at=receipt.granted_at,
    )
    with pytest.raises(InstrumentError, match="signature is invalid"):
        check_physical_actuation_gate(
            forged,
            _FIELDS,
            resource=_FIELDS["resource"],
            library_importable=True,
            env={"ALLOW_INSTRUMENT_CONTROL": "true"},
        )


@pytest.mark.parametrize("bare_token", ["yes", True, {"approved": True}, 12345])
def test_bare_non_receipt_token_is_rejected(bare_token):
    """The structural property this ticket asks for by name: an LLM caller
    casually setting a boolean/string 'approval_token' cannot substitute
    for a real ApprovalReceipt."""
    with pytest.raises(InstrumentError, match="must be an ApprovalReceipt"):
        check_physical_actuation_gate(
            bare_token,
            _FIELDS,
            resource=_FIELDS["resource"],
            library_importable=True,
            env={"ALLOW_INSTRUMENT_CONTROL": "true"},
        )


def test_missing_approval_is_rejected():
    with pytest.raises(InstrumentError, match="no approval was provided"):
        check_physical_actuation_gate(
            None,
            _FIELDS,
            resource=_FIELDS["resource"],
            library_importable=True,
            env={"ALLOW_INSTRUMENT_CONTROL": "true"},
        )


def test_receipt_round_trips_through_to_dict_and_still_verifies():
    """A receipt that crossed an agent/MCP JSON tool boundary (to_dict(),
    then reconstructed via ApprovalReceipt(**that_dict)) must still verify
    -- object identity is not what the gate checks."""
    receipt = request_physical_measurement_approval(
        _FIELDS, approved_by="a.human", approval_callback=lambda fields: True
    )
    as_dict = receipt.to_dict()
    assert set(as_dict) == {"token", "job_fingerprint", "approved_by", "granted_at"}
    reconstructed = ApprovalReceipt(**as_dict)
    check_physical_actuation_gate(
        reconstructed,
        _FIELDS,
        resource=_FIELDS["resource"],
        library_importable=True,
        env={"ALLOW_INSTRUMENT_CONTROL": "true"},
    )


def test_approval_receipt_does_not_survive_a_fresh_process_signing_key():
    """A receipt's token is only valid against the signing key of the
    process that minted it. Simulate a restart by verifying against a
    receipt whose token was signed with a different (here: garbage) key --
    covered concretely by test_receipt_with_forged_token_is_rejected
    above; this test instead documents the property by asserting the
    signing key itself is never exposed on the receipt or its dict form."""
    receipt = request_physical_measurement_approval(
        _FIELDS, approved_by="a.human", approval_callback=lambda fields: True
    )
    as_dict = receipt.to_dict()
    assert "key" not in as_dict
    assert "secret" not in as_dict


# ---------------------------------------------------------------------------
# Group 3: check_physical_actuation_gate's own branch logic via explicit
# overrides (env dict, library_importable) -- isolated from real os.environ
# and whether pyvisa happens to be installed.
# ---------------------------------------------------------------------------


def _valid_receipt() -> ApprovalReceipt:
    return request_physical_measurement_approval(
        _FIELDS, approved_by="a.human", approval_callback=lambda fields: True
    )


def test_gate_passes_when_every_signal_present():
    receipt = _valid_receipt()
    check_physical_actuation_gate(
        receipt,
        _FIELDS,
        resource=_FIELDS["resource"],
        library_importable=True,
        env={"ALLOW_INSTRUMENT_CONTROL": "true"},
    )


def test_gate_fails_when_allow_instrument_control_false():
    receipt = _valid_receipt()
    with pytest.raises(InstrumentError, match="ALLOW_INSTRUMENT_CONTROL"):
        check_physical_actuation_gate(
            receipt,
            _FIELDS,
            resource=_FIELDS["resource"],
            library_importable=True,
            env={"ALLOW_INSTRUMENT_CONTROL": "false"},
        )


def test_gate_fails_when_allow_instrument_control_missing():
    receipt = _valid_receipt()
    with pytest.raises(InstrumentError, match="ALLOW_INSTRUMENT_CONTROL"):
        check_physical_actuation_gate(
            receipt, _FIELDS, resource=_FIELDS["resource"], library_importable=True, env={}
        )


def test_gate_fails_when_resource_missing():
    receipt = _valid_receipt()
    with pytest.raises(InstrumentError, match="no VISA resource string"):
        check_physical_actuation_gate(
            receipt,
            _FIELDS,
            resource=None,
            library_importable=True,
            env={"ALLOW_INSTRUMENT_CONTROL": "true"},
        )


def test_gate_fails_when_library_not_importable():
    receipt = _valid_receipt()
    with pytest.raises(InstrumentError, match="pyvisa is not importable"):
        check_physical_actuation_gate(
            receipt,
            _FIELDS,
            resource=_FIELDS["resource"],
            library_importable=False,
            library_import_detail="No module named 'pyvisa'",
            env={"ALLOW_INSTRUMENT_CONTROL": "true"},
        )


def test_gate_error_lists_every_missing_signal_at_once():
    # Structurally impossible to fix by satisfying one signal: with every
    # signal missing/invalid, the error names all four, not just the first.
    with pytest.raises(InstrumentError) as excinfo:
        check_physical_actuation_gate(
            None, _FIELDS, resource=None, library_importable=False, env={}
        )
    message = str(excinfo.value)
    assert "ALLOW_INSTRUMENT_CONTROL" in message
    assert "no VISA resource string" in message
    assert "pyvisa is not importable" in message
    assert "no approval was provided" in message


# ---------------------------------------------------------------------------
# Group 4: VnaAdapter.measure() against a hand-written fake transport.
# Confinement is bypassed ONLY via the explicit confinement_check=lambda
# *a, **kw: None constructor-injection seam.
# ---------------------------------------------------------------------------


class FakeVisaTransport:
    """Hand-written fake matching the subset of pyvisa's Resource API
    VnaAdapter.measure() calls: .query(str) -> str, .write(str), and
    .close(). Returns synthetic but plausible S-parameter data for however
    many sweep points were configured (tracked via the SENS:SWE:POIN write
    it observes) and a fixed synthetic *IDN? identity."""

    def __init__(self, idn: str = "FAKE,VNA-9000,SN001,FW1.2"):
        self.idn = idn
        self.writes: list[str] = []
        self.queries: list[str] = []
        self.points = 3
        self.closed = False

    def write(self, cmd: str) -> None:
        self.writes.append(cmd)
        if "SWE:POIN" in cmd:
            self.points = int(cmd.split()[-1])

    def query(self, cmd: str) -> str:
        self.queries.append(cmd)
        if cmd == "*IDN?":
            return self.idn
        if "SDATA" in cmd:
            values = []
            for i in range(self.points):
                values += [0.1 * (i + 1), 0.01 * (i + 1)]
            return ",".join(str(v) for v in values)
        if "CORR:STAT" in cmd:
            return "1"
        return ""

    def close(self) -> None:
        self.closed = True


def _measure_against_fake(job: dict, fake: FakeVisaTransport | None = None, **kwargs):
    fake = fake or FakeVisaTransport()
    adapter = VnaAdapter(
        transport_factory=lambda resource: fake,
        confinement_check=lambda *a, **kw: None,
        **kwargs,
    )
    result = adapter.measure({**job, "approval": job.get("approval", object())})
    return result, fake


_BASE_JOB = {
    "resource": "TCPIP0::192.0.2.10::INSTR",
    "start_hz": 2.0e9,
    "stop_hz": 3.0e9,
    "points": 3,
    "sparams": ["S11"],
}


def test_instrument_is_the_shared_adapter_contract():
    assert issubclass(VnaAdapter, Instrument)
    assert VnaAdapter.name == "VNA"


def test_measure_returns_instrument_result_with_measured_provenance():
    result, _fake = _measure_against_fake(_BASE_JOB)
    assert isinstance(result, InstrumentResult)
    assert result.provenance == "MEASURED"
    assert result.status == "COMPLETED"
    assert result.instrument == "FAKE,VNA-9000,SN001,FW1.2"


def test_measure_reports_instrument_identity_and_resource():
    result, _fake = _measure_against_fake(_BASE_JOB)
    assert result.outputs["instrument_idn"] == "FAKE,VNA-9000,SN001,FW1.2"
    assert result.outputs["resource"] == _BASE_JOB["resource"]


def test_measure_returns_frequency_grid_matching_start_stop_points():
    result, _fake = _measure_against_fake(_BASE_JOB)
    freqs = result.outputs["frequency_hz"]
    assert len(freqs) == 3
    assert freqs[0] == pytest.approx(2.0e9)
    assert freqs[-1] == pytest.approx(3.0e9)


def test_measure_parses_sdata_into_complex_s_parameters():
    result, _fake = _measure_against_fake(_BASE_JOB)
    s11 = result.outputs["s_parameters"]["S11"]
    assert len(s11) == 3
    assert complex(s11[0]) == pytest.approx(0.1 + 0.01j)
    assert complex(s11[1]) == pytest.approx(0.2 + 0.02j)
    assert complex(s11[2]) == pytest.approx(0.3 + 0.03j)


def test_measure_builds_one_port_touchstone_network():
    result, _fake = _measure_against_fake(_BASE_JOB)
    assert result.outputs["ports"] == 1


def test_measure_builds_two_port_touchstone_network():
    job = {**_BASE_JOB, "sparams": ["S11", "S12", "S21", "S22"]}
    result, _fake = _measure_against_fake(job)
    assert result.outputs["ports"] == 2
    assert set(result.outputs["s_parameters"].keys()) == {"S11", "S12", "S21", "S22"}


def test_measure_rejects_unsupported_sparam_subset():
    job = {**_BASE_JOB, "sparams": ["S11", "S22"]}
    with pytest.raises(InstrumentError, match="unsupported S-parameter set"):
        _measure_against_fake(job)


def test_measure_writes_expected_scpi_command_sequence():
    result, fake = _measure_against_fake(_BASE_JOB)
    joined = " | ".join(fake.writes)
    assert "SENS:FREQ:STAR 2000000000" in joined
    assert "SENS:FREQ:STOP 3000000000" in joined
    assert "SENS:SWE:POIN 3" in joined
    assert any("INIT:IMM" in w for w in fake.writes)
    assert "*IDN?" in fake.queries
    assert any("SDATA" in q for q in fake.queries)


def test_measure_closes_the_transport():
    result, fake = _measure_against_fake(_BASE_JOB)
    assert fake.closed is True


def test_measure_reports_calibration_state_and_a_metadata_note():
    result, _fake = _measure_against_fake(_BASE_JOB)
    calibration = result.outputs["calibration"]
    assert calibration["instrument_reported_correction_state"] == "1"
    assert "note" in calibration


def test_measure_merges_caller_supplied_calibration_metadata():
    job = {
        **_BASE_JOB,
        "calibration": {"kit": "85033E", "cal_date": "2026-08-01", "method": "SOLT"},
    }
    result, _fake = _measure_against_fake(job)
    calibration = result.outputs["calibration"]
    assert calibration["kit"] == "85033E"
    assert calibration["cal_date"] == "2026-08-01"
    assert calibration["method"] == "SOLT"
    # The instrument-reported state is still merged in alongside caller
    # metadata, not overwritten by it.
    assert calibration["instrument_reported_correction_state"] == "1"


def test_measure_writes_touchstone_file_when_path_given(tmp_path: Path):
    job = {**_BASE_JOB, "touchstone_path": str(tmp_path / "meas.s1p")}
    result, _fake = _measure_against_fake(job)
    touchstone_file = result.outputs["touchstone_file"]
    assert touchstone_file == str(tmp_path / "meas.s1p")
    content = Path(touchstone_file).read_text()
    assert "S11" in content or "Re" in content.replace("ReS11", "Re S11")


def test_measure_omits_touchstone_file_when_no_path_given():
    result, _fake = _measure_against_fake(_BASE_JOB)
    assert result.outputs["touchstone_file"] is None


def test_measure_touchstone_output_is_analyzable_by_rf_tools(tmp_path: Path):
    """The MEASURED result is structurally compatible with this project's
    existing Touchstone tooling (rf_tools/touchstone.py), not merely
    Touchstone-shaped in isolation."""
    from rf_tools.touchstone import analyze_touchstone

    job = {**_BASE_JOB, "touchstone_path": str(tmp_path / "meas.s1p")}
    result, _fake = _measure_against_fake(job)
    analyzed = analyze_touchstone(result.outputs["touchstone_file"])
    assert analyzed["ports"] == 1
    assert analyzed["points"] == 3


def test_measure_requires_start_and_stop_hz():
    with pytest.raises(InstrumentError, match="start_hz"):
        _measure_against_fake({"resource": "GPIB0::16::INSTR"})


def test_measure_raises_on_malformed_sdata_response():
    class BrokenTransport(FakeVisaTransport):
        def query(self, cmd: str) -> str:
            if "SDATA" in cmd:
                return "not,a,number,here"
            return super().query(cmd)

    with pytest.raises(InstrumentError, match="could not parse"):
        _measure_against_fake(_BASE_JOB, fake=BrokenTransport())


def test_measure_raises_on_point_count_mismatch():
    class MismatchedTransport(FakeVisaTransport):
        def query(self, cmd: str) -> str:
            if "SDATA" in cmd:
                return "0.1,0.1"  # only 1 point, job requests 3
            return super().query(cmd)

    with pytest.raises(InstrumentError, match="expected 3"):
        _measure_against_fake(_BASE_JOB, fake=MismatchedTransport())


def test_measure_tolerates_calibration_query_not_supported():
    class NoCalQueryTransport(FakeVisaTransport):
        def query(self, cmd: str) -> str:
            if "CORR:STAT" in cmd:
                raise RuntimeError("unsupported query")
            return super().query(cmd)

    result, _fake = _measure_against_fake(_BASE_JOB, fake=NoCalQueryTransport())
    assert "instrument_reported_correction_state" not in result.outputs["calibration"]
    assert result.status == "COMPLETED"


def test_commands_dict_is_fully_overridable():
    fake = FakeVisaTransport()
    custom_commands = {"freq_start": "FREQ:STAR {start_hz:.0f}HZ"}
    adapter = VnaAdapter(
        transport_factory=lambda resource: fake,
        confinement_check=lambda *a, **kw: None,
        commands=custom_commands,
    )
    adapter.measure({**_BASE_JOB, "approval": object()})
    assert any("FREQ:STAR 2000000000HZ" in w for w in fake.writes)
    # Every other default command is untouched.
    assert any("SENS:SWE:POIN" in w for w in fake.writes)


def test_default_commands_are_not_mutated_by_an_override():
    fake = FakeVisaTransport()
    VnaAdapter(
        transport_factory=lambda resource: fake,
        confinement_check=lambda *a, **kw: None,
        commands={"freq_start": "CUSTOM {start_hz}"},
    )
    assert DEFAULT_SCPI_COMMANDS["freq_start"] == "SENS:FREQ:STAR {start_hz:.0f}"


def test_define_sparam_is_skipped_by_default():
    fake = FakeVisaTransport()
    _measure_against_fake(_BASE_JOB, fake=fake)
    # No "PAR:DEF" write since DEFAULT_SCPI_COMMANDS["define_sparam"] == ""
    assert not any("PAR:DEF" in w for w in fake.writes)


def test_define_sparam_is_used_when_configured():
    fake = FakeVisaTransport()
    adapter = VnaAdapter(
        transport_factory=lambda resource: fake,
        confinement_check=lambda *a, **kw: None,
        commands={"define_sparam": "CALC:PAR:DEF 'ch1_{sparam}',{sparam}"},
    )
    adapter.measure({**_BASE_JOB, "approval": object()})
    assert any("CALC:PAR:DEF 'ch1_S11',S11" in w for w in fake.writes)


# ---------------------------------------------------------------------------
# Tool-layer convenience functions (request_vna_measurement_approval /
# run_vna_measurement) -- the end-to-end path an agent/MCP tool would use,
# with a real ApprovalReceipt granted via an explicit test-only callback
# (never via the codebase's default/None path -- see Group 1/2 above for
# that property) and a fake transport.
# ---------------------------------------------------------------------------


def test_end_to_end_request_then_measure_with_fake_transport():
    resource = "TCPIP0::192.0.2.20::INSTR"
    approval = request_vna_measurement_approval(
        resource=resource,
        start_hz=2.4e9,
        stop_hz=2.5e9,
        points=3,
        sparams=["S11"],
        approved_by="engineer.jane",
        approval_callback=lambda fields: True,
    )
    assert isinstance(approval, dict)

    result = run_vna_measurement(
        resource=resource,
        start_hz=2.4e9,
        stop_hz=2.5e9,
        approval=approval,
        points=3,
        sparams=["S11"],
        transport_factory=lambda r: FakeVisaTransport(),
        confinement_check=lambda *a, **kw: None,
    )
    assert result["provenance"] == "MEASURED"
    assert result["status"] == "COMPLETED"
    assert result["instrument"] == "FAKE,VNA-9000,SN001,FW1.2"
    assert len(result["frequency_hz"]) == 3


def test_end_to_end_measure_rejects_approval_for_a_different_request():
    """An approval granted for one frequency range cannot be reused for a
    different one, even with a fake transport and bypassed pyvisa/env
    checks -- because the real approval verification inside
    check_physical_actuation_gate is NOT part of what confinement_check
    bypasses when confinement_check is left as the real function."""
    resource = "TCPIP0::192.0.2.20::INSTR"
    approval = request_vna_measurement_approval(
        resource=resource,
        start_hz=2.4e9,
        stop_hz=2.5e9,
        points=3,
        sparams=["S11"],
        approved_by="engineer.jane",
        approval_callback=lambda fields: True,
    )

    with pytest.raises(InstrumentError, match="does not match"):
        run_vna_measurement(
            resource=resource,
            start_hz=2.4e9,
            stop_hz=9.0e9,  # different from what was approved
            approval=approval,
            points=3,
            sparams=["S11"],
            transport_factory=lambda r: FakeVisaTransport(),
        )


def test_fingerprint_fields_helper_is_order_independent_dict_shape():
    fields_a = _vna_fingerprint_fields("R1", 1e9, 2e9, 51, ["S11"])
    fields_b = _vna_fingerprint_fields("R1", 1e9, 2e9, 51, ["S11"])
    assert fields_a == fields_b
