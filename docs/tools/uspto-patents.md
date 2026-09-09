# USPTO patent PDFs

The USPTO (United States Patent and Trademark Office) publishes every patent and published patent application it handles as a downloadable PDF, free and with no login, at a fixed web address built from the document's number — this repo calls that address directly to pull patents like US12089385B2 (a magnetic-mirror metasurface, cited in this project's own charter) into its knowledge base as evidence. "Free, no-auth" here means literally that: no account, no API key, no per-request fee, just an HTTP GET. The catch, covered below, is that this one endpoint only *fetches a document you already know the number of* — it cannot *search*, and USPTO's broader public-data offerings that can search are a separate, larger surface this repo does not yet touch.

## What it is

`image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/<number>` is the PDF-printing backend behind **Patent Public Search**, the USPTO's official web tool for searching and viewing patents. Patent Public Search itself launched publicly in 2022, consolidating and retiring four older systems — PubEAST, PubWEST, PatFT and AppFT — into one cloud-based application built on the same platform USPTO's own examiners use [uspto.gov/about-us/news-updates/uspto-launches-new-patent-public-search-tool-and-webpage]. USPTO is a Department of Commerce agency; the download endpoint is not a separately versioned or branded product, just infrastructure of that tool, and is not listed in USPTO's own developer/API documentation — this repo's adapter verified it directly by fetching five real documents rather than from any spec (`knowledge/sourcing/patent.py`, lines 9-19).

## Full capabilities

Three distinct things sit under "USPTO patent data," at very different capability levels than the one endpoint this repo uses:

1. **Patent Public Search** (`ppubs.uspto.gov`) — full-text, field, and boolean search (inventor, assignee, classification, date range) across US patents from 1790 to present and published applications from 2001 to present. It is an interactive browser application; no fetchable USPTO page documents a public REST API behind it for programmatic search.
2. **The Open Data Portal (ODP)**, `data.uspto.gov`/`api.uspto.gov`, launched February 12, 2025, folding together the old Patent Examination Data System and Bulk Data Storage System plus a developer hub into one platform [uspto.gov/about-us/news-updates/uspto-launches-new-open-data-portal-easy-quick-access-data]. It exposes a Patent File Wrapper API (bibliographic data, file-history documents, assignment and transaction history for applications filed since Jan 1, 2001), PTAB trial/appeal search APIs, and bulk-data search/download/product APIs for structured full-text and bibliographic products. Since June 18, 2026 it has required a free USPTO.gov account to register for access [uspto.gov/about-us/news-updates/uspto-open-data-portal-require-registration-access-beginning-june-18-2026]; its APIs take a free, USPTO-issued key [patent-client.readthedocs.io/en/latest/user_guide/open_data_portal.html].
3. **PatentsView** — a USPTO-funded, structured search/analytics resource (maintained by USPTO's Office of the Chief Economist) offering disambiguated inventor, assignee, and location data plus citation graphs, historically its own site and API. As of March 20, 2026 it migrated into the ODP, and its standalone search/API/visualization services paused mid-transition [uspto.gov/subscription-center/2026/patentsview-migrating-uspto-open-data-portal-march-20] — consistent with `search.patentsview.org` failing to resolve at all when this research fetched it.

## Integrations & interfaces

The downloadPdf endpoint is plain, unauthenticated HTTPS returning raw `application/pdf` bytes — no client library, no key, no documented rate limit. Patent Public Search is browser-only. ODP is JSON REST under `api.uspto.gov`, keyed, with a documented open-source Python client (`patent-client`) already wrapping it.

## Licensing & cost

Free at every layer discussed. USPTO-authored patent documents and data are works of the U.S. Government and outside copyright under 17 U.S.C. §105, which places them in the public domain [govinfo.gov/content/pkg/USCODE-2011-title17/html/USCODE-2011-title17-chap1-sec105.htm] — though, as this repo's adapter already notes, a specific patent can still embed third-party copyrighted material under its own notice. ODP registration and API keys are free; no paid tier was found for any USPTO service covered here.

## How this repo uses it today

`knowledge/sourcing/patent.py`'s `ingest_patent()` does exactly one thing: given a patent or publication number, `normalize_patent_number()` validates and reshapes it, `patent_pdf_url()` builds the bare-digits download URL, and the PDF is fetched with no fallback if USPTO doesn't have that number. `choose_conversion_route()` then decides, from measured text density, whether to read the real text layer (`TEXT_LAYER_ROUTE`, via the vendored arxiv-doc-builder skill's two-column extractor) or OCR and image-render every page (`SCANNED_VISION_ROUTE`) — because, as the module documents at length, every USPTO-served PDF sampled so far is a zero-text scanned image. `parse_front_page_metadata()` reads the front-sheet INID fields (title, inventors, assignee, dates) by regex. Nothing here searches; the module docstring states plainly that deriving one document's number from the other (grant ↔ publication) "needs a keyed USPTO/PatentsView API this project has no credential for."

## Capabilities not yet used here

The concrete gap: **USPTO's Open Data Portal (which now also carries PatentsView's role) offers a free, key-authenticated structured search API** — by inventor, assignee, CPC classification, keyword, and filing/publication date, with citation-graph data — and this repo's adapter has no path to it at all. Today a request like "find prior-art metasurfaces with 0°-reflection-phase claims filed since 2023" cannot be answered by this tool; it depends entirely on a human or a prior WebSearch already handing the model a specific number. The same API would also solve the adapter's stated blind spot of linking a pre-grant publication number to its later grant number. Separately unused: ODP's bulk full-text/bibliographic products (for a standing local mirror instead of one-document fetches) and PTAB trial/appeal data (validity challenges — likely out of scope for this repo's design purpose, but real).

## Sources

- https://www.uspto.gov/patents/search/patent-public-search
- https://www.uspto.gov/about-us/news-updates/uspto-launches-new-patent-public-search-tool-and-webpage
- https://www.uspto.gov/about-us/news-updates/uspto-launches-new-open-data-portal-easy-quick-access-data
- https://www.uspto.gov/about-us/news-updates/uspto-open-data-portal-require-registration-access-beginning-june-18-2026
- https://www.uspto.gov/subscription-center/2026/patentsview-migrating-uspto-open-data-portal-march-20
- https://www.govinfo.gov/content/pkg/USCODE-2011-title17/html/USCODE-2011-title17-chap1-sec105.htm (17 U.S.C. §105, primary statutory text)
- https://patent-client.readthedocs.io/en/latest/user_guide/open_data_portal.html (third-party open-source client's documentation of ODP's API-key requirement and scope)
- `knowledge/sourcing/patent.py`, `knowledge/sourcing/_patent_convert.py`, `knowledge/provenance.py`, `policies/tool_policy.yaml` (this repo's adapter and its config, read in full)
- Not independently fetchable during this research: `data.uspto.gov`'s own sub-pages (`/apis/getting-started`, `/bulkdata/datasets`, `/support/transition-guide/patentsview`, etc.) returned no extractable content (JS-rendered SPA) via WebFetch, and `search.patentsview.org` failed outright to resolve (`ENOTFOUND`) — consistent with the March 2026 migration/pause noted above. Facts about those pages here are instead drawn from official USPTO announcement pages and WebSearch result excerpts of them, cited above; anything not backed by one of those is omitted rather than guessed.
