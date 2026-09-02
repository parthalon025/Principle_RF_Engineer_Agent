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
| Qucs-S / qucsator_rf | GPL-2.0-or-later | Free; review obligations if redistributed. Verified from primary source: every cited source file's own header in both github.com/ra3xdh/qucsator_rf and github.com/ra3xdh/qucs_s grants "either version 2, or (at your option) any later version" (SPDX GPL-2.0-or-later) -- see simulation/qucs.py's module docstring for the full citation. GitHub's own repo-level license badge for both repos shows the coarser "GPL-2.0" because that only reflects which license TEXT the plain COPYING file matches, not the "or later" grant in each source file's own header. |
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
