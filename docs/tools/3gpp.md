# 3GPP specifications (FTP archive)

3GPP is the standards body that writes the technical rulebook cell phones
and towers follow to talk to each other — the specs behind GSM, 3G, 4G/LTE
and 5G NR (New Radio). It publishes Technical Specifications ("TS",
binding rules — exact frequencies, power levels, timing, radiation-pattern
limits) and Technical Reports ("TR", background study material). This repo
pulls TS/TR text in as evidence at the `standard` provenance tier because a
metasurface or antenna built for, say, 5G NR band n77 has to hit numbers
3GPP itself sets — quoting the spec beats guessing the number. The client
here (`knowledge/sourcing/threegpp.py`) is deliberately thin: one HTTP GET
against 3GPP's own public FTP archive, unzip, hand the one document inside
to this repo's existing parser. No login, no key, no 3GPP-specific parsing.

## What it is

3GPP ("Third Generation Partnership Project", created in 1998) "is not a
legal entity" itself — it is a collaboration between seven regional
standards bodies, its Organizational Partners: ARIB (Japan), ATIS (US),
CCSA (China), ETSI (Europe), TSDSI (India), TTA (South Korea) and TTC
(Japan) [3gpp.org/about-us/legal-matters]. Day-to-day running is handled by
the Mobile Competence Centre (MCC), based at ETSI's headquarters. 3GPP
maintains the cellular standard from 2G GSM through 5G NR: "2024 saw the
debut of 5G-Advanced services... work has started on 6G studies — due for
completion in 2026" [3gpp.org/about-us]. There's no software "version" to
track — specs instead advance in parallel-numbered **Releases** (a bundled
edition of the whole standard, the way a yearly OS release bundles many
components); Release 21 is newest per the site's own listings.

## Full capabilities

A spec number is a 2-digit **series** (e.g. "38" = radio technology beyond
LTE, i.e. 5G NR — spec 38.331 is titled "NR; Radio Resource Control (RRC);
Protocol specification") plus a number within it. Multi-part specs append
`-N` (`51.010-1`), zero-padded past nine parts (`29.198-08`), occasionally
with sub-parts (`29.998-06-2`) [.../file-name-conventions]. **Version** is a
three-field `major.technical.editorial` number: major 0/1/2 =
immature/60%/80% draft, major ≥3 = approved and under change control, at
which point the major field *becomes* the Release number (a spec can jump
straight from 2.0.0 to 7.0.0 on approval); technical increments per Change
Request, editorial covers non-technical fixes [.../version-numbering-scheme].
The filename packs that triple into three characters "coded in base 36"
(e.g. v15.1.1 → `f11`) — confirmed on the page itself — the "h00"-style
strings this adapter's `version` argument expects [.../file-name-conventions].

Three structured layers sit above the flat zip archive. **DynaReport**
(`3gpp.org/dynareport`) is a free, no-login, sortable-HTML database of
every active/withdrawn spec back to 1999, with per-series and per-spec
detail pages (its 38-series table flags TS 38.101 itself as "SPECIFICATION
WITHDRAWN" while its five parts, 38.101-1..5, remain current) — real,
addressable metadata, but HTML tables, not a JSON/REST/CSV feed. **The
3GPP Portal's Specifications search** (`portal.3gpp.org/Specifications`) is
genuinely more structured — real query filters for TSG/working group,
series, TS-vs-TR, Release (all 28, back to 1996), publication and
withdrawal status — but returned "0 specifications found" for every filter
tried without an EOL (3GPP member/delegate) account: the search machinery
is public, its results are not. **3GPP Forge** (`forge.3gpp.org`) is an
official GitLab instance for "software produced collaboratively by 3GPP
delegates," confirmed live via its public SA5 repository (YANG data models
for network management); other groups reportedly also publish the 5G
Core's Service-Based-Architecture interfaces there as OpenAPI 3.0 YAML —
search-result corroboration only, not independently re-fetched this pass.

## Integrations & interfaces

Plain HTTPS GET, no client library:
`https://www.3gpp.org/ftp/Specs/archive/{series}_series/{spec}/{spec-with-first-dot-removed}-{version}.zip`,
a plain browsable directory tree with no auth headers sent. Each zip
bundles the spec as one Word document (`.docx` current, legacy `.doc` for
older specs), sometimes with a small cover sheet alongside it. No OAI-PMH
bulk harvest (unlike arXiv), no key-based REST API for spec text —
DynaReport and the Portal above are the two structured metadata surfaces
this pass found, Forge a third for a different (non-prose) kind of
content.

## Licensing & cost

Free to download, no registration. **Not** public domain: "the copyright on
all 3GPP Technical Reports and Technical Specifications vests jointly with
the 3GPP Organizational Partners" [3gpp.org/about-us/legal-matters], and
3GPP's Terms of Use bar reproducing, distributing or publishing site/document
content "in whole or in part... without the prior express consent" of ETSI,
acting for the partners [3gpp.org/terms-of-use]. Reuse in training material
or publications requires filing 3GPP's Copyright Form with the ETSI Legal
Service. Patents essential to *implementing* a spec fall under each
partner's own IPR/FRAND policy — a build-time concern, not a citation one.
Matches this repo's own `docs/LICENSE_MATRIX.md`: free to read/cite
internally, not public domain — the same posture as ETSI, unlike the FCC's
public-domain eCFR.

## How this repo uses it today

`ingest_3gpp_spec(spec_number, version, *, license, classification,
supersedes_document_id=None, download_dir=None, fetch_fn=download_bytes)`
builds the archive URL itself (`_spec_url`: series is the text before the
first dot; only that first dot is dropped; a multi-part spec's own dash,
e.g. `38.521-1`, stays intact — both covered by dedicated tests), downloads
via `fetch_fn` (defaults to the shared
`knowledge.sourcing._http.download_bytes`: stdlib `urllib`, 60 s timeout,
no credentials, retries a transient network error or HTTP 5xx up to 3 times
with exponential backoff -- a 4xx fails immediately, no retry (issue #405)),
then `_extract_primary_document` picks exactly one zip
member — `.docx` over legacy `.doc`, largest file when several share a
suffix — before handing it unchanged to
`knowledge.ingest.ingest_document(source_type="standard", ...)`. `license`
and `classification` are mandatory caller-supplied strings; the module
assumes no specific license text. A legacy `.doc` docling can't parse falls
through to `ingest_document`'s existing `extraction_status="failed"` path
rather than crashing. Registered under `ingestion_auto` in
`policies/tool_policy.yaml` (ungated) alongside its ETSI/FCC/arXiv/patent
siblings. Five tests in `tests/test_sourcing_threegpp.py` cover URL
construction, the docx/largest-file preference, the legacy-`.doc` fallback
and the no-document-member error, all against a stubbed `fetch_fn` — no
real network access.

`lookup_3gpp_spec_status(spec_number, *, fetch_fn=download_bytes)` (ticket
#285) answers half of "what is the current version of spec X, and has it
been withdrawn?": it fetches 3GPP's own DynaReport per-series table
(`https://www.3gpp.org/dynareport?code={series}-series.htm`, series
derived the same way `_spec_url` does), parses it with a small stdlib
`html.parser.HTMLParser` subclass (no new dependency), and reports each
spec's title and withdrawn/current status — e.g. TS 38.101 comes back
withdrawn while 38.101-1..5 do not. It raises `SpecNotFoundError` rather
than guessing if `spec_number` isn't a row in the fetched table. **It
cannot report a version number**: fetching the live per-series page during
this ticket's implementation showed its own `<thead>` declares only three
columns — spec number, title, notes — and every one of its 272 data rows'
notes cell is either blank or "SPECIFICATION WITHDRAWN", never a version.
The paragraph below (written before this function existed) assumed
otherwise; that assumption was wrong, corrected here rather than left to
rot per this repo's own CLAUDE.md. A real current-version number does live
on 3GPP's site, on the much heavier, ASP.NET/RadGrid-rendered per-*spec*
detail page (`/dynareport/{spec-no-dot}.htm`, one fetch per spec, not per
series) — closing that half of the gap is unstarted work, not done here.
Seven tests in `tests/test_sourcing_threegpp.py` cover withdrawn/current
detection, series-URL derivation from a multi-part spec number, the
not-found error (`SpecNotFoundError`, a `ValueError` subclass naming every
spec the fetched table DID contain), the always-`None` version field (with
the reasoning above), and the pure HTML-parsing function on its own, no
`fetch_fn` involved. Registered under `ingestion_auto` in
`policies/tool_policy.yaml` (ungated, same as `ingest_3gpp_spec`), and
wired onto the MCP tool surface (`mcp_server/server.py`) and the systems
role's tool list (`agent/mcp_roles.py`) right beside `ingest_3gpp_spec` --
issue #215 found this exact "implemented and tested, wired onto no tool
surface" gap once already for the sibling ingest functions, so this one
ships alongside its own registration rather than repeating that gap.

## Capabilities not yet used here

DynaReport's per-*spec* detail page (`/dynareport/{spec-no-dot}.htm`) is
the one place on 3GPP's own site that publishes a spec's actual current
version string (confirmed live during ticket #285's implementation — its
"Versions" grid lists each Release's version, e.g. "20.0.0" for
38.101-1's latest, matching the "k00" filename encoding
`version-numbering-scheme` describes) — but it is a heavy,
ASP.NET/RadGrid-rendered page, one fetch per spec rather than per series,
and parsing it is unstarted work here. The Portal's filters
(`portal.3gpp.org/Specifications`) would do both halves of this lookup
better, but sit behind a member-login wall this adapter has no credentials
for. Forge's YANG/OpenAPI models were not pursued: they describe
network-management and core-network signalling interfaces, not RF/antenna
parameters — a real gap, but low priority here. Unlike arXiv's OAI-PMH
harvesting (`arxiv.py`), there is no bulk/corpus pull — each call fetches
one spec (or one series) at a time.

## Sources

- https://www.3gpp.org/about-us
- https://www.3gpp.org/about-us/legal-matters
- https://www.3gpp.org/terms-of-use
- https://www.3gpp.org/specifications-technologies/specifications-by-series/version-numbering-scheme
- https://www.3gpp.org/specifications-technologies/specifications-by-series/file-name-conventions
- https://www.3gpp.org/dynareport?code=status-report.htm
- https://www.3gpp.org/dynareport?code=38-series.htm
- https://www.3gpp.org/dynareport/38101-1.htm (per-spec detail page,
  fetched to confirm where a real current-version number does and does not
  live — ticket #285)
- https://www.3gpp.org/ftp/Specs/archive/ (plain directory listing, no auth
  headers sent)
- https://portal.3gpp.org/Specifications/ (structured search filters
  confirmed; returns zero results without an EOL member login)
- https://forge.3gpp.org/
- https://forge.3gpp.org/rep/sa5/MnS (public GitLab repo, no login required
  to view)
- `knowledge/sourcing/threegpp.py`, `knowledge/sourcing/_http.py`,
  `knowledge/ingest.py`, `policies/tool_policy.yaml`,
  `tests/test_sourcing_threegpp.py`, `docs/LICENSE_MATRIX.md` (this repo's
  own code and docs, read in full)
