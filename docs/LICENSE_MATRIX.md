# License matrix

Planning reference; not legal advice.

| Component | License/status | Internal-use note |
|---|---|---|
| Python | PSF | Free |
| OpenAI Agents SDK | MIT | Free library; model/API usage can cost money |
| MCP Python SDK | MIT | Free |
| scikit-rf | BSD-3-Clause | Free |
| NEC2++ | GPL | Free; review obligations if redistributed |
| openEMS | GPLv3 | Free; review obligations if redistributed |
| Qucs-S | GPL-2.0 | Free; review obligations if redistributed |
| PyAEDT | MIT | Requires legally licensed AEDT |
| HFSS/AEDT | Commercial | License required |
| PostgreSQL | PostgreSQL License | Free |
| pgvector | Permissive | Free |
| Manufacturer data | Varies | Internal use subject to source terms |
| Books/papers | Varies | Internal use subject to organizational rights |
| Standards | Varies | Many are copyrighted/licensed |
| 3GPP specifications (`knowledge/sourcing/threegpp.py`) | Free to download, no registration; copyright jointly held by the 3GPP Organizational Partners, each document carries its own reproduction-restriction notice -- **not** public domain | Internal ingestion for retrieval/citation is normal practice; bulk redistribution outside this repo's private DB is not. Separate FRAND-IPR patent-licensing caveat if guidance ever touches implementation, not just spec-reading |
| ETSI standards (`knowledge/sourcing/etsi.py`) | Free PDF download (editable Word version is access-restricted); ETSI's own copyright and (F)RAND patent terms | Same internal-use posture as 3GPP |
| FCC eCFR Title 47 rule text (`knowledge/sourcing/fcc_ecfr.py`) | Public domain -- a work of the U.S. Government | Free, no registration, no reuse restriction. eCFR is not the official legal edition (GPO's Federal Register printing is authoritative) -- fine for engineering reference, flag the distinction only for formal regulatory sign-off |
| arXiv preprints (`knowledge/sourcing/arxiv.py`) | Free access, zero paywall/registration; arXiv's default license lets arXiv distribute the work but does not itself grant downstream reuse beyond citation/summary use -- reuse licensing varies per paper (check each paper's stated license, e.g. CC0/CC-BY, where the author opted into one) | Not peer-reviewed -- authority rank is explicitly overridden below the peer-reviewed `paper` default at ingest time (`knowledge.provenance.arxiv_preprint_authority_rank`) |
| IEEE Xplore | Paid/paywalled; no broad free-developer tier (confirmed against IEEE's own subscriptions page) | **Not ingested by this repo.** No ingestion path assumes free access |

Maintain an SBOM and source/license inventory even for an internal system.
For redistribution or commercialization, obtain legal review of the exact
dependency and data-rights graph.
