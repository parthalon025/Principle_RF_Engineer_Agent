from knowledge.models import SourceType
from knowledge.provenance import (
    INFERRED,
    INTERNAL_HISTORY,
    LITERATURE_SUPPORTED,
    MANUFACTURER_SPECIFIED,
    UNKNOWN,
    component_field_provenance,
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


def test_design_record_is_internal_history():
    # Ticket #37: CONTEXT.md's "internal engineering history" evidence tier.
    assert provenance_tier_for(SourceType.DESIGN_RECORD) == INTERNAL_HISTORY


def test_literature_tier_outranks_internal_history_tier():
    # Evidence hierarchy (CONTEXT.md): authoritative reference > internal
    # engineering history. Lower authority_rank sorts first / wins.
    assert default_authority_rank(SourceType.STANDARD) < default_authority_rank(
        SourceType.DESIGN_RECORD
    )


# All four (extraction_confidence, physically_valid) combinations (ticket
# #11 acceptance criteria: one test per provenance-mapping combination).
def test_high_confidence_and_physically_valid_is_manufacturer_specified():
    assert component_field_provenance("high", True) == MANUFACTURER_SPECIFIED


def test_low_confidence_and_physically_valid_is_inferred():
    assert component_field_provenance("low", True) == INFERRED


def test_high_confidence_but_physically_invalid_is_unknown():
    # A bound violation overrides even a confident extraction (ADR-0003).
    assert component_field_provenance("high", False) == UNKNOWN


def test_low_confidence_and_physically_invalid_is_unknown():
    assert component_field_provenance("low", False) == UNKNOWN
