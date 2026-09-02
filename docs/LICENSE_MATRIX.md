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
| spicelib | GPLv3 (confirmed against `nunobrum/spicelib`'s own `LICENSE` file) | Free; review obligations if redistributed. Optional `pyproject.toml` extra (`ltspice`), not a hard dependency -- see `simulation/ltspice.py`. |
| LTspice | Free-of-charge proprietary freeware -- Analog Devices "Click-Through Software License Agreement" (doc ID `20191031-LTS-CTSLA`, https://ltwiki.org/files/LTspiceHelp.chm/html/License.pdf, confirmed against Analog Devices' own license text). Non-exclusive, non-transferable, non-sublicensable internal-use grant (per-workstation, single concurrent user); explicitly prohibits reverse engineering/decompiling; carries a reciprocal patent-license-back clause to ADI. **Closed source -- NOT OSI-approved**, distinct from every other (open-source) tool in this batch. | Free to install and use, but a licensed-terms proprietary EULA, not an open-source license -- do not conflate with the GPL/BSD/MIT entries above. The only non-open-source item in this batch (issue #59); ngspice/Xyce/Qucs-S remain the preferred, fully open-source ADS-alternative targets. |
| PostgreSQL | PostgreSQL License | Free |
| pgvector | Permissive | Free |
| Manufacturer data | Varies | Internal use subject to source terms |
| Books/papers | Varies | Internal use subject to organizational rights |
| Standards | Varies | Many are copyrighted/licensed |

Maintain an SBOM and source/license inventory even for an internal system.
For redistribution or commercialization, obtain legal review of the exact
dependency and data-rights graph.
