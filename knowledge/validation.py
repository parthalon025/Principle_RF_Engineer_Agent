"""Pure physical-plausibility validation for component specification field
values (ADR-0003, CONTEXT.md: Component).

`validate_field` returns a `ValidationResult`, it never raises -- a bound
violation is data to record on the field (`provenance: UNKNOWN`, via
`knowledge.provenance.component_field_provenance`), not a caller error, per
ticket #11's acceptance criteria. Style matches `rf_tools/calculations.py`'s
domain checks, but returns instead of raising.

Bounds are keyed by field name, not by (category, field) pair: the same
field name denotes the same physical quantity everywhere it appears across
the ten starter categories (e.g. `insertion_loss_db` means the same thing on
a filter, a coupler_splitter, or a switch), so one bound table covers all of
them. A field with no entry here (e.g. `polarization`, a string; `gain_db`,
which can legitimately be negative) always validates as physically valid --
"no bound defined" is not the same as "no violation possible".
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from numbers import Real
from typing import Any


@dataclass(frozen=True)
class ValidationResult:
    """Outcome of validating one field value against its physical bound."""

    physically_valid: bool
    error: str | None = None


# field_name -> (predicate, human-readable bound description). ADR-0003's
# literal list covers nf_db/attenuation_db/insertion_loss_db/coupling_db/
# isolation_db/vswr/tolerance_pct/switching_time_ns/power_rating_w/q_factor.
# conversion_loss_db is added here (not in that literal list) so the mixer
# category -- whose fields are otherwise all unbounded -- has a bounded
# field to validate; see the report for this assumption. It rests on the
# same physical reasoning already applied to insertion_loss_db: a loss
# quantity cannot be negative.
_BOUNDS: dict[str, tuple[Callable[[float], bool], str]] = {
    "nf_db": (lambda v: v >= 0, ">= 0 (a negative noise figure is not physically possible)"),
    "attenuation_db": (lambda v: v >= 0, ">= 0"),
    "insertion_loss_db": (lambda v: v >= 0, ">= 0"),
    "conversion_loss_db": (lambda v: v >= 0, ">= 0"),
    "coupling_db": (lambda v: v >= 0, ">= 0"),
    "isolation_db": (lambda v: v >= 0, ">= 0"),
    "vswr": (lambda v: v >= 1, ">= 1"),
    "tolerance_pct": (lambda v: v >= 0, ">= 0"),
    "switching_time_ns": (lambda v: v >= 0, ">= 0"),
    "power_rating_w": (lambda v: v > 0, "> 0"),
    "q_factor": (lambda v: v > 0, "> 0"),
}


def validate_field(field: str, value: Any) -> ValidationResult:
    """Validate one specification field's value against its physical bound.

    A field with no entry in `_BOUNDS` always returns `physically_valid=True`
    regardless of value (including non-numeric values like `polarization`).
    A field that does have a bound but was given a non-numeric value is
    itself a validation failure -- the bound can't be checked, and that's a
    signal worth recording, not silently passing.
    """
    bound = _BOUNDS.get(field)
    if bound is None:
        return ValidationResult(physically_valid=True)

    predicate, description = bound
    if not isinstance(value, Real) or isinstance(value, bool):
        return ValidationResult(
            physically_valid=False,
            error=f"{field} must be numeric to validate against bound {description}, got {value!r}",
        )
    if predicate(value):
        return ValidationResult(physically_valid=True)
    return ValidationResult(
        physically_valid=False, error=f"{field} must be {description}, got {value}"
    )
