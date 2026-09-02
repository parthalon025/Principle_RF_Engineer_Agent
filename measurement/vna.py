"""VNA (Vector Network Analyzer) adapter over SCPI/VISA (issue #43) -- the
first measurement/ adapter, Phase 10 ticket 1 of 2 ("Add SCPI/VISA adapters
for VNA, spectrum analyzer, signal generator, and power meter" per
docs/BUILD_PLAN.md's Phase 10; the other three instrument classes are a
later ticket).

Pulls measured S-parameter data from a real VNA into this system without
manual transcription, tagged MEASURED provenance (the top of this project's
own evidence hierarchy -- README.md's "Design goals" section), with
instrument identity and calibration metadata attached, and structured
compatibly with this project's existing Touchstone conventions
(rf_tools/touchstone.py) by building an in-memory `skrf.Network` from the
parsed data -- the same library simulation/hfss.py's export_touchstone path
and rf_tools/touchstone.py's analyze/interpolate/de-embed/cascade/compare
functions all use.

CRITICAL, NON-NEGOTIABLE PROJECT CONSTRAINT: physical lab instruments are
never controlled autonomously (README.md, docs/BUILD_PLAN.md Phase 10,
docs/SECURITY.md). VnaAdapter.measure() calls measurement.base.
check_physical_actuation_gate() as the FIRST thing it does, before any SCPI/
VISA traffic -- see measurement/base.py's module docstring for the full
approval-gate design (a distinct, auditable `request_physical_measurement_
approval()` step, cryptographically bound to the exact request it approves,
is required before this adapter will proceed). This module never bypasses
or duplicates that gate; it only supplies the two adapter-specific gate
inputs the gate itself does not know how to determine (the VISA resource
string, and whether pyvisa is actually importable on this host).

SOURCES CONSULTED (accessed 2026-09-02):
  - `SENS:FREQ:STAR` / `SENS:FREQ:STOP` (start/stop frequency), `SENS:SWE:
    POIN` (sweep points), `INIT:IMM` (trigger a sweep), and `CALC:DATA?
    SDATA` (complex S-parameter data query): scikit-rf's own Rohde &
    Schwarz VNA driver, `skrf/vi/vna/rohde_schwarz/rs_vna.py`, fetched
    directly from scikit-rf's GitHub `master` branch -- a real, maintained
    driver exercised against real R&S VNAs, not a guess. That driver
    channel-scopes each command (e.g. `SENS<cnum>:FREQ:STAR <arg>`,
    `INIT<cnum>:IMM`) and also documents `CALC<cnum>:DATA:SGR? SDAT` for
    reading a full S-parameter group in one query; this module uses the
    unscoped, single-channel form (no `<cnum>` suffix, which SCPI treats as
    channel 1 by default) and reads one S-parameter per query (`CALC:DATA?
    SDATA` after selecting a trace) rather than the group form, favoring
    the simplest form most single-trace-per-selection instruments accept
    over one driver's channel-grouped convention.
  - `SENS:CORR:STAT?` (a.k.a. `SENSe<cnum>:CORRection[:STATe]?`) as a
    correction/calibration-applied state query, and `CALC:MEAS:CORR:
    STATe?` as an equivalent alternate form: Keysight's NA520xA GP-IB
    Command Finder, "Sense Correction" reference page
    (helpfiles.keysight.com). That same page does NOT document any query
    for calibration kit name or calibration date/timestamp -- this module
    does not claim one exists (see the calibration-metadata handling in
    VnaAdapter.measure below, which always leaves a structured place for
    caller-supplied calibration metadata regardless).
  - `*IDN?` as the IEEE-488.2 standard identification query, common to
    every SCPI instrument by definition (not vendor-specific, not
    independently re-verified against one manual here).

HONEST, EXPLICIT VENDOR-VARIABILITY CAVEAT (same discipline as
simulation/hfss.py's PyAEDT caveat): exact SCPI syntax for *defining* and
*selecting* an S-parameter measurement (as opposed to querying its data,
cited above) is real but genuinely vendor-and-model variable -- Keysight,
Rohde & Schwarz, Copper Mountain, and Anritsu each spell "define a
measurement and assign it to a trace" differently (e.g. Keysight PNA-family
instruments require `CALC:PAR:DEF 'name',S11` before `CALC:PAR:SEL 'name'`
will succeed; other instruments' default trace can be selected directly).
This was NOT independently re-verified against every vendor's manual here.
`VnaAdapter.commands` is therefore deliberately a plain, fully-overridable
dict (see DEFAULT_SCPI_COMMANDS and VnaAdapter.__init__) rather than
command strings hardcoded deep in measure()'s logic -- a real deployment
tunes `commands` (and, if needed, `define_sparam`, which defaults to empty/
skipped) to its actual instrument rather than this module guessing wrong.

No real VNA and no pyvisa install exist in this environment (`import
pyvisa` genuinely fails here -- see tests/test_vna.py). Treat any result
from a real instrument as unverified end-to-end until this has actually
been run against real VNA hardware at least once.
"""

import importlib
import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

from .base import (
    Instrument,
    InstrumentError,
    InstrumentResult,
    check_physical_actuation_gate,
)

# ---------------------------------------------------------------------------
# Overridable SCPI command templates -- see module docstring's vendor-
# variability caveat. Every value is a Python format-string; measure()
# fills in {start_hz}/{stop_hz}/{points}/{sparam} as applicable. Pass a
# `commands` dict to VnaAdapter(...) to override any subset; unspecified
# keys keep their default here.
# ---------------------------------------------------------------------------

DEFAULT_SCPI_COMMANDS: dict[str, str] = {
    "idn": "*IDN?",
    "freq_start": "SENS:FREQ:STAR {start_hz:.0f}",
    "freq_stop": "SENS:FREQ:STOP {stop_hz:.0f}",
    "sweep_points": "SENS:SWE:POIN {points}",
    # Empty by default -- most single-trace instruments already have a
    # default trace to select via select_sparam below, with no separate
    # "define" step. Override with e.g. "CALC:PAR:DEF 'ch1_{sparam}',
    # {sparam}" for instruments (e.g. Keysight PNA family) that require
    # explicitly defining a named measurement before it can be selected.
    "define_sparam": "",
    "select_sparam": "CALC:PAR:SEL '{sparam}'",
    "trigger": "INIT:IMM;*WAI",
    "sdata_query": "CALC:DATA? SDATA",
    # Best-effort only (see module docstring) -- set to "" to skip
    # entirely on instruments that don't support any calibration-state
    # query.
    "cal_state_query": "SENS:CORR:STAT?",
}

_ONE_PORT = frozenset({"S11"})
_TWO_PORT = frozenset({"S11", "S12", "S21", "S22"})


def _vna_fingerprint_fields(
    resource: str | None, start_hz: float, stop_hz: float, points: int, sparams: list[str]
) -> dict[str, Any]:
    """The subset of a VNA measurement request that determines what will
    physically happen on the instrument -- what
    measurement.base.request_physical_measurement_approval() and
    check_physical_actuation_gate() fingerprint an approval against. Both
    request_vna_measurement_approval (the approval-request tool) and
    VnaAdapter.measure() (the actual measurement) compute this SAME dict
    from the SAME inputs, so a receipt granted for one exact
    resource/frequency-range/points/sparams combination verifies here and
    only here -- see measurement/base.py's module docstring for why this is
    kept separate from the adapter's full job dict (which also carries
    output-only fields like calibration metadata and touchstone_path that
    have no bearing on what gets sent to the instrument)."""
    return {
        "resource": resource,
        "start_hz": start_hz,
        "stop_hz": stop_hz,
        "points": points,
        "sparams": list(sparams),
    }


def _real_pyvisa_importable() -> tuple[bool, str]:
    """Actually attempt `import pyvisa`. Returns (importable, detail)
    rather than raising, so check_physical_actuation_gate can report it
    alongside every other missing signal in one message -- same pattern as
    simulation/hfss.py's _real_pyaedt_importable."""
    try:
        importlib.import_module("pyvisa")
    except ImportError as exc:
        return False, str(exc)
    return True, ""


def _import_pyvisa_module() -> Any:
    """Guarded import of pyvisa itself -- deferred to inside this function
    (rather than a top-of-module `import`) precisely because pyvisa
    genuinely will not be installed in most environments, including this
    one (see module docstring). Only ever reached from
    VnaAdapter._real_transport_factory, itself only reached after
    check_physical_actuation_gate has already passed."""
    try:
        import pyvisa
    except ImportError as exc:
        raise InstrumentError(
            "pyvisa is not installed. Install the optional 'measurement' "
            "dependency group, e.g. `uv sync --extra measurement` or "
            "`pip install '.[measurement]'`."
        ) from exc
    return pyvisa


def _parse_sdata_response(raw: str, expected_points: int | None = None) -> list[complex]:
    """Parse a SCPI SDATA-style ASCII response: comma-separated interleaved
    real,imag pairs (the standard shape returned by a CALC:DATA? SDATA-
    style query -- see module docstring citation)."""
    text = raw.strip()
    if not text:
        raise InstrumentError("VNA returned an empty S-parameter data response")
    parts = [p for p in text.replace("\n", ",").split(",") if p.strip() != ""]
    try:
        values = [float(p) for p in parts]
    except ValueError as exc:
        raise InstrumentError(
            "could not parse VNA S-parameter data response as comma-separated "
            f"floats: {raw!r}"
        ) from exc
    if len(values) % 2 != 0:
        raise InstrumentError(
            f"VNA S-parameter data response has an odd number of values "
            f"({len(values)}) -- expected interleaved real,imag pairs: {raw!r}"
        )
    complex_values = [complex(values[i], values[i + 1]) for i in range(0, len(values), 2)]
    if expected_points is not None and len(complex_values) != expected_points:
        raise InstrumentError(
            f"VNA S-parameter data response returned {len(complex_values)} "
            f"points, expected {expected_points} (the configured sweep point "
            "count)"
        )
    return complex_values


def _build_touchstone_network(
    frequency_hz: list[float], s_by_param: dict[str, list[complex]], z0: float
) -> Any:
    """Build an in-memory skrf.Network from parsed S-parameter data --
    reusing skrf (this project's established Touchstone library, see
    rf_tools/touchstone.py) so a MEASURED result is structurally the same
    kind of object a SIMULATED Touchstone export produces, and can be fed
    directly into rf_tools.touchstone's analyze/interpolate/de-embed/
    cascade/compare functions or written to a real .sNp file."""
    import skrf as rf

    param_names = frozenset(s_by_param.keys())
    if param_names == _ONE_PORT:
        nports = 1
    elif param_names == _TWO_PORT:
        nports = 2
    else:
        raise InstrumentError(
            "unsupported S-parameter set for Touchstone construction: "
            f"{sorted(param_names)} -- provide exactly {{'S11'}} (1-port) or "
            f"{sorted(_TWO_PORT)} (2-port)"
        )

    freqs = np.asarray(frequency_hz, dtype=float)
    npoints = len(freqs)
    s = np.zeros((npoints, nports, nports), dtype=complex)
    if nports == 1:
        s[:, 0, 0] = s_by_param["S11"]
    else:
        s[:, 0, 0] = s_by_param["S11"]
        s[:, 0, 1] = s_by_param["S12"]
        s[:, 1, 0] = s_by_param["S21"]
        s[:, 1, 1] = s_by_param["S22"]

    frequency = rf.Frequency.from_f(freqs / 1e9, unit="ghz")
    return rf.Network(frequency=frequency, s=s, z0=z0)


class VnaAdapter(Instrument):
    """SCPI/VISA-driven VNA adapter. See this module's docstring for the
    SCPI command citations/vendor-variability caveat, and
    measurement/base.py for the physical-actuation approval gate
    measure() cannot bypass or short-circuit."""

    name = "VNA"

    def __init__(
        self,
        transport_factory: Callable[[str], Any] | None = None,
        commands: dict[str, str] | None = None,
        confinement_check: Callable[..., None] | None = None,
    ):
        """`transport_factory` and `confinement_check` are constructor-
        injection seams for tests ONLY, mirroring HfssSimulator's
        hfss_factory/confinement_check pattern (simulation/hfss.py) -- a
        real call never passes them, so it always goes through the real
        approval/pyvisa gate and a real pyvisa resource. `transport_factory`,
        if given, is called with the resolved VISA resource string and must
        return an object implementing `.query(str) -> str`, `.write(str)`,
        and optionally `.close()` (the subset of pyvisa's Resource API this
        module calls -- see tests/test_vna.py's fake for the exact shape).
        `commands` overrides any subset of DEFAULT_SCPI_COMMANDS -- see this
        module's docstring on why exact SCPI syntax is deliberately
        overridable rather than hardcoded deep in measure()'s logic.
        `confinement_check` defaults to the real
        measurement.base.check_physical_actuation_gate."""
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
        resource = job.get("resource") or os.getenv("VNA_VISA_RESOURCE")
        start_hz = job.get("start_hz")
        stop_hz = job.get("stop_hz")
        if start_hz is None or stop_hz is None:
            raise InstrumentError("job['start_hz'] and job['stop_hz'] are required")
        points = int(job.get("points", 201))
        sparams = list(job.get("sparams") or ["S11"])
        z0 = float(job.get("z0", 50.0))
        fingerprint_fields = _vna_fingerprint_fields(resource, start_hz, stop_hz, points, sparams)

        importable, detail = _real_pyvisa_importable()

        # The approval/actuation gate -- checked BEFORE any SCPI/VISA
        # traffic, per this ticket's design guidance, mirroring
        # HfssSimulator.run()'s call to check_hfss_workstation_confinement
        # as the very first substantive action of run() (simulation/
        # hfss.py). Nothing below this call touches the instrument unless
        # it returns normally (it raises InstrumentError otherwise).
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

            transport.write(self.commands["freq_start"].format(start_hz=start_hz))
            transport.write(self.commands["freq_stop"].format(stop_hz=stop_hz))
            transport.write(self.commands["sweep_points"].format(points=points))

            s_by_param: dict[str, list[complex]] = {}
            for sparam in sparams:
                define_cmd = self.commands.get("define_sparam", "")
                if define_cmd:
                    transport.write(define_cmd.format(sparam=sparam))
                transport.write(self.commands["select_sparam"].format(sparam=sparam))
                transport.write(self.commands["trigger"])
                raw = transport.query(self.commands["sdata_query"].format(sparam=sparam))
                s_by_param[sparam] = _parse_sdata_response(raw, expected_points=points)

            cal_state: str | None = None
            cal_query = self.commands.get("cal_state_query", "")
            if cal_query:
                try:
                    cal_state = transport.query(cal_query).strip()
                except Exception:
                    # Calibration-state query support genuinely varies by
                    # vendor/model (see module docstring) -- best-effort
                    # only, never fatal to the measurement itself.
                    cal_state = None
        finally:
            close = getattr(transport, "close", None)
            if callable(close):
                close()

        frequency_hz = np.linspace(float(start_hz), float(stop_hz), points).tolist()

        calibration: dict[str, Any] = dict(job.get("calibration") or {})
        if cal_state is not None:
            calibration.setdefault("instrument_reported_correction_state", cal_state)
        calibration.setdefault(
            "note",
            "Calibration kit name/date are not reliably queryable via a "
            "standardized SCPI command across vendors (see this module's "
            "docstring) -- supply job['calibration'] with kit/date/method "
            "metadata from the operator's calibration record when available.",
        )

        network = _build_touchstone_network(frequency_hz, s_by_param, z0)
        touchstone_file = None
        touchstone_path = job.get("touchstone_path")
        if touchstone_path:
            path = Path(touchstone_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            network.name = path.stem
            path.write_text(network.write_touchstone(filename=str(path), return_string=True))
            touchstone_file = str(path)

        return InstrumentResult(
            instrument=idn or self.name,
            status="COMPLETED",
            outputs={
                "instrument_idn": idn,
                "resource": resource,
                "frequency_hz": frequency_hz,
                "z0": z0,
                "s_parameters": {
                    sparam: [str(complex(v)) for v in values]
                    for sparam, values in s_by_param.items()
                },
                "ports": network.nports,
                "touchstone_file": touchstone_file,
                "calibration": calibration,
                "measured_at": time.time(),
            },
        )


def request_vna_measurement_approval(
    resource: str | None,
    start_hz: float,
    stop_hz: float,
    points: int = 201,
    sparams: list[str] | None = None,
    approved_by: str | None = None,
    approval_callback: Callable[[dict[str, Any]], bool] | None = None,
) -> dict[str, Any]:
    """The VNA-adapter-facing wrapper around measurement.base.request_
    physical_measurement_approval() -- the distinct, separate, auditable
    step that MUST happen before run_vna_measurement()/VnaAdapter.measure()
    will proceed. Does nothing dangerous itself (see measurement/base.py's
    module docstring). Returns the resulting ApprovalReceipt as a plain
    JSON-serializable dict (ApprovalReceipt.to_dict()) so it can cross an
    agent/MCP tool boundary and be handed straight to run_vna_measurement's
    `approval` parameter.

    `approval_callback` defaults to None, meaning this ALWAYS raises
    InstrumentError -- there is no human-facing approval workflow wired up
    in this codebase yet (see measurement/base.py). The agent/MCP tool
    wrapping this function (see agent/main.py's
    request_vna_measurement_approval tool) never supplies one either, since
    a Python callable cannot cross that JSON boundary -- so a real agent
    invocation of that tool always raises too, by design.
    """
    from .base import request_physical_measurement_approval

    fields = _vna_fingerprint_fields(resource, start_hz, stop_hz, points, sparams or ["S11"])
    receipt = request_physical_measurement_approval(
        fields, approved_by=approved_by, approval_callback=approval_callback
    )
    return receipt.to_dict()


def run_vna_measurement(
    resource: str | None,
    start_hz: float,
    stop_hz: float,
    approval: dict[str, Any] | Any,
    points: int = 201,
    sparams: list[str] | None = None,
    z0: float = 50.0,
    calibration: dict[str, Any] | None = None,
    touchstone_path: str | None = None,
    transport_factory: Callable[[str], Any] | None = None,
    confinement_check: Callable[..., None] | None = None,
) -> dict[str, Any]:
    """Perform one VNA S-parameter measurement via VnaAdapter, and return a
    MEASURED-provenance result structured the same way as
    run_nec2_simulation/run_openems_simulation/run_hfss_simulation return
    their SIMULATED-provenance results.

    `approval` MUST be a genuine measurement.base.ApprovalReceipt (or a
    dict with the same fields -- e.g. one that already crossed an agent/MCP
    JSON tool boundary and back, see ApprovalReceipt.to_dict) obtained from
    a prior, separate call to
    measurement.base.request_physical_measurement_approval() for THIS
    exact resource/start_hz/stop_hz/points/sparams combination -- see
    measurement/base.py's module docstring for why this cannot be a bare
    boolean/string. `transport_factory`/`confinement_check` are the same
    test-only injection seams documented on VnaAdapter.__init__ -- omit
    both for a real call (the agent/MCP tool wiring always omits them, so a
    real invocation always goes through the real approval/pyvisa gate).
    """
    from .base import ApprovalReceipt

    if isinstance(approval, dict):
        approval = ApprovalReceipt(**approval)

    adapter = VnaAdapter(transport_factory=transport_factory, confinement_check=confinement_check)
    job = {
        "resource": resource,
        "start_hz": start_hz,
        "stop_hz": stop_hz,
        "points": points,
        "sparams": sparams or ["S11"],
        "z0": z0,
        "calibration": calibration,
        "touchstone_path": touchstone_path,
        "approval": approval,
    }
    result = adapter.measure(job)
    return {
        "provenance": "MEASURED",
        "instrument": result.instrument,
        "status": result.status,
        **result.outputs,
    }
