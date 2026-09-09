# Free APIs for finding a real equipment/ink/substrate alternative to a fabrication-capability gap

**Research date:** 2026-09-09
**Prompted by:** ADR-0030's live discussion of whether a "this doesn't fit the currently
loaded equipment" warning should just explain the shortfall to a human, or also actively
search for a specific real alternative (a named machine, ink, or substrate) that would
clear the capability bar, citing a source — the same "search precedent before inventing"
instinct the loop already applies to design geometry (`docs/element-library-prior-art.md`),
scoped here to the three domain-model libraries a candidate is checked against per
`CONTEXT.md`: **Fabrication capability** (print/cure/laminate stage limits),
**Ink-property library** (`(ink, process state, property)` → resistivity, cured thickness,
cure schedule, viscosity), and **Material-property library** (`(material, frequency,
property)` → permittivity, loss tangent, conductivity).
**Scope:** does a free or no-cost-tier API exist that a design loop could query to find a
named, real alternative when the configured shop can't meet a candidate's needs — and if
so, is wiring it into the warning path a small integration or a much bigger one.

---

## Bottom line up front

**A free-tier API exists for finding a named *ink or adhesive product* (conductive inks,
epoxies, and pastes are genuinely stocked, catalog SKUs at Digi-Key and Mouser). No free
or paid API exists for finding fabrication *equipment* (printers, curing ovens,
laminators) — those are capital goods sold by direct manufacturer quote, not catalog
items, and nobody publishes a queryable spec database for them. Materials databases split
the same way: MatWeb and Matmatch have real free-to-browse catalogs but no public API;
the one materials database that does have a free, documented API (Materials Project)
computes crystal-level, static/DC dielectric properties from first-principles simulation —
not the frequency-dependent, RF-band loss tangent this project's Material-property library
needs, and not something a manufacturer sells.**

Even where a real product match exists (the ink case), what the API hands back is catalog
metadata — description, price, a link to a PDF datasheet — not the structured numbers
(volume resistivity in Ω·cm, cure schedule in °C/minutes, viscosity in cP) the
Ink-property library is keyed on. Those numbers live inside the linked PDF, and this
project has already decided, for the Material-property library, that "the library itself
never parses a document; an uploaded document is the citation/audit trail, not an
extraction target" (`CONTEXT.md`, Material-property library entry). Wiring a distributor
API into the fabrication-gap warning would either inherit that same non-extraction stance
(cite the product and its datasheet URL, let a human read the number in) or would need to
solve PDF-datasheet parsing — a materially bigger, unsolved problem — to auto-populate the
library. **Recommendation: worth doing for the ink half, on the citation-only pattern; not
worth attempting for the equipment half, because there is nothing to query.**

---

## 1. Does a free/public API exist, filterable by a numeric capability?

| Source | Covers | Free? | Filterable by numeric spec? | Verdict |
|---|---|---|---|---|
| **Digi-Key Product Information API (v4)** | Electronic components **and** stocked chemical/adhesive SKUs (conductive inks, epoxies, pastes) | **Yes — free**, OAuth2 app registration, no fee | Category-level `ParametricFilters` mechanism exists; whether cure-temp/viscosity are numeric-range-filterable per category is unconfirmed (see §2) | **Ink/adhesive: usable. Equipment: not carried at all.** |
| **Mouser Search API** | Same ink/adhesive SKUs, electronic components | **Yes — free**, request-form signup | Returns fields, not demonstrated as numeric-range filterable | Same as above |
| **Nexar API (formerly Octopart)** | Electronic components, sourced from 280+ distributor feeds | Free **Evaluation** tier only (100 matched parts, lifetime — a trial, not an ongoing free tier); paid tiers beyond that | Parametric search exists for standard component categories | Catalog is component-centric; conductive inks/pastes are a Digi-Key/Mouser SKU category, not confirmed present in Nexar's aggregated feed |
| **MatWeb** | ~130,000 material datasheets (metals, plastics, composites, ceramics) | Free to **browse** without registration; **no public API** — access beyond browsing is a paid **database license** arrangement | N/A — no API | Not usable programmatically at zero cost |
| **Matmatch** | ~90,000+ materials, filterable by property, from licensed supplier data | Free to **browse and search on the website** | Web UI supports numeric-range filtering (sliders) | **No public developer API found** — search-based, not queryable from code |
| **Materials Project API (MAPI)** | Computed crystal-structure properties (DFT/DFPT) | **Yes — fully free**, API key required, no rate limit stated in its own docs | Yes, `mpr.materials.dielectric.search(...)` | Returns **static, zero-frequency, real-valued** dielectric tensors for crystalline compounds — not RF-band loss tangent, and not something manufacturers sell as ink/substrate stock (see §3) |
| **Manufacturer ink/printer datasheets** (NovaCentrix, DuPont, Henkel, Voltera, Optomec, Fujifilm Dimatix) | The specific inks/machines this project would actually specify | Datasheets themselves are free PDFs | No API of any kind — static PDF per product page | **No API exists to query** |
| **GlobalSpec/Engineering360, ThomasNet** | Industrial equipment and supplier directories, incl. printing equipment | Free web search (`SpecSearch`) | Web UI only | **No public developer API**; third-party scrapers exist but are unofficial and not free |

### 1a. Component/ink distributor catalogs — the one genuinely usable case

Conductive inks, silver epoxies, and conductive paints are real, stocked SKUs at both
major electronics distributors, confirmed by their own product listings — e.g. MG
Chemicals' 8330S/8331S silver conductive epoxies and 842AR conductive paint are carried at
both [Digi-Key](https://www.digikey.com/en/products/detail/mg-chemicals/8331-14G/2639875)
and [Mouser](https://www.mouser.com/ProductDetail/MG-Chemicals/842AR-P), alongside
comparable products from CAIG Laboratories and Chip Quik. This means a distributor API
query for "conductive ink" or "conductive epoxy" returns real, purchasable, named
alternatives — not a dead end.

**Digi-Key Product Information API v4** (`developer.digikey.com`, fetched directly):
offers `ProductSearch`/`KeywordSearch` endpoints, a documented sandbox tier for free
development, and production access via OAuth2 app + organization registration. Digi-Key's
own resources page states plainly that its APIs are offered "at no cost." Official rate
limits (`developer.digikey.com/tutorials-and-resources/shared-concepts`, confirmed via
search-indexed page text — the page itself returned 403 to direct fetch): Product
Information is rate-limited to **120 requests/minute, 1,000/day** per application, with
`X-RateLimit-*` response headers and a documented process to request a higher limit.
Community inspection of the live API (a GitHub script targeting API v4) confirms the
search response carries a `FilterOptions.ParametricFilters` object and an
`AppliedParametricFiltersDto`, i.e. the API supports filtering by category-specific
attributes — the mechanism a "find an ink with volume resistivity below X" query would
need. **Not independently confirmed here:** whether cure temperature, viscosity, or
volume resistivity are exposed as *numeric-range* parametric filters (vs. free-text or
categorical values like "High Viscosity") for the adhesives/conductive-materials category
specifically — Digi-Key's product pages returned 403 to direct fetch, so this rests on the
general API schema, not a category-specific field list.

**Mouser Search API** (`mouser.com/en/api-search/` — content below reconstructed from
consistent search-engine-indexed quotations of the official page; direct `WebFetch`
timed out repeatedly on this domain): free, instant-access signup via an online request
form tied to a My Mouser account; Mouser emails the API key. Limits: **up to 50 results
per call, 30 calls/minute, 1,000 calls/day**. Returned fields are catalog metadata —
Mouser/Manufacturer part number, manufacturer name, availability, **datasheet URL**,
description, category, packaging, compliance/RoHS/lifecycle status, lead time, suggested
replacements, and up to 4 price breaks. **No numeric electrical/thermal/rheological
property fields are part of the documented response** — a query returns the *datasheet
link*, not the *numbers on the datasheet*.

**Nexar API** (`nexar.com/api`, fetched directly): GraphQL API, OAuth2 via
`portal.nexar.com`, split into a **Design** scope (Altium 365 CAD data) and a **Supply**
scope (Octopart's distributor-aggregated pricing/stock/lifecycle data across 280+
providers). Its own page states: *"Our plans are tailored to your needs, ranging from the
FREE Evaluation plan that allows up to 100 matched parts to our custom Enterprise plan."*
That is a **100-part lifetime trial, not a recurring free tier** — meaningfully more
restrictive than Digi-Key's or Mouser's ongoing free quotas. Because Nexar's Supply data
is itself sourced by aggregating distributor feeds (including, per public reporting,
partners like OnlineComponents.com), it is not established here whether conductive-ink SKUs
specifically (as opposed to standard electronic components) surface in its aggregated
catalog — this project would need to test a live query, not assume coverage.

### 1b. Equipment (printers, curing, lamination) — nothing to query

No source found — official documentation, pricing page, or otherwise — describes a public
API, free or paid, for searching fabrication equipment by numeric capability. Aerosol-jet
printer maker **Optomec**, screen-printing and cure/laminate equipment makers generally,
and even **Voltera** (the NOVA/V-One platform this project's own prior research
(`docs/mxene-voltera-nova-printability.md`) already examined) publish only marketing pages
and static spec-sheet PDFs; there is no signup form, developer portal, or documented
endpoint of any kind. This is capital equipment sold by direct sales/quote relationship,
not a catalog SKU a distributor stocks — the entire commercial model that makes the
Digi-Key/Mouser case work (stocked, orderable-by-anyone parts with public list prices) does
not exist for a $50k–$500k aerosol-jet system or a production curing oven.
**Engineering360/GlobalSpec** does index "Industrial Printing Equipment" through its
web-based `SpecSearch` tool, and **ThomasNet** indexes 500,000+ suppliers by capability —
but neither publishes a developer API; the only programmatic access found for either is
unofficial third-party scraping services (Apify, Piloterr), which are not free beyond a
small trial credit and are not sanctioned by the site owners.

### 1c. Materials databases — free browsing, not free querying

**MatWeb** (`matweb.com/services/databaselicense.aspx`, direct fetch returned 403;
findings via search-indexed page content and independent secondary confirmation): over
130,000 entries, free to browse without registration for the "vast majority" of users, but
MatWeb's own licensing page frames programmatic/bulk access as a paid **database license**
arrangement ("Because MatWeb already has the programming in place, we can assemble a
complete property-based search program" — sold as a service to the licensee, not exposed
as a public API). No public REST/GraphQL endpoint exists.

**Matmatch**: genuinely free web search across 90,000+ materials with property-range
sliders and supplier links (Alcoa, ThyssenKrupp, VDM Metals, Plansee, per its own
marketing). No public developer API was found in searches of its own site or third-party
API directories — the free access is scoped to the website's own search UI, not to
external code.

**Materials Project API (MAPI)**: the one materials source with a genuine, fully free,
documented public API — confirmed directly from its own docs
(`docs.materialsproject.org/downloading-data/using-the-api/getting-started`): an API key
tied to a free account is the only requirement stated; no rate limit or cost is mentioned
anywhere in its own setup documentation. But its dielectric data is the wrong shape for
this project's need, confirmed directly from its own methodology page
(`docs.materialsproject.org/methodology/materials-methodology/dielectricity`): *"The
dielectric tensors from the Materials Project (MP) are calculated from first principles
Density Functional Perturbation Theory (DFPT)... we consider the static response (i.e.,
the response at constant electric fields or the long wavelength limit)."* That is a
**zero-frequency, real-valued, single-crystal** number computed by simulation — not a
measured, frequency-swept loss tangent at X-band or any other RF band, and not a property
of a purchasable substrate sheet (PET, Kapton, Rogers laminate) this project would actually
specify. The database also has no concept of "a material you can buy" — it indexes
crystal structures, most of which are not commercial engineering substrates at all.

---

## 2. What does a usable query actually return, and how much friction is there?

| API | Returned fields (confirmed) | Access friction |
|---|---|---|
| Digi-Key Product Information v4 | Part numbers, manufacturer, description, category, `FilterOptions`/parametric attributes, pricing, **datasheet URL**; no MyPricing on plain KeywordSearch | Free; requires My DigiKey account → register app → sandbox first → organization registration for production; OAuth2 client ID/secret on every call; 120 req/min, 1,000 req/day |
| Mouser Search API | Part numbers, manufacturer, description, category, packaging, compliance, lifecycle, lead time, suggested replacements, **datasheet URL**, up to 4 price breaks | Free; online request form → emailed API key; 50 results/call, 30 calls/min, 1,000 calls/day |
| Nexar (Octopart) Supply scope | Pricing, stock levels, lifecycle status, "technical component information" (exact field list not confirmed here) | Free tier is a **100-part lifetime trial**; OAuth2 via `portal.nexar.com`; paid tiers for ongoing use, pricing not published — "contact sales" |
| Materials Project API | Dielectric tensor (electronic + ionic), derived static dielectric constant, refractive index, ferroelectricity potential — per `DielectricDoc` | Free; API key from a free account; no stated rate limit; **wrong physical quantity for RF work** |
| MatWeb, Matmatch, GlobalSpec, ThomasNet | N/A — no public API | Free web search only; programmatic access requires a paid license (MatWeb) or unofficial scraping (ThomasNet) or doesn't exist (Matmatch, GlobalSpec) |
| Ink/printer/equipment manufacturers direct (NovaCentrix, DuPont, Henkel, Voltera, Optomec, Fujifilm Dimatix) | Full technical/safety datasheets, but only as static PDFs per product page | Free to download; **zero programmatic access of any kind** |

The one recurring, load-bearing gap across every *usable* API (Digi-Key, Mouser): **the
response is catalog metadata plus a link to a PDF, not the engineering numbers
themselves.** None of the three distributor APIs return volume resistivity, cure
temperature/time, or viscosity as first-class response fields for conductive-ink/adhesive
products — a spot check of the underlying MG Chemicals 8330S/8331S datasheets (via a
distributor product page, RS Online, since Digi-Key's own pages return 403 to automated
fetch) shows those numbers exist as structured attributes on *some* distributor product
pages (e.g. "Cure Time: 2 hr @ 65°C", "Viscosity Description: High Viscosity",
"Electrical Resistivity: 0.007 Ω·cm") — but whether Digi-Key's or Mouser's own API
responses expose these as machine-readable parametric fields (versus only rendering them
in the product-page HTML a human reads) is **not confirmed** here; direct verification was
blocked by both sites returning 403 to automated fetches of individual product pages.

---

## 3. Is this a viable, low-effort integration — a plain recommendation

**No, not as a drop-in — and the reason is not "the APIs don't exist," it's a field-mapping
and trust problem, split cleanly along the ink/equipment line:**

- **Equipment (print/cure/laminate capability gap): there is nothing to integrate.** No
  API, free or paid, lets code search "aerosol-jet printers with ≤50 µm minimum feature
  size" or "curing ovens rated above 200 °C" and get back a named, real machine. That
  branch of the warning can only ever say what's missing, never propose a fix — which is
  consistent with `CONTEXT.md`'s existing framing of Fabrication capability as "the
  configured, cross-run set of what a specific piece of equipment can currently build,"
  a fact about *owned* equipment, not a market to search.

- **Ink/adhesive (Ink-property library gap): a real, named product can be found for
  free**, via Digi-Key's or Mouser's product search, and both are already free enough for
  this project's likely query volume (a few thousand lookups/day, well under either
  service's daily cap). This is a genuine "search precedent before inventing" win, in the
  same spirit already applied to design geometry. **But it only gets the loop to "here is
  a named product and a link to its datasheet" — not to "here is the volume resistivity
  number to put in the Ink-property library."** Getting the number requires one of:
  1. **Citation-only integration** (low effort, consistent with existing project
     doctrine): surface the matched product name, distributor, and datasheet URL as a
     candidate the human reviews and manually enters into the Ink-property library with
     its own provenance — exactly the pattern already established for Material-property
     library entries ("the library itself never parses a document; an uploaded document
     is the citation/audit trail, not an extraction target"). This is genuinely small: one
     API call, one link, no new parsing surface.
  2. **Auto-populated integration** (materially bigger): parse the linked PDF datasheet to
     extract volume resistivity/cure schedule/viscosity automatically. This is a
     structured-data-extraction problem this project has already, deliberately, declined
     to take on for its own Material-property library — doing it here would be new scope,
     not a reuse of an existing pattern, and would need the same trust safeguards (a human
     checks the extracted number before it's treated as `MANUFACTURER-SPECIFIED`) that
     manual entry already gets for free.

- **A second, structural reason to keep a human in the loop regardless of which path is
  chosen:** even a successfully matched ink is a *different* ink than whatever the shop is
  actually configured with — new supplier relationship, new minimum order quantity, new
  qualification/testing burden before it's trusted on a real part. The API can find a
  name; it cannot vouch for whether the shop should actually buy it. That decision belongs
  to the same human who already approves any spend under this project's "warn, never
  block... nothing that spends real material, machine time or money happens without a
  human saying yes" principle.

**Recommendation:** wire the citation-only version (option 1) for the ink/adhesive half of
the warning path — it is cheap, uses an already-free API, and slots into a citation
pattern this project already has. Do not attempt the equipment half; there is no data
source to build it from. Do not attempt automatic datasheet parsing as part of this
integration; it is a separate, larger undertaking this project has already chosen not to
take on for its existing Material-property library, and there's no reason the ink case
should get a different answer.

---

## What could not be verified

1. **Whether Digi-Key's or Mouser's parametric-filter schema exposes cure
   temperature/viscosity/volume resistivity as numeric-range-filterable fields**, as
   opposed to free-text or categorical attributes, for the adhesives/conductive-materials
   category specifically. Both sites return 403 to automated fetches of individual product
   pages and API-docs subpages, so this rests on (a) the general API schema (confirmed to
   support *some* parametric filtering, category-unspecified) and (b) a same-product
   datasheet on a third-party distributor (RS Online) that does show these as structured
   fields. The two are consistent with each other but not the same site.
2. **Whether Nexar's aggregated Supply-scope catalog includes conductive-ink/adhesive SKUs
   at all**, as opposed to being scoped to standard electronic components. Not tested with
   a live query.
3. **Digi-Key's and Mouser's rate limits and field lists** are drawn from their own pages
   via search-engine-indexed text rather than a successful direct fetch in this session
   (Digi-Key's shared-concepts and product pages, and Mouser's api-search page, all failed
   direct `WebFetch` — 403 or timeout respectively). `developer.digikey.com`'s landing page
   and `nexar.com/api` were fetched directly and succeeded; those two are on firmer footing
   than the rate-limit specifics.
4. **Whether any ink/printer manufacturer offers a private, sales-relationship-gated API or
   PIM feed** (as opposed to a public one) — this would only surface via a direct sales
   conversation, which is out of scope for a research pass.

---

## Sources

Fetched or read directly in this session:
1. [Nexar API](https://nexar.com/api) — free Evaluation plan (100 matched parts), Design/Supply scopes, OAuth2 via `portal.nexar.com`.
2. [Digi-Key API Developer Portal](https://developer.digikey.com/) — Product Information V4, Quote API v4, sandbox tier.
3. [Materials Project — Getting Started with the API](https://docs.materialsproject.org/downloading-data/using-the-api/getting-started) — free API key, no stated rate limit.
4. [Materials Project — Dielectric Constants methodology](https://docs.materialsproject.org/methodology/materials-methodology/dielectricity) — DFPT-computed, static/zero-frequency dielectric tensor; no loss-tangent field.

Confirmed via search-engine-indexed quotation of the official page (direct fetch blocked by 403 or timeout):
5. [Mouser Search API](https://www.mouser.com/en/api-search/) — 50 results/call, 30 calls/min, 1,000 calls/day, free signup via request form.
6. [Digi-Key Shared Concepts — rate limits](https://developer.digikey.com/tutorials-and-resources/shared-concepts) — 120 req/min, 1,000 req/day for Product Information.
7. [Digi-Key API Solutions](https://www.digikey.com/en/resources/api-solutions) — "DigiKey offers a wide range of APIs at no cost."
8. [MatWeb Database License](https://www.matweb.com/services/databaselicense.aspx) — licensing model, no public API.
9. MG Chemicals 8330S/8331S product listings: [Digi-Key](https://www.digikey.com/en/products/detail/mg-chemicals/8331-14G/2639875), [Mouser](https://www.mouser.com/ProductDetail/MG-Chemicals/842AR-P), [RS Online datasheet excerpt](https://us.rs-online.com/product/mg-chemicals/8331s-50ml/70416915/) — confirms conductive ink/epoxy is a stocked distributor SKU with structured cure/viscosity/resistivity attributes on at least one distributor's page.
10. [Matmatch](https://matmatch.com/) coverage per third-party reporting (Interesting Engineering, TheFabricator, Digital Engineering 24/7, Engineering.com) — free web search, no public API found.
11. [GlobalSpec / Engineering360 Product Finder](https://www.globalspec.com/productfinder) — web-based `SpecSearch`, no public developer API found.
12. [ThomasNet](https://www.thomasnet.com/) and third-party scrapers (Apify, Piloterr) — no official API; unofficial paid scraping only.
13. Optomec [Aerosol Jet product pages](https://optomec.com/printed-electronics/aerosol-jet-printers/) and spec-sheet PDFs — no API, static marketing/spec documents only.

Cross-referenced against this repo's own prior research for consistency: `docs/mxene-voltera-nova-printability.md` (Voltera NOVA — no API, spec sheet only), `docs/element-library-prior-art.md` (citation-style convention followed here), `CONTEXT.md` (Fabrication capability, Ink-property library, Material-property library definitions), `docs/adr/0030-intended-effect-is-a-key-on-a-requirement-not-a-record-of-its-own.md`.
