# Nexar API (Octopart data)

Nexar is a single GraphQL API, owned by Altium, that sits on top of Octopart's aggregated database of electronic-component data — instead of asking one distributor "do you stock this part," it asks "who, across many distributors, stocks this part, at what price, with what datasheet" in one query [nexar.com/api]. This repo uses it as one of three component-sourcing tools (alongside `digikey.py` and `mouser.py`) to check that a part the model has proposed for a design — a substrate, an RF connector, a lumped element — actually exists, is stocked somewhere, and has a real datasheet to ingest as cited evidence, rather than trusting the model's memory of a part number.

## What it is

Nexar is a GraphQL-based API platform made and maintained by Altium Limited, unifying supply-chain data (from the Octopart component-search database Altium acquired), Altium 365 design data, and Altimade manufacturing services behind one endpoint [nexar.com/api]. Octopart itself has aggregated distributor/manufacturer catalog data since 2007; Nexar is the current, actively developed surface for that data — Octopart's legacy REST v3/v4 APIs are explicitly being migrated onto it, per Nexar's own migration guides [support.nexar.com's v3 and v4 migration articles].

## Full capabilities

The schema is organized by operation prefix into four domains: `sup` (supply — the Octopart component database), `des` (design — Altium 365 PCB/project data, gated on an Altium Designer license and workspace membership), manufacturing (Altimade production/quoting), and Spectra (market-intelligence analytics combining the other three) [support.nexar.com/.../introduction-to-the-nexar-api]. Within supply, `supSearchMpn` does exact manufacturer-part-number matching (one hit per exact MPN); `supSearch` does fuzzy keyword/family matching (a bare "STM32" query returns roughly 10,000 hits across the whole family); `supMultiMatch` batches several MPNs in one call; `supParts`/`supCategories`/`supManufacturers`/`supSellers` do direct-ID and reference lookups, the last three costing nothing against the part quota [support.nexar.com Playground query-examples article]. A matched `part` carries pricing/stock via nested `sellers → offers` (quantity price-breaks, per-seller inventory, multi-currency/per-country availability), `specs` (structured parametric attributes), `bestDatasheet`/`documentCollections`, images, and lifecycle status [support.nexar.com Playground query-examples article; support.nexar.com compliance-documents article]. Since June 2022 the schema also exposes ECAD data — `PartCadModel(s)` and CAD download/preview URLs — covering roughly 10 million symbol, footprint, schematic and 3D-model records sourced from Ultra Librarian and SnapEDA (symbols/footprints) and TraceParts (3D models) [altium.com/.../nexar-announces-massive-cad-model-marketplace, June 16 2022].

## Integrations & interfaces

OAuth 2.0 `client_credentials` grant against `https://identity.nexar.com/connect/token`, returning a bearer token good for 86,400 seconds; all data access is a single POST to `https://api.nexar.com/graphql` with `Authorization: Bearer <token>` [support.nexar.com "Authorization" article; github.com/NexarDeveloper/nexar-token-py]. Nexar hosts an in-browser IDE (Nitro, by ChilliCream) plus a Voyager schema visualizer [support.nexar.com Playground article], and official sample clients for Python, PowerShell, and a Blazor design-query demo under the `NexarDeveloper` GitHub org.

## Licensing & cost

Nexar's official sample repos (e.g. `nexar-token-py`) are MIT-licensed [github.com/NexarDeveloper/nexar-token-py/blob/main/LICENSE], but that covers only the sample code, not the underlying part data or the API service, whose usage terms were not found in a fetchable license file. Access is metered by "matched parts" — unique parts a query returns, not query count; zero-cost reference queries (categories, manufacturers, sellers) don't count [support.nexar.com "Part Limits and How They Work"; support.nexar.com FAQ]. On signup every account gets one free Evaluation application with a **lifetime** (not monthly) cap of 1,000 matched parts [support.nexar.com FAQ]; Nexar's marketing page separately advertises a 100-matched-part cap on the pre-signup Playground [nexar.com/api] — this repo's adapter docstring already captures both figures. Paid self-serve tiers are Standard (2,000 matched parts) and Pro (15,000), Enterprise custom-priced; no dollar figures are published, only "contact sales" [nexar.com/compare-plans]. Notably, per that page, Datasheets and Technical Specs are gated to Pro tier and above, while Advanced Search, Pricing, Availability, Images and Lead Time are on every tier including free Evaluation [nexar.com/compare-plans] — so this repo's datasheet lookup may need a paid tier to actually return results, a fact its module docstring doesn't flag. No numeric rate limit (requests/second) was found in Nexar's own docs; a third-party summary not corroborated from a Nexar primary source (so treated here as unverified) cites 2 req/s, 200/15 min, 3,000/12 h, 40,000/week.

## How this repo uses it today

`knowledge/nexar.py`'s `lookup_nexar_datasheet()` calls exactly one operation: an exact-MPN `supSearchMpn(q: $mpn, limit: 5)` query returning `part { mpn, manufacturer { name }, bestDatasheet { url } }`. `_parse_matches` takes only the first hit, and if it carries a `bestDatasheet.url`, downloads that PDF and hands it to the same `ingest_document(source_type="datasheet")` pipeline the other sourcing adapters use (`knowledge/ingest.py`). It gates on `ALLOW_EXTERNAL_NETWORK_TOOLS=true` (`knowledge/sourcing_common.py`), is fully dependency-injected (`get_token`/`search`/`download`/`ingest` all swappable for tests), and its own docstring flags that no `NEXAR_CLIENT_ID`/`SECRET` is registered here and the client has never been run against the live API end-to-end.

As of ticket #276, a second function, `lookup_nexar_part_data()`, runs a separate extended query (`_PART_DATA_QUERY`) also requesting `specs` (parametric attributes) and `sellers → offers` (multi-distributor pricing/stock) on the matched part — the two gaps this section used to name. It shares the same `get_token`/network-tools-gate seam as `lookup_nexar_datasheet()` but never calls `download`/`ingest_document`: it returns structured data (a `manufacturer`/`manufacturer_part_number`/`datasheet_url` identity block plus `specs` and `offers` lists), not a document. `lookup_nexar_datasheet()` itself, and its `_QUERY`, are unchanged. No CAD or design-domain query is called by either function.

## Capabilities not yet used here

The CAD/footprint domain (`PartCadModel`, from SnapEDA/Ultra Librarian/TraceParts) is unused; a real footprint or 3D model for an RF connector or SMD part is plausibly useful once this repo's manufacturing/geometry side matures, though it's generic ECAD data, not RF-specific characterization. `supSearch`'s fuzzy family search, `supMultiMatch`'s batch lookup, lifecycle status, and the whole `des`/Altimade/Spectra domains (Altium-account-gated design data, manufacturing quoting, market analytics) are also unused and are a poorer fit here.

## Sources

- https://nexar.com/api
- https://nexar.com/compare-plans
- https://support.nexar.com/support/solutions/articles/101000450648-introduction-to-the-nexar-api
- https://support.nexar.com/support/solutions/articles/101000497890-frequently-asked-questions
- https://support.nexar.com/support/solutions/articles/101000476314-part-limits-and-how-they-work
- https://support.nexar.com/support/solutions/articles/101000494582-nexar-playground-graphql-query-examples
- https://support.nexar.com/support/solutions/articles/101000452264-supply-sorting-and-filtering-your-queries-using-attributes (ticket #276: confirms `specs { attribute { name } value displayValue unitsName }` verbatim as one worked query)
- https://support.nexar.com/support/solutions/articles/101000470421-working-with-octopart-s-supply-data
- https://support.nexar.com/support/solutions/articles/101000525962-transitioning-from-restful-api-into-graphql-api
- https://support.nexar.com/support/solutions/articles/101000434416-migration-from-octopart-v3-api
- https://support.nexar.com/support/solutions/articles/101000469281-migration-from-octopart-v4-nexar-legacy-api-
- https://github.com/NexarDeveloper/nexar-token-py (and its `LICENSE` file, MIT)
- https://www.altium.com/company/newsroom/press-releases/nexar-announces-massive-cad-model-marketplace
- `knowledge/nexar.py` (this repo's adapter, read in full)
- `docs/tools/digikey.md` (read for comparison, not edited)
