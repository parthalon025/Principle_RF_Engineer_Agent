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
`simulation_tier` and `port_count` and neither of the other two; a repo-wide
grep found `sweep_axes`/`postprocess` in two ADRs and one findings document and
in **zero** `.py` files. #455 also noted this was not a backfill artefact —
**#109**, the registry's own implementation ticket, states the same four-field
requirement in its body and in its Resolution, settles four *other* fields
explicitly, and closed with two of four shipped.

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

And `shielded against` — one of CONTEXT.md's own seven intended effects — had
**no family, no `analysis_model` and no `physical_bound` anywhere**.
`designs/intended_effects.py` (ADR-0049) made both gaps queryable a day before
this work: `effects_without_family()` returned `transmitted`, `shielded
against` and `low infrared emissivity`, two of the three named in the glossary's
own seven. That ADR deliberately did not close them — *"this ADR does not add
that family, and `designs/design_families.py` is untouched."* This one does.

**The test that decides a family is ADR-0027 §5, as corrected on 2026-09-10.**
An import is a new **family** rather than a new **letter** if and only if it
needs a different `physical_bound`, `analysis_model`, `optimizer_class` or
`simulation_adapter` — **four** plug-ins, the fourth added by that correction
after #453 found the three-plug-in version filing a radome as a letter under
`ABSORBER_TRANSMISSIVE`. Every membership decision below applies the four-item
version and shows the working.

## Decision

**The registry gains the two ADR-0045 fields it was missing — `postprocess` and
`sweep_axes`, both required with no default — and two members, `BANDPASS_FSS`
and `SHIELD`. Low infrared emissivity is argued and declined: it is a
co-design constraint on a candidate whose family is set by its radar behaviour,
not a design family.**

Six parts.

### 1. `postprocess` and `sweep_axes` are two more fields. ADR-0045's "must" stands at four, not three.

#455 raised a genuinely open reading and it deserved a real answer rather than
a code change: `AnalysisModel` records the closed-form *analysis* calculation,
which **may or may not be** ADR-0045's post-processing of a solver's
S-parameters (power arithmetic / effective-medium retrieval /
polarisation-ellipse arithmetic). If they are the same, the right fix is to
narrow ADR-0045's Consequences to three fields, not to grow the dataclass.

**They are not the same, and three independent facts say so.**

1. **Different input, different step of the loop.** `analysis_model` names a
   **closed-form** calculation the ANALYSIS step runs on the **design** —
   geometry and material constants in, a predicted number out, no solver
   anywhere (`rf_tools.absorber.absorber_band_response`,
   `rf_tools.patch_synthesis.patch_resonant_frequency_hz` — moved from
   this package's former single calculations module under issue #522).
   `postprocess` names
   arithmetic the SIMULATION step runs on a **solver's output** — reflectance
   and transmittance in, absorptivity out
   (`orchestration/design_loop.py`'s `_one_port_absorption` /
   `_two_port_absorption`, which #243 wired). Cheap tier and expensive tier
   (CLAUDE.md: *"Evaluate cheap before expensive"*).
2. **One family carries both, and another carries neither.**
   `ABSORBER_TRANSMISSIVE` has a declared closed form **and** power arithmetic
   on the solver's S-parameters. `REFLECTION_PHASE` has neither, because
   Palace hands back the phase it is designed by. One field cannot hold two
   values for the first or two distinct nothings for the second.
3. **"None" is a real answer for one field and not for the other.** ADR-0045
   assigns post-processing **"none"** to three of the seven patent examples —
   the solver returns the scored quantity itself, so there is nothing to
   compute. `analysis_model` has no such value: its second state is
   `UndeclaredAnalysisModel`, meaning *"nobody has established one"* — the
   opposite statement. Collapsing the fields would make "nothing needs doing"
   indistinguishable from "nobody has worked out what to do", the exact
   ambiguity `designs/design_families.py`'s docstring exists to refuse.

*In plain terms: one is the sum you do on paper before running anything; the
other is the sum you do on the simulator's answer afterwards. A surface can
need both, either, or neither, so they cannot be one field.*

**Both are required with no default** — the #239/#241 pattern — and the
argument is sharper than "consistency". `port_count` **is** allowed a default
precisely because `__post_init__` cross-checks it against
`requires_ground_plane` and **catches** a wrong one. Nothing in the registry
implies a post-processing kind or a sweep axis; ADR-0045 says so in terms
(*"none of the three is derivable from the tier or from each other"*), so a
wrong default in either would be **undetectable** — and an undetectable wrong
default is exactly what #239 and #241 were. The registry now demonstrates
ADR-0045's independence claim rather than asserting it: two Tier A families
sweep frequency alone, a third Tier A family also sweeps incidence angle, and
the two Tier B families sweep completely different second and third axes from
**each other**.

**`postprocess` holds one of three states**, never a bare `None`, on the same
reasoning as `physical_bound`: `PostProcess` (built, naming what it consumes,
what it produces and the repo function it lives in), `_NoPostProcess` (the
solver returns the scored quantity itself — a positive statement), and
`UnbuiltPostProcess` (the arithmetic is **identified and missing**, which is
what makes it scoped work rather than a shrug). `declared_postprocess()` raises
**only** for the third, because "there is no sum to do" is an answer and "the
sum has not been written" is not. #220 states the live instance of the third in
the same terms for the Mie-resonant examples: effective-medium retrieval *"is a
post-process, and there is no code for it anywhere in the repo."*

**ADR-0045's own worked example is what the missing axis cost.** It assigns
Example 5 — the tunable, bias-controlled surface — the sweep axis *"frequency
× material state"*. A registry that cannot record that axis sweeps frequency,
reports the surface's response at **one** bias state, and presents it as the
whole answer for a device whose entire point is that the answer moves when you
change the bias. *In plain terms: measuring a dimmer switch at one setting and
writing down "this is how bright the lamp is."*

**A terminology finding, recorded because both readings are live and they
collide.** `docs/seven-example-design-unknowns.md` §5 heads this axis
*"Excitation sweep"*, and then lists geometry, tile assignment and aperture
size under it — which are **design** variables, not excitations. Both readings
are meant, so an axis here is anything a family's evaluation must be repeated
over before its scored quantity exists, and each `SweepAxis` carries a
`supplied_by` field saying which kind it is and who provides its values.
Separately, #455 uses *"post-processing kind"* for a **physical** process step
(a 350 °C anneal, Cl-termination editing — permanent chemical conversions of a
fabricated part). That is a different sense from ADR-0045's **numerical**
post-processing of a solver result, and the two must not be filed in one field:
the first is a Process record under ADR-0027 §4, the second is this field.

### 2. `BANDPASS_FSS` — the radome. A family, not an inverted objective.

The four-plug-in test, applied against `ABSORBER_TRANSMISSIVE` one plug-in at a
time:

| Plug-in | Verdict |
|---|---|
| `physical_bound` | **Same shape.** Both unread; Rozanov reaches neither, since its derivation opens by fixing a slab *"overlying a perfectly reflecting plane"*. Different bounds are *named*, neither is read, so this does not decide it. |
| `simulation_adapter` | **Same.** A periodic unit cell needs a Floquet boundary either way, and `simulation/meep.py` has returned the transmitted share since #240. |
| `optimizer_class` | **Same.** Neither declares one. |
| `analysis_model` | **DIFFERENT — and this is what decides it.** `TRANSMISSIVE_ABSORBER_BAND_RESPONSE` answers *"what fraction of the arriving power this surface turns into **heat** at its worst frequency in band"*. A radome is judged on what fraction goes **through**. |

Under the *three*-plug-in version of §5, all three tested plug-ins match and a
radome is filed as a **letter** under the absorber family — which is exactly
the outcome the 0.06-versus-0.900 arithmetic above prices. The fourth plug-in is
the one that separates them, which is why ADR-0027's correction exists.

`postprocess` corroborates independently: same solver, same two monitors,
different arithmetic on the way out. `ABSORBER_TRANSMISSIVE` must compute
`A = 1 − R − T`; a bandpass FSS reads MEEP's power transmittance straight off,
because `T = |S₂₁|²` **is** what MIL-R-7705B 3.4.1.1 calls *"one-way power
transmission"*. This is corroboration and not the ratio decidendi: §5 names four
plug-ins and `postprocess` is not among them — see Consequences.

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

### 3. `SHIELD` — and the argument is deliberately not the one it looks like.

The tempting argument is that a shield is "a radome with the objective
flipped". It must be resisted — accepting it here after rejecting it in part 2
would be inconsistent — and it is worse than inconsistent, it is **unavailable**.
For the radome the flip was refutable by a counterexample; here **no such
counterexample can exist.** Shielding effectiveness is
`SE_dB = −20·log₁₀|S₂₁|` and transmittance is `T = |S₂₁|²`, so
`SE_dB = −10·log₁₀(T)` exactly — a strictly decreasing function of `T`. Ranking
by "most SE" is the precise reverse of ranking by "most transmission", with no
exceptions. **On the scored quantity alone, these two really are one quantity
read two ways.**

**The argument that works is about the model, not the score.** §5 asks whether a
different `analysis_model` is *needed*, and an analysis model is a calculation
from a design's **own variables** to a predicted number — so the test is about
the inputs, not the output. The two calculations have **disjoint** inputs:

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

### 4. Low infrared emissivity is **not** a design family. Argued, and declined.

Applying §5's four-plug-in test honestly returns not "four differences" but
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

### 5. The Gustafsson & Sjöberg marker stays, and now says which half is missing.

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

### 6. The `"CODING"` → `DIFFUSIVE` alias routing is untouched (#452).

#452 observes that a candidate named `"CODING"` lands on `NO_PHYSICAL_BOUND`,
whose reason is conditional in its own text — it holds only for a surface that
**redistributes rather than dissipates**, and only above a supercell period of
`√2·λ` (42.4 mm at 10 GHz, 30.3 mm at 14 GHz), below which the diagonal orders
do not propagate and every dB of specular reduction must come from absorption,
which is fully Rozanov-bounded. A previous pass added both preconditions to that
sentinel's reason and deliberately did **not** re-route the alias, because the
routing is a decision with its own ticket.

**Nothing here takes it.** Neither family added above is a backscatter
mechanism, so nothing about the two new members changes what the right routing
would be. Recorded, and asserted in test, so the untouched state is visible as
deliberate rather than as an oversight.

## Considered and rejected

- **Narrowing ADR-0045's Consequences to three fields** — concluding that
  `analysis_model` *is* the post-processing kind and that the registry needs
  only `sweep_axes`. This was #455's own suggested alternative and it was taken
  seriously, because it is the cheaper answer and would have retired a stale
  "must" instead of growing a dataclass. **Rejected on the three facts in
  Decision part 1**, of which the second is decisive: `ABSORBER_TRANSMISSIVE`
  carries both a closed form and post-solver power arithmetic simultaneously,
  which one field cannot hold.

- **Defaulting `sweep_axes` to `(frequency,)` and `postprocess` to "none".**
  Rejected: both are the modal value and both are silently wrong for the
  families that matter most — the tunable one for the first, the two absorber
  families for the second. `port_count` is allowed a default only because a
  wrong one is caught by a cross-check; ADR-0045 states that no such cross-check
  can exist for these two.

- **An `objective_sense` field on `ABSORBER_TRANSMISSIVE` instead of a
  transmissive family** (#453's own alternative). Rejected on the mirror
  counterexample in Decision part 2: minimising absorptivity is not the same
  instruction as maximising transmission, so the flag does not fix the ranking
  it was proposed to fix.

- **Carrying `ObjectiveSense` on `DesignFamily` at all**, read from
  `designs/intended_effects.py`'s existing enum. Rejected: it duplicates a fact
  that already has a single home (ADR-0049 point 4), it inverts the relationship
  CONTEXT.md is careful about (a family is a mechanism, an effect is an ask),
  and it is not even mechanically possible in that direction —
  `intended_effects.py` imports `design_families.py`, so the dependency runs one
  way and an import here would be circular.

- **Registering a `LOW_IR_EMISSIVITY` family.** Rejected in Decision part 4:
  four sentinel plug-ins declare nothing, registering it would convert an honest
  gap into a family that appears to serve an effect it cannot, and the
  `__post_init__` port-count invariant refuses it on physics — an infrared layer
  has no ports.

- **Promoting `postprocess` to a fifth plug-in in ADR-0027 §5's family test.**
  It is arguably one: a family needing different arithmetic on the same solver's
  output is doing a different job. Rejected **here** as out of scope, not on the
  merits — ADR-0027 is another decision's document, its §5 was corrected only
  days ago, and this ADR rests its two membership decisions on `analysis_model`,
  which §5 already names. Flagged for that ADR's owner under #453/#455 rather
  than settled by a file this work does not own.

- **Marking the Gustafsson & Sjöberg slot as a live `PhysicalBound`.** Rejected:
  there is no function in `rf_tools/physical_bounds.py` to point `feasibility`
  at, and `rf_tools/` is outside this work's ownership in any case. Guessing a
  formula for an unread bound is the failure Provenance exists to prevent.

- **Re-routing the `"CODING"` alias away from `DIFFUSIVE`.** Rejected as #452's
  decision to make, not this one's.

## Consequences

- **`DesignFamily` now has nine required constructor arguments, and the
  registry has eight members.** Any code constructing a family must supply
  `postprocess` and
  `sweep_axes`; `tests/test_physical_bounds.py`'s two invariant fixtures were
  updated accordingly. Nothing in `orchestration/`, `rf_tools/` or
  `simulation/` constructs one, so no runtime call site changed.

- **#455 is answered and can be closed against this ADR.** ADR-0045's "must"
  stands at four fields and all four are now shipped. The gap that ADR named and
  no locus in the tree acknowledged is closed, and the reasoning for keeping
  `analysis_model` and `postprocess` apart is recorded on the dataclass itself
  rather than only here.

- **#453 is answered and can be closed against this ADR.** A radar-transparent
  bandpass architecture **does** need its own family; the `objective_sense`
  alternative is refuted rather than deprioritised; and the arithmetic that
  makes the refutation checkable (0.06 versus 0.900, mirror versus radome) is
  pinned in `tests/test_design_families.py` so the defect cannot silently
  return.

- **#452 is informed and explicitly not decided.** The `"CODING"` routing is
  untouched and now asserted-as-untouched, so a later reader can tell deliberate
  restraint from an oversight.

- **#220 is informed and not closed.** It asks whether the registry should carry
  an example→family mapping and what a Mie-resonant magnetic-mirror family would
  declare. This ADR adds no `Example` linkage and no such family; what it does
  add is `postprocess`, which is the field #220's *"effective-medium retrieval …
  is a post-process, and there is no code for it anywhere in the repo"* needs in
  order to be recordable at all. When Examples 1 and 2 get a family, that family
  carries `UnbuiltPostProcess("effective-medium retrieval", …)`, and the missing
  work becomes queryable instead of prose in a ticket.

- **#249 is informed and not closed.** It reports that the solver hardcodes one
  family's ANALYSIS fields and score field, so it can only rank a patch, and
  names the general fix: *"a family's capabilities should be read, and an
  unstated one should be a recognisable state rather than an accidental
  default."* `postprocess` is another declared capability for it to read — and
  a caution: two of the eight families now carry `UnbuiltPostProcess`, so a
  solver reading this field must handle the raise rather than assume a value.

- **Two families exist that no intended effect reaches yet, and that is
  outstanding work, not a finding.** `designs/intended_effects.py` has separate
  ownership and could not be edited here, so `TRANSMITTED.families` and
  `SHIELDED_AGAINST.families` are still empty tuples: `effects_without_family()`
  still reports both effects as gapped while `families_without_effect()` now
  reports `("BANDPASS_FSS", "PATCH", "SHIELD")`. **The two modules disagree.**
  ADR-0049's tripwire test fired exactly as designed and the disagreement is
  written into both test docstrings rather than hidden; the fix is two lines,
  adding the family names to those two profiles. Until it lands, a reader
  querying the effects library will be told a gap exists that the registry has
  closed.

- **`PATCH` still reaches no intended effect, and that is unchanged and still a
  finding** — a patch antenna radiates a wave rather than doing something to an
  arriving one, and "radiated" is not among CONTEXT.md's seven.

- **Neither new family can be scored today, and both say so honestly.** Both
  carry `UndeclaredAnalysisModel`, so the ANALYSIS step raises with the reason
  rather than borrowing a model that answers about a different device; `SHIELD`
  additionally carries `UnbuiltPostProcess`. **Nothing gates.** No candidate is
  withheld from a reader by any of this — what is refused is manufacturing a
  number the programme cannot stand behind, which is ADR-0028's hard stop
  boundary exactly where #239 already drew it.

- **Two pieces of small, well-scoped work are now named rather than latent:** a
  passband synthesis for `BANDPASS_FSS` (the equivalent-LC-circuit route the
  reported Ti₃C₂Tₓ chessboard used is the obvious shape, and #453 carries the
  reference), and a shielding-effectiveness function for `SHIELD` — whose
  ingredients already exist in `rf_tools.sheet_impedance` (`skin_depth_m`,
  `sheet_resistance_ohm_sq`, `min_overlay_sheet_resistance_ohm_sq`) and only
  need assembling. Both carry their traps in the code: SE is `20·log₁₀` of a
  **field** magnitude, equivalently `10·log₁₀` of a **power**, and taking
  `20·log₁₀` of a power transmittance doubles every answer — the same
  voltage-versus-power factor of two `docs/absorber-thickness-bandwidth-bound.md`
  §8.1 records corrupting a published Rozanov comparison.

- **The infrared decision is a decision, and it should be cited as one.** The
  407 / 1,695 Ω/sq compatibility thresholds are usable today as a stated
  constraint on any overlay proposed above a microwave absorber, with no
  registry change. If a later reader proposes registering an infrared family,
  the thing that would have to change first is that an infrared **solver** and
  an infrared **model** exist here — until then the four plug-ins are four
  nothings and the `__post_init__` invariant still refuses it.

- **Not decided here:** whether the design loop should consult
  `designs/intended_effects.py` at the ARCHITECTURE step to warn when a stated
  effect has no family (ADR-0049 left this open and it stays open), and whether
  `postprocess` belongs in ADR-0027 §5's family test as a fifth plug-in.
