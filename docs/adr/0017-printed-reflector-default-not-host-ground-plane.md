---
status: accepted
---

# The base printed layer defaults to its own reflector, never the host

Issue #104's wayfinder map ("Printed metamaterial EM skin design loop")
left one item open in `docs/seven-example-design-unknowns.md`'s "inherently
human input" list: the patent makes whether a host platform is itself a
ground plane conditional on the platform ("if we know that the platform
is a ground plane, there would be no need to repeat it"), with no rule for
how the design loop should treat that when it isn't stated. Ticket #108
("Confirm the band and the fabrication route") surfaced a second reason
this needed a real decision, not just a requirement field: `docs/voltera-
multilayer-capability.md` had already found that layer-to-layer print
registration accuracy is unpublished and unmeasured on the NOVA, and that
the registration problem "largely evaporates" whenever the bottom layer is
a plain, unpatterned sheet — because there's nothing on a blank layer to
misalign against.

**Decision: the base (bottom) printed layer always supplies its own
conductive reflector by default.** The loop never assumes the host
surface is a reliable ground plane. A Customer requirement may explicitly
assert that the host is a confirmed ground plane, and the loop may then
skip the printed reflector and rely on the host instead — asserted, never
inferred, the same rule ticket #117 already set for every other
requirement constraint (`CONTEXT.md`: Customer requirement gains a
ground-plane-presence field).

This also keeps every currently in-scope design (absorber, beam steering,
polarization conversion — all reflective-type functions per #108) to one
functional patterned layer over a blank backing, avoiding the unmeasured
registration risk rather than needing to solve it first.

## Considered and rejected

- **Trust the host by default when the requirement is silent.** Saves
  printed material on the plausible common case (a metal airframe), but
  makes an unverified assumption about the host's real-world conductivity
  the design's actual point of failure, with no way to recover if wrong.
- **Require the requirement to state ground-plane presence explicitly, no
  default.** Rejected — issue #117's "silence is permissive" rule already
  settled that an unstated field takes the safer default, not a blocking
  question.
- **Reproduce the patent's own two-independently-patterned-layer Example 3
  structure (I-shaped resonator over a separately patterned wire layer)
  as the general case.** Rejected for now: it needs the layer registration
  risk solved first, which #106's bench measurement hasn't done yet, and
  nothing in the currently in-scope design set requires it.

## Consequences

- Scope: this only holds for reflective-type functions. It would break a
  transmissive design (impedance-matched to free space, no reflection) —
  but the only such examples in the patent (1 and 2) are already excluded
  from this programme on fabrication-process grounds, so there is no live
  conflict today. **(Corrected — see Corrections, 2026-09-06.)**
- True independent multi-layer stacks with a different pattern on each
  level stay blocked on #106's still-unmeasured registration accuracy,
  and on ticket #128 ("Put the absorber's loss in the printed pattern, not
  the substrate," still open) for whether a second patterned layer is ever
  needed at all.
- This is a plan-only decision (issue #104's map is explicitly plan-only);
  no code changes accompany it. Implementation lands as a separate
  `ready-for-agent` issue once the design-loop spec is otherwise complete.

## Corrections

### 2026-09-06 — the transmissive class this ADR believed empty is not empty, and the exclusion it relied on no longer exists

**What this ADR said:**

> Scope: this only holds for reflective-type functions. It would break a
> transmissive design (impedance-matched to free space, no reflection) —
> but the only such examples in the patent (1 and 2) are already excluded
> from this programme on fabrication-process grounds, so there is no live
> conflict today.

**What is true instead**, in two parts, both fatal to that sentence:

1. **A printable transmissive design exists.** A bandpass frequency-
   selective surface is flat printed conductor — square-loop slots in a
   metal layer, ~15 µm thick, every feature clearing the 0.2 mm floor,
   modelled at a 62–80% passband with ~0 dB insertion loss. Examples 1 and
   2 were excluded because they are **solid 3D ceramic pieces**, a process
   exclusion specific to those two examples; this ADR generalised it into a
   statement about transmissive designs as a class, which does not follow.
2. **The exclusion itself is gone.** ADR-0021 settles that the patent's
   seven examples are candidate solution architectures scored per
   requirement against the configured capability, not a fixed selectable
   set. There is no longer a standing exclusion of Examples 1 and 2 for
   this paragraph to lean on, whatever the reasoning.

*In plain terms: this ADR said "the case that would break our rule can't
happen here." It can happen here, and the reason given for why it couldn't
has itself been retired.*

**The corollary cuts the other way, and is worth keeping.** This ADR's
whole motivation was avoiding the NOVA's unpublished layer-to-layer
registration accuracy by keeping every design to one patterned layer over a
blank backing. A bandpass needs **exactly one** patterned layer and no
backing at all — so it is the one architecture with *no* registration risk
whatsoever, the opposite of what the reflector default was protecting
against. (A rasorber, wanting two patterned layers on opposite faces, puts
registration back on the critical path; and the printed insulator cannot
separate two patterned layers in any case — ~73 mm² of overlap per cell at
30 µm gives ~64 pF against a 0.38 pF design value, which capacitively
shorts the stack.)

**Raised by:** ticket #188 ("A printable bandpass is the transmissive
design ADR-0017 assumed did not exist"), and by ADR-0021.

**The Decision is unaffected.** Defaulting the base printed layer to its
own reflector, and never assuming the host is a ground plane, remains right
for every reflective function — which is all of the currently-charted work.
What fails is only the claim that no conflicting case exists. A transmissive
candidate must state that it needs no reflector, as an explicit requirement
assertion, exactly as the Decision already provides for a confirmed host
ground plane. Amended rather than superseded, per ADR-0020.
