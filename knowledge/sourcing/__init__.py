"""Thin ingestion clients for external standards/literature sources feeding
`knowledge.ingest.ingest_document` (ticket #68) -- one module per source:

- `threegpp.py` -- 3GPP specifications (`source_type='standard'`)
- `etsi.py` -- ETSI standards (`source_type='standard'`)
- `fcc_ecfr.py` -- FCC Part 15/Part 97 rule text via eCFR Title 47
  (`source_type='standard'`)
- `arxiv.py` -- arXiv preprints (`source_type='paper'`, authority rank
  explicitly overridden below the peer-reviewed default -- see
  `knowledge.provenance.arxiv_preprint_authority_rank`)
- `patent.py` -- US granted patents and pre-grant publications from the
  USPTO (`source_type='patent'`, issue #219). No authority-rank override:
  `patent` already carries its own lower default
  (`knowledge.provenance.PATENT_AUTHORITY_RANK`). `ingest_patent` fetches by
  number only; `search_uspto_patents` (issue #280) is the credentialed
  full-text discovery search sibling that finds a number worth fetching in
  the first place -- see below.

Four of these five sources need no API authentication at all -- confirmed
individually against each source's own access-terms/API documentation
during this ticket's research, not assumed; see each module's own
docstring for its specific citation. `patent.py`'s `search_uspto_patents`
is the one exception: unlike its own `ingest_patent` sibling (and unlike
every other function in this package), it calls
`knowledge.sourcing_common.require_external_network_tools_enabled` because
the USPTO Open Data Portal endpoint it queries requires a free-but-
ID.me-identity-verified USPTO.gov account (issue #280) -- the same
credentialed posture as the three distributor clients
(`knowledge/digikey.py` and siblings), not the other four sources here.

**IEEE Xplore is deliberately not one of these five.** It is confirmed
genuinely paywalled with no broad free-developer tier analogous to the
above (IEEE's own subscriptions page,
https://www.ieee.org/publications/subscriptions/index.html, quotes
institutional package pricing in the tens of thousands of dollars/year --
see also docs/FREE_AND_OPEN_SOURCE_TOOLING.md's IEEE Xplore row, an
independent prior research pass that reached the same conclusion). No
ingestion path assuming free IEEE Xplore access is built here or anywhere
in this repo; `arxiv.py` is the free complement to (not a replacement for)
IEEE's paywalled peer-reviewed literature.

Every fetch-by-identifier client here (`ingest_arxiv_paper`,
`ingest_patent`, `ingest_etsi_standard`, `ingest_fcc_rule`,
`ingest_3gpp_spec`) is a thin wrapper, per this repo's knowledge-sourcing
seam (see this repo's CLAUDE.md): authenticate/query the source, download
the relevant file locally, call `knowledge.ingest.ingest_document`
unchanged. No new ingestion logic (parsing, chunking, storage) lives in
this package -- `knowledge/ingest.py` remains the one entry point. The two
discovery-search siblings (`search_arxiv_papers`, issue #257;
`search_uspto_patents`, issue #280) are the one deliberate exception to
"calls ingest_document": each returns a list of *candidate* dicts for a
caller to review and never itself calls `ingest_document` (or
`ingest_patent`), directly or indirectly -- finding a document and trusting
it as evidence are two separate, deliberate steps. See each search
function's own docstring for its "never auto-ingests" contract.

Every fetch-by-identifier function in this package takes a `fetch_fn`
parameter (default: a real HTTP GET via
`knowledge.sourcing._http.download_bytes`) so tests can inject a stub
instead of hitting the network -- the same seam-testing shape
`simulation.nec2pp.Nec2ppSimulator`'s `executable` parameter gives the
subprocess adapters, applied to a network fetch instead of a subprocess.
`search_arxiv_papers` shares that same `fetch_fn` seam (its query API is
credential-free, like the rest of this package); `search_uspto_patents`
does not, because its endpoint is credentialed -- it takes `get_api_key`/
`search` instead, mirroring `knowledge/digikey.py`'s `get_token`/`search`
seam rather than this package's own norm.
"""

from __future__ import annotations
