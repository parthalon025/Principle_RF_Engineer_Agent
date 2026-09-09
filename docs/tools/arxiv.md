# arXiv API

arXiv is a free preprint server: researchers post papers there before (or
instead of) publishing them in a journal or conference proceedings, so the
work is visible immediately but has not been through formal **peer review**
(independent experts checking the science before publication) [6][7]. Its
API is a no-login, no-API-key web interface for asking arXiv "what do you
have on X" or "give me the record for paper Y" by computer instead of by
browsing the website [1]. This repo uses it as the on-ramp for one specific
job: turning an arXiv paper (LaTeX/PDF + its bibliographic record) into a
Markdown file with structured metadata that the knowledge base can ingest,
citation-first, as `LITERATURE-SUPPORTED` (or lower) evidence rather than an
unsourced claim.

## What it is

arXiv hosts more than three million papers across eight subject areas —
physics, math, computer science, quantitative biology, quantitative finance,
statistics, electrical engineering and systems science ("eess", the category
most RF/antenna papers land in), and economics [6]. As of arXiv's own current
site, it is run as "an independent nonprofit organization" (having ended its
long-standing operational partnership with Cornell University), governed by
a Board of Directors and a CEO/staff, funded chiefly by the Simons
Foundation International, member institutions, individual donors, and
Schmidt Sciences [6]. Submissions go through **moderation** — a check for
topicality and scholarly form — which arXiv's own help page explicitly
distinguishes from peer review: "the arXiv moderation process is not a
peer-review process" [7].

## Full capabilities

The query API (`export.arxiv.org/api/query`) returns Atom 1.0 XML, and
supports two lookup modes: `search_query`, a Boolean (AND/OR/ANDNOT) search
across field-prefixed metadata — title (`ti`), author (`au`), abstract
(`abs`), comment (`co`), journal reference (`jr`), category (`cat`), report
number (`rn`), or all of these (`all`) — and `id_list`, a comma-delimited
list of specific arXiv IDs, with the two combinable as filters on each other
[1]. Pagination uses `start`/`max_results`, capped at 30,000 results per
query in slices of up to 2,000 [1]. Each returned entry carries title,
abstract, authors, categories, dates, and links to the abstract page and PDF
[1][5]. Search is metadata-only — it matches those named fields, not the
full body text of the paper [1][5]. Beyond the query API, arXiv also offers
OAI-PMH metadata harvesting, bulk full-text access via cloud storage (S3) and
a Kaggle dataset, per-category RSS feeds of new submissions, and an automated
DOI/journal-reference update feed for publishers [4].

## Integrations & interfaces

It is a plain HTTPS/REST endpoint with no SDK requirement and no
authentication or API key [1]. Etiquette, not a hard-enforced quota, governs
request rate: arXiv's Terms of Use ask for "no more than one request every
three seconds, and limit requests to a single connection at a time," applied
in aggregate across a caller's machines [2]; the User Manual adds that
results are cached daily, so repeated same-day queries gain nothing [1].

## Licensing & cost

Free, with no paid tier for the API itself [1][2]. Descriptive metadata
(title, abstract, authors, categories) is dedicated to the public domain
under CC0 1.0, so no attribution is legally required for it [2]. The paper
content is different: the author keeps copyright, and arXiv holds only a
"perpetual, non-exclusive" distribution license that by default limits
downstream reuse; authors may instead opt a given paper into CC BY 4.0, CC
BY-SA 4.0, CC BY-NC-ND 4.0, or CC0, and that choice is per-paper and
irrevocable [3]. Hosting or re-serving the PDF/source from a third party's
own server generally requires the copyright holder's permission [2].

## How this repo uses it today

`knowledge/sourcing/arxiv.py` is a thin client, not an API caller itself: its
one public function, `ingest_arxiv_paper(arxiv_id, *, license,
classification, ...)`, validates the ID with a permissive regex, then shells
out (`uv run --project .claude/skills/arxiv-doc-builder --no-dev
convert-paper <id>`) to the vendored `arxiv-doc-builder` skill, which is what
actually talks to arXiv: `arxiv_metadata.fetch_metadata()` calls
`export.arxiv.org/api/query?id_list=<id>` for one paper's metadata, while
`fetch_paper.py` separately downloads LaTeX source from
`arxiv.org/src/<id>` (falling back to PDF from `arxiv.org/pdf/<id>.pdf`) and
converts source via pandoc, or PDF via a naive fallback, into Markdown with a
YAML frontmatter block (title/authors/version/published/categories/DOI/
journal/abstract). `ingest_arxiv_paper` parses that frontmatter, forwards the
promoted fields (title, authors, version) plus everything else as
`extra_metadata` to `knowledge.ingest.ingest_document`, and always overrides
`authority_rank` downward via `arxiv_preprint_authority_rank()` — never
letting an arXiv source inherit `source_type='paper'`'s peer-reviewed
default rank, precisely because arXiv moderation is not peer review [7]. The
caller must supply `license` explicitly (no guessed default), because that
varies per paper [3]. Because no credential is needed, this path is not
gated behind `ALLOW_EXTERNAL_NETWORK_TOOLS` — the same ungated posture as
this package's 3GPP/ETSI/FCC siblings, unlike the credentialed Digi-Key/
Mouser/Nexar distributor APIs.

## Capabilities not yet used here

Both `id_list` calls in this pipeline fetch exactly one already-known arXiv
ID; nothing here ever calls the API's `search_query` discovery mode — the
Boolean, field-prefixed search across title/author/abstract/category that
would let the system ask arXiv "find papers about X" instead of requiring a
human or the model's own training knowledge to already name the ID.
CLAUDE.md's iteration method explicitly calls for "search precedent before
inventing" (step 2); the wired capability only converts a precedent already
found, it does not find one. Also unused: OAI-PMH bulk harvesting, the S3/
Kaggle bulk full-text dataset, per-category RSS feeds for new-paper
monitoring, and the DOI/journal-reference auto-update feed [4] — all
discovery- or monitoring-oriented, none currently load-bearing for a
single-paper ingestion flow.

## Sources

- [1] https://info.arxiv.org/help/api/user-manual.html — API User Manual (query syntax/fields, response format, pagination, no-auth, rate-limit etiquette)
- [2] https://info.arxiv.org/help/api/tou.html — API Terms of Use (one-request-per-3s etiquette, acceptable/prohibited use, metadata CC0)
- [3] https://info.arxiv.org/help/license/index.html — Licensing help page (author copyright retention, arXiv's distribution license, optional CC licenses)
- [4] https://info.arxiv.org/help/api/index.html — API/access overview (OAI-PMH, bulk S3/Kaggle data, RSS feeds, DOI update feed)
- [5] https://info.arxiv.org/help/api/basics.html — API Basics (metadata-only search scope, entry link structure)
- [6] https://info.arxiv.org/about/index.html — About arXiv (governance, funding, 8 subject areas incl. eess, corpus size)
- [7] https://info.arxiv.org/help/moderation/index.html — Moderation help page ("not a peer-review process" quote)
- `knowledge/sourcing/arxiv.py` (this repo) — adapter implementation and its own primary-source citations
- `.claude/skills/arxiv-doc-builder/arxiv_doc_builder/fetch_paper.py` and `arxiv_metadata.py` (this repo) — the vendored skill's actual arXiv HTTP calls (`export.arxiv.org/api/query?id_list=`, `arxiv.org/src/`, `arxiv.org/pdf/`)
