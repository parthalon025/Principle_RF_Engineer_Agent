---
status: accepted
---

# Volume-to-wire is a modelling decision, not a translation

`geometry/translate.py` restates one solver-independent `geometry.ir.Model`
into each adapter's own geometry dict. Five of its six targets are genuine
translations: openEMS, MEEP, Palace, gprMax and Elmer all describe the same
*volumetric* object, so moving between them rearranges vocabulary without
touching what the object is.

NEC2++ is not like the others. A method-of-moments wire code represents a
conductor as a one-dimensional filament with a radius, and a volumetric model
contains no filaments. Nothing in the source model *says* which filament
stands in for a solid — choosing one is an RF engineering judgment about
which currents matter, made by a person, and it changes the physics being
solved.

*In plain terms: the other five simulators all describe a shape the same way
and just spell it differently. NEC describes antennas as bits of wire. Going
from "a solid piece of metal" to "a wire with a thickness" is not spelling —
it is someone deciding what to throw away.*

This matters here more than it would elsewhere, because nobody with RF
expertise reviews this program's output (CLAUDE.md, "Who checks the answer").
A wrong wire model does not fail. It returns a plausible impedance and a
plausible pattern, tagged `SIMULATED`, and nothing downstream can tell.

## Decision

**`to_nec2` makes only the volume-to-wire judgments it can defend from the
geometry alone, and refuses the rest.**

1. **A `Cylinder` becomes a wire along its own centreline, at its own
   radius.** This is not an equivalence and involves no judgment: a thin
   cylindrical conductor is precisely what a NEC wire models. Exact, silent.

2. **A `Box` becomes a wire only when the caller has stated
   `equivalent_wire_radius_m` on it.** The widely-used thin-strip rule is
   `r_eq = w/4`, and this repo has **not read a primary source for it**.
   Applying it on the caller's behalf would bury an unverified constant
   inside a translation, where it would silently set the radius of every
   strip anyone ever models. Requiring the caller to state it makes the
   assumption theirs, visible at the call site, and attributable.

3. **Everything else is refused** — a solid box, a polygon, a dielectric
   region, and any conductor that is not `PERFECT`. Each raises
   `UnrepresentableGeometry` naming what could not cross and what to do
   instead.

4. **Segmentation is computed, never accepted.** Every emitted wire is
   segmented to at least ten per shortest in-band wavelength, and rounded up
   to an odd count so a feed lands on a true centre segment.

## Why not apply `w/4` and flag it

It was the obvious alternative and it is what most tools do. Rejected because
of where the flag would live. A warning attached to a translated geometry is
read by nobody: the geometry goes to a solver, the solver returns a number,
the number gets scored. `docs/adr/0028`'s "warn, never block" governs
withholding a *candidate* from a human reader who can weigh the warning —
there is no reader in this path. A refusal at the call site reaches a person;
a flag on a dict does not.

If a primary source for the strip equivalence is read and recorded, this
decision should be revisited: the rule could then move into the translator
with a citation, and the required field become an override.

## Why refusing lossy conductors is the load-bearing part

NEC's `GW` card carries no loss, and this repo's adapter emits no loading
card. A lossy conductor crossing into NEC would therefore become perfect
metal — reflecting everything it was designed to absorb. That is not a
hypothetical: it is **issue #230**, already recorded in this repo, where a
resistive sheet was modelled as ideal perfect metal and absorbed nothing
however it was designed. `tests/test_geometry_translate.py` holds the guard
against rebuilding it here.

## Consequences

- Most metamaterial and absorber work this programme does **cannot reach
  NEC2++ at all**, because it is lossy by construction. That is correct: NEC
  is a wire-antenna code and those are not wire antennas.
- The NEC path is narrow enough to be genuinely useful for what it is for —
  dipoles, monopoles, wire arrays — and refuses loudly for everything else.
- A caller who wants the `w/4` behaviour states it in one place and owns it.
