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
| ngspice | New (3-clause) BSD core, plus per-subtree LGPL (numparam, adms), LGPLv2.1 (tclspice), Public Domain (xspice), and a UC Berkeley "Research Software Agreement" (cider -- a custom, BSD-like but non-identical academic-use license, not literally BSD text) | Free; heterogeneous per-file licensing -- verified directly against ngspice's own COPYING file (github.com/ngspice/ngspice/blob/master/COPYING), not assumed to be one blanket license; review obligations if redistributed, especially for the LGPL/LGPLv2.1 subtrees |
| Xyce | GPL-3.0 | Free; review obligations if redistributed. Verified against Xyce's own COPYING file (github.com/Xyce/Xyce/blob/master/COPYING). Sandia's own binary installers additionally bundle proprietary device models not present in the open-source GitHub source -- irrelevant here since this repo only shells out to a locally-installed binary, never redistributes one |
| PyAEDT | MIT | Requires legally licensed AEDT |
| HFSS/AEDT | Commercial | License required |
| PostgreSQL | PostgreSQL License | Free |
| pgvector | Permissive | Free |
| Manufacturer data | Varies | Internal use subject to source terms |
| Books/papers | Varies | Internal use subject to organizational rights |
| Standards | Varies | Many are copyrighted/licensed |

Maintain an SBOM and source/license inventory even for an internal system.
For redistribution or commercialization, obtain legal review of the exact
dependency and data-rights graph.
