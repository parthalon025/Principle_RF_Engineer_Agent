from knowledge.models import SourceType
from knowledge.provenance import (
    LITERATURE_SUPPORTED,
    MANUFACTURER_SPECIFIED,
    default_authority_rank,
    provenance_tier_for,
)


def test_datasheet_and_application_note_are_manufacturer_specified():
    assert provenance_tier_for(SourceType.DATASHEET) == MANUFACTURER_SPECIFIED
    assert provenance_tier_for(SourceType.APPLICATION_NOTE) == MANUFACTURER_SPECIFIED


def test_standard_textbook_paper_are_literature_supported():
    assert provenance_tier_for(SourceType.STANDARD) == LITERATURE_SUPPORTED
    assert provenance_tier_for(SourceType.TEXTBOOK) == LITERATURE_SUPPORTED
    assert provenance_tier_for(SourceType.PAPER) == LITERATURE_SUPPORTED


def test_manufacturer_tier_outranks_literature_tier():
    # Lower authority_rank sorts first / wins (ADR-0002).
    assert default_authority_rank(SourceType.DATASHEET) < default_authority_rank(
        SourceType.STANDARD
    )
