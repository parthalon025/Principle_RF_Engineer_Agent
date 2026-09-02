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
| gprMax | GPLv3-or-later | Free; review obligations if redistributed. Not pip-installable (conda + C compiler build) -- see `simulation/gprmax.py`. Confirmed from its own `LICENSE` file, `setup.py`'s `License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)` classifier, and its README ("released under the GNU General Public License v3 or higher"), all fetched from github.com/gprMax/gprMax's `master` branch. Its bundled antenna-model library (`user_libs/antennas/`) is separately licensed CC-BY-SA-4.0 -- not used by this repo's adapter, see that module's docstring. |
| h5py | BSD-3-Clause | Free; reads gprMax's own .out HDF5 result format |
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
