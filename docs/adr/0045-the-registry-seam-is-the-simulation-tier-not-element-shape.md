---
status: accepted
---

# The design-family registry splits by simulation tier, not element shape

Issue #104's wayfinder map ("Printed metamaterial EM skin design loop") needed
a design-family registry, and at the time ticket #107
("What unknowns does each of the seven patent examples require?") was opened,
that registry had exactly one member: Example 3, the absorber. The ticket
named the risk plainly — *"The design-family registry has to be designed
while Example 3 is its only member, which risks a seam shaped around a single
case"* — and set out to buy breadth without chartering six more families, by
enumerating, for each of US12089385B2's seven examples, the design variables,
material properties, success criterion, simulation setup and human-only
inputs it demands. The ticket's own framing of the payoff: *"the point is to
see which of these quantities are common to all seven and which are
per-family... that boundary is the seam."*

The ticket also expected the patent text itself to block this: the uploaded
PDF is *"a scan with no text layer (32 pages, zero extractable characters, and
poppler is unavailable in this environment)."* That held for the description
prose but not for the drawings — FIG. 5C, 6C,
7F, 8D, 9C, 10C and 11C carry the per-example dimension tables, and rendering
those drawing sheets to raster and reading them recovered every design
variable, period and material constant for all seven. The enumeration below
is built on that recovered data, not on the prose.

## Decision

**1. The registry's seam is the simulation tier a family needs, not its
element shape, and it splits the seven examples 4 against 3.**

- **Tier A — uniform surface** (Examples 1, 2, 3, 6): one periodic/Floquet
  unit-cell solve *is* the whole evaluation; the criterion is read straight
  off it.
- **Tier B — aperture surface** (Examples 4, 5, 7): the unit-cell solve only
  populates a phase-vs-parameter lookup table under local periodicity. The
  function being designed for — a steered beam, a suppressed backscatter
  lobe — **does not exist at the unit-cell level at all**, and a second,
  aperture-level stage computes the scored quantity.

For Example 7 this is quantified, not asserted. Haji-Ahmadi *et al.*
(*Sci. Rep.* 7, 11437, 2017) run Floquet unit cells for the optimisation and
then a full finite 4×4-tile time-domain solve, "which accounts for edge
effects and finite-size interactions absent in periodic assumptions";
Murugesan & Selvan (*Frequenz* 77, 273–279, 2023) then show "the 8 and 10 dB
RCS reduction bandwidths drop as array size increases… attributable to
mutual coupling." **Aperture size is a design variable for #7 in a way it is
not for #1–#3 and #6.**

**2. Three axes cross-cut that tier split and need their own registry
fields**, independent of tier and of each other:

- **Port count** — two-port/transmissive (1, 2, 3) vs one-port/ground-backed
  (4, 5, 6, 7). *Not* the same partition as the tier split: #3 is Tier A +
  two-port + unbacked; #6 is Tier A + one-port + backed.
- **Post-processing** — none (4, 5, 7), power arithmetic (3), effective-medium
  retrieval (1, 2), polarisation-ellipse arithmetic (6).
- **Sweep axes** — frequency only (1, 2, 3); × geometry (4); × material state
  (5); × incidence angle (6); × tile assignment × aperture size (7).

**Example 3 alone would have made every one of those fields look like a
constant** — exactly the single-case bias the ticket existed to avoid.

**3. The registry's field set splits into a common spine and a per-family
block.**

**Common spine** (present on every family): band; host thickness `T`; **two**
cell periods, not one (#3 and #6 have rectangular cells); lattice type; host
εr/tanδ; conductor σ; incidence-angle and polarisation envelope; ground-plane
presence; `R = 3T` and `<10–20 µm` conformity; `T ≤ 2 mm`; and the
fabrication constraints the patent does not supply.

**Per-family** (varies by family): element parameterisation (1 scalar for
#4, 4–9 dimensions for the rest); constitutive class (bulk dielectric insert
/ *absence* of material / printed conductor / ferroelectric); number of
patterned layers and their front-to-back registration (#3 is the only
two-layer registered one); presence of an external control variable (#5's
bias only); whether a spatial gradient across the aperture is a design
variable (4, 5, 7); objective shape; and temperature sensitivity of a
design-critical property (acute for 1, 2, 5).

## Considered and rejected

- **Partitioning the registry by element shape.** Rejected: element
  geometry (cubes, cylinders, meanders, checkerboard rings) does not predict
  which simulation setup a family needs — the tier split does. Two families
  with unrelated shapes (1 and 6) share Tier A regardless.

## Consequences

- **This cross-cuts ADR-0018's registry and does not duplicate it.**
  ADR-0018 (from #109) decides that the design-family registry is an open
  interface — a thin common spine plus per-family fields, with `physical_bound`,
  `optimizer_class` and `simulation_adapter` as open, non-enum fields — but it
  does not itself record the Tier A/Tier B split; it cites #107 only in
  passing (spine-field provenance, and rejecting a "two separate registries"
  alternative). This ADR is that missing record: the tier a family needs
  (Decision point 1) is exactly the kind of thing `simulation_adapter` must
  be chosen against, and the three cross-cutting axes (Decision point 2) are
  additional per-family registry fields ADR-0018's open interface must carry
  alongside them.
- Every design-family registry entry must carry a **tier field** (A/B) plus
  independent fields for **port count**, **post-processing kind**, and
  **sweep axes** — none of the three is derivable from the tier or from each
  other, which #3 (Tier A, two-port, unbacked) and #6 (Tier A, one-port,
  backed) between them establish.
- The registry schema is a **common spine present on every entry** plus a
  **per-family block** sized from 1 scalar (#4) to 4–9 dimensions (the
  others) — the spine/per-family boundary named in Decision point 3.
- **This does not resolve Example 3's own reproduction ambiguity** — whether
  its `h₁ = 0.15 mm` is a second dielectric layer or a conductor thickness,
  and whether FIG. 7G's R/T axis is field magnitude or power — which the
  ticket flagged as unresolved and which was sharp enough to spawn its own
  follow-on, closed as #116 ("Pin down Example 3's reference geometry and the
  curve a reproduction is scored against"), with a further spec still open
  at #168 ("Spec Feature Selective Validation (FSV) for Example 3's
  reproduction check").
- **This does not decide how human-only inputs are captured** in the
  registry's structure. The ticket names several — band; incidence and
  polarisation envelope; whether the platform is already a ground plane;
  worst-case bend radius; coverage area; which of two conflicting objectives
  wins for #3; the wanted steering angle for #4/#5; the sense of circular
  polarisation for #6; and, sharpest of all, #7's redirection target (a
  checkerboard redirects rather than absorbs, so "reduction" is only a
  success if the redirected lobes land somewhere the customer doesn't care
  about, and no solver can know that) — but leaves their representation to
  the registry's implementation ticket.
