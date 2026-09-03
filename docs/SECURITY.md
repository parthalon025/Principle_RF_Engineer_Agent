# Security model

Treat the agent as an untrusted automation layer.

## Network

Default:
- no arbitrary outbound network
- allowlisted knowledge sources
- no direct internet access from simulation workers unless required

## Filesystem

Each simulation receives a separate work directory.
Never let the model choose arbitrary host paths.

## Shell

Do not expose a generic shell tool.
Expose narrow, validated tools such as `run_nec`, `run_openems`, and `run_hfss`.

## Physical equipment

Current state (ticket #90, ADR-0012): this codebase contains no
instrument-actuation code at all -- no SCPI/VISA adapters, no path from
any agent/MCP tool to a physical instrument. Measured data enters the
system only as a Touchstone file an engineer brought back from testing run
on equipment this system never touched (`measurement/external.py`,
ADR-0013).

The design principle stays in force regardless: were physical-instrument
control ever added back, RF transmission, high-power output, calibration
changes, or any other controlled instrument configuration would require a
distinct, auditable human approval before actuating anything -- never a
flippable boolean, never bundled into a broader "allow tools" switch. The
design-iteration loop's own MEASUREMENT step is held to this same
standard today (`orchestration/design_loop.py`'s `GATED_STEPS`) even
though its only data source is external.

## Design release

Default:
`ALLOW_PRODUCTION_RELEASE=false`

The agent can prepare release artifacts but a human approves release.

## Data classification

Classify material:
PUBLIC / INTERNAL / SENSITIVE / RESTRICTED

Apply outbound-model policy before transmitting data to an external provider.
