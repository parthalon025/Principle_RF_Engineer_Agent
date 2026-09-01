# First engineering task

## Requirement

Design a 2.45 GHz antenna concept.

Initial constraints:

- center frequency: 2.45 GHz
- impedance: 50 ohm
- bandwidth: not yet specified
- gain: not yet specified
- PCB stackup: not yet specified

## Expected agent behavior

The agent must not invent missing bandwidth, gain, substrate, or ground-plane
requirements.

It should:

1. identify missing requirements
2. state a provisional architecture only if useful
3. calculate free-space wavelength
4. identify required stackup/material data
5. produce a first-order estimate
6. identify what must be simulated
7. identify what must be measured
8. create a verification matrix

Known:
lambda0 = c / 2.45 GHz ≈ 122.36 mm

Unknown:
- dielectric constant
- substrate thickness
- copper thickness
- board dimensions
- ground-plane dimensions
- required gain
- required bandwidth
- enclosure
- connector/feed geometry
