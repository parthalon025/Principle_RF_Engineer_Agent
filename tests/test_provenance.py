from knowledge.models import SourceType
from knowledge.provenance import (
    INFERRED,
    INTERNAL_HISTORY,
    LITERATURE_SUPPORTED,
    MANUFACTURER_SPECIFIED,
    PARTNER_RESEARCH_AUTHORITY_RANK,
    PATENT_AUTHORITY_RANK,
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


def test_patent_is_literature_supported():
    assert provenance_tier_for(SourceType.PATENT) == LITERATURE_SUPPORTED


def test_patent_ranks_below_a_peer_reviewed_paper():
    # A patent office examines for novelty/non-obviousness/candor, not for
    # whether a stated number was measured correctly or reproduces. Ranking
    # a patent level with a peer-reviewed paper would claim a review that
    # never happened -- see PATENT_AUTHORITY_RANK's own note.
    assert default_authority_rank(SourceType.PATENT) > default_authority_rank(SourceType.PAPER)


def test_patent_still_outranks_internal_history():
    # It is unvetted for technical accuracy, but it is still externally
    # published and permanently archived -- better evidence than this team's
    # own unreviewed precedent.
    assert default_authority_rank(SourceType.PATENT) < default_authority_rank(
        SourceType.DESIGN_RECORD
    )


def test_patent_default_rank_needs_no_per_document_override():
    # The point of _SOURCE_TYPE_AUTHORITY_RANK: a patent lands at its honest
    # rank without any caller remembering to pass authority_rank_override,
    # unlike the arXiv case which is a per-source (not per-type) override.
    assert default_authority_rank(SourceType.PATENT) == PATENT_AUTHORITY_RANK


# ADR-0029: partner_research (unpublished technical work from an outside
# research partner) is its own source type, resolving to LITERATURE_SUPPORTED
# but ranked strictly between patent and design_record.
def test_partner_research_is_literature_supported():
    assert provenance_tier_for(SourceType.PARTNER_RESEARCH) == LITERATURE_SUPPORTED


def test_partner_research_ranks_below_a_patent():
    # Unreviewed and unpublished -- no patent office examined it -- so it
    # must not outrank a granted patent.
    assert default_authority_rank(SourceType.PARTNER_RESEARCH) > default_authority_rank(
        SourceType.PATENT
    )


def test_partner_research_ranks_above_design_record():
    # It is outside work, not this team's own internal precedent, so it must
    # not be discounted down to design_record's internal-history rank.
    assert default_authority_rank(SourceType.PARTNER_RESEARCH) < default_authority_rank(
        SourceType.DESIGN_RECORD
    )


def test_partner_research_default_rank_needs_no_per_document_override():
    assert (
        default_authority_rank(SourceType.PARTNER_RESEARCH) == PARTNER_RESEARCH_AUTHORITY_RANK
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
