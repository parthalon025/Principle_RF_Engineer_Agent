# Nexar API (Octopart data)

Nexar is a GraphQL API — a single flexible query endpoint you shape per-request, instead of dozens of fixed REST endpoints — that gives programmatic access to Octopart, an electronic-component search engine that aggregates catalog data (price, stock, datasheets) from many distributors' warehouses at once, rather than any one distributor's own inventory [nexar.com/api; support.nexar.com introduction article]. This repo uses it as one of three "component-sourcing" tools (with Digi-Key and Mouser) to check that a part the model proposed for a design — a connector, a substrate, a lumped element — is a real, orderable part with a real datasheet to cite as evidence, rather than trusting the model's memory of a part number that may not exist.

## What it is

Nexar is a platform and GraphQL API operated by Nexar, a business unit of Altium Limited; Octopart (founded independently, acquired by Altium in 2015) is the supply-chain data source behind it, and Octopart's older REST API was itself rebranded and rebuilt as the GraphQL-based Nexar API [resources.altium.com/p/the-nexar-story; nexar.com/api page footer, "©2024 Altium Limited"]. Altium in turn became a wholly owned subsidiary of Renesas Electronics on 1 August 2024, for approximately A$9.1 billion [renesas.com/en/about/newsroom/renesas-completes-acquisition-altium]. There is no separate open-source "version number" — it is a hosted, continuously updated commercial service, not a downloadable tool with releases.

## Full capabilities

The schema is organized by query prefix. **Supply** (`sup...`) covers over 70 million parts with distributor stock, pricing, lead time and lifecycle data updated daily [support.nexar.com introduction article], plus datasheets, technical specs, "similar parts" (alternates), and — notably for this repo's purpose — "ECAD Modules," i.e., CAD symbol/footprint data attached to a part record [nexar.com/compare-plans]. **Design** (`des...`) queries a connected Altium 365 workspace: PCB projects, schematic/PCB/BOM content, nets, component footprints and symbols, and positional data [support.nexar.com "Design Queries," "Working with Altium 365 & Design Data"] — this only returns anything for accounts with an Altium 365 workspace, not a general public catalog. **Manufacturing** integrates Altimade for quoting/ordering PCB fabrication and assembly, and **Spectra** layers market/competitive analytics across design, supply and manufacturing data [support.nexar.com introduction article]. Developer tooling includes a browser GraphQL IDE ("Nitro"), a schema visualizer ("Voyager," at `api.nexar.com/ui/voyager`), an Excel add-in, and Power Query/Mendix connectors, all under the `NexarDeveloper` GitHub org, MIT-licensed [github.com/NexarDeveloper].

## Integrations & interfaces

OAuth2 `client_credentials` against `https://identity.nexar.com/connect/token`, then a single POST endpoint `https://api.nexar.com/graphql` — both already confirmed directly against Nexar's own docs in `knowledge/nexar.py`'s module docstring. Access tokens last 24 hours; token *requests* are separately throttled (2/second, 200/15 min, 3,000/12 h, 40,000/week) [support.nexar.com "Application Access Token"], and each API call itself times out after 90 seconds [support.nexar.com FAQ]. Unlike Digi-Key's documented per-minute/per-day request caps, Nexar's real throttle on ordinary use is a **matched-parts quota**, not a request-rate limit — each part returned by a query is metered against a monthly (or, for the free tier, lifetime) allowance, so one query returning many hits can exhaust a quota faster than many queries returning few hits [support.nexar.com "Part Limits and How They Work"].

## Licensing & cost

Not open source; use is governed by Nexar's own terms of service, linked from its FAQ as `octopart.com/api/terms` — that page itself returned HTTP 403 when fetched directly here, so its exact clauses are not verified firsthand. Published plans are Evaluation (free), Standard, Pro, and Enterprise (custom quote); no monthly price is published on Nexar's own pricing-comparison page for any named tier [nexar.com/compare-plans]. Third-party reporting (not Nexar's own site, lower confidence) puts Standard around $500/month (2,000 parts/month, missing lifecycle/datasheets/tech-specs/ECAD) and Pro around $2,000/month (15,000 parts/month) [zenode.ai/posts/the-nexar-api-what-engineers-need-to-know-in-2026]. **Nexar's own docs disagree with each other on the free Evaluation tier's exact cap**: its FAQ states "a lifetime part limit of 1000" while its separate "Part Limits and How They Work" article states "a lifetime part limit of 100" for the same Evaluation app [support.nexar.com FAQ vs. "Part Limits and How They Work"] — noted here rather than resolved, matching `knowledge/nexar.py`'s own already-hedged "capped around 1,000... (100 in the pre-signup Playground)."

## How this repo uses it today

`knowledge/nexar.py`'s `lookup_nexar_datasheet()` gets a token, runs exactly one GraphQL query — `supSearchMpn(q: $mpn, limit: 5)` requesting `mpn`, `manufacturer { name }`, and `bestDatasheet { url }` — takes the first hit, downloads its datasheet PDF, and hands it unchanged to `knowledge/ingest.py`'s `ingest_document(source_type="datasheet")`. `_parse_matches` reads only those three fields per part. It gates on `ALLOW_EXTERNAL_NETWORK_TOOLS=true`, is fully dependency-injected for testing, and — per its own module docstring — has never been run against the live API (no `NEXAR_CLIENT_ID`/`SECRET` registered here). No pricing, availability, lifecycle, ECAD/footprint, design (`des`), or manufacturing query is ever sent.

## Capabilities not yet used here

The clearest gap for this repo's purpose is **ECAD Modules** — per-part CAD symbol/footprint data, which is directly useful once a design moves from "this part exists" to "this part needs to be placed and routed," and ties into the design-for-manufacture goal CLAUDE.md names as the destination. Also unused: multi-distributor **pricing/availability aggregation** itself (the trait that most distinguishes Nexar from a single-distributor API — one query surfaces every distributor's stock and price for the same MPN, useful for the cost trade-offs the program is meant to surface), **lifecycle status** (obsolescence risk for a part a design commits to), **similar-parts** (alternates when a match is discontinued), and the entire **design (`des`)** and **manufacturing (Altimade)** domains, which are irrelevant here unless this repo's own designs live in a connected Altium 365 workspace.

## Sources

- https://nexar.com/api
- https://nexar.com/compare-plans
- https://nexar.com/manufacturer-distributors
- https://support.nexar.com/support/solutions/articles/101000450648-introduction-to-the-nexar-api
- https://support.nexar.com/support/solutions/articles/101000452406-application-access-token
- https://support.nexar.com/support/solutions/articles/101000476314-part-limits-and-how-they-work
- https://support.nexar.com/support/solutions/articles/101000497890-frequently-asked-questions
- https://support.nexar.com/support/solutions/articles/101000497657-design-queries-in-an-ide-nitro-
- https://support.nexar.com/support/solutions/articles/101000477082-working-with-altium-365-design-data
- https://resources.altium.com/p/the-nexar-story
- https://www.renesas.com/en/about/newsroom/renesas-completes-acquisition-altium
- https://github.com/NexarDeveloper (org listing; MIT license as stated per-repo)
- https://octopart.com/api/terms — fetched directly, returned HTTP 403 Forbidden; terms text not independently verified, only its existence and URL (via the FAQ page above)
- `knowledge/nexar.py` (this repo's adapter, read in full) and `knowledge/sourcing_common.py`, `knowledge/mouser.py`, `docs/tools/digikey.md` (for comparison)
