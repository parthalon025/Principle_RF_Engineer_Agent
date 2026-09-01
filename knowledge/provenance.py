"""Source-type -> provenance tier / default authority rank (pure).

Per CONTEXT.md: datasheet/application_note sit at the manufacturer-spec
tier; standard/textbook/paper sit at the authoritative-reference tier.
Component-field provenance (ticket #4) belongs in a separate function
added here later, not in this ticket's scope.
"""

from __future__ import annotations

from knowledge.models import SourceType

MANUFACTURER_SPECIFIED = "MANUFACTURER-SPECIFIED"
LITERATURE_SUPPORTED = "LITERATURE-SUPPORTED"

_SOURCE_TYPE_TIER: dict[SourceType, str] = {
    SourceType.DATASHEET: MANUFACTURER_SPECIFIED,
    SourceType.APPLICATION_NOTE: MANUFACTURER_SPECIFIED,
    SourceType.STANDARD: LITERATURE_SUPPORTED,
    SourceType.TEXTBOOK: LITERATURE_SUPPORTED,
    SourceType.PAPER: LITERATURE_SUPPORTED,
}

# Lower rank sorts first / wins in `search_knowledge` ordering (ADR-0002).
_TIER_AUTHORITY_RANK: dict[str, int] = {
    MANUFACTURER_SPECIFIED: 20,
    LITERATURE_SUPPORTED: 40,
}


def provenance_tier_for(source_type: SourceType) -> str:
    """Return the evidence-hierarchy tier a source type defaults to."""
    return _SOURCE_TYPE_TIER[source_type]


def default_authority_rank(source_type: SourceType) -> int:
    """Return the default `documents.authority_rank` for a source type."""
    return _TIER_AUTHORITY_RANK[provenance_tier_for(source_type)]
