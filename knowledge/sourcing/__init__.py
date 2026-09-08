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
  (`knowledge.provenance.PATENT_AUTHORITY_RANK`). Fetch by number only --
  patent *search* is not built here or anywhere in this repo.

None of these five sources require API authentication -- confirmed
individually against each source's own access-terms/API documentation
during this ticket's research, not assumed; see each module's own
docstring for its specific citation.

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

Each client is a thin wrapper, per this repo's knowledge-sourcing seam
(see this repo's CLAUDE.md): authenticate/query the source, download the
relevant file locally, call `knowledge.ingest.ingest_document` unchanged.
No new ingestion logic (parsing, chunking, storage) lives in this package
-- `knowledge/ingest.py` remains the one entry point.

Every function in this package takes a `fetch_fn` parameter (default: a
real HTTP GET via `knowledge.sourcing._http.download_bytes`) so tests can
inject a stub instead of hitting the network -- the same seam-testing shape
`simulation.nec2pp.Nec2ppSimulator`'s `executable` parameter gives the
subprocess adapters, applied to a network fetch instead of a subprocess.
"""

from __future__ import annotations
