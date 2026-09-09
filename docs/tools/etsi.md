# ETSI standards (deliver-path PDFs) and the IPR/FRAND-declaration register

ETSI (the European Telecommunications Standards Institute) is the European
standards body that writes and publishes the radio-equipment and EMC
standards a European-market RF product has to comply with — including the
"Harmonised Standards" that, once listed against the EU Radio Equipment
Directive, are a manufacturer's normal route to proving a device meets that
law's essential requirements. This repo doesn't call any ETSI service to
*find* a standard; it takes a document URL the caller already has, downloads
the PDF, and files it into the knowledge base as citable evidence
(`source_type='standard'`) — the same "traceable to research" discipline
CLAUDE.md requires for every number the system states.

## What it is

ETSI is "an independent, not-for-profit, standardization organization,"
founded in 1988 by CEPT (the European Conference of Postal and
Telecommunications Administrations) following a European Commission
proposal, and is one of three European Standards Organisations officially
recognised by the EU [en.wikipedia.org/wiki/European_Telecommunications_Standards_Institute].
It has over 900 member organisations from 65 countries and standardises
across GSM/3G/4G/5G, DECT, TETRA and broader ICT — with radio and EMC work
in particular concentrated in its Technical Committee ERM (Electromagnetic
compatibility and Radio spectrum Matters), which develops Harmonised
Standards in response to formal Standardisation Requests from the European
Commission [etsi.org/technical-groups/erm, via search index].

## Full capabilities

As an organisation, ETSI is a standards-drafting body, not just a document
repository: work happens in 45+ Technical Committees, Industry
Specification Groups (ISGs) and Software Development Groups, each open to
member participation and led by a rapporteur, producing several distinct
deliverable types — EN (European Standard, the harmonised-standard track),
TS (Technical Specification), TR (Technical Report), ES/EG (whole-membership-approved
ETSI Standard/Guide), and GS (ISG Group Specification)
[etsi.org/standards/types-of-standards, etsi.org/expertise/standards-development-committees,
via search index]. Its catalogue is large — this repo's own prior research
put it at "over 56,000 documents"
(`docs/FREE_AND_OPEN_SOURCE_TOOLING.md`) — and RF-relevant content sits
heavily in the EN 300 (generic/short-range-device radio) and EN 301
(equipment-class-specific radio and EMC, e.g. EN 301 489's EMC requirements)
number ranges. Beyond documents, ETSI also runs ETSI Forge
(`forge.etsi.org`), a GitLab-hosted platform (mirrored read-only to GitHub
under `github.com/etsi-forge`) where ISGs publish machine-readable API
artifacts co-developed with a standard — OpenAPI/Swagger specs for NGSI-LD
and NFV-MANO, for instance — and a public IPR/patent-declaration register
(ETSI SR 000 314) listing FRAND licensing undertakings against each
standard [github.com/etsi-forge, etsi.org/images/files/IPR/etsi-ipr-policy.pdf,
via search index]. No confirmed public REST/JSON API exists for
*searching* the standards catalogue itself — `standards-search` is a
human-facing web form, and the Forge/Swagger material found is APIs
*defined by* ETSI standards (NGSI-LD, MEC), not an API onto the catalogue —
consistent with what `knowledge/sourcing/etsi.py`'s own docstring already
concluded.

## Integrations & interfaces

Plain HTTPS GET of a static PDF at a per-document, versioned path:
`www.etsi.org/deliver/<doc_type>/<numeric_range>/<doc_number>/<version>/<filename>.pdf`
— no API key, session, or client library. A separate, registration-gated
"Publications Download Area" also exists for bulk/draft access
[found via search index of etsi.org; not fetched directly, see Sources
note below], but the public deliver-path PDFs this repo uses need none of
that.

## Licensing & cost

Free, no account, for the published PDF; only the editable Word version is
access-restricted. The PDF itself is not public domain: ETSI holds
copyright on its deliverables and every document also carries ETSI's IPR
Policy — members declaring standards-essential patents commit to license
them on FRAND (fair, reasonable, and non-discriminatory) terms, not a
royalty-free grant [etsi.org/images/files/IPR/etsi-ipr-policy.pdf, via
search index; `docs/FREE_AND_OPEN_SOURCE_TOOLING.md`]. This repo's own
`policies/tool_policy.yaml` treats that as "same ungated posture as arXiv"
for *access* purposes only — no credential is needed to fetch the PDF —
while still requiring the caller to supply an explicit `license` string
per document, exactly as for every other ingested source.

## How this repo uses it today

`knowledge/sourcing/etsi.py` has two functions, both following the same
shape (issue #284 added the second, next to the first):

- `ingest_etsi_standard()` takes a caller-supplied `document_url`,
  validates it's `https://www.etsi.org/deliver/...` (rejecting anything
  else), downloads the bytes (`knowledge.sourcing._http.download_bytes`,
  injectable as `fetch_fn` for tests), writes them to a temp or
  caller-given directory, and hands the file to
  `knowledge.ingest.ingest_document(source_type="standard", ...)`
  unchanged — no ETSI-specific parsing.
- `ingest_etsi_ipr_declaration()` does the same thing against a document
  from SR 000 314, ETSI's public IPR/FRAND licensing-declaration register
  — confirmed (issue #284's own research) to be served from a *different*
  host than the deliver-path PDFs: `ipr.etsi.org`, a dedicated subdomain
  whose sole purpose is this database, rather than a directory under
  `www.etsi.org`'s general site. An individual declaration's URL there is
  `https://ipr.etsi.org/IPRDetails.aspx?IPRD_ID=<n>&IPRD_TYPE_ID=<n>&
  MODE=<n>` — confirmed live, not assumed: Google's own crawler has
  indexed `https://ipr.etsi.org/IPRDetails.aspx?IPRD_ID=198&
  IPRD_TYPE_ID=2&MODE=2` with no `sessionkey` query parameter at all,
  which is decisive since Googlebot holds no ETSI session — a page it can
  render, cache, and index must not require one. That matches ETSI's own
  "ETSI IPR Online Database User Guide for Anonymous Users"
  (`ipr.etsi.org/UserGuide/UserGuide_Anonymous.htm`, via search index),
  which documents that anonymous, unauthenticated users get read-only
  access to declarations in "reflected" state. The function validates
  `document_url` is exactly `https://ipr.etsi.org/IPRDetails.aspx?...`
  (rejecting, e.g., the search form itself), downloads it the same way,
  and passes `extra_metadata={"declared_against_document_id": ...}`
  through to `ingest_document()` so the stored declaration stays
  traceably linked to the standard it was filed against (also
  `source_type="standard"` — a licensing declaration is still an ETSI
  document, not a new source type).

`policies/tool_policy.yaml` lists both `ingest_etsi_standard` and
`ingest_etsi_ipr_declaration` under `ingestion_auto` (no human-approval
gate) precisely because neither needs a credential.

## Capabilities not yet used here

The adapter cannot discover a deliver URL from a bare standard number
(e.g. "EN 300 328") — the caller must already have the exact versioned
path, since no scriptable catalogue-search endpoint was found; the same is
true of an IPR declaration's `IPRD_ID` — no scriptable search/query API
was found for `ipr.etsi.org` either (it's a dynamic ASP.NET application,
not a static per-document path), so a caller must already have the
specific declaration's `IPRDetails.aspx` URL, obtained by searching
`https://ipr.etsi.org/` by hand. Neither function ever checks whether a
previously ingested standard has since been superseded by a newer version
(ETSI's own version folder in the URL, e.g. `02.02.01_60`, is exactly the
signal that would drive that check).

## Sources

- https://www.etsi.org/standards/get-standards — direct WebFetch returned
  HTTP 403 (bot-blocked); content used here is drawn from this exact page
  as quoted/paraphrased in WebSearch's indexed snippets, not from memory
- https://en.wikipedia.org/wiki/European_Telecommunications_Standards_Institute
  (fetched directly)
- https://www.etsi.org/technical-groups/erm — via search index (direct
  fetch of etsi.org returned HTTP 403 for every URL tried this session)
- https://www.etsi.org/standards/types-of-standards — via search index
- https://www.etsi.org/expertise/standards-development-committees/ — via
  search index
- https://www.etsi.org/images/files/IPR/etsi-ipr-policy.pdf — via search
  index
- https://github.com/etsi-forge (fetched via search index; organisation
  page lists the read-only GitHub mirrors of ETSI Forge/GitLab projects)
- `docs/FREE_AND_OPEN_SOURCE_TOOLING.md` (this repo) — prior research row
  on ETSI, including the "over 56,000 documents" figure
- `knowledge/sourcing/etsi.py`, `knowledge/ingest.py`,
  `policies/tool_policy.yaml` (this repo, read in full)

Issue #284 (IPR/FRAND-declaration register) additions, all via search
index — direct WebFetch of every `ipr.etsi.org` URL tried this session
also returned HTTP 403 (same bot-blocking behaviour as `www.etsi.org`
above, not evidence of an auth requirement):

- https://ipr.etsi.org/ — the IPR Online Database's own landing/search page
- https://ipr.etsi.org/ETSI_UserGuide.aspx?uniqueId=1 and
  https://ipr.etsi.org/UserGuide/UserGuide_Anonymous.htm — ETSI's own
  "User Guide for Anonymous Users," confirming anonymous/unauthenticated
  read-only access to declarations in "reflected" state
- https://ipr.etsi.org/IPRDetails.aspx?IPRD_ID=198&IPRD_TYPE_ID=2&MODE=2 —
  a live individual-declaration URL, found indexed by Google with no
  `sessionkey` parameter, which is the decisive signal that this page
  renders without one (Googlebot holds no ETSI session)
- Several further `https://ipr.etsi.org/IPRDetails.aspx?IPRD_ID=...`
  results (IDs including 1152, 1193, 2071, 2774, 2969, 3043, 6456, 8008,
  8872), all sharing the same `IPRDetails.aspx?IPRD_ID=<n>&
  IPRD_TYPE_ID=<n>&MODE=<n>[&sessionkey=...]` shape — cross-checked to
  confirm the query-parameter pattern, not a one-off
- https://www.etsi.org/deliver/etsi_sr/000300_000399/000314/ (several
  dated versions found, e.g. `02.38.01_60/sr_000314v023801p.pdf`) — SR 000
  314 itself, the periodic snapshot report of the live database
- https://www.etsi.org/images/files/IPR/etsi-guide-on-ipr.pdf and
  https://www.etsi.org/images/files/IPR/FAQ-IPR-Question1.pdf — ETSI's own
  guide/FAQ describing the database and its declaration workflow
- `knowledge/sourcing/etsi.py`, `mcp_server/server.py`, `agent/main.py`,
  `policies/tool_policy.yaml` (this repo, re-read after this ticket's
  changes)
