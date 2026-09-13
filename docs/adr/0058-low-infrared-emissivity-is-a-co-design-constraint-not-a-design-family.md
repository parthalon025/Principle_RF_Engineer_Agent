---
status: accepted
---

# Low infrared emissivity is a co-design constraint, not a design family

Split out from [ADR-0050](0050-the-registry-carries-post-processing-and-sweep-axes-and-grows-a-transmissive-and-a-shielding-family.md)
for readability; see that file for the shared context and the four-plug-in
family test ([ADR-0027](superseded/0027-the-alphabet-admits-only-printed-letters-and-identity-includes-the-process.md) §5, corrected 2026-09-10:
a candidate is a new **family**, not a new **letter**, if and only if it needs
a different `physical_bound`, `analysis_model`, `optimizer_class` or
`simulation_adapter`) this decision applies.

`low infrared emissivity` was, alongside `transmitted` and `shielded against`,
one of the three effects `designs/intended_effects.py`'s
`effects_without_family()` reported as gapped. Unlike the other two (closed by
[ADR-0056](0056-bandpass-fss-is-a-new-design-family-not-an-inverted-absorber.md)
and [ADR-0057](0057-shield-is-a-new-design-family-not-a-radome-with-the-sense-flipped.md)),
this one was examined and declined.

## Decision

**Low infrared emissivity is not registered as a design family.**

Applying the four-plug-in test honestly returns not "four differences" but
**four nothings**: no `physical_bound`, no `analysis_model`, no
`optimizer_class`, and no `simulation_adapter` — nothing in this repo solves at
12–120 THz. Four nothings is not the same as four differences. A family whose
every plug-in is a sentinel **declares nothing**, and registering one would do
active harm: `families_serving("low infrared emissivity")` would return a name
and the `FamilyGap` would vanish, so the gap report would say the gap was closed
when it was not. **An honest, queryable gap is worth more than a family that
appears to serve an effect and cannot.**

**The registry's own invariant is what refuses it, and that is the load-bearing
part.** Every other family answers *"what does this surface do to the arriving
radio wave"*. Emissivity is a thermal-radiation property three to four orders of
magnitude up in frequency, and it is not an S-parameter measurement at all —
`designs/intended_effects.py`'s `INFRARED_EMITTANCE` fixture already records
`port_count=None` for exactly that reason. But `DesignFamily.__post_init__`
requires `requires_ground_plane=True` to pair with `port_count=1` and
`False` with `port_count=2`. An infrared layer has **no ports**. To register it
one would have to declare `port_count=2` (a lie) or a ground plane (also a lie).
The invariant written for #216 is what says no, and it says no on physics.

**What it is instead: a second requirement row, a co-design constraint on a
candidate whose family is set by its radar behaviour.** And that constraint has
a number, so it is usable today with no registry change at all. A **continuous**
low-emissivity conductive layer over a radar absorber **shorts it out**:
`rf_tools.sheet_impedance.min_overlay_sheet_resistance_ohm_sq` returns **407 Ω/sq**
as the floor an overlay must exceed to leave 90 % microwave absorption intact
(1,695 Ω/sq for 99 %). A dense printed MXene film at this repo's own
best-evidenced as-printed conductivity — 6.9 × 10⁵ S/m,
`docs/mxene-voltera-nova-printability.md` — has an RF sheet resistance of
**0.24 Ω/sq** at 10 GHz and 20 µm (`CALCULATED` via
`rf_tools.sheet_impedance.sheet_resistance_ohm_sq`), about **1,700× too
conductive**. So **only a patterned infrared layer can coexist with an
absorber**, which is `docs/five-paper-absorber-corpus-findings.md` §4's own
conclusion: every continuous IR-functional conductor in that corpus fails the
threshold by one to three orders of magnitude and every patterned one passes by
two to three, because a metal grid of period `p` presents
`Y/Y₀ ≈ 2π·k·(p/λ)` and an infrared-scale period is microscopic at 10 GHz. *In
plain terms: a solid metal film on top ruins the radar absorber underneath; the
same metal cut into a fine grid is invisible to the radar wave, because the
holes are thousands of times smaller than the wavelength it cares about.*

Whether the effect belongs in CONTEXT.md's seven remains a `/domain-modeling`
decision with its own owner, exactly as ADR-0049 left it. Nothing here touches
CONTEXT.md.

*Not adding something, argued, is a result. This is one.*

## Considered and rejected

- **Registering a `LOW_IR_EMISSIVITY` family.** Rejected: four sentinel
  plug-ins declare nothing, registering it would convert an honest gap into a
  family that appears to serve an effect it cannot, and the `__post_init__`
  port-count invariant refuses it on physics — an infrared layer has no
  ports.

## Consequences

- **The infrared decision is a decision, and it should be cited as one.** The
  407 / 1,695 Ω/sq compatibility thresholds are usable today as a stated
  constraint on any overlay proposed above a microwave absorber, with no
  registry change. If a later reader proposes registering an infrared family,
  the thing that would have to change first is that an infrared **solver** and
  an infrared **model** exist here — until then the four plug-ins are four
  nothings and the `__post_init__` invariant still refuses it.
- `low infrared emissivity` stays a legitimate, permanent gap in
  `effects_without_family()` — unlike `transmitted` and `shielded against`,
  there is nothing here for the effects library to wire up to once this ADR
  ships.
