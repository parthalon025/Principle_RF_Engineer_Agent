---
status: accepted
---

# The design-family registry carries post-processing kind and sweep axes as their own fields, and grows a transmissive and a shielding family — but not an infrared one

Three open tickets pointed at the same file and asked three versions of one
question: **what does a registry entry have to say, and which entries are
missing?**

**[#455](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/455)**
found an accepted ADR asserting a "must" the code does not satisfy. ADR-0045's
Consequences state, verbatim: *"Every design-family registry entry must carry a
**tier field** (A/B) plus independent fields for **port count**,
**post-processing kind**, and **sweep axes** — none of the three is derivable
from the tier or from each other."* The shipped `DesignFamily` carried
`simulation_tier` and `port_count` and neither of the other two. **[ADR-0055](0055-the-design-family-registry-gains-postprocess-and-sweep-axes-as-required-fields.md)**
closes this.

**[#453](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/453)**
found the cost of a missing member: `ABSORBER_TRANSMISSIVE` was the only
ground-less two-port family in the registry, so a radome — a radar-transparent
window — would land there by elimination, scored on absorptivity instead of
transmittance. **[ADR-0056](0056-bandpass-fss-is-a-new-design-family-not-an-inverted-absorber.md)**
registers the family that fixes it.

`shielded against` — one of CONTEXT.md's own seven intended effects — had no
family, no `analysis_model` and no `physical_bound` anywhere.
**[ADR-0057](0057-shield-is-a-new-design-family-not-a-radome-with-the-sense-flipped.md)**
registers one.

Low infrared emissivity was examined for the same treatment and declined.
**[ADR-0058](0058-low-infrared-emissivity-is-a-co-design-constraint-not-a-design-family.md)**
records why.

## Why this ADR is now a hub, not the decision record itself

The four decisions above were originally recorded together in this one
document, because they came out of the same research pass against the same
two tickets. On a later pass they were split into their own files
(ADR-0055–0058) so each is short enough to read on its own — this document's
own length had grown past what a single decision record should be. **Nothing
about the decisions themselves changed in the split**: each new file carries
its origin's full Decision, Considered-and-rejected and Consequences text
verbatim, just filed separately. Existing citations to "ADR-0050" elsewhere in
this repo's code and tests remain valid; this file still exists, at the same
number, as the place those citations resolve to.

**The test that decided family membership in all four is [ADR-0027](superseded/0027-the-alphabet-admits-only-printed-letters-and-identity-includes-the-process.md) §5, as corrected on 2026-09-10.**
An import is a new **family** rather than a new **letter** if and only if it
needs a different `physical_bound`, `analysis_model`, `optimizer_class` or
`simulation_adapter` — **four** plug-ins, the fourth added by that correction
after #453 found the three-plug-in version filing a radome as a letter under
`ABSORBER_TRANSMISSIVE`. Each of ADR-0056/0057/0058 applies this test and
shows its own working.

## Two smaller findings from the same pass, kept here rather than split out

Neither is substantial enough to deserve its own file, and neither depends on
ADR-0055's new fields or ADR-0056–0058's new families.

### The Gustafsson & Sjöberg marker stays, and now says which half is missing

ADR-0049's Consequences reported a discrepancy and deliberately did not
adjudicate it: `designs/design_families.py` carries the bound as an
`UnreadPhysicalBound` — *"primary source NOT yet read by this programme"* —
while `docs/absorber-thickness-bandwidth-bound.md` §7.1 quotes that paper's
Eqs. (4.10), (4.11) and (5.1) verbatim from the open-access Lund author
manuscript and ADR-0047 states `B·λ₀/d ≤ 2.6` as settled. *"Those cannot both be
true"* — and it sent the resolution here, per ADR-0020's rule that a correction
lands at the claim that owns it.

**Reading the doc first-hand shows they were never in contradiction.** They
answer different questions:

- **The doc quoted the paper.** §7.1 reproduces the abstract, three displayed
  equations, and the §6 tightness figures. So the **formula** is on the record
  and is not in doubt.
- **This marker's own error message defines what "read" means here**, and it is
  a higher bar than quoting: *"Read it first-hand and record it the way
  `docs/rozanov-bound-primary-source.md` and
  `docs/patch-q-factor-bound-primary-source.md` do."* Those two are dedicated
  primary-source read-throughs recording each bound's derivation, assumptions
  and validity box. **No `docs/gustafsson-sjoberg-bound-primary-source.md`
  exists.**

And a second, independent reason the slot cannot become a callable
`PhysicalBound` today: `rf_tools/physical_bounds.py` implements Rozanov and the
Nel/Skrivervik/Gustafsson patch bound and **nothing** for this one, so there is
no `feasibility` function to point at. Reading the paper is necessary and not
sufficient. *In plain terms: somebody copied the formula out of the paper.
Nobody has sat down with the paper to write out where it comes from and when it
stops applying, and nobody has coded it — and this programme's rule is that a
bound is read to that standard before it is relied on, because the Rozanov
"λ/17 versus 17.2" slip is what happens when a round number is taken from an
abstract instead of a derivation.*

**So the marker stays and the citation is corrected to say which half is
missing** rather than implying both are. The phrase
`designs/intended_effects.py` quotes is kept **verbatim** so that quotation
stays true — that file has a separate owner and could not be edited here.

**Considered and rejected: marking the Gustafsson & Sjöberg slot as a live
`PhysicalBound`.** Rejected: there is no function in `rf_tools/physical_bounds.py`
to point `feasibility` at, and `rf_tools/` is outside this work's ownership in
any case. Guessing a formula for an unread bound is the failure Provenance
exists to prevent.

### The `"CODING"` → `DIFFUSIVE` alias routing is untouched (#452)

#452 observes that a candidate named `"CODING"` lands on `NO_PHYSICAL_BOUND`,
whose reason is conditional in its own text — it holds only for a surface that
**redistributes rather than dissipates**, and only above a supercell period of
`√2·λ` (42.4 mm at 10 GHz, 30.3 mm at 14 GHz), below which the diagonal orders
do not propagate and every dB of specular reduction must come from absorption,
which is fully Rozanov-bounded. A previous pass added both preconditions to that
sentinel's reason and deliberately did **not** re-route the alias, because the
routing is a decision with its own ticket.

**Nothing here takes it.** Neither `BANDPASS_FSS` nor `SHIELD` is a backscatter
mechanism, so nothing about either changes what the right routing would be.
Recorded, and asserted in test, so the untouched state is visible as
deliberate rather than as an oversight.

**Considered and rejected: re-routing the `"CODING"` alias away from
`DIFFUSIVE`.** Rejected as #452's decision to make, not this one's.

## Consequences (this document's own)

- **#452 is informed and explicitly not decided.** The `"CODING"` routing is
  untouched and now asserted-as-untouched, so a later reader can tell deliberate
  restraint from an oversight.
- The Gustafsson & Sjöberg citation in `designs/design_families.py` now says
  which half of "read" is missing (the derivation write-up) rather than
  implying the formula itself is in doubt.
- See ADR-0055, ADR-0056, ADR-0057 and ADR-0058 for the consequences of each
  split-out decision.
