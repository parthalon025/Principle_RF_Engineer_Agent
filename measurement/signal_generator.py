"""Signal generator adapter over SCPI/VISA (issue #44, Phase 10 ticket 2
of 2 -- extending #43's VNA adapter and measurement/spectrum_analyzer.py's
spectrum analyzer adapter to the rest of the standard test-bench instrument
set per docs/BUILD_PLAN.md's Phase 10).

THIS IS THE ONE ADAPTER IN THIS TICKET THAT WRITES TO THE PHYSICAL WORLD,
NOT JUST READS FROM IT. A VNA's own stimulus (measurement/vna.py) and a
spectrum analyzer's/power meter's passive observation
(measurement/spectrum_analyzer.py, measurement/power_meter.py) are all
either low, calibrated, and expected, or purely receive-only. A signal
generator actively commands RF power onto whatever is connected to its
output port at a caller-specified frequency and level -- arguably a MORE
consequential physical actuation than a VNA's own stimulus, since a caller
could in principle request significant output power at an arbitrary
frequency. SignalGeneratorAdapter.measure()'s approval-gate usage is
therefore held to be AT LEAST as strict as VnaAdapter's, and in one respect
more pointedly so: `_siggen_fingerprint_fields` below deliberately puts
`frequency_hz`, `power_dbm`, AND `output_on` all into the fingerprinted
request (not just `frequency_hz`), so an approval granted for "10 dBm at
2.4 GHz, output on" cryptographically cannot be replayed to instead command
"30 dBm at 900 MHz" or to flip `output_on` from what was approved -- see
tests/test_signal_generator.py's
test_end_to_end_measure_rejects_approval_for_a_different_power_level and
...for_a_different_frequency for the direct proof this ticket's design
guidance calls for.

CRITICAL, NON-NEGOTIABLE PROJECT CONSTRAINT (unchanged from #43): physical
lab instruments are never controlled autonomously (README.md, docs/
BUILD_PLAN.md Phase 10, docs/SECURITY.md). SignalGeneratorAdapter.measure()
calls measurement.base.check_physical_actuation_gate() as the FIRST thing
it does, before any SCPI/VISA traffic -- exactly as VnaAdapter.measure()
does. This module reuses measurement/base.py's gate COMPLETELY UNMODIFIED.
Per this ticket's design guidance: check_physical_actuation_gate is keyed
generically on whatever `fingerprint_fields` dict the calling adapter
supplies (see measurement/base.py's module docstring, "fingerprint_fields
is the small, explicit, adapter-defined subset of parameters that DOES
determine what the instrument will be told to do") and on the caller-
supplied resource/library-importability signals -- none of which is VNA-
specific. It already extends correctly to a signal generator's
frequency_hz/power_dbm/output_on parameters with zero changes to
measurement/base.py; this module confirms that concretely rather than
assuming it (see the fingerprinting tests referenced above). No change to
measurement/base.py was needed or made.

SOURCES CONSULTED (accessed 2026-09-02):
  - `:FREQUENCY <value> Hz` (set output frequency), `:POWER <value> dBm`
    (set output power level), and `:OUTPUT ON`/`:OUTPUT OFF` (RF output
    enable/disable): PyMeasure's Anritsu MG3692C signal-generator driver,
    `pymeasure/instruments/anritsu/anritsuMG3692C.py`, fetched directly
    from the PyMeasure GitHub `master` branch -- a real, maintained driver
    exercised against a real Anritsu signal generator, not a guess. That
    driver colon-prefixes each command (`:FREQUENCY`, `:POWER`, `:OUTPUT`)
    and always includes an explicit `Hz`/`dBm` unit suffix on the set
    commands; this module's defaults below use the unprefixed, unit-
    suffix-free form (`FREQ <value>`, `POW <value>`) to match this
    ticket's own suggested command set and this project's existing VNA/
    spectrum-analyzer adapters' convention of raw-Hz-without-suffix
    numeric arguments -- both are real, valid SCPI forms; which one a given
    instrument accepts is genuinely vendor/model-specific (see the
    vendor-variability caveat below).
  - `OUTP:STAT ON` / `OUTP:STAT OFF` as the RF-output-enable command's
    long-form, colon-qualified spelling (as opposed to the MG3692C
    driver's bare `:OUTPUT ON`/`:OUTPUT OFF`): this ticket's own design
    guidance (the issue body's suggested command set), matching the
    `SUBSYSTEM:STATe` naming convention Keysight signal generators
    (e.g. the N51xxB/E8257D families) document for RF output enable.
  - `*IDN?` as the IEEE-488.2 standard identification query, common to
    every SCPI instrument by definition (not vendor-specific) -- same
    citation measurement/vna.py and measurement/spectrum_analyzer.py make.

HONEST, EXPLICIT VENDOR-VARIABILITY CAVEAT (same discipline as this
project's other adapters): whether a given signal generator accepts a bare
numeric frequency/power argument (implicitly in Hz/dBm) or requires an
explicit unit suffix (`Hz`, `GHz`, `dBm`), and the exact readback query
spelling (`FREQ?` vs `:FREQUENCY?`, `OUTP:STAT?` vs `:OUTPUT?`), are
genuinely vendor-and-model variable and were NOT independently re-verified
against every vendor's manual here. `SignalGeneratorAdapter.commands` is
therefore a plain, fully-overridable dict (see DEFAULT_SCPI_COMMANDS and
SignalGeneratorAdapter.__init__), exactly like VnaAdapter.commands and
SpectrumAnalyzerAdapter.commands -- a real deployment tunes it to its
actual instrument rather than this module guessing wrong.

No real signal generator and no pyvisa install exist in this environment
(`import pyvisa` genuinely fails here -- see
tests/test_signal_generator.py). Treat any result from a real instrument as
unverified end-to-end until this has actually been run against real
signal-generator hardware at least once -- and, given the safety stakes
described above, only ever with a real, wired-up human-approval workflow in
front of it (which, per measurement/base.py's module docstring, does not
yet exist anywhere in this codebase).
"""

import importlib
import os
import time
from collections.abc import Callable
from typing import Any

from .base import (
    Instrument,
    InstrumentError,
    InstrumentResult,
    check_physical_actuation_gate,
)

# ---------------------------------------------------------------------------
# Overridable SCPI command templates -- see module docstring's vendor-
# variability caveat. Every value is a Python format-string; measure()
# fills in {frequency_hz}/{power_dbm} as applicable. Pass a `commands`
# dict to SignalGeneratorAdapter(...) to override any subset; unspecified
# keys keep their default here.
# ---------------------------------------------------------------------------

DEFAULT_SCPI_COMMANDS: dict[str, str] = {
    "idn": "*IDN?",
    "freq_set": "FREQ {frequency_hz:.0f}",
    "freq_query": "FREQ?",
    "power_set": "POW {power_dbm}",
    "power_query": "POW?",
    "output_on": "OUTP:STAT ON",
    "output_off": "OUTP:STAT OFF",
    "output_query": "OUTP:STAT?",
}


def _siggen_fingerprint_fields(
    resource: str | None, frequency_hz: float, power_dbm: float, output_on: bool
) -> dict[str, Any]:
    """The subset of a signal-generator actuation request that determines
    what will physically happen on the instrument -- what
    measurement.base.request_physical_measurement_approval() and
    check_physical_actuation_gate() fingerprint an approval against. Both
    request_signal_generator_output_approval (the approval-request tool)
    and SignalGeneratorAdapter.measure() (the actual actuation) compute
    this SAME dict from the SAME inputs, mirroring measurement/vna.py's
    _vna_fingerprint_fields -- see this module's docstring for why
    `power_dbm` and `output_on`, not just `frequency_hz`, are deliberately
    part of the fingerprint: an approval for one power level/on-off state
    must not be reusable for a different one."""
    return {
        "resource": resource,
        "frequency_hz": frequency_hz,
        "power_dbm": power_dbm,
        "output_on": bool(output_on),
    }


def _real_pyvisa_importable() -> tuple[bool, str]:
    """Actually attempt `import pyvisa`. Returns (importable, detail)
    rather than raising, so check_physical_actuation_gate can report it
    alongside every other missing signal in one message -- same pattern as
    measurement/vna.py's _real_pyvisa_importable."""
    try:
        importlib.import_module("pyvisa")
    except ImportError as exc:
        return False, str(exc)
    return True, ""


def _import_pyvisa_module() -> Any:
    """Guarded import of pyvisa itself -- deferred to inside this function
    precisely because pyvisa genuinely will not be installed in most
    environments, including this one (see module docstring). Only ever
    reached from SignalGeneratorAdapter._real_transport_factory, itself
    only reached after check_physical_actuation_gate has already passed."""
    try:
        import pyvisa
    except ImportError as exc:
        raise InstrumentError(
            "pyvisa is not installed. Install the optional 'measurement' "
            "dependency group, e.g. `uv sync --extra measurement` or "
            "`pip install '.[measurement]'`."
        ) from exc
    return pyvisa


def _parse_readback_float(raw: str, what: str) -> float | None:
    """Best-effort parse of a numeric readback query response (e.g.
    FREQ?/POW?) into a float. Returns None (never raises) on anything
    unparseable -- readback is confirmatory metadata, never load-bearing
    for whether the actuation itself succeeded, exactly like
    measurement/vna.py's calibration-state readback discipline."""
    try:
        return float(raw.strip())
    except (ValueError, AttributeError):
        return None


class SignalGeneratorAdapter(Instrument):
    """SCPI/VISA-driven signal generator adapter. See this module's
    docstring for the SCPI command citations, vendor-variability caveat,
    and -- most importantly -- why this adapter's approval-gate usage is
    held to be at least as strict as VnaAdapter's, given that a signal
    generator actively outputs RF power rather than merely observing or
    stimulating with a low, calibrated, expected signal. Structurally
    identical to measurement/vna.py's VnaAdapter -- same constructor-
    injection seams, same gate-first measure() discipline."""

    name = "SignalGenerator"

    def __init__(
        self,
        transport_factory: Callable[[str], Any] | None = None,
        commands: dict[str, str] | None = None,
        confinement_check: Callable[..., None] | None = None,
    ):
        """See measurement/vna.py's VnaAdapter.__init__ docstring --
        `transport_factory` and `confinement_check` are test-only
        constructor-injection seams; a real call never passes them, so it
        always goes through the real approval/pyvisa gate and a real
        pyvisa resource. `commands` overrides any subset of
        DEFAULT_SCPI_COMMANDS."""
        self._transport_factory = transport_factory
        self.commands = {**DEFAULT_SCPI_COMMANDS, **(commands or {})}
        self._confinement_check = confinement_check or check_physical_actuation_gate

    def _real_transport_factory(self, resource: str) -> Any:
        pyvisa = _import_pyvisa_module()
        resource_manager = pyvisa.ResourceManager()
        return resource_manager.open_resource(resource)

    def measure(self, job: dict[str, Any]) -> InstrumentResult:
        # Pure data extraction from `job` -- no SCPI/VISA I/O of any kind
        # happens in this block, so doing it before the gate check below
        # is safe; it is needed to compute fingerprint_fields, which the
        # gate must verify the approval against.
        resource = job.get("resource") or os.getenv("SIGNAL_GENERATOR_VISA_RESOURCE")
        frequency_hz = job.get("frequency_hz")
        power_dbm = job.get("power_dbm")
        if frequency_hz is None or power_dbm is None:
            raise InstrumentError("job['frequency_hz'] and job['power_dbm'] are required")
        output_on = bool(job.get("output_on", True))
        fingerprint_fields = _siggen_fingerprint_fields(
            resource, frequency_hz, power_dbm, output_on
        )

        importable, detail = _real_pyvisa_importable()

        # The approval/actuation gate -- checked BEFORE any SCPI/VISA
        # traffic, mirroring VnaAdapter.measure()'s call to the same
        # measurement.base.check_physical_actuation_gate, unmodified. For
        # this adapter in particular this is the single most important
        # line in the file: nothing below it may run unless a valid,
        # request-bound approval receipt for THIS EXACT frequency/power/
        # output-on combination was already granted.
        self._confinement_check(
            job.get("approval"),
            fingerprint_fields,
            resource=resource,
            library_importable=importable,
            library_import_detail=detail,
            library_name="pyvisa",
        )

        transport_factory = self._transport_factory or self._real_transport_factory
        transport = transport_factory(resource)
        try:
            idn = transport.query(self.commands["idn"]).strip()

            transport.write(self.commands["freq_set"].format(frequency_hz=frequency_hz))
            transport.write(self.commands["power_set"].format(power_dbm=power_dbm))
            transport.write(
                self.commands["output_on"] if output_on else self.commands["output_off"]
            )

            frequency_hz_readback: float | None = None
            freq_query = self.commands.get("freq_query", "")
            if freq_query:
                try:
                    frequency_hz_readback = _parse_readback_float(
                        transport.query(freq_query), "frequency"
                    )
                except Exception:
                    # Readback support genuinely varies by vendor/model
                    # (see module docstring) -- best-effort only, never
                    # fatal to the actuation itself (which has already
                    # happened by this point).
                    frequency_hz_readback = None

            power_dbm_readback: float | None = None
            power_query = self.commands.get("power_query", "")
            if power_query:
                try:
                    power_dbm_readback = _parse_readback_float(
                        transport.query(power_query), "power"
                    )
                except Exception:
                    power_dbm_readback = None

            output_state_readback: str | None = None
            output_query = self.commands.get("output_query", "")
            if output_query:
                try:
                    output_state_readback = transport.query(output_query).strip()
                except Exception:
                    output_state_readback = None
        finally:
            close = getattr(transport, "close", None)
            if callable(close):
                close()

        return InstrumentResult(
            instrument=idn or self.name,
            status="COMPLETED",
            outputs={
                "instrument_idn": idn,
                "resource": resource,
                "frequency_hz": float(frequency_hz),
                "power_dbm": float(power_dbm),
                "output_on": output_on,
                "frequency_hz_readback": frequency_hz_readback,
                "power_dbm_readback": power_dbm_readback,
                "output_state_readback": output_state_readback,
                "measured_at": time.time(),
            },
        )


def request_signal_generator_output_approval(
    resource: str | None,
    frequency_hz: float,
    power_dbm: float,
    output_on: bool = True,
    approved_by: str | None = None,
    approval_callback: Callable[[dict[str, Any]], bool] | None = None,
) -> dict[str, Any]:
    """The signal-generator-adapter-facing wrapper around
    measurement.base.request_physical_measurement_approval() -- the
    distinct, separate, auditable step that MUST happen before
    run_signal_generator_output()/SignalGeneratorAdapter.measure() will
    proceed. Does nothing dangerous itself (see measurement/base.py's
    module docstring) -- no SCPI, no VISA, no RF output of any kind.
    Returns the resulting ApprovalReceipt as a plain JSON-serializable
    dict (ApprovalReceipt.to_dict()) so it can cross an agent/MCP tool
    boundary and be handed straight to run_signal_generator_output's
    `approval` parameter, for THIS EXACT resource/frequency_hz/power_dbm/
    output_on combination -- see this module's docstring for why
    `power_dbm` and `output_on` are deliberately part of what gets
    fingerprinted, not just `frequency_hz`.

    `approval_callback` defaults to None, meaning this ALWAYS raises
    InstrumentError -- there is no human-facing approval workflow wired up
    in this codebase yet (see measurement/base.py). The agent/MCP tool
    wrapping this function never supplies one either, since a Python
    callable cannot cross that JSON boundary -- so a real agent invocation
    of that tool always raises too, by design. Mirrors measurement/vna.py's
    request_vna_measurement_approval exactly, extended with the extra
    power_dbm/output_on fingerprint fields this instrument type requires.
    """
    from .base import request_physical_measurement_approval

    fields = _siggen_fingerprint_fields(resource, frequency_hz, power_dbm, output_on)
    receipt = request_physical_measurement_approval(
        fields, approved_by=approved_by, approval_callback=approval_callback
    )
    return receipt.to_dict()


def run_signal_generator_output(
    resource: str | None,
    frequency_hz: float,
    power_dbm: float,
    approval: dict[str, Any] | Any,
    output_on: bool = True,
    transport_factory: Callable[[str], Any] | None = None,
    confinement_check: Callable[..., None] | None = None,
) -> dict[str, Any]:
    """Set a real signal generator's output frequency/power/on-off state
    via SignalGeneratorAdapter, and return a MEASURED-provenance result
    structured the same way measurement/vna.py's run_vna_measurement
    returns its VNA result -- confirmation of the actuated state, plus
    best-effort instrument readback, not a "measurement" in the sensing
    sense (see this module's docstring on why this is the one adapter in
    this ticket that WRITES to the physical world).

    `approval` MUST be a genuine measurement.base.ApprovalReceipt (or a
    dict with the same fields) obtained from a prior, separate call to
    request_signal_generator_output_approval() for THIS EXACT resource/
    frequency_hz/power_dbm/output_on combination -- an approval granted
    for one power level or on/off state is cryptographically rejected if
    applied to a different one (see
    tests/test_signal_generator.py's fingerprint-specificity tests).
    `transport_factory`/`confinement_check` are the same test-only
    injection seams documented on VnaAdapter.__init__ -- omit both for a
    real call.
    """
    from .base import ApprovalReceipt

    if isinstance(approval, dict):
        approval = ApprovalReceipt(**approval)

    adapter = SignalGeneratorAdapter(
        transport_factory=transport_factory, confinement_check=confinement_check
    )
    job = {
        "resource": resource,
        "frequency_hz": frequency_hz,
        "power_dbm": power_dbm,
        "output_on": output_on,
        "approval": approval,
    }
    result = adapter.measure(job)
    return {
        "provenance": "MEASURED",
        "instrument": result.instrument,
        "status": result.status,
        **result.outputs,
    }
