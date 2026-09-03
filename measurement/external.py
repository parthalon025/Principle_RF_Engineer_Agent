"""Externally-obtained test-iteration results (issue #89), following
directly from ADR-0012 (physical-instrument control leaves this codebase)
and ADR-0013 (the design loop's MEASUREMENT step's replacement data source).

WHY THIS LIVES IN `measurement/`: ADR-0012's own "Consequences" section says
it plainly -- ticket #90 deleted `measurement/vna.py` and the rest of the
SCPI/VISA instrument-actuation package, leaving this module the only thing
in the package, and the package's own purpose inverted: instead of "this
system reaches out to a physical instrument," it is now "measured data
enters this system from outside it." That is a deliberate placement, not a
leftover.

WHAT THIS MODULE DOES: an engineer who measured a prototype on equipment
this system never touched -- a bench VNA, a range, a chamber, anything --
brings back a Touchstone (`.sNp`) file. `record_external_measurement`
parses it via `rf_tools.touchstone.analyze_touchstone` (Phase 2, reused
completely unmodified -- no Touchstone-format parsing is re-implemented
here) and returns a result dict carrying `MEASURED` provenance and a
top-level `touchstone_file` key.

WHY EXTERNALLY-OBTAINED DATA STILL EARNS `MEASURED`, NOT SOMETHING LOWER:
this project's evidence hierarchy (`CONTEXT.md`: "measured > validated
simulation > ...") ranks a result by how it was physically obtained -- a
real instrument reading of a real prototype -- not by whether THIS SYSTEM
was the one that actuated the instrument. A Touchstone file from a range
test run entirely by a human, on hardware this codebase has never seen,
still reports what a real device actually did in the real world, which is
exactly the property that earns the top evidence tier -- provenance here
is justified by "a physical instrument produced this number," which is
just as true whether this system or a human hand turned the knobs.

THE RESULT SHAPE THIS PRODUCES, ON PURPOSE, MATCHES WHAT `rf_tools.
correlation._result_to_network` ALREADY ACCEPTS: that function already
coerces a dict carrying a `"touchstone_file"` (or `"file"`) key straight
into an `skrf.Network` by loading the path directly (see that module's
docstring's "WHAT'S ACTUALLY USABLE AS SIMULATED INPUT TODAY" section).
`analyze_touchstone`'s own return dict already carries a `"file"` key (the
resolved path); this module adds a `"touchstone_file"` alias of the same
value so a MEASUREMENT decision carrying this result needs zero changes to
`rf_tools/correlation.py` or its `CORRELATION` design-loop handler to be
consumed downstream -- the whole point of reusing an already-accepted
shape instead of inventing a new one CORRELATION would need to learn.

THE LAB REPORT AND NOTES ARE STORED, NEVER PARSED, PER ADR-0013: `lab_report`
(a path, URL, or any other free-form reference the caller wants to keep) and
`notes` (test date, chamber/range, calibration standard, ambient conditions,
anything else in prose) ride along on the returned dict UNTOUCHED -- this
function never opens, reads, or extracts a number from either one. ADR-0013
considered and rejected auto-extracting measured values from an unstructured
lab report (reusing `knowledge/ingest.py`+`knowledge/extract.py`'s
provenance-aware document-extraction pipeline) as a materially larger
feature deserving its own dedicated design session; "a lab report may be
attached" is honored here as *attachable context of any kind*, not as a
second, competing data-extraction path. A value only enters this system
when a human puts it into the structured Touchstone data itself.

WHAT THIS MODULE DELIBERATELY DOES NOT DO: no VISA resource, no live
instrument, no SCPI traffic, and no instrument-actuation gate call. There
is no instrument-actuation decision to gate here at all -- "may this exact
SCPI command sequence run" is meaningless when no SCPI command is ever
sent. (Ticket #90 removed the gate that question belonged to, along with
the whole SCPI/VISA package: `measurement/base.py`'s
`check_physical_actuation_gate` no longer exists anywhere in this
codebase, so do not go looking for it -- see ADR-0012 and
`docs/SECURITY.md`, which keeps the reasoning for why such a gate matters
as a design principle for whenever instrument control returns to scope.)
The design loop's OWN, separate, higher-level
MEASUREMENT gate (`orchestration/design_loop.py`'s `GATED_STEPS`, checked by
`orchestration.approval.check_loop_step_approval_gate` before
`_handle_measurement` ever runs) still applies unchanged -- "should this
design accept this measurement evidence at all" is a business decision
orthogonal to how the evidence was physically produced, and ADR-0013's own
"Consequences" section says exactly this.
"""

from typing import Any

from rf_tools.touchstone import analyze_touchstone


class ExternalMeasurementError(ValueError):
    """Raised when a Touchstone file brought back from external testing
    cannot be turned into evidence -- missing, unreadable, or not a valid
    Touchstone network -- naming the offending file in every case, so a
    caller sees exactly which file to check rather than the MEASUREMENT
    step silently recording empty/fabricated evidence. A `ValueError`
    subclass, matching `rf_tools.touchstone`'s and `rf_tools.correlation.
    CorrelationError`'s own convention of raising a `ValueError` (or a
    `ValueError` subclass) for bad input, so an existing `except ValueError`
    caller still catches this."""


def record_external_measurement(
    touchstone_file: str,
    lab_report: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Turn a Touchstone file an engineer measured on independent equipment
    into a `MEASURED`-provenance design-loop MEASUREMENT result (CONTEXT.md's
    "Test iteration").

    `touchstone_file`: path to the `.sNp` file. Parsed via `rf_tools.
    touchstone.analyze_touchstone` (Phase 2, unmodified) -- this function
    re-implements no Touchstone-format parsing of its own. A missing path
    raises `ExternalMeasurementError` naming it; a path that exists but
    isn't a readable/valid Touchstone network (corrupt data, wrong format)
    raises the same, naming the file and the underlying parse failure --
    either way, MEASUREMENT never records an empty or fabricated result.

    `lab_report` (optional): a reference to a lab report covering this test
    iteration -- a file path, a URL, a document ID, whatever the caller
    already has. Stored on the returned dict verbatim. NEVER opened, read,
    or parsed for numbers -- see this module's docstring's ADR-0013
    section. A value only enters the structured result when a human puts it
    directly into the Touchstone data (via `touchstone_file`).

    `notes` (optional): free-text context -- test date, chamber or range,
    calibration standard, ambient conditions, anything else worth recording
    alongside the reading. Stored verbatim, same as `lab_report`; never
    parsed for numbers.

    Returns a dict with everything `analyze_touchstone` returns (`file`,
    `ports`, `frequency_start_hz`, `frequency_stop_hz`, `points`, `z0`, and
    -- for a 2+-port network -- `s11_min_db`/`s21_max_db`/their frequencies),
    plus:
      - `touchstone_file`: the same resolved path as `file`, added so this
        result is directly consumable by `rf_tools.correlation.
        _result_to_network` with zero changes to `rf_tools/correlation.py`
        (see this module's docstring).
      - `provenance`: always `"MEASURED"` -- see this module's docstring for
        why externally-obtained data still earns the top evidence tier.
      - `source`: always `"external_test_iteration"` -- an honest marker of
        how this evidence was obtained, kept even though this is now the
        only MEASUREMENT path (ticket #90 removed the instrument-actuation
        package this module's docstring describes ADR-0012/ADR-0013
        replacing), so a decision's own result stays self-describing
        without depending on the caller already knowing which module
        produced it.
      - `lab_report` / `notes`: passed through exactly as given (including
        `None` when omitted) -- never read for numeric values.
    """
    try:
        analysis = analyze_touchstone(touchstone_file)
    except FileNotFoundError as exc:
        raise ExternalMeasurementError(
            f"Touchstone file {touchstone_file!r} does not exist -- the "
            "MEASUREMENT step records no evidence without a real Touchstone "
            "reading brought back from the test iteration. Check the path "
            "and try again once the file is in place."
        ) from exc
    except Exception as exc:
        raise ExternalMeasurementError(
            f"Touchstone file {touchstone_file!r} could not be read as a "
            f"Touchstone network ({type(exc).__name__}: {exc}) -- the "
            "MEASUREMENT step records no evidence without a real, "
            "parseable Touchstone reading. Confirm the file is a genuine, "
            "uncorrupted .sNp export from the test equipment."
        ) from exc

    return {
        **analysis,
        "touchstone_file": analysis["file"],
        "provenance": "MEASURED",
        "source": "external_test_iteration",
        "lab_report": lab_report,
        "notes": notes,
    }
