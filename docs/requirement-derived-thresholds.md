# Every threshold traces back to the requirement

**Date:** 2026-09-04
**Serves:** [#110](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/110), [#112](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/112), [#115](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/115), part of [#104](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/104).
**Question:** Which numbers in this loop are the customer's, which are physics', and which are ours — and what happens when we confuse them?

---

## Why this exists

On 2026-09-04 the super-cell sizing rule ([#130](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/130)) was found to be gating on **±22.5°** of phase error. That number is the half-step of a 3-bit phase quantisation: a **beam-forming** convention, imported into a **backscatter-reduction** design. It made the rule roughly six times stricter than the objective warranted and produced a headline conclusion — "three of six element families are infeasible" — that was an artefact of the borrowed constant and nothing else.

The failure was not arithmetic. Every step after the constant was correct. **The failure was that a number nobody had asked for was doing the work of a requirement**, and because it was expressed in the design's internal units (degrees) rather than the customer's (decibels of reduction), nothing about it looked out of place.

`RUNNING-LISTS.md` §3 item 13 had already recorded the exact trap. The same effort that wrote the warning imported the convention.

**So this document is an audit.** It classifies every fixed number the loop currently relies on, and states the rule that keeps the failure from recurring.

---

## The rule

> **A convention is a default. It is never a threshold.**
>
> A convention may fill a silence, and must be recorded as having filled it. It
> may never override a stated requirement, and it may never become a pass/fail
> line on its own authority. A number that cannot be traced to the customer, to
> physics, or to the machine is a **smuggled assumption** and must be labelled
> as one wherever it appears.

**This is not a new preference — it follows from one already settled.** [#117](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/117) decided that **silence is permissive**: an unstated requirement does not prune the candidate space. A convention adopted as a threshold does exactly the opposite — it converts a silence into a hard prune, on the authority of a literature the customer never cited. Adopting *"−10 dB is the threshold"* because the field defaults to it is not neutral; it is inventing a requirement and then enforcing it.

---

## The three kinds of number

| Kind | Where it comes from | May it prune? | Example |
|---|---|---|---|
| **A — Requirement** | The customer states it | **Yes**, per #117's threshold/objective | "≥ 15 dB reduction, 9–11 GHz, within ±30° of broadside" |
| **B — Physics or machine** | Nature, or the hardware in the room | **Yes** — it is a fact about what can exist | Skin depth; the NOVA's 0.12 mm line floor |
| **C — Convention** | A field's reporting habit | **No** | "−10 dB is the threshold"; "±22.5° phase error" |

**Every failure of this kind is a C wearing A's clothes.** The tell is that a C-number is stated in the *design's* units rather than the *requirement's*, so there is nothing to compare it against and nothing to notice.

**C-numbers are still valuable** — they are how published work is compared to published work, and abandoning them would make the literature unusable. The rule is only that they do not gate.

---

## The audit

### Fixed and traced

| Number | Was | Kind | Now |
|---|---|---|---|
| **±22.5° phase budget** | a gate on the alphabet (#130) | **C** | Derived: `δ = 2·arcsin(10^(−RCSR_dB/20))`. **36.9° at 10 dB.** ±22.5° silently encoded a 14.2 dB requirement nobody stated |
| **θ_min = 30° scattering angle** | a gate on block size (#130) | **C** | Split. Its floor is **B** — the panel's own specular lobe, ≈ `λ/(2L)`, 4.8° for a 6 λ coupon. Anything above that is **A**, from whatever the requirement says about bistatic angles |

### Open, and at risk of the same error

| Number | Status | Kind | What it should be |
|---|---|---|---|
| **−10 dB reflectivity / 90 % absorption** | `absorber-scoring-conventions.md` §1 lists it among four things to *"adopt without argument"*; **#110 has not yet decided** | **C** | **A default, not a threshold.** The requirement states how much reduction is needed. −10 dB fills the silence when it does not, is recorded as having done so, and is overridden without argument by any stated figure. That document is honest that this is *journal* convention with no standards backing — IEEE Std 1128 stops at 5 GHz and standardises measurement, not scoring |
| **"10 dB bandwidth" as the band** | implied throughout | **C** | The requirement states the band. The −10 dB contour is a *reporting* device for comparing published designs, not the definition of the customer's band |
| **Worst-case vs mean in band** | `absorber-scoring-conventions.md` §7.2: "nobody argues the choice" | **C → A** | The requirement decides. Worst-case is the safe default when it is silent — and must be recorded as a default, because it is the stricter of the two |
| **Off-band behaviour** | §7.3: "essentially never reported or scored" | **A** | A genuine gap. Silence here is not "don't care" — a surface that is transparent out of band may be worse than one that is not. Must be asked, not assumed |
| **`R = 3T` vs IPC-2223's 6× rule** | open on #115 | **A + B** | The host's radius of curvature is **A**. Which rule governs is a standards choice that should be *stated*, not inherited — the patent's rule is twice as permissive as the flex-circuit industry standard, so picking silently approves parts bent twice as tight as IPC allows |
| **Cell pitch 0.4–0.5 λ** | assumed throughout | **C over B** | Grating-lobe onset is **B** and sets a real ceiling. The particular 0.4–0.5 λ *range* is convention, and #130's rule is sensitive to it — Δφ_max more than triples between 0.5 λ and 0.4 λ |
| **Host polymer εr 2–5** | the patent's own stated range; three of its seven examples sit outside it | **unresolved** | Open on #104: constraint to enforce, or description of the examples shown? |

### Legitimate — B, and staying

| Number | Why it is not negotiable |
|---|---|
| **Skin depth; ~3 δ for "electrically thick"** | Physics. 0.66 µm in copper at 10 GHz; conductor thickness above ~2 µm is a null variable (#116) |
| **NOVA minimum line 0.12 mm; minimum film ~10 µm** | The machine in the room. A requirement cannot argue with it |
| **Cure ceiling of the host** | The host melts or it does not |
| **Rozanov bound** | A theorem. The one item in `absorber-scoring-conventions.md` that is stronger than convention |
| **Coupon ≥ 6 λ focused / 20 λ unfocused** | Measurement physics (#106). Note what it constrains: **what we can verify**, not what the design must achieve. It must never migrate into the design's thresholds |

### Not requirement quantities at all

The **provenance ladder** and the **threshold/objective** structure are methodology — how confidence and hardness are expressed, not values to be met. They are not in scope here and do not need tracing.

---

## What this asks of the loop

1. **Every threshold carries its origin.** `A`, `B`, or `C-as-default`, alongside the provenance rung it already carries. A threshold whose origin is `C-as-default` is **reversible on contact with a stated requirement**, exactly like #117's unconfirmed thresholds.
2. **A `C-as-default` threshold prunes for one pass at most**, recorded, and is surfaced to the morning review under the unattended mode. It never removes a candidate permanently.
3. **The requirement is stated in the customer's units.** If a threshold cannot be expressed in the units the requirement uses — decibels, gigahertz, degrees of incidence, millimetres of bend radius — it is an internal quantity and cannot be a threshold. **That test alone would have caught ±22.5°.**
4. **Report against purpose.** A candidate's report says what reduction it achieves over what band at what angles, not what phase error its alphabet carries. The internal quantity is the means; the requirement is the end, and only the end is scoreable.

---

## Honest limits

- **This is an audit of what is written down, not proof there is nothing else.** It covers the documents and decisions on the map as of 2026-09-04. The Python does not currently hardcode thresholds — `success_score.py` takes `target_value` and `tolerance` from its caller, which is the right shape — so the exposure is in the decisions, not the code. That will change once the spec is implemented.
- **The classification of a few entries is arguable.** Cell pitch in particular sits across B and C, and reasonable people could put the −10 dB convention in a fourth category of "industry expectation the customer will assume without stating." If they do, that is an argument for *asking*, not for adopting.
- **Nothing here is measured, and nothing here needs to be.** This is a bookkeeping discipline, not a physical claim.

**What would falsify it:** a case where refusing to adopt a convention as a threshold leaves the loop unable to score anything at all, and where asking the customer is genuinely not possible. That would argue for a fourth kind — *conventions strong enough to be treated as requirements* — which would need to be a deliberate, recorded decision rather than the default drift.

---

## The one-line version

**A threshold in the design's own units is not a requirement.** A requirement is decibels of reduction, over a band, over an angular window, on a host of a stated radius. Anything that cannot be written that way is ours, not theirs, and must say so.
