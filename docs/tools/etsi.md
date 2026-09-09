# ETSI standards (deliver-path PDFs)

ETSI (European Telecommunications Standards Institute) is the European body that writes the radio/telecom standards a physical product has to meet — including the "harmonised standards" that, in the EU, are the paperwork trail proving a radio device is legal to sell. This repo treats an ETSI document the same way it treats a datasheet or a patent: something to download once, feed to the existing PDF-parsing pipeline, and cite as evidence at the `standard` tier. There is no ETSI-specific parsing logic here — the whole client is "fetch this one PDF, hand it to the ingester unchanged."

## What it is

ETSI is an independent, not-for-profit standards body founded in 1988, headquartered in Sophia Antipolis, France, with "over 950 members" across "more than 60 countries" and formal status as an EU-recognised European Standardisation Organisation (ESO) alongside CEN and CENELEC [etsi.org/about/, fetched live]. It "publishes thousands of freely-available technology standards, specifications and reports every year" [etsi.org/standards/, fetched live]. It is a standards-writing organization, not software — there is no version number or release cadence to report the way there is for a library.

## Full capabilities

ETSI's RF-relevant catalog centers on the EN 300-series and EN 301-series wireless/radio-equipment standards — e.g. EN 300 328 (2.4 GHz wideband/Wi-Fi/Bluetooth) and EN 301 893 (5 GHz RLAN) — many of which are "harmonised standards" under the EU Radio Equipment Directive 2014/53/EU, meaning compliance creates a legal presumption of conformity for CE marking [search-result corroboration: eur-lex.europa.eu, radiwiki, ezurio.com — not independently re-fetched from ETSI itself this pass]. Every published deliverable — EN, TS, TR, EG, GS, across all technical domains, not only radio — is a directly downloadable PDF at a predictable `www.etsi.org/deliver/{doc-type}/{numeric-range}/{doc-number}/{version}/{filename}.pdf` path; **confirmed live this pass** by fetching one such URL directly with `curl` (no auth headers sent): HTTP 200, `content-type: application/pdf`, 501,880 bytes. The human-facing search UI is `www.etsi.org/standards-search` (that exact URL now 301-redirects to `www.etsi.org/standards/` — a site restructure since the adapter's docstring was written, confirmed live). Beyond text standards, ETSI also runs **ETSI Forge** (`forge.etsi.org`), a GitHub-hosted home for standards-adjacent software and machine-readable API descriptors (e.g. OpenAPI/YAML specs for NFV-MANO APIs) — a real but separate capability from PDF deliverables, and not relevant to this repo's RF-surface work.

## Integrations & interfaces

Plain HTTPS GET, no client library, no key. **New this pass**: the standards-search page's own front-end script (`.../standards/js/script.js`) calls an internal AJAX endpoint, `https://www.etsi.org/custom/standardssearch/data.php?format=json&search=...`, that returns exactly the fields needed to build a deliver-path URL — confirmed live by querying it for "EN 300 328" and getting back JSON rows with `EDSpathname` + `EDSPDFfilename` (concatenating those two reproduces the real deliver URL), plus `TITLE`, `ETSI_DELIVERABLE`, `IsCurrent`, `superseded`, and a `total_count`. This is a real, working JSON endpoint — but it is undocumented, unversioned, and exists only as the WordPress theme's own internal plumbing, not a published API with a stability contract. It answers this ticket's research question ("has a search API appeared") with "an unofficial one has always technically existed," not "yes, a supported one now exists."

## Licensing & cost

Free, zero registration, confirmed live. Copyright in the standard text itself is ETSI's: its Terms of Use state the site's "structure and its contents shall not be reproduced, distributed or published, in whole or in part... without the prior express consent of ETSI," directing reproduction requests to ETSI Legal Services or a Copyright Licence request form [etsi.org/terms/, fetched live]. Separately, patented technology inside a standard is governed by ETSI's IPR Policy's FRAND (Fair, Reasonable And Non-Discriminatory) licensing commitment for Standard Essential Patents [etsi.org/intellectual-property-rights, fetched live, quoted] — a build-implementation concern, not a document-citation one. Net posture: free to read and cite internally, not public-domain, same as 3GPP and unlike the FCC's eCFR.

## How this repo uses it today

`knowledge/sourcing/etsi.py`'s `ingest_etsi_standard(document_url, *, license, classification, supersedes_document_id=None, download_dir=None, fetch_fn=download_bytes)` validates that `document_url` is `https://www.etsi.org/deliver/...` (raising `ValueError` otherwise — an allowlist check, not a lookup), downloads it via the shared `knowledge.sourcing._http.download_bytes` plain-`urllib` GET (60 s timeout, descriptive User-Agent, no credentials), writes it to a temp or caller-given directory, and passes it unchanged to `knowledge.ingest.ingest_document(source_type="standard", ...)`. `license` and `classification` are mandatory, caller-supplied strings — the module deliberately assumes no specific license. `ingest_etsi_standard` is registered under `ingestion_auto` in `policies/tool_policy.yaml` (ungated, no `ALLOW_EXTERNAL_NETWORK_TOOLS` check), alongside its 3GPP/FCC/arXiv/patent siblings, because it needs no account or key.

## Capabilities not yet used here

The `data.php` JSON search endpoint found this pass would close the adapter's one stated gap — resolving a bare document number (e.g. "EN 300 328") to its deliver URL without a human first using the web UI — but its undocumented, unofficial status argues for cautious/manual use rather than depending on it in shipped code. Also unused: the search results' own freshness metadata (`IsCurrent`, `superseded`, `ReviewDate`) that could flag when an already-ingested standard has been superseded, and any bulk/mirroring mechanism — unlike arXiv's OAI-PMH, there is no way to pull ETSI's RF-relevant catalog as a corpus rather than one deliver-URL at a time.

## Sources

- https://www.etsi.org/about/ (fetched live via curl)
- https://www.etsi.org/standards/ (fetched live via curl; `www.etsi.org/standards-search` and `www.etsi.org/standards/get-standards` both 301-redirect here)
- https://www.etsi.org/terms/ (fetched live via curl)
- https://www.etsi.org/intellectual-property-rights (fetched live via curl)
- https://portal.etsi.org/Services/editHelp/To-help-you-in-your-work/Use-and-reproduction-of-text-signs-and-material-legally-protected/Copyrights (fetched)
- https://www.etsi.org/deliver/etsi_ts/119600_119699/119612/02.02.01_60/ts_119612v020201p.pdf (fetched live via curl to confirm no-auth direct PDF download)
- https://www.etsi.org/deliver/etsi_en/300300_300399/300328/02.02.02_60/en_300328v020202p.pdf (deliver URL reconstructed from and confirmed against a live `standardssearch/data.php` JSON query for "EN 300 328")
- https://www.etsi.org/wp-content/themes/etsi/standards/js/script.js (fetched live via curl; source of the `standardssearch/data.php` endpoint)
- https://www.etsi.org/custom/standardssearch/data.php (queried live via curl with `search=EN 300 328` — undocumented internal endpoint, not an officially published API)
- Not independently re-confirmed this pass (secondary/search-result corroboration only): EN 300/301-series harmonisation under EU Radio Equipment Directive 2014/53/EU (eur-lex.europa.eu, radiwiki, ezurio.com) and the specific "only the Word version is access-restricted" claim carried over from this module's own docstring and `docs/FREE_AND_OPEN_SOURCE_TOOLING.md`
- `knowledge/sourcing/etsi.py`, `knowledge/sourcing/_http.py`, `knowledge/ingest.py`, `policies/tool_policy.yaml`, `docs/FREE_AND_OPEN_SOURCE_TOOLING.md` (this repo's own code and docs, read in full)
