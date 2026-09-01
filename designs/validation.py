"""Pure validation for design-creation inputs (ticket #17; CONTEXT.md,
docs/adr/0006).

Both functions here are pure -- no DB access, no I/O. `extract_component_refs`
only pulls `component_id` references out of `architecture` for
`designs.db.create_design`'s I/O layer to existence-check against real
`components` rows; it never validates those ids itself (that needs a live
connection), matching the pure/I/O seam `knowledge/validation.py` and
`knowledge/db.py` already establish.
"""

from __future__ import annotations

from typing import Any

from designs.models import VerificationStatus


class InvalidRequirementsError(ValueError):
    """Raised by `validate_requirements` when `requirements` is not a dict
    keyed by `requirement_id`, or when one of its values is missing its
    mandatory `requirement` text field. Never raised for extra fields on a
    requirement -- only the shape `create_design` and `verification_items`
    auto-creation actually depend on is checked."""


def validate_requirements(requirements: Any) -> None:
    """Validate `requirements`'s shape: a dict keyed by `requirement_id`,
    each value itself a dict carrying a non-empty string `requirement`
    field. Raises `InvalidRequirementsError` naming exactly what's wrong
    -- not a dict at all, a value that isn't a dict, or a value missing
    `requirement` -- rather than a bare `TypeError`/`KeyError`, so the
    message identifies the offending `requirement_id` directly. Returns
    nothing; a well-formed `requirements` simply doesn't raise.
    """
    if not isinstance(requirements, dict):
        raise InvalidRequirementsError(
            "requirements must be a dict keyed by requirement_id, "
            f"got {type(requirements).__name__}"
        )
    for requirement_id, value in requirements.items():
        if not isinstance(value, dict):
            raise InvalidRequirementsError(
                f"requirements[{requirement_id!r}] must be a dict, got {type(value).__name__}"
            )
        requirement_text = value.get("requirement")
        if not isinstance(requirement_text, str) or not requirement_text:
            raise InvalidRequirementsError(
                f"requirements[{requirement_id!r}] is missing a non-empty 'requirement' "
                "text field"
            )


class InvalidVerificationStatusError(ValueError):
    """Raised by `verify_requirement` when `status` is not one of
    `VerificationStatus`'s four values (NOT VERIFIED/PASS/FAIL/MARGINAL)."""


def validate_verification_status(status: Any) -> None:
    """Validate that `status` is one of `VerificationStatus`'s legal
    values. Raises `InvalidVerificationStatusError` naming the offending
    value and the legal set; returns nothing when `status` is valid.
    """
    try:
        VerificationStatus(status)
    except ValueError as exc:
        legal = ", ".join(v.value for v in VerificationStatus)
        raise InvalidVerificationStatusError(
            f"status must be one of {legal}, got {status!r}"
        ) from exc


def _iter_component_refs(node: Any, block: str | None = None) -> list[tuple[str, int]]:
    """Depth-first walk of `node` (a JSON-shaped value drawn from
    `architecture`) yielding `(block, component_id)` for every
    `component_id` scalar found, where `block` is the nearest enclosing
    dict key -- the label `designs.db.create_design` names a dangling
    reference against. A `component_id` with no enclosing key (at
    `architecture`'s own top level) is reported under the literal block
    name "architecture". Internal to this module and `designs.db`, which
    needs the block label for its structured dangling-reference error;
    `extract_component_refs` is the public seam other callers use.
    """
    refs: list[tuple[str, int]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "component_id" and isinstance(value, int) and not isinstance(value, bool):
                refs.append((block or "architecture", value))
            else:
                refs.extend(_iter_component_refs(value, block=str(key)))
    elif isinstance(node, list):
        for item in node:
            refs.extend(_iter_component_refs(item, block=block))
    return refs


def extract_component_refs(architecture: dict) -> list[int]:
    """Return every `component_id` referenced anywhere in `architecture`
    (recursively, at any nesting depth -- under a list included), in the
    order encountered. Not deduplicated: `create_design` only needs to
    know which ids exist, and the same component appearing in two blocks
    is not itself an error. Pure -- no database access -- so it's testable
    against a hand-built dict fixture with zero, one, or many references.
    """
    return [component_id for _, component_id in _iter_component_refs(architecture)]
