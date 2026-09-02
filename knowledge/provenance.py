"""Source-type -> provenance tier / default authority rank (pure).

Per CONTEXT.md: datasheet/application_note sit at the manufacturer-spec
tier; standard/textbook/paper sit at the authoritative-reference tier.
Ticket #37 adds `design_record` at the "internal engineering history" tier
CONTEXT.md's evidence hierarchy already names -- below authoritative
reference, since it is the team's own precedent rather than a published
authority, but still well above general web material or LLM inference.

Ticket #11 adds `component_field_provenance`: the analogous pure mapping for
one extracted component specification field's provenance, from its
extraction confidence and whether it passed `knowledge.validation`'s
physical-plausibility bound (ADR-0003).
"""

from __future__ import annotations

from typing import Literal

from knowledge.models import SourceType

MANUFACTURER_SPECIFIED = "MANUFACTURER-SPECIFIED"
LITERATURE_SUPPORTED = "LITERATURE-SUPPORTED"
INTERNAL_HISTORY = "INTERNAL-HISTORY"
INFERRED = "INFERRED"
UNKNOWN = "UNKNOWN"

_SOURCE_TYPE_TIER: dict[SourceType, str] = {
    SourceType.DATASHEET: MANUFACTURER_SPECIFIED,
    SourceType.APPLICATION_NOTE: MANUFACTURER_SPECIFIED,
    SourceType.STANDARD: LITERATURE_SUPPORTED,
    SourceType.TEXTBOOK: LITERATURE_SUPPORTED,
    SourceType.PAPER: LITERATURE_SUPPORTED,
    SourceType.DESIGN_RECORD: INTERNAL_HISTORY,
}

# Lower rank sorts first / wins in `search_knowledge` ordering (ADR-0002).
_TIER_AUTHORITY_RANK: dict[str, int] = {
    MANUFACTURER_SPECIFIED: 20,
    LITERATURE_SUPPORTED: 40,
    INTERNAL_HISTORY: 60,
}


def provenance_tier_for(source_type: SourceType) -> str:
    """Return the evidence-hierarchy tier a source type defaults to."""
    return _SOURCE_TYPE_TIER[source_type]


def default_authority_rank(source_type: SourceType) -> int:
    """Return the default `documents.authority_rank` for a source type."""
    return _TIER_AUTHORITY_RANK[provenance_tier_for(source_type)]


def component_field_provenance(
    extraction_confidence: Literal["high", "low"], physically_valid: bool
) -> str:
    """Return the provenance tag for one extracted `components.specifications`
    field (ADR-0003, CONTEXT.md: Provenance).

    `physically_valid=False` always yields `UNKNOWN`, regardless of
    `extraction_confidence` -- a bound violation (e.g. a negative noise
    figure) is not something a confident read can override, since there's no
    human review step to adjudicate the two signals against each other.
    Otherwise, `"high"` confidence yields `MANUFACTURER_SPECIFIED` (a clean,
    unambiguous read) and `"low"` yields `INFERRED` (an ambiguous or
    low-confidence read).
    """
    if not physically_valid:
        return UNKNOWN
    return MANUFACTURER_SPECIFIED if extraction_confidence == "high" else INFERRED
