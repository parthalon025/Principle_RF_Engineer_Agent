---
status: accepted
---

# Design family registry is an open interface, not a fixed schema

Issue #109 asked what a design family (absorber, reflection-phase steering
surface, patch antenna, etc.) declares to the design loop. A design family
is represented as an open interface — each family is its own object
satisfying a thin common contract (the spine fields #107 already
established: band, host thickness, both cell periods, host εr/tanδ,
conductor σ, incidence/polarisation envelope, ground-plane presence,
`R = 3T`, `T ≤ 2mm`) — rather than one fixed schema with optional
per-family fields.

The deciding factor: `physical_bound` is not one formula with a per-family
constant swapped in. The absorber family's Rozanov bound, the
reflection-phase family's Gustafsson & Sjöberg bound, and the patch
family's Nel/Skrivervik/Gustafsson Q-factor bound are three structurally
different functions with different required inputs (a target reflectivity;
a phase window; a reference half-wave-patch simulation), and one family
(diffusive/coding backscatter reduction) has no bound at all. A fixed
schema would need an escape hatch for that shape of variation anyway.

This choice is corroborated by Palace — a solver this repo already calls —
whose own shipped config schema implements exactly this shape: a thin
shared "Solver" spine plus a `Problem.Type` discriminator selecting one of
five structurally independent sub-schemas, each with
`additionalProperties: false` so one family's fields can't leak into
another's.

## Considered Options

- **Fixed dataclass, optional fields.** Rejected: `physical_bound` alone
  shows the per-family content isn't optional-value variation, it's
  different-function variation; a `None` would be ambiguous between "not
  yet computed" and "doesn't exist for this family."
- **Two registries (Tier A / Tier B).** Rejected: tier, port count,
  post-processing, and sweep axes already cross-cut that shape split
  (#107); a second registry class would duplicate the shared spine for no
  benefit.

## Consequences

- `optimizer_class` and `simulation_adapter` follow the same open-value
  pattern — declared fields, not hardcoded two-literal enums — since both
  have a credible third value on the horizon (ML-direct inverse design; a
  future openEMS periodic adapter) that a closed enum would need a
  breaking change to add.
- Patch antenna retrofits into this registry as `design_family = PATCH`,
  the validation test for the shape: if the existing patch code doesn't
  fit, the shape is wrong.
