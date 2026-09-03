# Full build plan

## Phase 0 — workstation

Install Ubuntu 24.04 LTS, Git, Docker, uv, Python 3.12+, and an editor.

Acceptance:
`docker compose up -d postgres`
followed by
`uv run pytest`

## Phase 1 — deterministic RF core

Implement and test:
wavelength, VSWR, return loss, S-parameter conversions, cascade gain,
Friis noise, link budget, IP3/intermodulation, stability, impedance transforms.

No model-generated numerical result is authoritative when a deterministic
function can produce it.

## Phase 2 — Touchstone

Support s1p/s2p/sNp, reference impedance, interpolation, de-embedding,
network cascading, and comparison.

## Phase 3 — knowledge

Index only authorized material. Preserve source, revision, license, authority,
units, equations, tables, and document provenance.

## Phase 4 — agent

Add principal RF, systems, microwave, antenna, test, and verification roles.

## Phase 5 — MCP

Expose calculations, Touchstone analysis, knowledge retrieval, design retrieval,
and simulation dispatch through narrow tools.

## Phase 6 — NEC2++

Add input generation, execution, result parsing, timeouts, resource limits,
and provenance.

## Phase 7 — openEMS

Add geometry, materials, ports, mesh, execution, S-parameters, far fields,
and convergence metadata. Cross-check independently against Palace,
OpenParEM, Elmer, and gprMax (FEM/FDTD alternatives) and MEEP (a second
FDTD engine) instead of resting on one solver alone -- `simulation/palace.py`,
`openparem.py`, `elmer.py`, `gprmax.py`, `meep.py`.

## Phase 8 — circuit-level simulation

Add nonlinear/active-device circuit-level simulation via ngspice and Xyce,
and schematic-level simulation via Qucs-S/qucsator_rf --
`simulation/ngspice.py`, `xyce.py`, `qucs.py`. This phase completes on the
free/OSS path above. HFSS/PyAEDT (`simulation/hfss.py`) and Keysight ADS
remain supported, confined to a controlled licensed workstation, for
anyone holding a paid license -- an optional alternative, not required to
complete this or any later phase.

## Phase 9 — optimization

Add parameter sweeps, grid search, Bayesian optimization, genetic algorithms,
and differentiable methods where appropriate.

## Phase 10 — measurement

Add SCPI/VISA adapters for VNA, spectrum analyzer, signal generator,
and power meter. Physical control remains approval-required.

## Phase 11 — correlation

Normalize frequency, reference impedance, calibration plane, de-embedding,
temperature, and fixture effects before comparing simulation and measurement.

## Phase 12 — controlled autonomous loop

requirements → architecture → analysis → simulation → optimization →
verification → measurement → correlation → redesign.

Never allow autonomous manufacturing release.
