# 3GPP specifications (FTP archive)

3GPP is the standards body that writes the actual technical rulebook cell
phones and cell towers follow to talk to each other — the specs behind
GSM, 3G, 4G/LTE, and 5G NR (New Radio). Its two document types are
Technical Specifications ("TS", the binding normative rules — exact
frequencies, power levels, timing, radiation-pattern limits) and Technical
Reports ("TR", background/study material that isn't itself binding). This
repo pulls TS/TR text in as evidence at the `standard` provenance tier
because a metasurface or antenna built for, say, 5G NR band n77 has to hit
numbers 3GPP itself sets — quoting the spec beats guessing the number. The
client here (`knowledge/sourcing/threegpp.py`) is deliberately thin: one
HTTP GET against 3GPP's own public archive, unzip, hand the one document
inside to this repo's existing parser. No login, no key, no 3GPP-specific
parsing logic.

## What it is

3GPP ("Third Generation Partnership Project") was created in 1998 and "is
not a legal entity" itself — it is a collaborative activity between seven
regional Standards Development Organizations acting as its Organizational
Partners: ARIB (Japan), ATIS (US), CCSA (China), ETSI (Europe), TSDSI
(India), TTA (South Korea) and TTC (Japan) [3gpp.org/about-us/legal-matters,
fetched live]. It maintains and evolves the cellular standard from 2G GSM
through 3G/UMTS, 4G/LTE and 5G NR; per its own history page, 2024 saw
"5G-Advanced" services debut and "work has started on 6G studies — due for
completion in 2026" [3gpp.org/about-us, fetched live]. There's no software
"version" to report — instead specs advance in parallel-numbered
**Releases** (a bundled edition of the whole standard family, the way a
yearly OS release bundles many components); Release 21 is the newest
listed on the site's own navigation as of this pass.

## Full capabilities

A spec number is a 2-digit **series** plus a number within it (e.g.
"38.331"); series generally group by technical domain — confirmed directly
by fetching the 38-series' own status table, whose entries describe 5G NR
radio (e.g. TS 38.101-1, "NR; User Equipment (UE) radio transmission and
reception") [3gpp.org/dynareport?code=38-series.htm, fetched live].
Multi-part specs append `-N` (`51.010-1`); parts past nine get zero-padded
to two digits for sort order (`29.198-08`), and some specs even have
sub-parts (`29.998-06-2`) [.../file-name-conventions, fetched live].
**Version** is a three-field `major.technical.editorial` number: major
0/1/2 = immature/60%-complete/80%-complete draft, major ≥3 = approved and
under change control, at which point the major field *becomes* the Release
number (a spec can jump straight from 2.0.0 to 7.0.0 on approval, skipping
3–6); technical increments per approved Change Request; editorial covers
non-technical fixes [.../version-numbering-scheme, fetched live]. The
filename packs that triple into three base-36 characters (1–9, then a–z
for 10–35; e.g. v15.1.1 → `f11`) — exactly the "h00"-style strings this
adapter's `version` argument expects [.../file-name-conventions, fetched
live]. New TS/TR numbers are issued by 3GPP's own "Specifications Manager"
on written request tied to an approved Work Item
[.../issuing-new-ts-and-tr-numbers, fetched live].

Two structured layers sit above the flat zip archive. **DynaReport**
(`www.3gpp.org/dynareport`) is a free, no-login, sortable-HTML database: a
full status report listing every active and withdrawn spec across every
Release back to 1999, per-series tables (title + withdrawal notes), and a
detail page per spec — confirmed live by fetching both the status-report
and 38-series pages directly; it is not a documented JSON/REST/CSV feed,
but a real, addressable metadata surface. **3GPP Forge**
(`forge.3gpp.org`) is an official GitLab instance — "collaborative tools
... download software produced collaboratively by 3GPP delegates" per its
own front page — hosting machine-readable interface artifacts alongside
prose specs; confirmed live via its public SA5 "Management and
Orchestration APIs" repo (2,375 commits, 592 branches, 64 tags), which
publishes YANG data models for network-management interfaces. Search-result
corroboration only, not independently re-fetched this pass: that SA5 and
other groups also publish the 5G Core Service-Based-Architecture APIs there
as OpenAPI 3.0 YAML.

## Integrations & interfaces

Plain HTTPS GET against a fixed URL shape, no client library:
`https://www.3gpp.org/ftp/Specs/archive/{series}_series/{spec}/{spec-with-first-dot-removed}-{version}.zip`.
The archive root is a plain browsable directory listing — confirmed live,
no auth headers sent, series subfolders visible from `00_series` through
`37_series` and beyond. Each zip bundles the spec as one Word document
(`.docx` current, legacy `.doc` for older specs), sometimes with a small
cover/history sheet alongside it. There is no OAI-PMH bulk-harvest
mechanism (unlike arXiv) and no key-based REST API for spec text itself;
DynaReport and Forge above are the two structured/scriptable surfaces this
pass found beyond the flat archive.

## Licensing & cost

Free to download, no registration — confirmed live via unauthenticated
curl. **Not** public domain: copyright in every TS/TR "vests jointly" with
the seven Organizational Partners [.../legal-matters, fetched live], and
3GPP's Terms of Use state site/spec content "shall not be reproduced,
distributed or published, in whole or in part ... without the prior
express consent" of ETSI, acting for the partners
[3gpp.org/terms-of-use, fetched live]. Reuse in training, conference
presentations, or textbooks requires filing 3GPP's own Copyright Form with
ETSI Legal Service [.../legal-matters, fetched live]. Separately, patents
essential to *implementing* a spec fall under each Organizational Partner's
own IPR/FRAND policy — a build-time concern, not a citation one. This
matches what this repo's own `docs/LICENSE_MATRIX.md` already records: free
to read/cite internally, not public domain — the same posture as ETSI, and
unlike the FCC's public-domain eCFR.

## How this repo uses it today

`ingest_3gpp_spec(spec_number, version, *, license, classification,
supersedes_document_id=None, download_dir=None, fetch_fn=download_bytes)`
builds the archive URL itself (`_spec_url`: series = text before the first
dot; only that first dot is dropped from the spec number; a multi-part
spec's own internal dash, e.g. `38.521-1`, is left intact — both rules
covered by dedicated tests), downloads via `fetch_fn` (defaults to the
package-shared `knowledge.sourcing._http.download_bytes`: stdlib
`urllib`, 60 s timeout, descriptive User-Agent, no credentials), then
`_extract_primary_document` opens the zip in memory and picks exactly one
member — `.docx` over legacy `.doc`, and the largest file when several
share a suffix, to skip a bundled cover sheet — before handing that one
file unchanged to `knowledge.ingest.ingest_document(source_type="standard",
license=..., classification=..., supersedes_document_id=...)`. `license`
and `classification` are mandatory caller-supplied strings; the module
assumes no specific license text. If the extracted file is a legacy `.doc`
that docling can't parse, `ingest_document`'s existing failure path stores
the row with `extraction_status="failed"` rather than crashing — this
client does not special-case that itself. Registered under `ingestion_auto`
in `policies/tool_policy.yaml` (ungated), alongside its ETSI/FCC/arXiv/
patent siblings, "because it needs no account or key" per that file's own
comment. Five tests in `tests/test_sourcing_threegpp.py` cover the URL
construction (plain and multi-part), the docx-over-doc/largest-file
preference, the legacy-`.doc`-only fallback, and the no-document-member
error path — all against a stubbed `fetch_fn`, no real network access.

## Capabilities not yet used here

The adapter has no way to resolve "what is the current version of spec
X" — the caller must already know 3GPP's own version string. DynaReport's
per-spec detail pages or its full status-report table could close that gap
without a human checking the site by hand first, the same shape of gap
this repo's ETSI adapter has. Nor does it read DynaReport's
withdrawal/status flag — a spec DynaReport marks e.g.
"SPECIFICATION WITHDRAWN" (seen live on TS 38.101 in the fetched 38-series
table) can still be requested and ingested as if current. 3GPP Forge's
machine-readable YANG data models were not judged useful to fetch further
for this repo's purpose: they describe network-management/core-network
interfaces, not RF/antenna parameters, so that gap is real but low-priority
for thin-conformal-surface work. Unlike arXiv's OAI-PMH harvesting (this
package's `arxiv.py`), there is no bulk/corpus pull — each call fetches one
spec at a time.

## Sources

- https://www.3gpp.org/about-us (fetched live via curl)
- https://www.3gpp.org/about-us/legal-matters (fetched live via curl; the
  Terms of Use's own copyright-authorization link, and the URL 3GPP's site
  now serves for `/about-us/1904-copyright-authorization`, land here —
  that older slug now resolves to the generic "About 3GPP" page instead
  of distinct content, a site-restructure artifact confirmed by comparing
  both pages' bodies)
- https://www.3gpp.org/terms-of-use (fetched live via curl)
- https://www.3gpp.org/specifications-technologies/specifications-by-series/version-numbering-scheme
  (fetched live via curl)
- https://www.3gpp.org/specifications-technologies/specifications-by-series/file-name-conventions
  (fetched live via curl)
- https://www.3gpp.org/specifications-technologies/specifications-by-series/issuing-new-ts-and-tr-numbers
  (fetched live via curl)
- https://www.3gpp.org/dynareport?code=status-report.htm (fetched live via
  curl)
- https://www.3gpp.org/dynareport?code=38-series.htm (fetched live via
  curl)
- https://www.3gpp.org/ftp/Specs/archive/ (fetched live via curl — plain
  directory listing, no auth headers sent)
- https://forge.3gpp.org/ (fetched live via curl)
- https://forge.3gpp.org/rep/sa5/MnS (fetched live via curl — public
  GitLab repo, no login required to view)
- Not independently re-fetched this pass (search-result corroboration
  only): that 3GPP Forge also hosts the 5G Core Service-Based-Architecture
  APIs as OpenAPI 3.0 YAML, beyond the YANG models this pass confirmed
  directly
- `knowledge/sourcing/threegpp.py`, `knowledge/sourcing/_http.py`,
  `knowledge/ingest.py`, `policies/tool_policy.yaml`,
  `tests/test_sourcing_threegpp.py`, `docs/LICENSE_MATRIX.md`,
  `docs/FREE_AND_OPEN_SOURCE_TOOLING.md` (this repo's own code and docs,
  read in full)
