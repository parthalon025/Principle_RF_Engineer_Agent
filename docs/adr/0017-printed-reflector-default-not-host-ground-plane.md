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
  conflict today.
- True independent multi-layer stacks with a different pattern on each
  level stay blocked on #106's still-unmeasured registration accuracy,
  and on ticket #128 ("Put the absorber's loss in the printed pattern, not
  the substrate," still open) for whether a second patterned layer is ever
  needed at all.
- This is a plan-only decision (issue #104's map is explicitly plan-only);
  no code changes accompany it. Implementation lands as a separate
  `ready-for-agent` issue once the design-loop spec is otherwise complete.
