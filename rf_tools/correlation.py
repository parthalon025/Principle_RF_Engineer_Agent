"""Simulation/measurement correlation (issue #45, Phase 11 ticket 1 of 1 --
the last Phase 11 ticket).

Correlates a SIMULATED result (NEC2++/openEMS, or any future source shaped
the same way) against a MEASURED result (a Touchstone file an engineer
measured on independent equipment and brought back -- measurement/
external.py, ADR-0012/ADR-0013) so an engineer can judge how much to trust
a given simulation for future design decisions on similar geometries --
this project's evidence
hierarchy (CONTEXT.md: "measured > validated simulation > ...") only means
something once there is a quantified number for how far apart the two
actually are, not a bare pass/fail.

BRIDGING THE TYPE GAP: rf_tools/touchstone.py's `interpolate_touchstone`/
`deembed_touchstone`/`compare_touchstone` (Phase 2, tickets #29-32) take
FILE PATHS -- they load Touchstone files internally -- while a simulated or
measured result here typically arrives as an in-memory dict (or an
already-built `skrf.Network`), not a file on disk. Per this ticket's own
design guidance, the chosen approach is (a): coerce whatever's given into an
`skrf.Network`, write it to a temp Touchstone file via `Network.
write_touchstone(...)`, and call the existing path-based Phase 2 functions
UNCHANGED -- not (b) refactoring those already-tested functions to accept a
Network directly. This keeps rf_tools/touchstone.py's tested code completely
untouched; the minor extra I/O is a deliberate, acceptable trade per the
ticket's own guidance.

WHAT THIS FUNCTION ACTUALLY NORMALIZES, HONESTLY, PER INPUT:

  - Frequency grid: always. `compare_touchstone` (reused unmodified) brings
    both networks onto a common grid via `interpolate_touchstone` before
    quantifying any difference.
  - Reference impedance: always checked; renormalized via `skrf.Network.
    renormalize()` (skrf's own built-in, not hand-derived) when simulated
    and measured z0 differ, so the two are never compared at mismatched
    reference impedances. See `_normalize_reference_impedance` below.
  - Calibration plane (fixture de-embedding): ONLY when `fixture_path` is
    supplied, by reusing `deembed_touchstone` (Phase 2, ticket #31) as-is on
    the measured network. When `fixture_path` is omitted, this is explicitly
    SKIPPED -- the returned result's `calibration_plane_note` says so in
    plain language, rather than silently implying every call de-embeds a
    fixture it was never told about.
  - Temperature: a documented, honest NO-OP pass-through. Neither
    `simulation.base.SimulationResult` nor `measurement.external.
    record_external_measurement`'s own result carries a dedicated
    temperature field as of this ticket, and neither `simulation/nec2pp.py`
    nor `simulation/openems.py` populates one in their `outputs`/result
    dicts. If a
    caller-supplied `simulated`/`measured` dict happens to carry a
    `temperature_c` key anywhere a generic metadata dict could hold one
    (top-level, or under an `"outputs"`/`"calibration"` sub-dict), it IS read
    and compared -- flagging the result when the two differ by more than
    `temperature_tolerance_c`, since S-parameters can drift with
    temperature. When neither carries one (the common case today, since no
    upstream adapter populates it), `temperature_note` says plainly that
    temperature normalization is a no-op pending upstream temperature-
    metadata support -- not a fabricated "temperatures matched" claim.

WHAT'S ACTUALLY USABLE AS SIMULATED INPUT TODAY: this function accepts any
of an `skrf.Network`, a dict carrying a `"network"` (`skrf.Network`) key, a
dict carrying a `"touchstone_file"`/`"file"` path, or a dict carrying the
same generic `"frequency_hz"`/`"s_parameters"`/`"z0"` shape `measurement.
external.record_external_measurement` returns (see
`_network_from_generic_result`). That generic shape unconditionally covers
the MEASURED side (`record_external_measurement`'s own output, which also
carries a top-level `"touchstone_file"` -- accepted either way, see that
function's own module docstring). It does NOT cover
`simulation.nec2pp.run_nec2_simulation`'s
output (single-frequency feed-point impedance only -- no frequency-swept
S-parameter data at all, still true today) or the *fallback* case of
`simulation.openems.run_openems_simulation`'s output (`s_parameters`
carries `"computed": False` with an explanatory note when the run's port
ProbeBox time-domain dumps weren't available -- see that module's own
"SCOPE OF THIS IMPLEMENTATION"). Handing either of those to this function
as-is raises `CorrelationError` naming exactly why, rather than fabricating
S-parameters from data that was never produced. When openEMS DID compute
real S-parameters (the single-port case, `"computed": True`), its result
carries a top-level `"touchstone_file"` (mirroring `simulation.hfss.
run_hfss_simulation`'s own `"computed": True` shape) and is accepted via
that path, not the generic `"s_parameters"` dict shape (which stays a
self-describing `{"computed", "values", ...}` structure, not the bare
`{"S11": [...], ...}` shape this function's generic path expects).
`simulation.gprmax.run_gprmax_simulation` (issue #63) follows the exact
same `"computed"`/top-level-`"touchstone_file"` convention as openEMS's
S-parameter output (both single-port, FFT-computed from a port's own
time-domain dumps) and is accepted/rejected via the same two paths. This
function works today against any source that already carries real swept
S-parameter data -- a raw Touchstone file/`skrf.Network`, a computed
NEC2++/openEMS/gprMax/HFSS export, or a future simulator export in this
generic shape.
"""

import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import skrf as rf

from .touchstone import compare_touchstone, deembed_touchstone

_ONE_PORT = frozenset({"S11"})
_TWO_PORT = frozenset({"S11", "S12", "S21", "S22"})

_PARAMS_BY_PORT_COUNT: dict[int, tuple[str, ...]] = {
    1: ("S11",),
    2: ("S11", "S12", "S21", "S22"),
}


class CorrelationError(ValueError):
    """Raised when a simulated/measured result can't be correlated -- e.g.
    it doesn't carry usable S-parameter data, or the two networks have
    incompatible port counts. A `ValueError` subclass (matching rf_tools.
    touchstone's own convention of raising plain `ValueError` for bad
    input) so existing `except ValueError` callers still catch it."""


def _parse_complex(value: Any) -> complex:
    """Parse one S-parameter value in any of the shapes this project's
    result sources actually emit: a native complex/real number, a
    `[re, im]` pair, or a `str(complex(...))`-style string."""
    if isinstance(value, complex):
        return value
    if isinstance(value, (int, float)):
        return complex(value)
    if isinstance(value, str):
        try:
            return complex(value.replace(" ", ""))
        except ValueError as exc:
            raise CorrelationError(
                f"could not parse {value!r} as a complex S-parameter value"
            ) from exc
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return complex(value[0], value[1])
    raise CorrelationError(f"could not parse {value!r} as a complex S-parameter value")


def _network_from_generic_result(result: dict[str, Any], label: str) -> rf.Network:
    """Build an `skrf.Network` from a generic parsed-result dict shaped
    like `measurement/external.py`'s `record_external_measurement` output:
    `{"frequency_hz": [...], "s_parameters": {"S11": [...], ...}, "z0":
    float}`. See this module's docstring for exactly which of this
    project's current simulator/external-measurement sources do and do not
    produce this shape today."""
    frequency_hz = result.get("frequency_hz")
    s_parameters = result.get("s_parameters")
    if not frequency_hz or not s_parameters:
        raise CorrelationError(
            f"{label} result does not carry real per-frequency S-parameter "
            "data ('frequency_hz' + 's_parameters' keys) that "
            "correlate_simulation_measurement can use. This is a known, "
            "honestly-scoped gap: simulation/nec2pp.py's "
            "parse_nec2_output/run_nec2_simulation returns only a "
            "single-frequency feed-point impedance, no S-parameter sweep, "
            "and simulation/openems.py's parse_openems_output/"
            "run_openems_simulation returns 's_parameters' with "
            "'computed': False when the run's port probe time-domain dumps "
            "weren't available (see that module's 'SCOPE OF THIS "
            "IMPLEMENTATION') -- when they ARE available, openEMS's result "
            "instead carries a top-level 'touchstone_file' (like "
            "simulation/hfss.py's own computed=True results), which this "
            "function accepts via the 'touchstone_file'/'file' path below, "
            "not this generic 'frequency_hz'/'s_parameters' shape. Supply "
            "a result carrying real 'frequency_hz'/'s_parameters'/'z0' "
            "data (e.g. measurement/external.py's "
            "record_external_measurement output), "
            "a 'touchstone_file' path, or an already-built skrf.Network "
            "via a 'network' key."
        )

    if not isinstance(s_parameters, dict):
        raise CorrelationError(
            f"{label} result's 's_parameters' must be a dict of S-parameter "
            f"name -> per-frequency values, got {type(s_parameters).__name__}"
        )

    param_names = frozenset(s_parameters.keys())
    if param_names == _ONE_PORT:
        nports = 1
    elif param_names == _TWO_PORT:
        nports = 2
    else:
        raise CorrelationError(
            f"{label} result's s_parameters keys {sorted(param_names)} are "
            f"not a supported set -- expected {sorted(_ONE_PORT)} (1-port) "
            f"or {sorted(_TWO_PORT)} (2-port)"
        )

    freqs = np.asarray(frequency_hz, dtype=float)
    npoints = len(freqs)
    if npoints == 0:
        raise CorrelationError(f"{label} result's 'frequency_hz' is empty")
    z0 = result.get("z0", 50.0)

    s = np.zeros((npoints, nports, nports), dtype=complex)
    for name in _PARAMS_BY_PORT_COUNT[nports]:
        values = s_parameters[name]
        if len(values) != npoints:
            raise CorrelationError(
                f"{label} result's s_parameters[{name!r}] has {len(values)} "
                f"points but frequency_hz has {npoints}"
            )
        i, j = int(name[1]) - 1, int(name[2]) - 1
        s[:, i, j] = [_parse_complex(v) for v in values]

    frequency = rf.Frequency.from_f(freqs / 1e9, unit="ghz")
    return rf.Network(frequency=frequency, s=s, z0=float(z0))


def _result_to_network(result: Any, label: str) -> rf.Network:
    """Coerce a simulated/measured `result` into an `skrf.Network`,
    accepting whatever shape is actually at hand -- see this module's
    docstring for the full list and the honest limits on what today's
    simulator adapters can supply."""
    if isinstance(result, rf.Network):
        return result
    if not isinstance(result, dict):
        raise CorrelationError(
            f"{label} result must be an skrf.Network or a dict, got {type(result).__name__}"
        )

    network = result.get("network")
    if isinstance(network, rf.Network):
        return network

    touchstone_file = result.get("touchstone_file") or result.get("file")
    if touchstone_file:
        path = Path(touchstone_file)
        if not path.exists():
            raise CorrelationError(
                f"{label} result's touchstone file {touchstone_file!r} does not exist"
            )
        return rf.Network(str(path))

    return _network_from_generic_result(result, label)


def _extract_temperature_c(result: Any) -> float | None:
    """Best-effort read of a `temperature_c` field from wherever a generic
    metadata dict could plausibly carry one -- top-level, or nested under
    an `"outputs"` or `"calibration"` sub-dict (the shapes `SimulationResult
    .outputs` and `run_vna_measurement`'s `calibration` sub-dict already
    use for other free-form metadata). Returns None, not a fabricated
    value, when nothing is found -- see this module's docstring's honest
    temperature-handling scope."""
    if not isinstance(result, dict):
        return None
    for container in (result, result.get("outputs"), result.get("calibration")):
        if isinstance(container, dict) and container.get("temperature_c") is not None:
            try:
                return float(container["temperature_c"])
            except (TypeError, ValueError):
                return None
    return None


def _build_temperature_note(
    simulated: Any, measured: Any, temperature_tolerance_c: float
) -> tuple[str, dict[str, Any]]:
    sim_temp_c = _extract_temperature_c(simulated)
    meas_temp_c = _extract_temperature_c(measured)
    detail: dict[str, Any] = {
        "simulated_temperature_c": sim_temp_c,
        "measured_temperature_c": meas_temp_c,
        "tolerance_c": temperature_tolerance_c,
    }

    if sim_temp_c is None and meas_temp_c is None:
        detail["flagged"] = False
        return (
            "Temperature normalization is a documented NO-OP pass-through "
            "in this ticket: neither the simulated nor the measured result "
            "carried a 'temperature_c' field, and none of "
            "simulation/nec2pp.py, simulation/openems.py, or "
            "measurement/external.py currently populates one -- this is a "
            "genuine upstream gap (SimulationResult/the external-"
            "measurement result don't carry a dedicated temperature field "
            "yet), not something this function silently handled.",
            detail,
        )

    if sim_temp_c is None or meas_temp_c is None:
        detail["flagged"] = False
        missing = "simulated" if sim_temp_c is None else "measured"
        return (
            f"Temperature data was present on one side only (missing on "
            f"the {missing} result) -- comparison skipped; both sides need "
            "a 'temperature_c' field for a meaningful check.",
            detail,
        )

    delta_c = abs(sim_temp_c - meas_temp_c)
    detail["delta_c"] = delta_c
    if delta_c > temperature_tolerance_c:
        detail["flagged"] = True
        return (
            f"FLAGGED: simulated temperature {sim_temp_c:g} C and measured "
            f"temperature {meas_temp_c:g} C differ by {delta_c:g} C, "
            f"exceeding the {temperature_tolerance_c:g} C tolerance -- "
            "S-parameters can drift with temperature, so this correlation "
            "result should be read with that in mind.",
            detail,
        )

    detail["flagged"] = False
    return (
        f"Simulated temperature {sim_temp_c:g} C and measured temperature "
        f"{meas_temp_c:g} C agree within the {temperature_tolerance_c:g} C "
        "tolerance.",
        detail,
    )


def correlate_simulation_measurement(
    simulated: dict[str, Any] | rf.Network,
    measured: dict[str, Any] | rf.Network,
    fixture_path: str | None = None,
    output_fixture_path: str | None = None,
    temperature_tolerance_c: float = 5.0,
) -> dict[str, Any]:
    """Correlate a SIMULATED result against a MEASURED result: normalize
    frequency grid, reference impedance, and (when a fixture is given)
    calibration plane, then produce a quantified per-S-parameter
    correlation result reusing `rf_tools.touchstone.compare_touchstone`
    (which itself reuses `interpolate_touchstone` for the frequency-grid
    step) -- not a bare pass/fail, so an engineer can judge how much to
    trust this simulation for similar future designs.

    `simulated`/`measured` accept an `skrf.Network` directly, a dict
    carrying `{"network": skrf.Network}`, a dict carrying
    `{"touchstone_file" | "file": <path>}`, or a dict shaped like
    `measurement.external.record_external_measurement`'s output
    (`"frequency_hz"` + `"s_parameters"` + `"z0"`). See this module's
    docstring for exactly what today's NEC2++/openEMS simulator adapters
    can and can't supply.

    `fixture_path` (optional): when given, the MEASURED network has fixture
    effects de-embedded via `rf_tools.touchstone.deembed_touchstone`
    (Phase 2, unmodified) BEFORE comparison -- this is the calibration-
    plane-normalization step. Pass `output_fixture_path` too for a fixture
    on both sides (same path twice for a symmetric fixture). When
    `fixture_path` is omitted, calibration-plane normalization is SKIPPED
    for this call -- see the returned `calibration_plane_note`.

    `temperature_tolerance_c`: threshold (default 5 C) above which a
    caller-supplied temperature difference is flagged in
    `temperature_note` -- only meaningful when both `simulated` and
    `measured` happen to carry a `temperature_c` field; otherwise this is
    a documented no-op (see this module's docstring).

    Returns a dict with:
      - `comparison`: `compare_touchstone`'s own return shape (per
        S-parameter `diff`/`magnitude_diff_db`/`max_magnitude_diff_db`/
        `rms_diff`/`max_abs_diff`, plus `ports`/`common_frequencies_hz`/
        `common_grid_source`) -- reused unmodified, not reimplemented.
      - `reference_impedance_note`: what z0 normalization actually did.
      - `calibration_plane_note`: what de-embedding actually did (or that
        it was skipped, and why that's an honest default).
      - `temperature_note` / `temperature_detail`: what temperature
        handling actually did (a documented no-op unless data was
        present).
      - `simulated_provenance` / `measured_provenance`: the provenance tag
        carried by each input, when present (defaulting to "SIMULATED"/
        "MEASURED" -- this project's own conventions for these two input
        kinds -- when the input didn't carry an explicit `provenance` key).
      - `provenance`: `"CALCULATED"` for the correlation result itself --
        it is a deterministic comparison of two prior results, computed
        by this function, not a new measured or simulated value in its
        own right.

    Raises `CorrelationError` (a `ValueError` subclass) if either input
    can't be coerced into usable S-parameter data, or if the two networks
    have different port counts.
    """
    simulated_provenance = (
        simulated.get("provenance", "SIMULATED") if isinstance(simulated, dict) else "SIMULATED"
    )
    measured_provenance = (
        measured.get("provenance", "MEASURED") if isinstance(measured, dict) else "MEASURED"
    )

    sim_network = _result_to_network(simulated, "simulated")
    meas_network = _result_to_network(measured, "measured")

    if sim_network.nports != meas_network.nports:
        raise CorrelationError(
            f"simulated network has {sim_network.nports} port(s) but "
            f"measured network has {meas_network.nports} port(s) -- "
            "correlate_simulation_measurement requires both to have the "
            "same port count"
        )

    temperature_note, temperature_detail = _build_temperature_note(
        simulated, measured, temperature_tolerance_c
    )

    with tempfile.TemporaryDirectory(prefix="correlation_") as tmpdir:
        tmp = Path(tmpdir)
        nports = meas_network.nports

        measured_raw_path = tmp / f"measured_raw.s{nports}p"
        meas_network.write_touchstone(filename=str(measured_raw_path), form="ri")

        # --- Calibration-plane normalization (de-embedding) ---
        if fixture_path is not None:
            meas_network = deembed_touchstone(
                str(measured_raw_path), fixture_path, output_fixture_path
            )
            calibration_plane_note = (
                "De-embedded fixture effects from the measured network via "
                f"rf_tools.touchstone.deembed_touchstone (fixture_path="
                f"{fixture_path!r}"
                + (f", output_fixture_path={output_fixture_path!r}" if output_fixture_path else "")
                + ") before comparison -- this is the calibration-plane "
                "normalization step."
            )
        else:
            calibration_plane_note = (
                "No fixture_path was supplied -- calibration-plane "
                "de-embedding was SKIPPED for this call. The simulated and "
                "measured networks are assumed to already be referenced to "
                "the same calibration plane (e.g. the VNA's own "
                "calibration already moved the reference plane to the DUT, "
                "or no physical fixture sits between them). Pass "
                "fixture_path to de-embed a known fixture network via "
                "rf_tools.touchstone.deembed_touchstone before comparison "
                "when one is present."
            )

        # --- Reference impedance normalization ---
        sim_z0 = np.asarray(sim_network.z0[0])
        meas_z0 = np.asarray(meas_network.z0[0])
        if sim_z0.shape != meas_z0.shape:
            raise CorrelationError(
                f"simulated network's z0 has {sim_z0.shape[0]} port(s) "
                f"worth of reference impedance but measured network's z0 "
                f"has {meas_z0.shape[0]} -- port count mismatch"
            )

        if not np.allclose(sim_z0, meas_z0, atol=1e-6):
            # skrf's own built-in renormalization (not a hand-derived
            # formula) -- mutates meas_network in place, per its own API.
            # sim_z0 (the first-frequency-point z0, same convention
            # cascade_touchstone's own z0 check uses) is passed rather than
            # sim_network.z0's full per-frequency array, which need not
            # share meas_network's frequency-point count at this stage
            # (the two networks aren't yet on a common grid -- that's
            # compare_touchstone's job, below); z0 is broadcast across
            # meas_network's own frequency points instead.
            meas_network.renormalize(sim_z0)
            reference_impedance_note = (
                f"Reference impedance mismatch detected (simulated z0="
                f"{sim_z0.tolist()}, measured z0={meas_z0.tolist()}) -- the "
                "measured network was renormalized to the simulated "
                "network's reference impedance via skrf.Network."
                "renormalize() before comparison."
            )
        else:
            reference_impedance_note = (
                f"Reference impedance already matched (z0={sim_z0.tolist()}) "
                "-- no renormalization needed."
            )

        # --- Frequency-grid normalization + quantified comparison ---
        # compare_touchstone (Phase 2, ticket #32) both brings the two
        # networks onto a common frequency grid (via interpolate_touchstone,
        # ticket #29) and quantifies the per-S-parameter difference --
        # reused via temp Touchstone files, not reimplemented. diff = b - a
        # = measured - simulated, i.e. "how far measurement is from the
        # simulated prediction."
        simulated_path = tmp / f"simulated.s{nports}p"
        measured_normalized_path = tmp / f"measured_normalized.s{nports}p"
        sim_network.write_touchstone(filename=str(simulated_path), form="ri")
        meas_network.write_touchstone(filename=str(measured_normalized_path), form="ri")

        comparison = compare_touchstone(str(simulated_path), str(measured_normalized_path))

    return {
        "comparison": comparison,
        "reference_impedance_note": reference_impedance_note,
        "calibration_plane_note": calibration_plane_note,
        "temperature_note": temperature_note,
        "temperature_detail": temperature_detail,
        "simulated_provenance": simulated_provenance,
        "measured_provenance": measured_provenance,
        "provenance": "CALCULATED",
    }
