---
status: accepted
---

# `BANDPASS_FSS` is a new design family, not an inverted absorber

Split out from [ADR-0050](0050-the-registry-carries-post-processing-and-sweep-axes-and-grows-a-transmissive-and-a-shielding-family.md)
for readability; see that file for the shared context and the four-plug-in
family test ([ADR-0027](superseded/0027-the-alphabet-admits-only-printed-letters-and-identity-includes-the-process.md) §5, corrected 2026-09-10:
a candidate is a new **family**, not a new **letter**, if and only if it needs
a different `physical_bound`, `analysis_model`, `optimizer_class` or
`simulation_adapter`) this decision applies.

**[#453](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/453)**
found the cost of a missing member. `ABSORBER_TRANSMISSIVE` was the only
ground-less two-port family in the registry, so a radome — a radar-transparent
window — would land there by elimination, and that family's `analysis_model`
scores worst-in-band **absorptivity**. A real measured part settles what that
costs: a screen-printed Ti₃C₂Tₓ chessboard FSS reported at X-band average radar
**transmittance 78 %** and **reflectivity as low as 16 %** (*J. Alloys Compd.*,
PII S0925838826025946, recorded on #453; provenance `UNVERIFIED` — the primary
paper has not been read here) has

```
A = 1 − |S₁₁|² − |S₂₁|²  =  1 − 0.16 − 0.78  =  0.06
```

Against ADR-0041's −10 dB / `A ≥ 0.900` default that is **6 % of the bar** — a
catastrophic failure, for a near-ideal radome. *In plain terms: a see-through
window and a sponge want opposite things. Measure the window with the sponge's
ruler and the best window in the room comes bottom of the class.*

## Decision

**`BANDPASS_FSS` is registered as a new design family.**

The four-plug-in test, applied against `ABSORBER_TRANSMISSIVE` one plug-in at a
time:

| Plug-in | Verdict |
|---|---|
| `physical_bound` | **Same shape.** Both unread; Rozanov reaches neither, since its derivation opens by fixing a slab *"overlying a perfectly reflecting plane"*. Different bounds are *named*, neither is read, so this does not decide it. |
| `simulation_adapter` | **Same.** A periodic unit cell needs a Floquet boundary either way, and `simulation/meep.py` has returned the transmitted share since #240. |
| `optimizer_class` | **Same.** Neither declares one. |
| `analysis_model` | **DIFFERENT — and this is what decides it.** `TRANSMISSIVE_ABSORBER_BAND_RESPONSE` answers *"what fraction of the arriving power this surface turns into **heat** at its worst frequency in band"*. A radome is judged on what fraction goes **through**. |

Under the *three*-plug-in version of the test, all three tested plug-ins match
and a radome is filed as a **letter** under the absorber family — which is
exactly the outcome the 0.06-versus-0.900 arithmetic above prices. The fourth
plug-in is the one that separates them, which is why ADR-0027's correction
exists.

`postprocess` corroborates independently: same solver, same two monitors,
different arithmetic on the way out. `ABSORBER_TRANSMISSIVE` must compute
`A = 1 − R − T`; a bandpass FSS reads MEEP's power transmittance straight off,
because `T = |S₂₁|²` **is** what MIL-R-7705B 3.4.1.1 calls *"one-way power
transmission"*. This is corroboration and not the ratio decidendi: the family
test names four plug-ins and `postprocess` is not among them — see
Consequences.

**The alternative #453 raises is rejected on arithmetic, not taste.** The other
candidate fix is an `objective_sense` field on `ABSORBER_TRANSMISSIVE`: one
family, one model, a flag saying which direction is better. Flip the sense and
the rule becomes *"minimise absorptivity"*. Under that rule a **perfect mirror**
(`R = 1`, `T = 0`, `A = 0.00`) beats the 78 %-transmitting radome (`A = 0.06`)
— and a perfect mirror is the **worst possible radome**, reflecting everything
straight back into the antenna it is supposed to be transparent to. **The
quantity is wrong, not just its direction**, because a third term (reflection)
absorbs the difference. Pinned in `tests/test_design_families.py` so the
alternative cannot quietly return.

**And the registry deliberately carries no objective sense at all.**
`designs/intended_effects.py` already holds it, **per quantity** rather than per
effect (ADR-0049 point 4), which is where the opposition actually lives: both
`absorbed` and `transmitted` *maximise their own* quantity, and the defect is
one level down, in what each wants from **absorptivity**. A second copy on the
family would be two places that can disagree about one fact — and it cannot be
done by import in any case, since `intended_effects.py` reads
`design_families.py` and the dependency only runs one way. **A family declares
what quantity it computes; which direction is better belongs to the
requirement's intended effect.**

The entry is Tier A, `requires_ground_plane=False`, `port_count=2`,
`MEEP_FLOQUET`, an honest `UndeclaredAnalysisModel` (no closed form in
`rf_tools` computes a passband — `filter_synthesis` is a stepped-impedance
**lowpass** in transmission line under ADR-0031, a circuit on a board rather
than a periodic aperture in free space), and an `UnreadPhysicalBound` naming
broadband-matching theory (Bode, Fano) as **where a search should start** and
explicitly not as a claim that either applies.

**Its description records the fabrication finding, because it changes the
ranking.** ADR-0017's 2026-09-06 correction: a bandpass FSS is flat printed
conductor — square-loop slots in a ~15 µm metal layer, every feature clearing
the 0.2 mm floor, a 62–80 % passband at ~0 dB insertion loss — and is *"the one
architecture with **no** registration risk whatsoever"*, because it needs
exactly one patterned layer and no backing at all. #188 reached the same
finding independently. Its tuning handle is a gap swept 120→360 µm; the useful
end clears the Voltera NOVA's ~100–120 µm line floor about three times over,
while 120 µm itself sits **at** that floor — a Capability warning on the narrow
end, never an exclusion (ADR-0028: warn and proceed; equipment shapes the
ranking, never the search).

## Considered and rejected

- **An `objective_sense` field on `ABSORBER_TRANSMISSIVE` instead of a
  transmissive family** (#453's own alternative). Rejected on the mirror
  counterexample above: minimising absorptivity is not the same
  instruction as maximising transmission, so the flag does not fix the ranking
  it was proposed to fix.

- **Carrying `ObjectiveSense` on `DesignFamily` at all**, read from
  `designs/intended_effects.py`'s existing enum. Rejected: it duplicates a fact
  that already has a single home (ADR-0049 point 4), it inverts the relationship
  CONTEXT.md is careful about (a family is a mechanism, an effect is an ask),
  and it is not even mechanically possible in that direction —
  `intended_effects.py` imports `design_families.py`, so the dependency runs one
  way and an import here would be circular.

## Consequences

- **#453 is answered and can be closed against this ADR.** A radar-transparent
  bandpass architecture **does** need its own family; the `objective_sense`
  alternative is refuted rather than deprioritised; and the arithmetic that
  makes the refutation checkable (0.06 versus 0.900, mirror versus radome) is
  pinned in `tests/test_design_families.py` so the defect cannot silently
  return.

- **`BANDPASS_FSS` cannot be scored today, and says so honestly.** It carries
  `UndeclaredAnalysisModel`, so the ANALYSIS step raises with the reason rather
  than borrowing a model that answers about a different device. **Nothing
  gates.** No candidate is withheld from a reader by this — what is refused is
  manufacturing a number the programme cannot stand behind, which is
  ADR-0028's hard stop boundary exactly where #239 already drew it.

- **`transmitted` still reaches no intended effect, and that is outstanding
  work, not a finding.** `designs/intended_effects.py` has separate ownership
  and could not be edited here, so `TRANSMITTED.families` is still an empty
  tuple: `effects_without_family()` still reports `transmitted` as gapped
  while `families_without_effect()` now reports `BANDPASS_FSS` among its
  entries. **The two modules disagree.** ADR-0049's tripwire test fired
  exactly as designed and the disagreement is written into both test
  docstrings rather than hidden; the fix is one line, adding `BANDPASS_FSS`
  to that profile.

- **A passband synthesis for `BANDPASS_FSS` is now named, well-scoped work.**
  The equivalent-LC-circuit route the reported Ti₃C₂Tₓ chessboard used is the
  obvious shape, and #453 carries the reference.
