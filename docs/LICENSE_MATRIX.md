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
| CSXCAD | LGPLv3 | Free; openEMS's own geometry/materials library, verified from thliebig/CSXCAD's own repo -- a separate row/license from openEMS's own GPLv3 (issue #55); no PyPI package, manual source/wheel install (see README.md) |
| gdstk | Boost Software License 1.0 (BSL-1.0) | Free; permissive, no redistribution review obligation; PyPI-installable (`pyproject.toml`'s `geometry` extra, issue #55) |
| OpenParEM | GPL-3.0-or-later | Free; review obligations if redistributed. Confirmed from the license header in every OpenParEM3D source file ("either version 3 of the License, or (at your option) any later version") and the repo's own LICENSE file; source/binary install only, not pip-installable -- see simulation/openparem.py |
| Qucs-S / qucsator_rf | GPL-2.0-or-later | Free; review obligations if redistributed. Verified from primary source: every cited source file's own header in both github.com/ra3xdh/qucsator_rf and github.com/ra3xdh/qucs_s grants "either version 2, or (at your option) any later version" (SPDX GPL-2.0-or-later) -- see simulation/qucs.py's module docstring for the full citation. GitHub's own repo-level license badge for both repos shows the coarser "GPL-2.0" because that only reflects which license TEXT the plain COPYING file matches, not the "or later" grant in each source file's own header. |
| Elmer (ElmerSolver core, incl. VectorHelmholtz module) | LGPL-2.1 | Free; review obligations if redistributed. Verified directly against `license_texts/LGPL-2.1.txt` and `fem/src/modules/VectorHelmholtz.F90`'s own file header at github.com/ElmerCSC/elmerfem -- Elmer's own `ElmerLicensePolicy.md` states the GPL/LGPL version numbers backwards ("GPL v.2.1"/"LGPL v.2.0"); see simulation/elmer.py's module docstring for the full resolution. |
| ElmerGUI / ElmerGrid / ElmerParam | GPL-2.0 | Free; review obligations if redistributed. ElmerGUI and ElmerGrid confirmed directly (`elmergrid/GPL-2`, `elmergrid/src/fempre.c` header) at github.com/ElmerCSC/elmerfem; ElmerParam was NOT found as a present top-level component in that repo during this verification pass (see simulation/elmer.py's module docstring) -- recorded honestly as unconfirmed-present, not assumed still shipping. |
| Gmsh | GPL-2.0-or-later | Free; review obligations if redistributed. Verified directly against `LICENSE.txt` at github.com/live-clones/gmsh (mirror of gmsh's canonical gitlab.onelab.info repo); includes an explicit linking exception for Netgen/METIS/OpenCASCADE/ParaView. |
| KiCad (application/kicad-cli) | GPL-3.0-or-later | Free; review obligations if redistributed. Verified against kicad.org/about/licenses/. |
| kicad-python (`kipy`) | MIT | Free. Verified against the project's own `pyproject.toml` (`license = "MIT"`), corroborated by PyPI's `license_expression`. |
| gerber2ems | Apache-2.0 | Free; NOTICE/attribution obligations if redistributed. Verified against the project's own LICENSE file. Not on PyPI -- manual/source install. |
| gerbv | GPL-2.0 | Free; review obligations if redistributed. Verified against the maintained fork's own README/LICENSE. Manual/system install. |
| ngspice | New (3-clause) BSD core, plus per-subtree LGPL (numparam, adms), LGPLv2.1 (tclspice), Public Domain (xspice), and a UC Berkeley "Research Software Agreement" (cider -- a custom, BSD-like but non-identical academic-use license, not literally BSD text) | Free; heterogeneous per-file licensing -- verified directly against ngspice's own COPYING file (github.com/ngspice/ngspice/blob/master/COPYING), not assumed to be one blanket license; review obligations if redistributed, especially for the LGPL/LGPLv2.1 subtrees |
| Xyce | GPL-3.0 | Free; review obligations if redistributed. Verified against Xyce's own COPYING file (github.com/Xyce/Xyce/blob/master/COPYING). Sandia's own binary installers additionally bundle proprietary device models not present in the open-source GitHub source -- irrelevant here since this repo only shells out to a locally-installed binary, never redistributes one |
| PyAEDT | MIT | Requires legally licensed AEDT |
| HFSS/AEDT | Commercial | License required |
| PyVISA | MIT | Free; requires a VISA backend (vendor or pyvisa-py) for real hardware |
| PyVISA-py | MIT | Free; pure-Python VISA backend, no vendor install required |
| PyVISA-sim | MIT | Free; simulated-instrument backend, no hardware or VISA backend required |
| spicelib | GPLv3 (confirmed against `nunobrum/spicelib`'s own `LICENSE` file) | Free; review obligations if redistributed. Optional `pyproject.toml` extra (`ltspice`), not a hard dependency -- see `simulation/ltspice.py`. |
| LTspice | Free-of-charge proprietary freeware -- Analog Devices "Click-Through Software License Agreement" (doc ID `20191031-LTS-CTSLA`, https://ltwiki.org/files/LTspiceHelp.chm/html/License.pdf, confirmed against Analog Devices' own license text). Non-exclusive, non-transferable, non-sublicensable internal-use grant (per-workstation, single concurrent user); explicitly prohibits reverse engineering/decompiling; carries a reciprocal patent-license-back clause to ADI. **Closed source -- NOT OSI-approved**, distinct from every other (open-source) tool in this batch. | Free to install and use, but a licensed-terms proprietary EULA, not an open-source license -- do not conflate with the GPL/BSD/MIT entries above. The only non-open-source item in this batch (issue #59); ngspice/Xyce/Qucs-S remain the preferred, fully open-source ADS-alternative targets. |
| PostgreSQL | PostgreSQL License | Free |
| pgvector | Permissive | Free |
| Digi-Key Product Information API v4 | Free developer-account tier (self-service OAuth2 registration); proprietary API terms, not an OSI license | Free, no purchase; internal use of returned catalog/datasheet data subject to Digi-Key's own API terms |
| Mouser Search API | Free with a registered API key; proprietary terms at mouser.com/en/apiterms/, not an OSI license | Free, no purchase; internal use subject to Mouser's own API terms |
| Nexar API (Octopart data) | Free "Evaluation" tier (OAuth2 self-registration, capped ~1,000 matched parts); proprietary API terms, not an OSI license | Free, no purchase; higher volume needs a paid plan; internal use subject to Nexar's own API terms |
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
