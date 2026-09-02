"""RF power meter adapter over SCPI/VISA (issue #44, Phase 10 ticket 2 of
2 -- extending #43's VNA adapter and this ticket's spectrum analyzer/
signal generator adapters to the rest of the standard test-bench
instrument set per docs/BUILD_PLAN.md's Phase 10).

Pulls a single scalar power reading (with units, frequency, and any
correction-factor metadata) from a real RF power meter into this system,
tagged MEASURED provenance -- like measurement/spectrum_analyzer.py's
spectrum analyzer adapter, this is read-only: a power meter only observes
whatever RF energy is already present at its sensor input, it never
transmits anything.

CRITICAL, NON-NEGOTIABLE PROJECT CONSTRAINT (unchanged from #43): physical
lab instruments are never controlled autonomously (README.md, docs/
BUILD_PLAN.md Phase 10, docs/SECURITY.md). PowerMeterAdapter.measure()
calls measurement.base.check_physical_actuation_gate() as the FIRST thing
it does, before any SCPI/VISA traffic -- exactly as VnaAdapter.measure()
does. This module reuses measurement/base.py's gate UNMODIFIED, supplying
only the two adapter-specific gate inputs the gate itself does not know
how to determine (the VISA resource string, and whether pyvisa is actually
importable on this host), following measurement/vna.py's exact structural
pattern.

SOURCES CONSULTED (accessed 2026-09-02):
  - `INITiate[1]|2|3|4[:IMMediate]` (trigger a measurement),
    `FETCh[1]|2|3|4[:SCALar][:POWer:AC]?` (fetch the last-triggered
    reading), `MEASure[1]|2|3|4[:SCALar][:POWer:AC]?` (a compound
    ABORt+CONFigure+READ? convenience query), `[SENSe[1]]|SENSe2:
    FREQuency[:CW|:FIXed] <numeric_value>` (set the measurement frequency,
    used by the meter to look up its stored calibration-factor table), and
    `[SENSe[1]]|SENSe2:CORRection:CFACtor|GAIN[1][:INPut][:MAGNitude]
    <numeric_value>` (a directly-settable calibration/gain correction
    factor): Keysight's N1913A/N1914A EPM Series Power Meters Programming
    Guide (part number 9018-02514), a real vendor SCPI command reference
    for a real, currently-sold RF power meter family, fetched directly
    (accessed via a Transcat-hosted mirror of the Keysight PDF, since
    Keysight's own site gates the download behind an interactive form).
    That guide documents these as per-channel-scoped commands (`[1]|2|3|4`
    suffixes for the meter's measurement channels/sequences); this module
    uses the unscoped, single-channel form (channel 1 implied by default,
    same SCPI convention measurement/vna.py's and measurement/
    spectrum_analyzer.py's unscoped commands already rely on) and favors
    the lower-level `INIT`+`FETC?` pair over the compound `MEAS?` query
    (the guide's own "Making Measurement" section documents `MEAS?` as
    equivalent to `ABORt`+`CONFigure`+`READ?`; `INIT`+`FETC?` gives this
    adapter an explicit trigger step to gate behind the same approval
    check as every other adapter in this project, rather than folding
    triggering into one opaque compound query).
  - `*IDN?` as the IEEE-488.2 standard identification query, common to
    every SCPI instrument by definition (not vendor-specific) -- same
    citation this project's other adapters make.

HONEST, EXPLICIT VENDOR-VARIABILITY CAVEAT (same discipline as this
project's other adapters): exact SCPI syntax for frequency-argument units
(a bare numeric Hz value vs. a suffixed literal like `500KHZ`, both of
which the cited EPM programming guide's own examples use in different
places) and for which correction-factor command family (`CFACtor` vs.
`GAIN` vs. a calibration-factor-table `CSET` selection) a given power
sensor expects are genuinely vendor-and-model variable and were NOT
independently re-verified against every vendor's manual here.
`PowerMeterAdapter.commands` is therefore a plain, fully-overridable dict
(see DEFAULT_SCPI_COMMANDS and PowerMeterAdapter.__init__), exactly like
this project's other adapters -- a real deployment tunes it to its actual
instrument rather than this module guessing wrong.

No real power meter and no pyvisa install exist in this environment
(`import pyvisa` genuinely fails here -- see tests/test_power_meter.py).
Treat any result from a real instrument as unverified end-to-end until
this has actually been run against real power-meter hardware at least
once.
"""

import os
import time
from collections.abc import Callable
from typing import Any

from .base import (
    Instrument,
    InstrumentError,
    InstrumentResult,
    _import_pyvisa_module,
    _real_pyvisa_importable,
    check_physical_actuation_gate,
)

# ---------------------------------------------------------------------------
# Overridable SCPI command templates -- see module docstring's vendor-
# variability caveat. Every value is a Python format-string; measure()
# fills in {frequency_hz} as applicable. Pass a `commands` dict to
# PowerMeterAdapter(...) to override any subset; unspecified keys keep
# their default here.
# ---------------------------------------------------------------------------

DEFAULT_SCPI_COMMANDS: dict[str, str] = {
    "idn": "*IDN?",
    "freq_set": "SENS:FREQ {frequency_hz:.0f}",
    "trigger": "INIT:IMM;*WAI",
    "fetch_query": "FETC?",
    # Best-effort only (see module docstring) -- set to "" to skip
    # entirely on instruments that don't support any calibration-factor
    # query.
    "cal_factor_query": "SENS:CORR:CFAC?",
}


def _power_meter_fingerprint_fields(
    resource: str | None, frequency_hz: float
) -> dict[str, Any]:
    """The subset of a power-meter measurement request that determines
    what will physically happen on the instrument -- what
    measurement.base.request_physical_measurement_approval() and
    check_physical_actuation_gate() fingerprint an approval against. Both
    request_power_meter_measurement_approval (the approval-request tool)
    and PowerMeterAdapter.measure() (the actual measurement) compute this
    SAME dict from the SAME inputs, mirroring measurement/vna.py's
    _vna_fingerprint_fields."""
    return {"resource": resource, "frequency_hz": frequency_hz}


def _parse_power_reading(raw: str) -> float:
    """Parse a SCPI FETCh?/MEASure?-style power reading response: a single
    ASCII floating-point number (the standard shape returned by these
    queries -- see module docstring citation)."""
    text = raw.strip()
    if not text:
        raise InstrumentError("power meter returned an empty reading response")
    try:
        return float(text.split(",")[0])
    except ValueError as exc:
        raise InstrumentError(
            f"could not parse power meter reading response as a number: {raw!r}"
        ) from exc


class PowerMeterAdapter(Instrument):
    """SCPI/VISA-driven RF power meter adapter. See this module's
    docstring for the SCPI command citations/vendor-variability caveat,
    and measurement/base.py for the physical-actuation approval gate
    measure() cannot bypass or short-circuit. Structurally identical to
    measurement/vna.py's VnaAdapter -- same constructor-injection seams,
    same gate-first measure() discipline -- adapted to a scalar power
    reading instead of an S-parameter sweep."""

    name = "PowerMeter"

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
        resource = job.get("resource") or os.getenv("POWER_METER_VISA_RESOURCE")
        frequency_hz = job.get("frequency_hz")
        if frequency_hz is None:
            raise InstrumentError("job['frequency_hz'] is required")
        fingerprint_fields = _power_meter_fingerprint_fields(resource, frequency_hz)

        importable, detail = _real_pyvisa_importable()

        # The approval/actuation gate -- checked BEFORE any SCPI/VISA
        # traffic, mirroring VnaAdapter.measure()'s call to the same
        # measurement.base.check_physical_actuation_gate, unmodified.
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
            transport.write(self.commands["trigger"])
            raw = transport.query(self.commands["fetch_query"])
            power_dbm = _parse_power_reading(raw)

            cal_factor: float | None = None
            cal_query = self.commands.get("cal_factor_query", "")
            if cal_query:
                try:
                    cal_factor = float(transport.query(cal_query).strip())
                except Exception:
                    # Calibration-factor query support genuinely varies by
                    # vendor/model (see module docstring) -- best-effort
                    # only, never fatal to the measurement itself.
                    cal_factor = None
        finally:
            close = getattr(transport, "close", None)
            if callable(close):
                close()

        calibration: dict[str, Any] = dict(job.get("calibration") or {})
        if cal_factor is not None:
            calibration.setdefault("instrument_reported_correction_factor", cal_factor)
        calibration.setdefault(
            "note",
            "Which correction-factor command family (CFACtor/GAIN/a "
            "calibration-factor-table CSET selection) applies is genuinely "
            "vendor/model-variable (see this module's docstring) -- supply "
            "job['calibration'] with sensor cal-factor-table/date metadata "
            "from the operator's calibration record when available.",
        )

        return InstrumentResult(
            instrument=idn or self.name,
            status="COMPLETED",
            outputs={
                "instrument_idn": idn,
                "resource": resource,
                "frequency_hz": float(frequency_hz),
                "power_dbm": power_dbm,
                "units": "dBm",
                "calibration": calibration,
                "measured_at": time.time(),
            },
        )


def request_power_meter_measurement_approval(
    resource: str | None,
    frequency_hz: float,
    approved_by: str | None = None,
    approval_callback: Callable[[dict[str, Any]], bool] | None = None,
) -> dict[str, Any]:
    """The power-meter-adapter-facing wrapper around
    measurement.base.request_physical_measurement_approval() -- the
    distinct, separate, auditable step that MUST happen before
    run_power_meter_measurement()/PowerMeterAdapter.measure() will
    proceed. Does nothing dangerous itself (see measurement/base.py's
    module docstring). Returns the resulting ApprovalReceipt as a plain
    JSON-serializable dict (ApprovalReceipt.to_dict()) so it can cross an
    agent/MCP tool boundary and be handed straight to
    run_power_meter_measurement's `approval` parameter, for THIS EXACT
    resource/frequency_hz combination.

    `approval_callback` defaults to None, meaning this ALWAYS raises
    InstrumentError -- there is no human-facing approval workflow wired up
    in this codebase yet (see measurement/base.py). The agent/MCP tool
    wrapping this function never supplies one either, since a Python
    callable cannot cross that JSON boundary -- so a real agent invocation
    of that tool always raises too, by design. Mirrors measurement/vna.py's
    request_vna_measurement_approval exactly.
    """
    from .base import request_physical_measurement_approval

    fields = _power_meter_fingerprint_fields(resource, frequency_hz)
    receipt = request_physical_measurement_approval(
        fields, approved_by=approved_by, approval_callback=approval_callback
    )
    return receipt.to_dict()


def run_power_meter_measurement(
    resource: str | None,
    frequency_hz: float,
    approval: dict[str, Any] | Any,
    calibration: dict[str, Any] | None = None,
    transport_factory: Callable[[str], Any] | None = None,
    confinement_check: Callable[..., None] | None = None,
) -> dict[str, Any]:
    """Perform one RF power-meter reading via PowerMeterAdapter, and return
    a MEASURED-provenance result structured the same way measurement/
    vna.py's run_vna_measurement returns its VNA result.

    `approval` MUST be a genuine measurement.base.ApprovalReceipt (or a
    dict with the same fields) obtained from a prior, separate call to
    request_power_meter_measurement_approval() for THIS EXACT resource/
    frequency_hz combination -- see measurement/base.py's module docstring
    for why this cannot be a bare boolean/string. `transport_factory`/
    `confinement_check` are the same test-only injection seams documented
    on VnaAdapter.__init__ -- omit both for a real call.
    """
    from .base import ApprovalReceipt

    if isinstance(approval, dict):
        approval = ApprovalReceipt(**approval)

    adapter = PowerMeterAdapter(
        transport_factory=transport_factory, confinement_check=confinement_check
    )
    job = {
        "resource": resource,
        "frequency_hz": frequency_hz,
        "calibration": calibration,
        "approval": approval,
    }
    result = adapter.measure(job)
    return {
        "provenance": "MEASURED",
        "instrument": result.instrument,
        "status": result.status,
        **result.outputs,
    }
