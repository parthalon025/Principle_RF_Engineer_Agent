"""The first test in the repo that exercises `documents`/`document_chunks`
(ADR-0001/ADR-0002/ADR-0004, `knowledge/ingest.py` + `knowledge/db.py`) and
`material_properties` (ADR-0015, `designs/material_properties.py`) together,
against a live database, with real data end to end.

Issue #458 found this had never been proven: a 2026-09-10 direct query of
the live local database found both `documents` and `material_properties` at
zero rows, despite `knowledge/ingest.py` and `designs/material_properties.py`
each already having their own module-scoped tests. Neither of those existing
suites ever calls the other module, so nothing in the repo had ever run
ingest -> store -> retrieve -> resolve as one real, live-database sequence.
This file is that sequence.

WHY THE FIXTURE TEXT IS REAL, NOT A PLACEHOLDER LIKE THIS FILE'S SIBLINGS.
Every other `_write_pdf`-built fixture in tests/test_ingest.py and
tests/test_read.py uses invented placeholder text ("Widget Amplifier
Datasheet, Gain: 20 dB typical.") because those tests are only proving
`ingest_document`'s own mechanics -- what the text says has never mattered.
Issue #458's acceptance criterion is explicitly "real data, not just
synthetic fixtures", so the sentences below are copied verbatim, unchanged,
from a real, verified, open-access paper: Ozden, K., Ozer, A., Yucedag,
O.M. & Kocer, H. 2016, "Polarization-Independent Metamaterial Based Dual
Band Absorber For Stealth Applications In Microwave Bands," IU-JEEE
16(2):3001-3006 -- fetched in full via DergiPark
(https://dergipark.org.tr/tr/download/article-file/226127) on 2026-09-10 and
independently corroborated (title/authors/journal/volume/pages) via a web
search matching this project's own already-published citation of it in
RUNNING-LISTS.md. Only the PDF *container* is hand-built, via this
project's own established `write_pdf` fixture helper (tests/conftest.py) --
matching every other ingest test's no-third-party-PDF-library convention --
not the words inside it.

ONE HONEST GAP, RECORDED HERE RATHER THAN PAPERED OVER: the DOI issue #458
gives for this paper, `10.16984/saufenbilder.62549`, returns HTTP 404 from
doi.org as of this verification (2026-09-10) -- "saufenbilder" is Sakarya
University's journal-of-science DOI prefix, not IU-JEEE's, so this looks
like a mismatched/unregistered DOI carried over from an earlier research
pass, not evidence the paper itself is fake (title, authors, journal,
volume and page range all match the real, independently fetched PDF
byte-for-byte). Recorded in `extra_metadata` on the ingested row below
instead of silently repeating the unresolving DOI as if it were confirmed.

WHY search_lexical, NOT search_semantic. `knowledge.db.search_semantic`
requires a populated `embedding`/`embedding_local` column, which
`insert_chunks` deliberately leaves NULL -- embedding is issue #2's job, a
separate step (`knowledge.index`) `ingest_document` does not call. Exercising
it here would mean this test's pass/fail depended on a live local embedding
backend (Ollama/LM Studio) being up, which is not guaranteed in every
environment this suite runs in. `search_lexical` needs nothing beyond
Postgres itself and is exactly as real a `knowledge/db.py` retrieval path,
so it is what proves the "retrieve" leg of the round trip.

WHY THIS TEST ROLLS BACK ITS `material_properties` ROW INSTEAD OF DELETING
IT. Mirrors tests/test_material_properties.py's own
`TestInsertWrappersEnforceTheVocabulary` -- a fresh connection, never
committed, rolled back in `finally`. `documents`/`document_chunks` can't use
that same trick because `ingest_document` opens and commits its own pooled
connection internally (hence `cleanup_documents`'s explicit DELETE); a
hand-opened, never-committed connection has no such constraint.

WHAT THIS TEST DOES *NOT* PROVE. It does not, by itself, satisfy issue
#458's "at least the 4 open-access papers are real rows in `documents`"
acceptance criterion -- a pytest fixture that deletes what it inserts on
teardown cannot be the thing that leaves a persistent row behind. That
criterion is satisfied separately, by really running `ingest_document`
against the real fetched papers with no cleanup afterward (see the issue's
resolution comment for the verification query). This test's job is
narrower and different: prove the *mechanism* -- ingest, store, retrieve,
and resolve -- actually works end to end against a live database, using
real data, which is precisely the thing that had never been exercised.
"""

from __future__ import annotations

import os

import psycopg
from conftest import extraction_error, write_pdf

from designs.material_properties import (
    insert_material_property_entry,
    resolve_material_property_from_db,
)
from knowledge import db
from knowledge.ingest import ingest_document
from knowledge.provenance import LITERATURE_SUPPORTED


def test_ingest_document_and_material_properties_round_trip(
    tmp_path, cleanup_documents, no_ocr
):
    pdf_path = tmp_path / "ozden2016_iujeee_excerpt.pdf"
    write_pdf(
        pdf_path,
        [
            "Polarization-Independent Metamaterial Based Dual Band Absorber",
            "For Stealth Applications In Microwave Bands",
            "Kadir Ozden, Ahmet Ozer, O. Mert Yucedag and Hasan Kocer",
            "IU-JEEE Vol. 16(2), (2016), 3001-3006",
            "The first layer is a periodically shaped metallic layer which is",
            "copper, the second layer is a dielectric layer which is FR-4, and",
            "the third layer is a continuous metallic layer which is also copper.",
            "FR-4 has 1.6 mm thickness and has 3.6 relative dielectric",
            "permittivity and 0.03 loss tangent.",
        ],
    )

    # --- ingest ------------------------------------------------------------
    result = ingest_document(
        file_path=str(pdf_path),
        source_type="paper",
        license="open-access (DergiPark/IU-JEEE; exact license terms not independently verified)",
        classification="PUBLIC",
        title_override=(
            "Polarization-Independent Metamaterial Based Dual Band Absorber For "
            "Stealth Applications In Microwave Bands (excerpt, real text)"
        ),
        author="Kadir Ozden, Ahmet Ozer, O. Mert Yucedag, Hasan Kocer",
        extra_metadata={
            "doi_as_cited_by_issue_458": "10.16984/saufenbilder.62549",
            "doi_resolution_note": (
                "doi.org returns HTTP 404 for this DOI as of 2026-09-10 -- "
                "'saufenbilder' is Sakarya University's Journal of Science DOI "
                "prefix, not IU-JEEE's. The paper itself is independently "
                "confirmed real (title/authors/journal/volume/pages match the "
                "actual fetched PDF); only the DOI string is unresolved."
            ),
            "source_note": (
                "Verbatim excerpt of the real paper, fetched via DergiPark on "
                "2026-09-10 (issue #458); not the full 6-page document."
            ),
        },
    )
    cleanup_documents.append(result["document_id"])

    assert result["status"] == "ingested"
    assert result["extraction_status"] == "ok", extraction_error(result["document_id"])
    assert result["chunk_count"] >= 1

    # --- retrieve: knowledge/db.py's search_lexical must find the real
    # content by a distinctive phrase actually present in it.
    conn = db.get_connection()
    try:
        hits = db.search_lexical(
            conn, "relative dielectric permittivity", document_id=result["document_id"]
        )
    finally:
        conn.close()
    assert len(hits) >= 1
    assert any("3.6" in hit["content"] for hit in hits)

    # --- store + resolve: a material_properties row citing the document we
    # just ingested (by its real, live document_id), round-tripped through
    # a real DB read and then through
    # designs.material_properties.resolve_material_property.
    citation = (
        "Ozden, Ozer, Yucedag & Kocer 2016, IU-JEEE 16(2):3001-3006 -- "
        f"ingested as documents.id={result['document_id']} in this test run"
    )
    mp_conn = psycopg.connect(os.environ["DATABASE_URL"])
    try:
        insert_material_property_entry(
            mp_conn,
            material="FR4",
            property_name="eps_r",
            frequency_low_hz=7.0e9,
            frequency_high_hz=10.0e9,
            value=3.6,
            unit="unitless",
            provenance=LITERATURE_SUPPORTED,
            citation=citation,
        )
        resolved = resolve_material_property_from_db(
            mp_conn, material="FR4", property_name="eps_r", frequency_hz=9.0e9
        )
    finally:
        # Never committed -- the real material_properties table is untouched
        # by this test, matching tests/test_material_properties.py's own
        # DB-backed test isolation.
        mp_conn.rollback()
        mp_conn.close()

    assert resolved["status"] == "material_entries"
    assert resolved["low"] == resolved["high"] == 3.6
    assert resolved["unit"] == "unitless"
    assert any(entry["citation"] == citation for entry in resolved["entries"])
