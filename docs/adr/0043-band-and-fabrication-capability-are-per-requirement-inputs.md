---
status: accepted
---

# Band and fabrication capability are per-requirement, per-configuration inputs, never project constants

Issue #104's wayfinder map ("Printed metamaterial EM skin design loop") left
two questions open for the printed-EM-skin design loop: whether X-band
8–12 GHz is this programme's fixed target band, and whether the fabrication
route is this programme's own direct-ink-write (DIW) process or the
patent's own punch-and-insert route. Ticket #108 ("Confirm the band and the
fabrication route") answered both. The same resolution also settled a
third, related point — the base printed layer defaulting to its own
reflector rather than trusting the host as a ground plane — which was
recorded separately as ADR-0017. The wayfinder map had filed the
band/fabrication half of #108's resolution under ADR-0017 too, even though
that ADR is scoped only to the reflector default; this ADR is the record
#108 itself never received.

## Decision

1. **Band is a per-requirement input, never a project constant.** X-band
   8–12 GHz is not "the" target frequency for this programme — it is the
   band of the anchor validation example (Example 3) and of whatever
   near-term requirement happens to be on the table, treated the same way
   the map already treats host surface: arriving per requirement, never
   assumed fixed. Whether to widen the design-family registry to the
   Ku-band families in Examples 6 and 7 is a separate, multi-band
   **registry-scope** question, deferred to #109.

2. **Fabrication capability is a configured fact the loop checks, not a
   hardcoded one.** This answers #108's Q2 — direct-ink-write or the
   patent's own punch-and-insert route — by removing it as a fixed
   either/or: the loop asks what is configured, not which of two named
   processes the programme has committed to. Today's configuration has
   exactly one entry: the Voltera NOVA, DIW printing only.

3. **Fabrication decomposes into three independent stages, never one
   lumped "which printer" fact:**
   - **Print** — flat patterns only, ever.
   - **Cure** — gated by whether the part can leave its host for an
     external oven (already established by #105), **not** by the
     printer's own ~40 °C ink-viscosity warmer. *In plain terms: the
     printer's built-in warmer only keeps the silver ink runny enough to
     print — it cannot harden a print. Curing needs a separate
     bake in an external oven (this programme's existing cures run
     120–135 °C), so the real gate on curability is whether the printed
     part can physically leave its host and go into that oven, not
     whether the printer itself feels warm.*
   - **Laminate** — bonding an already-cured coupon onto the final host;
     as configured today, flat-film-to-flat-film only, with no
     embedded-component capability.

## Considered and rejected

- **Treating X-band 8–12 GHz as a fixed project band.** Rejected —
  that would elevate the anchor validation example's band into a
  programme-wide constant; band arrives per requirement, the same as host
  surface already does.
- **A single lumped "printer capability" fact standing in for
  fabrication.** Rejected — collapsing print, cure, and laminate into one
  fact hides which of the three stages is actually the one blocking a
  given candidate.
- **Gating cure readiness on the printer's own ~40 °C ink-viscosity
  warmer.** Rejected — the warmer keeps ink printable; it does not cure
  anything. The real gate, already established by #105, is external-oven
  reachability.
- **Committing the programme to one fixed fabrication route — DIW or the
  patent's punch-and-insert process — as a standing choice.** Rejected —
  fabrication capability is configured and checked at run time; today's
  single configured entry happens to be DIW-only, but that is a
  configuration fact, not a hardcoded programme decision.

## Consequences

- #109 (design-family declare/derive work) inherits band-as-input,
  the multi-band registry-scope question (Ku-band Examples 6/7), and a new
  requirement-schema field for ground-plane-presence assertion — the last
  of these amending #117's closed requirement-constraints list, per
  ADR-0017.
- #152 (the `tooling.py` persistence seam) is the natural home for a
  fabrication-capability config store, sibling to the material-property
  library from #148/ADR-0015. Not built yet.
- Applying this rule to the patent's seven examples produced a per-example
  disposition, recorded in `docs/example6-polarization-converter-permittivity.md`
  and `docs/flexible-high-permittivity-composites.md`: Examples 3, 6, and 7
  are printable today (flat printed conductor on a flexible substrate);
  Examples 1 and 2 are excluded on process grounds (solid 3D ceramic
  pieces — no printing or lamination route produces a solid 3D block, in
  any material); Example 4 is excluded on a likely-permanent
  materials-physics conflict (no published material combines εr ≈ 100 with
  real flexibility at microwave frequency); Example 5 is excluded on a
  revisable materials-sourcing gap (a pre-crystallised BST particulate ink,
  cured externally at ~150 °C and measured at 15% tunability at 10 GHz, is
  real and published but not yet sourced or qualified). This disposition is
  a downstream application of the decision above, not itself locked in by
  it, and none of Examples 1, 2, 4, or 5 sit in the map's "Out of scope"
  section — each is excluded from candidate selection today with its
  reason stated, revisable without redrawing the destination.
  `docs/seven-example-design-unknowns.md`'s BLUF item 4 and its
  manufacturability table were corrected to match Example 5's real
  exclusion reason.
- #116/#142 (the patent-vs-Landy ~20% frequency disagreement on Example 3)
  stays open, unaffected by this ticket.
- #128 (absorber loss lives in the printed pattern, not the substrate)
  remains still open; the layer-architecture discussion from the same
  ticket (recorded in ADR-0017) is consistent with and builds on the
  premise #128 is investigating, but does not resolve it.
- #106 remains the place layer-to-layer print registration accuracy is
  actually measured on the machine in hand, if and when true independent
  multi-layer alphabets are ever needed.
- This ADR does not decide the base-printed-layer/ground-plane default —
  that is ADR-0017's decision, reached in the same ticket discussion but
  recorded there, not here.
