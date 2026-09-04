"""Tests for knowledge/component_resolution.py (ticket #67).

Uses the real local Postgres via the `db_conn` fixture (tests/conftest.py),
matching tests/test_db.py's philosophy -- rolled back at teardown, so no
separate cleanup fixture is needed even though `reconcile_components`
writes real `components` rows through `knowledge.db.upsert_component`.
"""

import os

import psycopg
import pytest

from knowledge import db
from knowledge.component_resolution import (
    ResolvedComponentIdentity,
    normalize_manufacturer,
    normalize_part_number,
    reconcile_components,
    reconcile_components_from_matches,
    resolve_identity,
)
from knowledge.models import Classification, ComponentCategory, DocumentDraft, SourceType
from knowledge.sourcing_common import ComponentMatch


def _seed_document(conn, checksum: str) -> int:
    draft = DocumentDraft(
        title=f"Seeded Doc {checksum}",
        source_type=SourceType.DATASHEET,
        classification=Classification.PUBLIC,
        license="manufacturer-datasheet",
        checksum_sha256=checksum,
        metadata={"classification": Classification.PUBLIC.value},
    )
    row = db.insert_document(conn, draft, authority_rank=20)
    return row["id"]


def _match(distributor: str, manufacturer: str, mpn: str, url: str = "https://x/y.pdf"):
    return ComponentMatch(
        distributor=distributor,
        manufacturer=manufacturer,
        manufacturer_part_number=mpn,
        datasheet_url=url,
    )


# ---------------------------------------------------------------------------
# normalize_manufacturer / normalize_part_number
# ---------------------------------------------------------------------------


def test_normalize_manufacturer_casefolds_and_collapses_whitespace():
    assert normalize_manufacturer("  Texas   Instruments ") == normalize_manufacturer(
        "texas instruments"
    )


def test_normalize_manufacturer_does_not_merge_different_companies():
    assert normalize_manufacturer("Texas Instruments") != normalize_manufacturer(
        "Texas Instruments Incorporated"
    )


def test_normalize_part_number_uppercases_and_strips_whitespace():
    assert normalize_part_number(" lm358dr ") == "LM358DR"
    assert normalize_part_number("LM358 DR") == "LM358DR"


def test_normalize_part_number_preserves_package_and_reel_suffix_distinctions():
    """CONTEXT.md: package/tape-and-reel suffix is part of identity -- these
    must NOT normalize to the same string."""
    assert normalize_part_number("LM358DR") != normalize_part_number("LM358PWR")
    assert normalize_part_number("AD8318ACPZ-R7") != normalize_part_number("AD8318ACPZ-RL7")


# ---------------------------------------------------------------------------
# resolve_identity (pure grouping, no DB)
# ---------------------------------------------------------------------------


def test_resolve_identity_groups_same_part_across_distributors_despite_formatting_noise():
    matches = [
        _match("digikey", "Texas Instruments", "LM358DR"),
        _match("mouser", " texas instruments ", " lm358dr "),
        _match("nexar", "Texas Instruments", "LM358DR"),
    ]

    resolved = resolve_identity(matches)

    assert len(resolved) == 1
    assert resolved[0].manufacturer == "Texas Instruments"
    assert resolved[0].part_number == "LM358DR"
    assert [m.distributor for m in resolved[0].sources] == ["digikey", "mouser", "nexar"]


def test_resolve_identity_keeps_same_manufacturer_different_package_as_two_groups():
    matches = [
        _match("digikey", "Texas Instruments", "LM358DR"),
        _match("mouser", "Texas Instruments", "LM358PWR"),
    ]

    resolved = resolve_identity(matches)

    assert len(resolved) == 2
    part_numbers = {r.part_number for r in resolved}
    assert part_numbers == {"LM358DR", "LM358PWR"}


def test_resolve_identity_keeps_different_manufacturers_as_two_groups():
    matches = [
        _match("digikey", "Texas Instruments", "PART1"),
        _match("mouser", "Analog Devices", "PART1"),
    ]

    resolved = resolve_identity(matches)

    assert len(resolved) == 2


def test_resolve_identity_first_seen_member_wins_canonical_casing():
    matches = [
        _match("digikey", "Texas Instruments", "LM358DR"),
        _match("mouser", "TEXAS INSTRUMENTS", "lm358dr"),
    ]

    resolved = resolve_identity(matches)

    assert len(resolved) == 1
    assert resolved[0].manufacturer == "Texas Instruments"
    assert resolved[0].part_number == "LM358DR"


def test_resolve_identity_returns_dataclass_instances():
    resolved = resolve_identity([_match("digikey", "Acme", "P1")])
    assert isinstance(resolved[0], ResolvedComponentIdentity)


# ---------------------------------------------------------------------------
# reconcile_components (DB-backed, real Postgres via db_conn)
# ---------------------------------------------------------------------------


def test_reconcile_components_same_part_across_sources_writes_one_row(db_conn):
    matches = [
        _match("digikey", "Acme RF", "T67-SAME-1"),
        _match("mouser", "acme rf", "t67-same-1"),
    ]

    reconciled = reconcile_components(db_conn, matches, ComponentCategory.AMPLIFIER)

    assert len(reconciled) == 1
    assert set(reconciled[0]["sources"]) == {"digikey", "mouser"}

    with db_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM components WHERE manufacturer = %s", ("Acme RF",))
        (count,) = cur.fetchone()
    assert count == 1


def test_reconcile_components_different_package_across_sources_writes_two_rows(db_conn):
    """The synthetic same-manufacturer-different-package case the ticket
    explicitly asks to be tested against: two distinct orderable parts must
    NOT collapse into one row."""
    matches = [
        _match("digikey", "Acme RF", "T67-PKG-DR"),
        _match("mouser", "Acme RF", "T67-PKG-PWR"),
    ]

    reconciled = reconcile_components(db_conn, matches, ComponentCategory.AMPLIFIER)

    assert len(reconciled) == 2
    part_numbers = {r["part_number"] for r in reconciled}
    assert part_numbers == {"T67-PKG-DR", "T67-PKG-PWR"}

    with db_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM components WHERE manufacturer = %s", ("Acme RF",))
        (count,) = cur.fetchone()
    assert count == 2


def test_reconcile_components_unrelated_different_manufacturer_is_not_merged(db_conn):
    matches = [
        _match("digikey", "Acme RF", "T67-DIFFMFR-1"),
        _match("mouser", "Beta Semi", "T67-DIFFMFR-1"),
    ]

    reconciled = reconcile_components(db_conn, matches, ComponentCategory.AMPLIFIER)

    assert len(reconciled) == 2


def test_reconcile_components_preserves_existing_specifications(db_conn):
    """This module has no per-field spec data of its own -- reconciliation
    must never wipe specifications a prior extract_components run already
    stored (knowledge/db.py's upsert_component otherwise overwrites
    specifications wholesale on every call)."""
    existing_specs = {
        "gain_db": {"value": 20.0, "unit": "dB", "provenance": "MANUFACTURER-SPECIFIED"}
    }
    db.upsert_component(
        db_conn,
        manufacturer="Acme RF",
        part_number="T67-PRESERVE-1",
        category="amplifier",
        specifications=existing_specs,
        datasheet_document_id=None,
    )

    matches = [_match("digikey", "Acme RF", "T67-PRESERVE-1")]
    reconciled = reconcile_components(db_conn, matches, ComponentCategory.AMPLIFIER)

    assert reconciled[0]["row"]["specifications"] == existing_specs


def test_reconcile_components_links_datasheet_document_id_from_first_available_source(db_conn):
    doc_id_mouser = _seed_document(db_conn, "t67-doc-mouser" * 3)

    matches = [
        _match("digikey", "Acme RF", "T67-DOC-1"),
        _match("mouser", "Acme RF", "T67-DOC-1"),
    ]

    reconciled = reconcile_components(
        db_conn,
        matches,
        ComponentCategory.AMPLIFIER,
        # digikey's own ingest didn't succeed (no entry), mouser's did.
        datasheet_document_ids={"mouser": doc_id_mouser},
    )

    assert reconciled[0]["row"]["datasheet_document_id"] == doc_id_mouser


def test_reconcile_components_without_document_ids_leaves_datasheet_document_id_null(db_conn):
    matches = [_match("digikey", "Acme RF", "T67-NODOC-1")]

    reconciled = reconcile_components(db_conn, matches, ComponentCategory.AMPLIFIER)

    assert reconciled[0]["row"]["datasheet_document_id"] is None


def test_reconcile_components_category_is_stored_as_given(db_conn):
    matches = [_match("digikey", "Acme RF", "T67-CAT-1")]

    reconciled = reconcile_components(db_conn, matches, ComponentCategory.FILTER)

    assert reconciled[0]["row"]["category"] == "filter"


# ---------------------------------------------------------------------------
# reconcile_components_from_matches: the connection-owning, tool-facing
# entrypoint (agent/main.py's reconcile_component_sources /
# mcp_server/server.py's equivalent). Commits its own connection, so --
# unlike the db_conn-fixture tests above -- cleanup is manual (mirrors
# tests/test_extract.py's cleanup_documents fixture rationale).
# ---------------------------------------------------------------------------


def _delete_components(manufacturer: str, part_number: str) -> None:
    conn = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM components WHERE manufacturer = %s AND part_number = %s",
                (manufacturer, part_number),
            )
    finally:
        conn.close()


def test_reconcile_components_from_matches_accepts_raw_dicts_and_commits():
    matches = [
        {
            "distributor": "digikey",
            "manufacturer": "Acme RF",
            "manufacturer_part_number": "T67-TOOL-1",
            "datasheet_url": "https://x/y.pdf",
        },
        {
            "distributor": "mouser",
            "manufacturer": "acme rf",
            "manufacturer_part_number": "t67-tool-1",
        },
    ]

    try:
        result = reconcile_components_from_matches(matches, "amplifier")

        assert result["status"] == "reconciled"
        assert len(result["components"]) == 1
        assert set(result["components"][0]["sources"]) == {"digikey", "mouser"}
        assert result["components"][0]["row"]["category"] == "amplifier"
    finally:
        _delete_components("Acme RF", "T67-TOOL-1")


def test_reconcile_components_from_matches_rejects_unknown_category():
    matches = [_match("digikey", "Acme RF", "T67-TOOL-BADCAT")]
    with pytest.raises(ValueError):
        reconcile_components_from_matches(matches, "not-a-real-category")
