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
| Qucs-S | GPL-2.0 | Free; review obligations if redistributed |
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
