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

This is the *only* confidence vocabulary in the project -- there is no parallel
"provisional"/"beta"/"draft" tag, and the LLM never performs RF arithmetic or
substitutes an estimated confidence for a computed one (`docs/adr/0003`,
`docs/adr/0014`).

See `CONTEXT.md` for the current domain model and open scope questions.

## What the system does

The unit of work is a **design loop**: a nine-step state machine
(`orchestration/design_loop.py`) that carries one design from a customer
requirement to a redesign decision, calling into the deterministic tools rather
than reimplementing them.

```text
REQUIREMENTS → ARCHITECTURE → ANALYSIS → SIMULATION → OPTIMIZATION
             → VERIFICATION → MEASUREMENT → CORRELATION → REDESIGN_DECISION
```

Three of those steps are **gated** and cannot advance without a recorded
approval receipt (`orchestration/approval.py`): `ARCHITECTURE`, `MEASUREMENT`,
and `REDESIGN_DECISION` -- every transition whose result is a human judgment
call rather than a `CALCULATED`/`SIMULATED` number.

Around that loop:

- **Prose requirements become confirmable targets.** `designs/requirement_targets.py`
  takes an agent's structured reading of prose ("needs to work at 2.4 GHz
  without losing gain") and stores it as a value/comparator/unit/tolerance
  tagged `ASSUMED`, plus the original prose. A human confirms the reading
  before anything is scored against it; the provenance stays `ASSUMED` even
  after confirmation, because it is still a reading of prose.
- **A success score measures proximity to that target.** `designs/success_score.py`
  is deterministic floating-point comparison, `CALCULATED` provenance, never an
  LLM-estimated confidence. `ARCHITECTURE` and `REDESIGN_DECISION` get no score
  at all.
- **The solver iterates in software until software runs out.** `orchestration/solver.py`
  drives batches of LLM-proposed candidate parameter sets through the loop's
  *ungated* `ANALYSIS`/`SIMULATION`/`OPTIMIZATION` span, scoring each, and stops
  on target satisfaction, a score plateau, its evaluation budget, or a gated
  step -- reporting which, so an engineer knows exactly when a lab trip or a
  fresh architecture decision is the honest next move. It is additive: it never
  modifies the loop, never forges an approval receipt, and never drives
  `CORRELATION` (`docs/adr/0014`).
- **The bench is a batched confirmation step, not the iteration mechanism.**
  `orchestration/lab_test_plan.py` compiles, before the trip, what should be
  measured for each requirement, by what method, and what this iteration's own
  evidence already predicts -- so a requirement nothing on hand can confirm is
  flagged in advance rather than discovered at the bench.
- **Measurement data arrives from outside this system.** There is no instrument
  control. `MEASUREMENT` accepts a Touchstone (`.sNp`) file an engineer measured
  on independent equipment and brought back, parsed by `rf_tools/touchstone.py`
  and tagged `MEASURED`; a lab report may ride along as unparsed audit context
  (`docs/adr/0012`, `docs/adr/0013`).

Capabilities are exposed both as agent tools (`agent/main.py`, six scoped
specialist roles) and over MCP (`mcp_server/server.py`), governed by
`policies/tool_policy.yaml`.

## Repository

```text
.
├── agent/            # role-scoped agents + principal delegation/synthesis
├── mcp_server/       # the same tool surface over MCP (stdio)
├── rf_tools/         # deterministic calculations, Touchstone, correlation
├── designs/          # design records, requirement targets, success score
├── orchestration/    # design loop, approval gates, solver, lab test plan
├── simulation/       # EM/circuit solver adapters (see Optional below)
├── geometry/         # unit-cell arrays, curved/conformal host surfaces
├── optimization/     # sweeps, grid/Bayesian search, GA, gradient
├── measurement/      # externally-obtained results only (no instrument control)
├── verification/     # verification-matrix field shape
├── knowledge/        # ingestion, embedding, extraction, component lookup
├── db/               # Postgres schema + init
├── policies/         # tool_policy.yaml (permission model)
├── prompts/          # principal-engineer system prompt
├── tests/
├── examples/
├── docs/             # ADRs, build plan, roadmap, security, license matrix
├── CONTEXT.md        # domain model and open scope questions
├── AGENTS.md         # repo conventions for AI coding agents
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
- An LLM provider. `LLM_PROVIDER` selects between `local` (the default in
  `.env.example` -- a self-hosted OpenAI-compatible server, the `ollama`
  service in `docker-compose.yml`, no per-token cost), `openai`, or
  `anthropic`. No paid API key is required to run the system. Note the
  knowledge base's own backend is a *separate* choice (`DEFAULT_LLM_BACKEND`)
  driven by document sensitivity: `SENSITIVE`/`RESTRICTED` documents must use
  the local backend, with no fallback to a hosted API (`docs/adr/0004`).

Optional. Every EM/circuit solver below is free or open source, and the
free/OSS stack alone reaches a working, verified design -- see
`docs/FREE_AND_OPEN_SOURCE_TOOLING.md` for the survey and
`docs/LICENSE_MATRIX.md` for obligations:

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
- LTspice (batch/CLI mode, driven via the optional `ltspice` extra --
  `uv sync --extra ltspice` -- see `simulation/ltspice.py`)
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

Commercial, off the default path:

- Ansys AEDT/HFSS + PyAEDT -- requires a paid AEDT license. `simulation/hfss.py`
  is a real, working `HfssSimulator` adapter for teams that already hold one
  (confined to a controlled licensed workstation, see
  `check_hfss_workstation_confinement`), but it is not part of the path to a
  working, verified design -- see
  `docs/adr/0012-hardware-removed-paid-eda-tooling-stays-out-of-roadmap.md`
- Keysight ADS -- no code adapter exists in this repo. ngspice / Xyce / Qucs-S
  (above) are the free/OSS circuit-level alternatives

## Quick start

```bash
cp .env.example .env
docker compose up -d            # postgres + ollama (the default local provider)
docker compose exec ollama ollama pull gpt-oss:20b   # LOCAL_AGENT_MODEL
docker compose exec ollama ollama pull bge-m3        # LOCAL_EMBEDDING_MODEL
uv sync
uv run pytest
uv run python -m agent.main "Analyze the requirements for a 2.45 GHz PCB antenna."
```

With `LLM_PROVIDER=openai` or `anthropic`, `docker compose up -d postgres` is
enough and the model pulls are unnecessary -- set the matching API key in
`.env` instead. The compose `ollama` service reserves an NVIDIA GPU; on a host
with no `nvidia` runtime registered, remove that `deploy:` block or the service
will fail to start.

## Development order

1. Deterministic calculations
2. Touchstone analysis
3. Knowledge database
4. MCP tools
5. Principal-agent orchestration
6. NEC2++ / openEMS (and the rest of the free/OSS solver stack)
7. Optimization
8. Externally-obtained measurement ingestion
9. Simulation/measurement correlation
10. Controlled optimization and the candidate solver

Steps 1–10 require no paid license and no lab instrument. HFSS/PyAEDT sits
outside this sequence for teams that already hold an AEDT license.

Do not give the agent unrestricted control of laboratory instruments or
production release. Physical-instrument control is not merely disabled --
it was deleted (`docs/adr/0012`), and re-entering that scope means rebuilding
it deliberately, not flipping a flag.

See `docs/BUILD_PLAN.md` and `docs/ROADMAP.md` for the detailed sequence, and
`docs/SECURITY.md` / `policies/tool_policy.yaml` for the tool-permission model.

## Planning in progress

Large efforts are planned as a **Wayfinder map**: one GitHub issue labelled
`wayfinder:map` holding the destination, standing constraints and decisions so
far, with child issues as decision tickets. The map is an index -- each decision
lives in its own ticket.

The active map is
[Printed metamaterial EM skin design loop](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/104):
a handoff-ready spec for a design loop that takes a prose customer requirement
and returns scored, fabricable printed-metamaterial candidates, with material
and substrate as searched variables and unit-cell periodicity (not patch
length) as the degree of freedom. It is **plan-only** -- its tickets produce
decisions; implementation lands separately as `ready-for-agent` issues.

Two of its established constraints govern how results from that effort should
be read:

- **No VNA and no measurement fixture are available.** The provenance ceiling
  for RF response is `SIMULATED`, and a reproduction verdict reads "agrees with
  our reading of the published figure," never "agrees with the patent." Geometry,
  thickness and sheet resistance *are* measurable and are the simulation's
  inputs.
- **Threshold prunes, objective scores.** A requirement carries a minimum
  acceptable value and, optionally, a desired one; hardness is asserted, never
  inferred. Preference enters as an explicit recorded constraint, never as
  scoring bias.

The map's supporting research documents live on their own branches
(`research/*`, and `claude/open-repo-ctrg29`), not on `main`.

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
- Ollama: MIT (the default local LLM/embedding server; confirmed in
  `docs/FREE_AND_OPEN_SOURCE_TOOLING.md`, not yet carried into
  `docs/LICENSE_MATRIX.md`). Model weights carry their own separate licenses --
  `gpt-oss:20b` Apache-2.0, `bge-m3` MIT
- Digi-Key Product Information API v4 / Mouser Search API / Nexar API (Octopart data):
  free developer tiers, proprietary API terms (not OSI licenses) -- see
  `docs/LICENSE_MATRIX.md`
- PostgreSQL: PostgreSQL License
- pgvector: permissive PostgreSQL-style license

Technical books, papers, standards, datasheets, and internal documents have separate rights from software licenses.
See `docs/LICENSE_MATRIX.md` for the full inventory.

## Agent skills (repo process conventions)

This repo's own issue-tracker, triage-label, wayfinding and domain-doc
conventions for AI coding agents working in this codebase are documented in
`AGENTS.md` / `CLAUDE.md` and `docs/agents/`.
