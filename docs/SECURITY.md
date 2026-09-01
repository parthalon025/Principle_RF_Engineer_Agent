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

Default:
`ALLOW_INSTRUMENT_CONTROL=false`

Human approval is required before RF transmission, high-power output,
calibration changes, or controlled instrument configuration.

## Design release

Default:
`ALLOW_PRODUCTION_RELEASE=false`

The agent can prepare release artifacts but a human approves release.

## Data classification

Classify material:
PUBLIC / INTERNAL / SENSITIVE / RESTRICTED

Apply outbound-model policy before transmitting data to an external provider.
