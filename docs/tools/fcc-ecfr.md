# FCC rules via eCFR Title 47 API

The eCFR ("electronic Code of Federal Regulations") is the U.S. government's own free, no-login web republication of federal regulations, kept current within about two business days of each change [ecfr.gov/reader-aids/understanding-the-ecfr/what-is-the-ecfr]; its "versioner" REST API is the machine-readable door into that same content, returning JSON or XML instead of a page meant for a human to read. This repo uses it to pull FCC Part 15 (unlicensed-device emission limits) and other Title 47 rule text — the actual legal ceilings an antenna/EM-surface design has to clear — straight into the knowledge base as `source_type='standard'` evidence, the same authoritative-reference tier as a 3GPP or ETSI standard.

## What it is

eCFR is jointly authorized and maintained by the Administrative Committee of the Federal Register (ACFR), which tasked the National Archives' Office of the Federal Register (OFR) and the Government Publishing Office (GPO) with developing and running it as "an informational resource," with the stated long-term goal of eventually becoming the ACFR's officially recognized publication [ecfr.gov/reader-aids/understanding-the-ecfr/what-is-the-ecfr]. It is not that yet: "those relying on it for legal research should verify their results against the most current official edition of the CFR, the daily Federal Register, and the List of CFR Sections Affected (LSA)" — i.e. engineering reference is fine, formal regulatory sign-off is not, without a cross-check [same page]. The versioner API itself carries no separate version number in its docs; its OpenAPI (Swagger 2.0) description groups it with two sibling APIs — Search and Admin — under one "eCFR API Documentation" spec served live at `www.ecfr.gov/developers/documentation/api/v1.json` [fetched directly, 2026-09-09].

## Full capabilities

Confirmed directly from that live OpenAPI spec, three services, all unauthenticated (no `securityDefinitions` in the spec, and the endpoints this repo already calls are confirmed no-auth in the adapter's own docstring):

- **Versioner Service** — `GET .../versioner/v1/titles.json` (status of every title: name, `latest_amended_on`, `latest_issue_date`, `up_to_date_as_of`, whether it's reserved or mid-reprocessing); `GET .../versioner/v1/structure/{date}/title-{title}.json` (the title's full hierarchy — subtitle/chapter/subchapter/part/subpart/section/appendix — as JSON, structure only, no body text); `GET .../versioner/v1/full/{date}/title-{title}.xml` (the actual rule text as XML, filterable down to a specific part/subpart/section/appendix via query params — "the largest title source xml files can be dozens of megabytes"); `GET .../versioner/v1/versions/title-{title}.json` (every section/appendix inside a title, with paging and an `issue_date` range filter — this is the point-in-time version list); `GET .../versioner/v1/ancestry/{date}/title-{title}.json` (walks a given node back up to its title).
- **Search Service** — `GET .../search/v1/results` (full-text search with `query`, `agency_slugs[]`, `date`, `last_modified_*` filters, paging and sort) plus `count`, `counts/daily`, `counts/hierarchy`, `counts/titles`, `suggestions`, and `summary` variants of the same filtered query.
- **Admin Service** — `GET .../admin/v1/agencies.json` (agency hierarchy/metadata) and `.../admin/v1/corrections.json` / `.../admin/v1/corrections/title/{title}.json` (eCFR's own logged editorial-error corrections, with the date the error occurred and the date it was fixed).

The XML format is a Federal-Register-specific DTD, not general-purpose XHTML: nested `<DIV1>`…`<DIV9>` elements typed by level (`TYPE="TITLE"`, `"PART"` — a part is specifically `<DIV5>` — etc.), `<HEAD>` for the heading text, and `<P>`/`<PSPACE>`/`<FP>`/`<P-1>` for body paragraphs, per GPO's own eCFR XML User Guide [github.com/usgpo/bulk-data ECFR-XML-User-Guide.md, fetched directly] — the same shape the adapter's docstring reports encountering live.

## Integrations & interfaces

Plain unauthenticated HTTPS/JSON and HTTPS/XML — no client library, SDK, or API key. No documented rate limit was found in the OpenAPI spec, the developer-resources pages, or the response headers of a live call (no `X-RateLimit-*` headers observed); this doc does not assert a number that wasn't found. `robots.txt` blocks crawler indexing of `/api/versioner/v1/full/` specifically (a courtesy against search engines hammering the largest payloads), not a rate limit on programmatic callers [ecfr.gov/robots.txt].

## Licensing & cost

Free, zero registration, at every endpoint used. The regulation text itself is a work of the U.S. Government and carries no copyright: "Copyright protection under this title is not available for any work of the United States Government" (17 U.S.C. § 105(a), text confirmed at copyright.gov/title17). eCFR's own legal-status guidance repeats the caveat above — accurate but not (yet) the ACFR's official edition — which is a currency/authoritativeness distinction, not a licensing one.

## How this repo uses it today

`knowledge/sourcing/fcc_ecfr.py`'s `ingest_fcc_rule(part, *, license, classification, title=47, ...)` uses exactly two of the endpoints above. `_resolve_as_of_date()` calls `titles.json` and reads back Title 47's `up_to_date_as_of` date — the module deliberately never accepts a caller-supplied date, because an arbitrary historical date can 404 against `full/`, confirmed directly during this ticket's research. `_full_text_url()` then calls `full/{date}/title-{title}.xml?part={part}` for that resolved date. `_xml_to_text()` flattens the returned XML with stdlib `xml.etree.ElementTree` (every text node, document order, whitespace-joined) rather than handing it to this repo's `docling`-based ingestion, because docling's confirmed supported-input-formats list doesn't include this DTD; the flattened text is written to a `.txt` file and handed unchanged to `knowledge.ingest.ingest_document(source_type='standard', ...)`. `fetch_fn` is injectable for tests (no network, no database — see `tests/test_sourcing_fcc_ecfr.py`). It is registered in `policies/tool_policy.yaml`'s `ingestion_auto` category — ungated, since it needs no credential and spends nothing.

## Capabilities not yet used here

Everything except `titles.json` and `full/…xml` sits unused. `structure/{date}/title-{title}.json` would let the model browse Title 47's part/subpart/section tree and decide what to pull before spending a possibly-dozens-of-megabytes `full` fetch — today `ingest_fcc_rule` always fetches a whole named part. `versions/title-{title}.json` and repeated `titles.json` snapshots are this API's actual point-in-time mechanism (an `issue_date` range), unused because the module always resolves the *current* date only — a real gap if a design ever needs to know what Part 15 said as of a specific past filing date, not just today's limits. Search Service (`results`/`suggestions`/`counts/*`) is entirely unused: there is no way today to ask "which Title 47 sections mention EIRP" without already knowing the part number, unlike a real full-text search. `ancestry` and the Corrections/Agencies endpoints (Admin Service) are also unused; Corrections in particular could flag that an already-ingested rule text was later found erroneous by OFR itself.

## Sources

- https://www.ecfr.gov/developers/documentation/api/v1.json (live OpenAPI/Swagger 2.0 spec, fetched directly)
- https://www.ecfr.gov/api/versioner/v1/titles.json (live endpoint, fetched directly)
- https://www.ecfr.gov/reader-aids/understanding-the-ecfr/what-is-the-ecfr (legal-status disclaimer, fetched directly)
- https://www.ecfr.gov/robots.txt (fetched directly)
- https://raw.githubusercontent.com/usgpo/bulk-data/master/ECFR-XML-User-Guide.md (GPO's own XML DTD guide, fetched directly)
- https://www.copyright.gov/title17/92chap1.html (17 U.S.C. § 105 text, fetched directly)
- `knowledge/sourcing/fcc_ecfr.py`, `knowledge/sourcing/_http.py`, `knowledge/ingest.py`, `tests/test_sourcing_fcc_ecfr.py`, `policies/tool_policy.yaml`, `docs/FREE_AND_OPEN_SOURCE_TOOLING.md` (this repo's adapter, tests, config and prior research, read in full)
