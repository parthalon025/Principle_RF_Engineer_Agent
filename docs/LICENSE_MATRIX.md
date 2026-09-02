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
| Elmer (ElmerSolver core, incl. VectorHelmholtz module) | LGPL-2.1 | Free; review obligations if redistributed. Verified directly against `license_texts/LGPL-2.1.txt` and `fem/src/modules/VectorHelmholtz.F90`'s own file header at github.com/ElmerCSC/elmerfem -- Elmer's own `ElmerLicensePolicy.md` states the GPL/LGPL version numbers backwards ("GPL v.2.1"/"LGPL v.2.0"); see simulation/elmer.py's module docstring for the full resolution. |
| ElmerGUI / ElmerGrid / ElmerParam | GPL-2.0 | Free; review obligations if redistributed. ElmerGUI and ElmerGrid confirmed directly (`elmergrid/GPL-2`, `elmergrid/src/fempre.c` header) at github.com/ElmerCSC/elmerfem; ElmerParam was NOT found as a present top-level component in that repo during this verification pass (see simulation/elmer.py's module docstring) -- recorded honestly as unconfirmed-present, not assumed still shipping. |
| Gmsh | GPL-2.0-or-later | Free; review obligations if redistributed. Verified directly against `LICENSE.txt` at github.com/live-clones/gmsh (mirror of gmsh's canonical gitlab.onelab.info repo); includes an explicit linking exception for Netgen/METIS/OpenCASCADE/ParaView. |
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
