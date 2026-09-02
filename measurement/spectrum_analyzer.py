"""Spectrum analyzer adapter over SCPI/VISA (issue #44, Phase 10 ticket 2
of 2 -- "Add SCPI/VISA adapters for a spectrum analyzer, signal generator,
and power meter", extending #43's VNA adapter to the rest of the standard
test-bench instrument set per docs/BUILD_PLAN.md's Phase 10).

Pulls a measured amplitude-vs-frequency trace from a real spectrum analyzer
into this system, tagged MEASURED provenance, with instrument identity and
calibration metadata attached -- the read-only counterpart to
measurement/vna.py's VNA adapter (a spectrum analyzer, like a power meter,
only observes whatever RF energy is already present at its input; it does
not transmit anything).

CRITICAL, NON-NEGOTIABLE PROJECT CONSTRAINT (unchanged from #43): physical
lab instruments are never controlled autonomously (README.md, docs/
BUILD_PLAN.md Phase 10, docs/SECURITY.md). SpectrumAnalyzerAdapter.measure()
calls measurement.base.check_physical_actuation_gate() as the FIRST thing
it does, before any SCPI/VISA traffic -- exactly as VnaAdapter.measure()
does. This module reuses measurement/base.py's gate UNMODIFIED: it only
supplies the two adapter-specific gate inputs the gate itself does not know
how to determine (the VISA resource string, and whether pyvisa is actually
importable on this host), following measurement/vna.py's exact structural
pattern (guarded pyvisa import, overridable `commands` dict,
confinement_check test-only injection seam). See measurement/base.py's
module docstring for why the gate already generalizes to a new instrument
type without modification: it is keyed on the request/instrument via an
adapter-supplied `fingerprint_fields` dict and a caller-supplied VISA
resource/library-importability signal, neither of which is VNA-specific.

SOURCES CONSULTED (accessed 2026-09-02):
  - `FREQ:CENT` / `FREQ:SPAN` (center frequency / span), `BAND:RES`
    (resolution bandwidth), `INIT; *WAI` (trigger a sweep and wait for
    completion), and `TRAC{n}? TRACE{n}` (read back trace data): PyMeasure's
    Rohde & Schwarz FSL/FSW spectrum-analyzer driver,
    `pymeasure/instruments/rohdeschwarz/fsseries.py`, fetched directly from
    the PyMeasure GitHub `master` branch -- a real, maintained driver
    exercised against real R&S spectrum analyzers, not a guess. That driver
    also documents `FREQ:STAR`/`FREQ:STOP` (start/stop frequency, an
    alternate way to specify the same span) and `SWE:TIME` (sweep time,
    not modeled here -- out of scope for this ticket's trace-pull use
    case). This module's default trace-query command,
    `TRAC:DATA? TRACE1`, is a deliberate, honestly-flagged variant of that
    driver's `TRAC1? TRACE1` form (see the vendor-variability caveat
    below) chosen to mirror this project's own VNA adapter's
    `CALC:DATA? SDATA`-style "colon-qualified `:DATA?`" query convention;
    override `commands["trace_query"]` for an instrument that expects the
    unqualified `TRACn?` form instead.
  - `INIT:IMM` as an unscoped, single-channel immediate-trigger form (SCPI
    treats an omitted `<cnum>` as channel 1 by default) and `TRAC:DATA?`
    as a trace-data query verb: this ticket's own design guidance
    (docs/agents -- the issue body), matching the same unscoped-single-
    channel convention measurement/vna.py already established for the VNA
    adapter's own `INIT:IMM;*WAI` trigger command.
  - `*IDN?` as the IEEE-488.2 standard identification query, common to
    every SCPI instrument by definition (not vendor-specific, not
    independently re-verified against one manual here) -- same citation
    measurement/vna.py makes.

HONEST, EXPLICIT VENDOR-VARIABILITY CAVEAT (same discipline as
measurement/vna.py's and simulation/hfss.py's caveats): exact SCPI syntax
for sweep-point count (whether a spectrum analyzer's trace length is even
user-settable via SCPI, as opposed to a fixed instrument-class default of
e.g. 601 points) and for any query of the instrument's own internal
alignment/self-calibration state (as distinct from a VNA's user-applied
S-parameter correction, which has no real spectrum-analyzer analog) are
genuinely vendor-and-model variable and were NOT independently re-verified
against every vendor's manual here. `SpectrumAnalyzerAdapter.commands` is
therefore a plain, fully-overridable dict (see DEFAULT_SCPI_COMMANDS and
SpectrumAnalyzerAdapter.__init__), exactly like VnaAdapter.commands -- a
real deployment tunes it to its actual instrument rather than this module
guessing wrong. Unlike the VNA adapter, this module does NOT attempt any
instrument-side "calibration state" SCPI query at all (there is no
standardized SCPI query for spectrum-analyzer self-alignment state
comparable to `SENS:CORR:STAT?`'s VNA-correction-state meaning); calibration
metadata here is caller-supplied only (job['calibration']), same shape as
VnaAdapter's calibration dict otherwise.

No real spectrum analyzer and no pyvisa install exist in this environment
(`import pyvisa` genuinely fails here -- see tests/test_spectrum_analyzer.py).
Treat any result from a real instrument as unverified end-to-end until this
has actually been run against real spectrum-analyzer hardware at least once.
"""

import os
import time
from collections.abc import Callable
from typing import Any

import numpy as np

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
# fills in {center_hz}/{span_hz}/{res_bw_hz}/{points} as applicable. Pass a
# `commands` dict to SpectrumAnalyzerAdapter(...) to override any subset;
# unspecified keys keep their default here.
# ---------------------------------------------------------------------------

DEFAULT_SCPI_COMMANDS: dict[str, str] = {
    "idn": "*IDN?",
    "freq_center": "FREQ:CENT {center_hz:.0f}",
    "freq_span": "FREQ:SPAN {span_hz:.0f}",
    # Empty by default -- skipped when job['res_bw_hz'] is not given.
    "res_bandwidth": "BAND:RES {res_bw_hz:.0f}",
    # Empty by default -- most spectrum analyzers have a fixed trace-length
    # instrument-class default and do not expose a settable sweep-point
    # count via SCPI (see vendor-variability caveat above). Override with
    # e.g. "SWE:POIN {points}" for instruments that do.
    "sweep_points": "",
    "trigger": "INIT:IMM;*WAI",
    "trace_query": "TRAC:DATA? TRACE1",
}


def _spectrum_analyzer_fingerprint_fields(
    resource: str | None,
    center_hz: float,
    span_hz: float,
    res_bw_hz: float | None,
    points: int,
) -> dict[str, Any]:
    """The subset of a spectrum-analyzer measurement request that
    determines what will physically happen on the instrument -- what
    measurement.base.request_physical_measurement_approval() and
    check_physical_actuation_gate() fingerprint an approval against. Both
    request_spectrum_analyzer_measurement_approval (the approval-request
    tool) and SpectrumAnalyzerAdapter.measure() (the actual measurement)
    compute this SAME dict from the SAME inputs, mirroring measurement/
    vna.py's _vna_fingerprint_fields -- see measurement/base.py's module
    docstring for why this is kept separate from the adapter's full job
    dict (which also carries output-only fields like calibration
    metadata that have no bearing on what gets sent to the instrument)."""
    return {
        "resource": resource,
        "center_hz": center_hz,
        "span_hz": span_hz,
        "res_bw_hz": res_bw_hz,
        "points": points,
    }


def _parse_trace_response(raw: str, expected_points: int | None = None) -> list[float]:
    """Parse a SCPI trace-data ASCII response: comma-separated amplitude
    values (dBm), the standard shape returned by a TRAC:DATA?-style query
    (see module docstring citation). Unlike VNA S-parameter data, a
    spectrum-analyzer trace is real-valued (amplitude only, no phase), so
    there is no interleaved real/imag pairing to undo."""
    text = raw.strip()
    if not text:
        raise InstrumentError("spectrum analyzer returned an empty trace data response")
    parts = [p for p in text.replace("\n", ",").split(",") if p.strip() != ""]
    try:
        values = [float(p) for p in parts]
    except ValueError as exc:
        raise InstrumentError(
            "could not parse spectrum analyzer trace data response as "
            f"comma-separated floats: {raw!r}"
        ) from exc
    if expected_points is not None and len(values) != expected_points:
        raise InstrumentError(
            f"spectrum analyzer trace data response returned {len(values)} "
            f"points, expected {expected_points} (the configured sweep point "
            "count)"
        )
    return values


class SpectrumAnalyzerAdapter(Instrument):
    """SCPI/VISA-driven spectrum analyzer adapter. See this module's
    docstring for the SCPI command citations/vendor-variability caveat, and
    measurement/base.py for the physical-actuation approval gate measure()
    cannot bypass or short-circuit. Structurally identical to
    measurement/vna.py's VnaAdapter -- same constructor-injection seams,
    same gate-first measure() discipline -- adapted to a read-only trace
    pull instead of an S-parameter sweep."""

    name = "SpectrumAnalyzer"

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
        resource = job.get("resource") or os.getenv("SPECTRUM_ANALYZER_VISA_RESOURCE")
        center_hz = job.get("center_hz")
        span_hz = job.get("span_hz")
        if center_hz is None or span_hz is None:
            raise InstrumentError("job['center_hz'] and job['span_hz'] are required")
        res_bw_hz = job.get("res_bw_hz")
        points = int(job.get("points", 401))
        fingerprint_fields = _spectrum_analyzer_fingerprint_fields(
            resource, center_hz, span_hz, res_bw_hz, points
        )

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

            transport.write(self.commands["freq_center"].format(center_hz=center_hz))
            transport.write(self.commands["freq_span"].format(span_hz=span_hz))

            res_bw_cmd = self.commands.get("res_bandwidth", "")
            if res_bw_cmd and res_bw_hz is not None:
                transport.write(res_bw_cmd.format(res_bw_hz=res_bw_hz))

            points_cmd = self.commands.get("sweep_points", "")
            if points_cmd:
                transport.write(points_cmd.format(points=points))

            transport.write(self.commands["trigger"])
            raw = transport.query(self.commands["trace_query"])
            amplitude_dbm = _parse_trace_response(raw, expected_points=points)
        finally:
            close = getattr(transport, "close", None)
            if callable(close):
                close()

        start_hz = float(center_hz) - float(span_hz) / 2.0
        stop_hz = float(center_hz) + float(span_hz) / 2.0
        frequency_hz = np.linspace(start_hz, stop_hz, points).tolist()

        peak_index = int(np.argmax(amplitude_dbm))

        calibration: dict[str, Any] = dict(job.get("calibration") or {})
        calibration.setdefault(
            "note",
            "Spectrum analyzers do not expose a standardized SCPI query for "
            "internal self-alignment state comparable to a VNA's applied-"
            "correction state (see this module's docstring) -- supply "
            "job['calibration'] with any relevant metadata (last self-"
            "alignment date, external attenuator/cable loss corrections, "
            "etc.) from the operator's record when available.",
        )

        return InstrumentResult(
            instrument=idn or self.name,
            status="COMPLETED",
            outputs={
                "instrument_idn": idn,
                "resource": resource,
                "center_hz": float(center_hz),
                "span_hz": float(span_hz),
                "resolution_bandwidth_hz": res_bw_hz,
                "frequency_hz": frequency_hz,
                "amplitude_dbm": amplitude_dbm,
                "peak_frequency_hz": frequency_hz[peak_index],
                "peak_amplitude_dbm": amplitude_dbm[peak_index],
                "calibration": calibration,
                "measured_at": time.time(),
            },
        )


def request_spectrum_analyzer_measurement_approval(
    resource: str | None,
    center_hz: float,
    span_hz: float,
    res_bw_hz: float | None = None,
    points: int = 401,
    approved_by: str | None = None,
    approval_callback: Callable[[dict[str, Any]], bool] | None = None,
) -> dict[str, Any]:
    """The spectrum-analyzer-adapter-facing wrapper around
    measurement.base.request_physical_measurement_approval() -- the
    distinct, separate, auditable step that MUST happen before
    run_spectrum_analyzer_measurement()/SpectrumAnalyzerAdapter.measure()
    will proceed. Does nothing dangerous itself (see measurement/base.py's
    module docstring). Returns the resulting ApprovalReceipt as a plain
    JSON-serializable dict (ApprovalReceipt.to_dict()) so it can cross an
    agent/MCP tool boundary and be handed straight to
    run_spectrum_analyzer_measurement's `approval` parameter.

    `approval_callback` defaults to None, meaning this ALWAYS raises
    InstrumentError -- there is no human-facing approval workflow wired up
    in this codebase yet (see measurement/base.py). The agent/MCP tool
    wrapping this function never supplies one either, since a Python
    callable cannot cross that JSON boundary -- so a real agent invocation
    of that tool always raises too, by design. Mirrors measurement/vna.py's
    request_vna_measurement_approval exactly.
    """
    from .base import request_physical_measurement_approval

    fields = _spectrum_analyzer_fingerprint_fields(resource, center_hz, span_hz, res_bw_hz, points)
    receipt = request_physical_measurement_approval(
        fields, approved_by=approved_by, approval_callback=approval_callback
    )
    return receipt.to_dict()


def run_spectrum_analyzer_measurement(
    resource: str | None,
    center_hz: float,
    span_hz: float,
    approval: dict[str, Any] | Any,
    res_bw_hz: float | None = None,
    points: int = 401,
    calibration: dict[str, Any] | None = None,
    transport_factory: Callable[[str], Any] | None = None,
    confinement_check: Callable[..., None] | None = None,
) -> dict[str, Any]:
    """Perform one spectrum-analyzer trace measurement via
    SpectrumAnalyzerAdapter, and return a MEASURED-provenance result
    structured the same way measurement/vna.py's run_vna_measurement
    returns its VNA result.

    `approval` MUST be a genuine measurement.base.ApprovalReceipt (or a
    dict with the same fields) obtained from a prior, separate call to
    request_spectrum_analyzer_measurement_approval() for THIS EXACT
    resource/center_hz/span_hz/res_bw_hz/points combination -- see
    measurement/base.py's module docstring for why this cannot be a bare
    boolean/string. `transport_factory`/`confinement_check` are the same
    test-only injection seams documented on VnaAdapter.__init__ -- omit
    both for a real call.
    """
    from .base import ApprovalReceipt

    if isinstance(approval, dict):
        approval = ApprovalReceipt(**approval)

    adapter = SpectrumAnalyzerAdapter(
        transport_factory=transport_factory, confinement_check=confinement_check
    )
    job = {
        "resource": resource,
        "center_hz": center_hz,
        "span_hz": span_hz,
        "res_bw_hz": res_bw_hz,
        "points": points,
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
