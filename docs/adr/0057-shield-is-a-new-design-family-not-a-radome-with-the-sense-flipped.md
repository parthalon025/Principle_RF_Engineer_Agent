---
status: accepted
---

# `SHIELD` is a new design family, not a radome with the sense flipped

Split out from [ADR-0050](0050-the-registry-carries-post-processing-and-sweep-axes-and-grows-a-transmissive-and-a-shielding-family.md)
for readability; see that file for the shared context and the four-plug-in
family test ([ADR-0027](superseded/0027-the-alphabet-admits-only-printed-letters-and-identity-includes-the-process.md) §5, corrected 2026-09-10:
a candidate is a new **family**, not a new **letter**, if and only if it needs
a different `physical_bound`, `analysis_model`, `optimizer_class` or
`simulation_adapter`) this decision applies. Reference
[ADR-0056](0056-bandpass-fss-is-a-new-design-family-not-an-inverted-absorber.md)
(`BANDPASS_FSS`) for the sibling family from the same pass.

`shielded against` — one of CONTEXT.md's own seven intended effects — had **no
family, no `analysis_model` and no `physical_bound` anywhere**.
`designs/intended_effects.py` (ADR-0049) made this gap queryable a day before
this work: `effects_without_family()` returned it as one of three gapped
effects. ADR-0049 deliberately did not close it — *"this ADR does not add that
family, and `designs/design_families.py` is untouched."* This one does.

## Decision

**`SHIELD` is registered as a new design family — and the argument for it is
deliberately not the one it looks like.**

The tempting argument is that a shield is "a radome with the objective
flipped." It must be resisted — accepting it here after rejecting the mirror
version of it for `BANDPASS_FSS` would be inconsistent — and it is worse than
inconsistent, it is **unavailable**. For the radome the flip was refutable by a
counterexample; here **no such counterexample can exist.** Shielding
effectiveness is `SE_dB = −20·log₁₀|S₂₁|` and transmittance is `T = |S₂₁|²`, so
`SE_dB = −10·log₁₀(T)` exactly — a strictly decreasing function of `T`. Ranking
by "most SE" is the precise reverse of ranking by "most transmission", with no
exceptions. **On the scored quantity alone, these two really are one quantity
read two ways.**

**The argument that works is about the model, not the score.** The family test
asks whether a different `analysis_model` is *needed*, and an analysis model is
a calculation from a design's **own variables** to a predicted number — so the
test is about the inputs, not the output. The two calculations have
**disjoint** inputs:

- A bandpass FSS is designed by **resonant aperture geometry** — slot length,
  gap, period; its published tuning handle is a gap swept 120–360 µm. Make the
  conductor thicker and, past a few skin depths, the passband does not move.
- A shield is designed by **conductor thickness against skin depth** and by
  sheet resistance. Make it thicker and SE rises. Cut a gap in it and you have
  made a hole, which is the one thing a shield must not have.

They are **opposite constructions**: the best bandpass FSS is a *patterned*
conductor (a solid sheet has no passband at all) and the best shield is an
*unpatterned continuous* one (every aperture leaks). No single parameterisation
and no single closed form covers both. *In plain terms: a window and a wall are
both judged on how much gets past them, but you design a window by choosing the
size of the holes and a wall by choosing how thick to make it — and there is no
setting of one dial that turns one into the other.*

**Its `physical_bound` is `UnreadPhysicalBound`, and the restraint is the
point.** Nothing names a shielding bound in #109 or in ADR-0047's per-family
table, and nobody here has searched. There **is** a structural reason to suspect
no bound of the Rozanov/Chu shape governs it — SE rises monotonically with
thickness and conductivity with no bandwidth penalty, so there is no
thickness-versus-bandwidth *trade* for a sum rule to constrain — but that
reasoning is this programme's own, unread and unconfirmed, and it is **not
enough**. `DIFFUSIVE`'s `NO_PHYSICAL_BOUND` rests on a documented argument from
Rozanov's own derivation (`docs/absorber-thickness-bandwidth-bound.md` §7.3) and
even that is labelled `INFERRED` and *"needing confirmation before anything
depends on it."* Absence of a citation is not evidence that no bound exists. The
citation records the suspicion as a reason to search and notes for whoever does:
Schelkunoff's decomposition is a **model**, not a bound, and MIL-STD-461 and its
relatives are **requirement standards**, not bounds.

**The ADR-0017 consequence is recorded on the family, because it is severe.**
ADR-0017 makes every skin this programme designs print its own conductive
reflector by default, and a ground-backed structure transmits nothing by
construction — the reason `DesignFamily.__post_init__` forces
`requires_ground_plane=True` to pair with `port_count=1`. So `|S₂₁| = 0`, SE is
effectively infinite, and the number carries **no design information for that
architecture**. *In plain terms: asking a metal-backed skin how well it blocks
radio is like asking a brick wall how well it blocks daylight. The answer is
"completely", every time, and it tells you nothing about how to build a better
wall.* This family is therefore for a requirement that genuinely wants
transmission stopped through an **unbacked** stack — one where the requirement
has explicitly asserted that no reflector is wanted, exactly as ADR-0017's
correction provides for — and **not** for this programme's own reflector-backed
skins.

**What this does not decide.** ADR-0049 left open whether *"shielded against"*
is a distinct intended **effect** or *"transmitted"* with the sense flipped, and
called it a glossary question. Nothing here answers it and nothing here needs
to: a family is a **mechanism**, an effect is an **ask**, the mapping is
many-to-many by design, and attenuation-through-a-conductive-layer is a
different mechanism from a resonant passband however the glossary resolves the
ask.

Why it is worth registering at all: it is one of CONTEXT.md's own seven, and
shielding effectiveness is what a large share of the published Ti₃C₂Tₓ microwave
measurements report where an absorber paper would report reflection loss
(`docs/absorber-scoring-decision-confirmation.md` §3.3 records the field
instrumenting its bands that way). A precise share — roughly 56 % of the
microwave evidence in this programme's MXene corpus — was quoted to this work
and is **not verified here**; the argument does not depend on the figure. Either
way, a registry that cannot express shielding cannot reach a large part of the
material evidence the programme already holds.

## Consequences

- **`SHIELD` cannot be scored today, and says so honestly.** It carries
  `UndeclaredAnalysisModel` and `UnbuiltPostProcess`, so the ANALYSIS step
  raises with the reason rather than borrowing a model that answers about a
  different device. **Nothing gates.** No candidate is withheld from a reader
  by this — what is refused is manufacturing a number the programme cannot
  stand behind, which is ADR-0028's hard stop boundary exactly where #239
  already drew it.

- **`shielded against` still reaches no intended effect, and that is
  outstanding work, not a finding.** `designs/intended_effects.py` has
  separate ownership and could not be edited here, so
  `SHIELDED_AGAINST.families` is still an empty tuple:
  `effects_without_family()` still reports `shielded against` as gapped while
  `families_without_effect()` now reports `SHIELD` among its entries. **The
  two modules disagree.** ADR-0049's tripwire test fired exactly as designed
  and the disagreement is written into both test docstrings rather than
  hidden; the fix is one line, adding `SHIELD` to that profile.

- **A shielding-effectiveness function for `SHIELD` is now named, well-scoped
  work.** Its ingredients already exist in `rf_tools.sheet_impedance`
  (`skin_depth_m`, `sheet_resistance_ohm_sq`,
  `min_overlay_sheet_resistance_ohm_sq`) and only need assembling. It carries
  a trap in the arithmetic: SE is `20·log₁₀` of a **field** magnitude,
  equivalently `10·log₁₀` of a **power**, and taking `20·log₁₀` of a power
  transmittance doubles every answer — the same voltage-versus-power factor
  of two `docs/absorber-thickness-bandwidth-bound.md` §8.1 records corrupting
  a published Rozanov comparison.
