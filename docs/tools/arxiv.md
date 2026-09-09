# arXiv API

arXiv is a free, no-login preprint server — a public archive where researchers post papers before (or instead of) publishing them in a paywalled journal — covering physics, math, computer science, and related fields; its API is a plain web-request interface (no password or account needed) for asking arXiv "what do you have for this paper ID or this search term" and getting back a structured, machine-readable answer instead of a web page meant for humans. This repo uses that API to pull RF/electromagnetics papers straight into its knowledge base as evidence for a design decision, tagged at the `LITERATURE-SUPPORTED` tier — one step below a peer-reviewed, published paper — because, as arXiv itself says, a preprint has passed only a "superficial" moderator check, not peer review (below).

## What it is

arXiv began in 1991 (founder Paul Ginsparg) and, as of July 1, 2026, spun out from 25 years at Cornell University to become its own independent nonprofit, arXiv, Inc., funded by the Simons Foundation, Cornell, member institutions and donors, led by a Board of Directors and a newly appointed CEO [blog.arxiv.org/2026/06/30; info.arxiv.org/about/index.html]. It now hosts "more than three million scholarly articles in eight subject areas" [info.arxiv.org/about/index.html]. Submissions get a light moderator check, not a scientific review — arXiv's own words: "the arXiv moderation process is not a peer-review process. arXiv staff and moderators cannot give feedback on the submission" [info.arxiv.org/help/moderation/index.html], elsewhere described on arXiv's blog as a quick "one look" scan [blog.arxiv.org/2019/08/29/our-moderation-process]. The query API carries no separate version number; it has run as a stable, documented REST/Atom service for years.

## Full capabilities

The REST query API (`https://export.arxiv.org/api/query`) returns Atom 1.0 XML for either an `id_list` (exact paper lookup) or a `search_query` across fields `ti` (title), `au` (author), `abs` (abstract), `co` (comment), `jr` (journal reference), `cat` (subject category), `rn` (report number), or `all`, combinable with `AND`/`OR`/`ANDNOT`, filterable by `submittedDate` range, sortable by relevance/`lastUpdatedDate`/`submittedDate`, and paginated via `start`/`max_results` (2,000 per slice, 30,000 total) [info.arxiv.org/help/api/user-manual.html]. It is metadata-only — title, authors, abstract, category, DOI, journal-ref, comment — never the paper's full body text; full documents are fetched separately from the direct content URLs `arxiv.org/pdf/{id}.pdf` and `arxiv.org/src/{id}` (LaTeX source, when the author supplied it). Beyond the query API, arXiv also runs an OAI-PMH v2.0 metadata-harvesting endpoint built for bulk mirroring/sync rather than one-off lookups [info.arxiv.org/help/oa/index.html], a Kaggle metadata dataset, and a requester-pays AWS S3 bucket of the full PDF/LaTeX corpus for bulk full-text access [info.arxiv.org/help/bulk_data/index.html]. No authentication or API key is required for any of these [info.arxiv.org/help/api/user-manual.html]. Category `physics.app-ph` explicitly covers "microwaves, spintronics, advanced materials, metamaterials" [arxiv.org/category_taxonomy] — squarely this repo's domain — alongside `eess.SP` (signal processing) and `physics.optics`.

## Integrations & interfaces

Plain HTTPS, no client library required: this repo's tooling calls it with `curl`/`urllib` directly. Etiquette, not a hard-enforced limit, governs pacing: arXiv's Terms of Use ask callers to "make no more than one request every three seconds, and limit requests to a single connection at a time," and forbid routing around that with multiple machines [info.arxiv.org/help/api/tou.html].

## Licensing & cost

Free, no cost at any tier. Authors, not arXiv, hold copyright; each paper carries whichever license its author picked at submission — arXiv's own limited non-exclusive distribution license by default, or an author-chosen Creative Commons license (CC BY, CC BY-SA, CC BY-NC-SA, CC BY-NC-ND, or CC0 public-domain) [info.arxiv.org/help/license/index.html]. That choice varies paper to paper and is irrevocable once made, so a downstream reuse right (redistributing the full text, not just citing it) has to be checked per paper, not assumed. All arXiv *metadata* (title, authors, abstract, category — not the paper itself) is separately dedicated to the public domain under CC0 [info.arxiv.org/help/license/index.html]. The Terms of Use permit storing and sharing metadata but say to "direct users to arXiv.org to retrieve e-print content" rather than re-hosting the PDFs/source yourself [info.arxiv.org/help/api/tou.html].

## How this repo uses it today

`knowledge/sourcing/arxiv.py`'s `ingest_arxiv_paper(arxiv_id, *, license, classification, ...)` is a thin wrapper: it shells out (`uv run --project`) to the vendored `arxiv-doc-builder` skill's `convert-paper` CLI, which fetches LaTeX source (preferred) or falls back to PDF, converts to Markdown via pandoc, and emits a YAML frontmatter block. Internally that skill's `arxiv_metadata.fetch_metadata()` hits `https://export.arxiv.org/api/query?id_list={id}` — the query API's single-ID lookup path only, never `search_query` — pulling title/authors/version/published/category/DOI/journal/abstract, and using it to detect version drift against a locally cached copy before re-fetching. `ingest_arxiv_paper` parses that frontmatter, promotes `title`/`authors`/`version` to `ingest_document()`'s named parameters, passes every other field through as `extra_metadata`, and always overrides `documents.authority_rank` downward via `arxiv_preprint_authority_rank()` (rank 50 — below a peer-reviewed paper's default, but above unreviewed internal notes) — holding arXiv to its own "not peer-reviewed" description rather than letting a preprint inherit a peer-reviewed paper's trust level. The caller supplies `license` explicitly, never guessed, matching the per-paper license variability above. It runs ungated (no `ALLOW_EXTERNAL_NETWORK_TOOLS` check): like this repo's 3GPP/ETSI/FCC siblings, it needs no account or credential.

## Capabilities not yet used here

`search_query` — field/boolean/date search across title, author, abstract, category and report number — is entirely unused; every call here supplies a known `id_list` and never discovers a paper the model doesn't already have an ID for. That is the single largest gap: it means a request like "find prior art on 0°-reflection-phase metasurfaces published since 2023" cannot currently be answered by the API itself and depends on the model already knowing the ID (e.g. from a citation, a WebSearch hit, or a human). Also unused: OAI-PMH bulk harvesting (for building a standing local mirror of RF-relevant categories instead of one-paper-at-a-time fetches), the S3/Kaggle bulk datasets, and `submittedDate` filtering/`sortBy` for finding the newest work in a category. None of these change what a paper says — they only change how one gets found.

## Sources

- https://info.arxiv.org/help/api/user-manual.html
- https://info.arxiv.org/help/api/tou.html
- https://info.arxiv.org/help/api/index.html
- https://info.arxiv.org/help/license/index.html
- https://info.arxiv.org/help/moderation/index.html
- https://info.arxiv.org/help/oa/index.html
- https://info.arxiv.org/help/bulk_data/index.html
- https://info.arxiv.org/about/index.html
- https://arxiv.org/category_taxonomy
- https://blog.arxiv.org/2026/06/30/arxivs-next-chapter/
- https://blog.arxiv.org/2019/08/29/our-moderation-process (via search result excerpt corroborating the "superficial"/"one look" moderation characterization)
- `knowledge/sourcing/arxiv.py`, `knowledge/provenance.py`, `.claude/skills/arxiv-doc-builder/arxiv_doc_builder/{fetch_paper,arxiv_metadata}.py`, `policies/tool_policy.yaml` (this repo's adapter and its config, read in full)
