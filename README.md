# Principal RF Engineer Agent

Internal-use reference implementation for an AI-assisted RF/microwave engineering workstation.

## Design goals

The system is built around evidence and tools rather than asking an LLM to "know RF."

Evidence hierarchy:

1. Measured
2. Validated simulation
3. Deterministic calculation
4. Manufacturer specification/model
5. Authoritative technical reference
6. Internal engineering history
7. General web material
8. LLM inference

Every significant result should carry provenance:
`MEASURED`, `SIMULATED`, `CALCULATED`, `MANUFACTURER-SPECIFIED`,
`LITERATURE-SUPPORTED`, `INFERRED`, `ASSUMED`, or `UNKNOWN`.

See `CONTEXT.md` for the current domain model and open scope questions.

## Repository

```text
.
├── agent/
├── mcp_server/
├── rf_tools/
├── simulation/
├── knowledge/
├── db/
├── policies/
├── prompts/
├── tests/
├── examples/
├── docs/
├── docker-compose.yml
├── pyproject.toml
└── .env.example
```

## Requirements

- Ubuntu 24.04 LTS recommended
- Python 3.12+
- Git
- Docker + Docker Compose plugin
- 16 GB RAM minimum; 32–64 GB recommended
- 1 TB SSD recommended
- OpenAI API access, or another supported provider

Optional:
- NEC2++
- openEMS
- CSXCAD (openEMS's own geometry/materials library -- no PyPI package; build
  from source or install a platform-specific pre-built wheel, see
  docs.openems.de/python/install.html. `pip install '.[geometry]'` installs
  gdstk, this repo's other geometry-generation dependency, which IS a
  regular PyPI package -- see `geometry/unit_cell.py` and
  `pyproject.toml`'s `geometry` extra)
- OpenParEM (OpenParEM2D/OpenParEM3D -- source or pre-compiled-binary install only, not
  pip-installable; see simulation/openparem.py)
- Elmer FEM (ElmerSolver, VectorHelmholtz module) + Gmsh + ElmerGrid
- Qucs-S / qucsator_rf (manual build from source -- see
  github.com/ra3xdh/qucsator_rf; the CLI binary this repo's
  `simulation/qucs.py` shells out to is named `qucsator_rf`, not the bare
  `qucsator` its upstream project is colloquially called)
- ngspice
- Xyce
- Palace (github.com/awslabs/palace) -- full-wave FEM with native Floquet/periodic-port
  boundaries, for periodic metamaterial unit cells; manual source/binary install, no
  pyproject extra
- gprMax (ground-coupled/lossy-half-space FDTD -- conda + a C compiler with
  OpenMP, then `python setup.py build && python setup.py install`; not
  pip-installable, see `simulation/gprmax.py`'s module docstring)
- MEEP (FDTD, driven as a Python library -- `import meep`; a second, independent
  full-wave solver for cross-checking a design decision against openEMS instead of
  resting on one solver alone. No PyPI wheel: install via conda-forge
  (`conda create -n mp -c conda-forge pymeep`); no native Windows support (WSL
  required on Windows). See `simulation/meep.py`.)
- Ansys AEDT/HFSS + PyAEDT
- Keysight ADS
- LTspice (batch/CLI mode, driven via the optional `ltspice` extra --
  `uv sync --extra ltspice` -- see `simulation/ltspice.py`)
- VISA/SCPI-capable instruments
- KiCad (application + `kicad-cli`) -- for PCB geometry export via kicad-python's IPC API (issue #65)
- gerbv -- Gerber rasterizer gerber2ems shells out to internally
- gerber2ems -- PCB trace signal-integrity simulation front end for openEMS; not on PyPI, install from github.com/antmicro/gerber2ems
- FreeCAD (headless `FreeCADCmd`) -- for `geometry/freecad_curved.py`'s curved/
  conformal host-surface geometry mapping (issue #66); not pip-installable, install
  from freecad.org/downloads.php (or your OS package manager -- e.g. `apt install
  freecad` on Ubuntu) and confirm `FreeCADCmd` is on `PATH`, or point the
  `FREECAD_BIN` env var at it
- Digi-Key/Mouser/Nexar distributor component-lookup credentials (issue #67) --
  free developer accounts, no purchase required: `DIGIKEY_CLIENT_ID`/
  `DIGIKEY_CLIENT_SECRET`, `MOUSER_API_KEY`, `NEXAR_CLIENT_ID`/
  `NEXAR_CLIENT_SECRET` in `.env` (see `.env.example`). These three
  `lookup_*_component` tools additionally require `ALLOW_EXTERNAL_NETWORK_TOOLS=true`
  (they place a real, credentialed call to a third party) -- see
  `policies/tool_policy.yaml`'s `approval_self_gated` category.

## Quick start

```bash
cp .env.example .env
docker compose up -d postgres
uv sync
uv run pytest
uv run python -m agent.main "Analyze the requirements for a 2.45 GHz PCB antenna."
```

## Development order

1. Deterministic calculations
2. Touchstone analysis
3. Knowledge database
4. MCP tools
5. Principal-agent orchestration
6. NEC2++ / openEMS
7. HFSS / ADS
8. Measurement interfaces
9. Simulation/measurement correlation
10. Controlled optimization

Do not give the agent unrestricted control of laboratory instruments or production release.

See `docs/BUILD_PLAN.md` and `docs/ROADMAP.md` for the detailed sequence, and
`docs/SECURITY.md` / `policies/tool_policy.yaml` for the tool-permission model.

## Licensing

Upstream licenses must be preserved and tracked. Internal use does not eliminate license obligations.

Notable components:
- OpenAI Agents SDK: MIT
- MCP Python SDK: MIT
- scikit-rf: BSD-3-Clause
- openEMS: GPLv3
- CSXCAD: LGPLv3 (separate from openEMS's own GPLv3 -- see docs/LICENSE_MATRIX.md)
- gdstk: Boost Software License 1.0 (BSL-1.0)
- NEC2++: GPL
- OpenParEM: GPL-3.0-or-later
- Qucs-S / qucsator_rf: GPL-2.0-or-later (see docs/LICENSE_MATRIX.md for the primary-source verification)
- Elmer (ElmerSolver core, incl. VectorHelmholtz): LGPL-2.1; ElmerGUI/ElmerGrid/ElmerParam: GPL-2.0
- Gmsh: GPL-2.0-or-later
- ngspice: New (3-clause) BSD core, plus per-subtree LGPL/LGPLv2.1/Public-Domain/custom-academic components -- see `docs/LICENSE_MATRIX.md`
- Xyce: GPL-3.0
- Palace: Apache-2.0
- gprMax: GPLv3-or-later
- h5py: BSD-3-Clause (reads gprMax's own .out HDF5 result format)
- MEEP: GPLv2
- PyAEDT: MIT; requires a legally licensed AEDT installation
- KiCad (application/kicad-cli): GPL-3.0-or-later
- kicad-python: MIT
- gerber2ems: Apache-2.0
- gerbv: GPL-2.0
- FreeCAD: LGPL-2.1-or-later
- Digi-Key Product Information API v4 / Mouser Search API / Nexar API (Octopart data):
  free developer tiers, proprietary API terms (not OSI licenses) -- see
  `docs/LICENSE_MATRIX.md`
- PostgreSQL: PostgreSQL License
- pgvector: permissive PostgreSQL-style license

Technical books, papers, standards, datasheets, and internal documents have separate rights from software licenses.
See `docs/LICENSE_MATRIX.md` for the full inventory.

## Agent skills (repo process conventions)

This repo's own issue-tracker, triage-label, and domain-doc conventions for
AI coding agents working in this codebase are documented in `AGENTS.md` /
`CLAUDE.md` and `docs/agents/`.
