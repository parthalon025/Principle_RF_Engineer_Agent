# FCC rules via eCFR Title 47 API

The eCFR ("electronic Code of Federal Regulations") is the U.S. government's own free, no-login republication of federal regulations, updated daily and current within about two business days of each change [archives.gov/federal-register/cfr/about-ecfr]. Its "versioner" REST API is the machine-readable door into that same content — JSON or XML instead of a page meant for a human to read. This repo uses it to pull FCC Part 15 (unlicensed-device emission limits) and other Title 47 rule text — the actual legal ceilings an antenna/EM-surface design has to clear — into the knowledge base as `source_type='standard'` evidence, the same authoritative-reference tier as a 3GPP or ETSI standard.

## What it is

eCFR is authorized by the Administrative Committee of the Federal Register (ACFR), which tasked the National Archives' Office of the Federal Register (OFR) and the Government Publishing Office (GPO) with running it as "an editorial compilation of CFR material and Federal Register amendments," with the eventual goal of becoming the ACFR's officially recognized publication [archives.gov/federal-register/cfr/about-ecfr]. It is not that yet: "those relying on it for legal research should verify their results against the official edition of the CFR, the Federal Register, and the List of CFR Sections Affected" [same page] — engineering reference is fine, formal regulatory sign-off is not. Its interactive documentation page returned eCFR's own bot-block ("Federal Register :: Request Access") to every automated fetch attempted here, so the endpoint list below was confirmed by calling each endpoint directly, not by reading its spec.

## Full capabilities

Confirmed live, by direct HTTPS call, three unauthenticated endpoint groups:

- **Versioner** — `titles.json` (per-title status: name, `latest_amended_on`, `up_to_date_as_of`); `structure/{date}/title-{n}.json` (chapter/part/subpart/section tree, structure only); `full/{date}/title-{n}.xml` (the rule text, filterable to one part/subpart/section — a full title can run ~20 MB); `versions/title-{n}.json` (every section's amendment history, paginated, with an `issue_date` filter — the point-in-time mechanism); `ancestry/{date}/title-{n}.json` (a node's path back up to its title).
- **Search** — `search/v1/results` (full-text query, confirmed returning 734 hits for "EIRP"), plus `count`, `counts/hierarchy`, `suggestions` and `summary` variants of the same query.
- **Admin** — `agencies.json` (agency hierarchy with each agency's CFR title/chapter references — confirmed live: the FCC entry lists Title 47, Chapter I) and `corrections/title/{n}.json` (eCFR's own logged editorial errors, each dated when the error occurred and when it was fixed).

The XML is a Federal-Register-specific DTD, not XHTML: nested `<DIV1>`…`<DIV9>` elements typed by level (a part is `<DIV5>`, `TYPE="PART"`), `<HEAD>` for headings, `<P>`/`<PSPACE>`/`<FP>` for body paragraphs, per GPO's own user guide for this DTD [github.com/usgpo/bulk-data] — the shape the adapter's own docstring reports seeing live.

## Integrations & interfaces

Plain unauthenticated HTTPS/JSON and HTTPS/XML — no client library, SDK, or API key. No rate-limit headers appear on a live response (`curl -D-` against `titles.json` shows no `X-RateLimit-*` header), and no documented numeric rate limit was found. `robots.txt` disallows crawler indexing of `/api/versioner/v1/full/` and `/api/renderer/v1/content/` [ecfr.gov/robots.txt] — a courtesy against search engines, not a limit on programmatic callers.

## Licensing & cost

Free, zero registration, at every endpoint used. The regulation text is a work of the U.S. Government and carries no copyright: "Copyright protection under this title is not available for any work of the United States Government" (17 U.S.C. §105(a)) [law.justia.com/codes/us/2010/title17/chap1/sec105]. GPO's eCFR XML user guide repeats this and adds there are "no restrictions on re-use" beyond not misusing NARA/CFR seals [github.com/usgpo/bulk-data]. The not-yet-official-edition caveat above is a currency (how up to date/legally binding) distinction, not a licensing one.

## How this repo uses it today

`knowledge/sourcing/fcc_ecfr.py`'s `ingest_fcc_rule(part, *, license, classification, title=47, ...)` uses exactly two endpoints. `_resolve_as_of_date()` calls `titles.json` and reads back Title 47's `up_to_date_as_of` date — the module never accepts a caller-supplied date, since an arbitrary historical date can 404 against `full/` (confirmed during the ticket's research, per the module docstring). `_full_text_url()` then calls `full/{date}/title-{title}.xml?part={part}` for that date. `_xml_to_text()` flattens the XML with stdlib `xml.etree.ElementTree` (every text node, document order, whitespace-joined) rather than handing it to this repo's docling-based ingestion, since docling's supported formats don't include this DTD; the flattened text is written to a `.txt` file and passed unchanged to `knowledge.ingest.ingest_document(source_type='standard', ...)`. `fetch_fn` is injectable for tests (no network, no database — `tests/test_sourcing_fcc_ecfr.py`). It sits in `policies/tool_policy.yaml`'s `ingestion_auto` category — ungated, since it needs no credential and spends nothing.

Issue #279 closed the discovery gap this section used to name: `search_fcc_rules(query, *, max_results=10, fetch_fn=download_bytes)`, alongside `ingest_fcc_rule` in the same module, now calls the third endpoint group — `search/v1/results?query=<query>` — and parses its `results` array into `part`/`title`/`section`/`heading`/`full_text_excerpt` candidate dicts, mirroring `search_arxiv_papers`'s "search returns candidates, a separate call ingests one" shape (issue #257). Because the Search Service spans every CFR title and rejects a server-side `title` parameter outright ("Found unpermitted parameter: :title" — confirmed live), the function filters non-Title-47 hits out client-side before returning, so a candidate handed back is always one `ingest_fcc_rule`'s hardcoded Title-47 assumption can actually fetch. It never calls `ingest_document` itself (enforced by `tests/test_sourcing_fcc_ecfr.py::test_search_fcc_rules_never_calls_ingest_document`) and sits in the same `ingestion_auto` category as `ingest_fcc_rule`, ungated for the same reason.

## Capabilities not yet used here

`structure/{date}/title-{n}.json` would let the model browse Title 47's tree before spending a possibly-20-MB `full` fetch — today `ingest_fcc_rule` always fetches a whole named part. `versions/title-{n}.json` is this API's real point-in-time mechanism (an `issue_date` range); unused because the module always resolves the current date only — a gap if a design needs what Part 15 said as of a past filing date, not just today's limits. The Search Service's `count`/`counts/hierarchy`/`suggestions`/`summary` variants are also unused — `search_fcc_rules` (above) only calls `results`; `suggestions` could offer query auto-complete and `counts/hierarchy` a per-part hit-count breakdown, neither needed for the "get back a shortlist of candidates" use case this ticket scoped. `ancestry`, `agencies.json` and `corrections/title/{n}.json` are also unused; Corrections could flag that an already-ingested rule text was later found erroneous by OFR itself.

## Sources

- https://www.ecfr.gov/api/versioner/v1/titles.json (fetched directly)
- https://www.ecfr.gov/api/versioner/v1/structure/2026-09-04/title-47.json (fetched directly)
- https://www.ecfr.gov/api/versioner/v1/ancestry/2026-09-04/title-47.json?part=15 (fetched directly)
- https://www.ecfr.gov/api/versioner/v1/versions/title-47.json?part=15 (fetched directly)
- https://www.ecfr.gov/api/versioner/v1/full/2026-08-31/title-47.xml?part=15 (fetched directly)
- https://www.ecfr.gov/api/search/v1/results?query=radio, `.../count`, `.../summary`, `.../counts/hierarchy`, `.../suggestions` (each fetched directly)
- https://www.ecfr.gov/api/admin/v1/agencies.json (fetched directly)
- https://www.ecfr.gov/api/admin/v1/corrections/title/47.json (fetched directly)
- https://www.ecfr.gov/robots.txt (fetched directly)
- https://www.ecfr.gov/developers/documentation/api/v1.json — blocked: every automated fetch (WebFetch and raw `curl`, several attempts) returned eCFR's "Federal Register :: Request Access" bot-check page instead of the spec; not used as a source for that reason
- https://www.archives.gov/federal-register/cfr/about-ecfr (NARA's own description of what eCFR is, who maintains it, and its legal-status disclaimer; fetched directly)
- https://law.justia.com/codes/us/2010/title17/chap1/sec105/ (17 U.S.C. §105 text, fetched directly)
- https://raw.githubusercontent.com/usgpo/bulk-data/main/ECFR-XML-User-Guide.md (GPO's own XML DTD guide, fetched directly)
- `knowledge/sourcing/fcc_ecfr.py`, `knowledge/sourcing/_http.py`, `knowledge/ingest.py`, `tests/test_sourcing_fcc_ecfr.py`, `policies/tool_policy.yaml`, `docs/FREE_AND_OPEN_SOURCE_TOOLING.md` (this repo's adapter, tests, config and prior research, read in full)
