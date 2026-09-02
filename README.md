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
- gprMax (ground-coupled/lossy-half-space FDTD -- conda + a C compiler with
  OpenMP, then `python setup.py build && python setup.py install`; not
  pip-installable, see `simulation/gprmax.py`'s module docstring)
- Ansys AEDT/HFSS + PyAEDT
- Keysight ADS
- VISA/SCPI-capable instruments

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
- NEC2++: GPL
- gprMax: GPLv3-or-later
- Qucs-S: GPL-2.0
- PyAEDT: MIT; requires a legally licensed AEDT installation
- PostgreSQL: PostgreSQL License
- pgvector: permissive PostgreSQL-style license

Technical books, papers, standards, datasheets, and internal documents have separate rights from software licenses.
See `docs/LICENSE_MATRIX.md` for the full inventory.

## Agent skills (repo process conventions)

This repo's own issue-tracker, triage-label, and domain-doc conventions for
AI coding agents working in this codebase are documented in `AGENTS.md` /
`CLAUDE.md` and `docs/agents/`.
