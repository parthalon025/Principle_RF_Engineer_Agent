# Meep absorber validation: the first physics this repo has checked

**Date:** 2026-09-08 · **Solver:** pymeep 1.34.0 (conda-forge, the same install path `Dockerfile` uses) · **Issues:** #230, #231, #191, #240, #244

## What changed, in one line

Four cases are recorded below and have been run against a real solver, checked against answers that exist independently of this code — two of them through the committed adapter, and the last of those through the design loop's own two-port absorption sum as well. Three are registered `ReferenceCase` entries (all the MEEP ones); Case 3, the conductive slab, is a check of the adapter rather than a registered case. The registry's fourth entry, the NEC2 dipole, has **not** been run — see `verification/simulator_reference_cases.py`.

> **Correction to this document's first version**, which opened *"until now every simulator adapter here was tested against a hand-built fake."* **That was already false when written.** #210 had driven `simulation/palace.py` against a real compiled Palace binary and found two genuine defects (comma-vs-semicolon column labels, and `specular` returning −158 dB noise where the true reflection was −18.9 dB), recorded in [`docs/palace-floquet-validation.md`](palace-floquet-validation.md). The claim was written on a branch cut before that work merged, and the two branches could not see each other — which is the mundane cause, not an excuse for the claim.

The narrower claim survives, and is the one worth making. The two efforts started on **different halves** — and the Meep half has since been carried across both, by the two adapter-driven cases at the end of this document:

| | Adapter path (deck emission, shell-out, parsing) | Physics (does the answer match a known-correct one) |
|---|---|---|
| **#210, Palace** | ✅ validated against a real binary | ❌ its own §4 says the run is "no check at all on the physics" |
| **This work, Meep** | ✅ cases 3 and 4, after the caveat below | ✅ against an exact answer and an independent method |

*In plain terms: #210 proved we can talk to a solver correctly. This proves a solver told us the truth. Those are different claims and both are needed.*

⚠️ **Caveat on the second row, and how it was closed.** `verification/meep_absorber_validation.py` deliberately builds `mp.Simulation` objects directly rather than calling `run_meep_simulation()`, and re-derives the unit conversions, so that the validation does not assume the thing it validates. The consequence is that **the adapter's own deck emission, subprocess handoff and result parsing are not what those numbers check.**

That gap is now closed from the other side, twice. `verification/meep_adapter_transmittance_check.py` (#240) calls the real `run_meep_simulation` through the real `MEEP_PYTHON` subprocess path on a conductive slab (Case 3). `verification/meep_two_port_absorption_check.py` (#244) goes one step further and runs the design loop's SIMULATION step, so the absorption *sum* is scored by committed code too (Case 4). None of the three scripts replaces another: one validates the physics without the adapter, one validates the adapter's own path, and one validates the whole path a design run takes.

## Case 1 — free-standing resistive sheet (exact answer)

A thin resistive sheet hanging in free space, no ground plane. It has a **closed-form maximum**: absorptance peaks at exactly **0.5** when the sheet's resistance equals half the impedance of free space (188.365 Ω/sq). Not an approximation — an exact result, so any disagreement is the model's fault.

| Rs (Ω/sq) | σ_D | A (Meep) | A (exact) |
|---|---|---|---|
| 94.2 | 19.996 | 0.4359 | 0.4445 |
| **188.4** | **9.998** | **0.4999** | **0.5000** |
| 377.0 | 4.996 | 0.4532 | 0.4443 |
| 754.0 | 2.498 | 0.3316 | 0.3199 |

Meep lands the maximum **at exactly the right sheet resistance**, and hits 0.4999 against 0.5000 — one part in ten thousand. The ~1% drift away from the optimum is finite sheet thickness (0.2 mm is not the zero-thickness ideal), not a conversion error: it grows with distance from the match and vanishes at it.

> **Two numbers appear for this case, and they are both real.** The sweep above ran at resolution 80 px/mm with a 0.2 mm sheet and returned **0.4999**. `verification/meep_absorber_validation.py`, the committed runner, uses a thinner 0.1 mm sheet at 60 px/mm — fewer grid cells across the sheet — and returns **0.4971**. Both pass the ±0.01 tolerance; the difference is discretisation of the sheet itself, and it is quoted here rather than smoothed over because the committed runner is what anyone will actually re-run.

**This case also fails loudly against the defect #230 recorded.** Model the sheet as ideal perfect metal, as the adapter did before, and it returns **0** — a perfect mirror absorbs nothing, no matter what was designed.

## Case 2 — Salisbury screen (two independent methods)

The canonical ground-backed absorber: a 376.73 Ω/sq sheet a quarter-wavelength above a metal plate. At the design frequency the plate, seen through a quarter wave, looks like an open circuit, so the wave sees only a sheet matched to free space and essentially nothing comes back.

Compared against `rf_tools/absorber.py`, which models the same stack by a **completely different method** — an equivalent circuit, no grid, no time stepping.

| f (GHz) | A (Meep FDTD) | A (closed form) | diff |
|---|---|---|---|
| 6.0 | 0.8838 | 0.8834 | +0.0004 |
| 7.0 | 0.9395 | 0.9391 | +0.0004 |
| 8.0 | 0.9746 | 0.9743 | +0.0003 |
| 9.0 | 0.9940 | 0.9938 | +0.0002 |
| **10.0** | **1.0000** | **1.0000** | **−0.0000** |
| 11.0 | 0.9935 | 0.9938 | −0.0002 |
| 12.0 | 0.9738 | 0.9743 | −0.0005 |
| 13.0 | 0.9383 | 0.9391 | −0.0007 |
| 14.0 | 0.8825 | 0.8834 | −0.0009 |

**Agreement to within 0.001 across the whole band**, both peaking at exactly 10.0 GHz. Two unrelated methods agreeing this closely is worth far more than either alone.

## What the cross-check caught

It earned its keep immediately. The **first** run disagreed: the closed form put the peak at 9 GHz where Meep and theory put it at 10.

The cause was real, not a tuning issue. `rf_tools/absorber.py` always included Luukkonen's grid capacitance, which represents the gaps between neighbouring printed elements. A *continuous* sheet has no gaps — but the model could not express that, because the capacitance diverges only **logarithmically**:

| gap | C | X_C at 10 GHz |
|---|---|---|
| 1 nm | 2.446e-13 F | 65.1 Ω |
| 1 pm | 3.614e-13 F | 44.0 Ω |
| 1 fm | 4.782e-13 F | 33.3 Ω |

Even a one-femtometre gap leaves 33 Ω of stray reactance — enough to drag the resonance a full GHz. A continuous sheet is a **different structure, not a limiting case**, and shrinking a gap never reaches it.

Fixed by giving `patterned_sheet_impedance` an explicit unpatterned branch (`gap_m=None`). Without it the model could not reproduce the canonical absorber at all — which also meant it could never have been validated against one.

## Reproducing

```sh
MEEP_PYTHON=/opt/conda/envs/mp/bin/python3 \
  /opt/conda/envs/mp/bin/python3 -m verification.meep_absorber_validation
```

Runs both cases and checks them against the tolerances in `verification/simulator_reference_cases.py`. Deliberately a script rather than a pytest test: it needs a solver CI does not have, and takes minutes rather than milliseconds. `tests/test_meep.py` covers the mechanics; this covers the physics.

## Case 3 — conductive slab, through the adapter itself

The first two cases prove the *physics* is right while bypassing the adapter. This one proves the **adapter** is right, by calling `run_meep_simulation` exactly as the design loop does — through the `MEEP_PYTHON` subprocess handoff — and checking what comes back against an answer derived on paper.

A 3 mm slab of conductivity 0.5 S/m at 10 GHz, free space on both sides. Its complex permittivity is `1 − j·σ/(ωε₀)`, so one ABCD section gives exact R and T.

| | R | T | A = 1 − R − T |
|---|---|---|---|
| **exact** | 0.0422 | 0.6034 | 0.3544 |
| **adapter, real Meep** | 0.0425 | 0.6018 | 0.3557 |
| delta | +0.0003 | −0.0016 | +0.0013 |

**Why this case and not an absorber.** Transmittance is what #240 added, and the way a transmittance goes wrong is a **fixed multiplicative offset** — the wrong baseline plane, or a monitor area folded in twice — which shows up as a T uniformly 2× or 0.5× the truth, not as a small drift. Catching that needs a case that transmits *most* of its power and whose answer is exactly known. A uniform slab is that case, and unlike a thin resistive sheet its answer does not depend on how many grid cells land across it, so a disagreement is the adapter's fault rather than the mesh's.

*In plain terms: a partly see-through slab. We can work out on paper exactly how much bounces back and how much comes out the far side, so if the adapter says anything else, the adapter is wrong. It agrees to a third of a percent.*

## Case 4 — the two-port path, end to end, against a number physics fixes

**Date:** 2026-09-08 · **Issue:** #244 · **Runner:** `verification/meep_two_port_absorption_check.py`

The tickets before this one under spec #237 built the two-port absorber path: an adapter that measures transmitted power (#240), a closed-form two-port model (#242), and a design loop that picks its absorption sum from the design family's declared port count (#243). Every check on them so far compared this code against this code, or against a file recorded from this code's own output. This one does not.

A thin resistive sheet hanging in free space absorbs **at most exactly one half** of the power that hits it, and does so when its sheet resistance is exactly η₀/2 = 188.365 Ω/sq. That is a closed-form maximum from network theory. It was true before this repository existed and it does not move.

*In plain terms: a single grey film hanging in air can never swallow more than half of what lands on it, whatever ink you print it with. So if our machinery says otherwise, the machinery is wrong.*

**Why this sheet and not an absorber.** It is genuinely a two-port problem — a quarter of the power comes back, a quarter carries straight on through, and the remaining half turns into heat. A ground-backed absorber cannot test the two-port path at all: its transmission is structurally zero, so `A = 1 − R − T` collapses into `A = 1 − R` whether the arithmetic is right or not.

**What is under test, and what is not.** Case 1 runs this same sheet, but `verification/meep_absorber_validation.py` builds its own `mp.Simulation` objects on purpose so the physics check does not assume the adapter. Case 4 goes the other way: it calls `orchestration/design_loop.py`'s SIMULATION step, which calls `run_meep_simulation` through the real `MEEP_PYTHON` subprocess and then chooses the sum from `ABSORBER_TRANSMISSIVE`'s declared `port_count=2`. The committed path a real design run takes, in other words, checked against a number nothing here produced.

| | R | T | A |
|---|---|---|---|
| **exact** | 0.2500 | 0.2500 | **0.5000** |
| **full wave, through the adapter and the loop** | 0.2899 | 0.2130 | **0.4971** |
| delta | +0.0399 | −0.0370 | **−0.0029** |

Scored against `free-standing-resistive-sheet-two-port-10ghz`: **PASS** on all three (A within ±0.01, R and T within ±0.06 — see below for why those bands differ by a factor of six).

### The absorbed total is converged. The split is not.

This is the most useful thing the run says, and it would be lost if only the pass were reported. **A is accurate to 0.003. R is about 16 % high and T about 15 % low.** Those two errors are anti-correlated and very nearly cancel in `1 − R − T`.

*In plain terms: this grid counts how much power vanished into the sheet accurately, and is much vaguer about which side of the sheet the surviving power left by.*

Two consequences, both practical:

- **Do not assert on R or T at the absorptance's tolerance.** Asking for the split at ±0.01 fails for a reason that has nothing to do with the arithmetic under test. The case's ±0.06 on each is six times the absorptance band and is documented as such rather than quietly widened. It still catches what it is for: a transmittance off by the factor of two a wrong normalisation plane produces (#240) lands at 0.5 or 0.125, a missing sheet gives R = 0, and a perfect-metal sheet gives R = 1.
- **This case is forgiving of sheet-resistance error.** A(Rs) is flat near its maximum, so a sheet the grid renders as the wrong resistance still lands close to 0.5. By the closed form:

  | Rs (Ω/sq) | 125.6 | 150 | 170 | **188.4** | 210 | 250 |
  |---|---|---|---|---|---|---|
  | A | 0.4800 | 0.4936 | 0.4987 | **0.5000** | 0.4985 | 0.4901 |

  A sheet 15 % off the match still absorbs 0.4967 and sails through the ±0.01 band; it takes roughly a third off to fail. That flatness cuts both ways, and the honest reading is the unflattering one: **this case validates the arithmetic and the normalisation far more strongly than it validates the meshing.** A meshing error large enough to matter elsewhere could pass here barely noticed.

### The same run, scored by the one-port collapse

The reflectance from this run, put through the committed `one_port_absorption` aimed at the real ground-backed `ABSORBER` family:

| sum | value |
|---|---|
| two-port, `A = 1 − R − T` | 0.4971 |
| one-port collapse, `A = 1 − R` | **0.7101** |
| overstatement | **1.428×** |

**It is not "roughly double", and the reason is structural rather than a matter of precision.** At the matched sheet the power splits 25 / 25 / 50, so discarding the transmitted quarter inflates a half into three quarters: 1.5 exactly, on the exact numbers. The measured 1.428 is lower only because this mesh reflects slightly too much, and a high R pulls `1 − R` down faster than it pulls `1 − R − T` down. Half of what escapes this sheet escapes *backwards*, and the collapse already subtracts that — which is why the error is one and a half times, not twice.

*What that means for a reader is worse than the ratio sounds: it presents a surface that passes a fifth of the arriving power straight through as though it had absorbed seven tenths of it.*

No run can reach that number through the loop by accident: `one_port_absorption` refuses a family declaring `port_count=2` outright, and the runner records the refusal's own text. The 0.7101 above had to be asked for deliberately, by aiming the ground-backed family's arithmetic at this run — which is exactly the mistake #216 found in the tree.

### Closed form beside full wave, disagreement stated rather than smoothed

`rf_tools/transmissive_absorber.py` models the same bare sheet as a single shunt resistance across free space (`thickness_m=None`, `gap_m=None`, load = η₀):

| | R | T | A |
|---|---|---|---|
| closed form (#242) | 0.2500 | 0.2500 | 0.5000 |
| full wave, through the loop | 0.2899 | 0.2130 | 0.4971 |
| **disagreement** | **+0.0399** | **−0.0370** | **−0.0029** |

The closed form lands on the exact answer to every digit shown, so this disagreement row is the same discretisation delta as the table above. **That repetition is the finding, not a redundancy: every bit of the gap between the two methods belongs to the mesh, and none of it to the model.** The closed form gives the sheet no thickness at all; the grid gives it 0.1 mm across six pixels, and a resistive film of real thickness is a slightly different structure from a zero-thickness one. It shows up where you would expect — in the split between bouncing back and passing through, hardly at all in the total absorbed.

### Reproducing

```sh
MEEP_PYTHON=/opt/conda/envs/mp/bin/python3 \
  uv run --no-sync python -m verification.meep_two_port_absorption_check
```

A script rather than a pytest test, for the same reason as the others: it needs a solver CI does not have. `tests/test_simulator_reference_cases.py` covers the mechanics with no solver installed — the geometry it poses, the scoring, the collapse arithmetic, and the assertion that scoring this run at 0.7101 **fails** the case.

## What these four cases earn for `SIMULATED` (issue #222, criterion 4)

CONTEXT.md's evidence hierarchy has always ranked *validated* simulation above a bare one. Before this work there was no such thing anywhere in the codebase to point at — every `SIMULATED` tag meant only "an adapter shelled out to a solver and parsed something back", never "and the number it parsed was checked against a truth this codebase did not produce." That is what changed, and precisely this much of it changed:

**What it now means, and only for this:** for a bare or ground-backed *uniform, unpatterned* resistive sheet, hit at *normal incidence*, with any dielectric's loss tangent read at *band centre*, solved by Meep FDTD at 10 GHz — `SIMULATED` means the returned number was checked against an answer this codebase did not produce (an exact closed form, or an independent equivalent-circuit model), to the tolerances in `verification/simulator_reference_cases.py`. Cases 3 and 4 above extend that same claim to the adapter itself: the deck emission, the subprocess handoff and the result parsing were exercised too, not only the physics.

*In plain terms: this work earned the word "validated" for one narrow shape — a plain, flat, uniform sheet hit head-on — not for the actual printed metasurfaces this programme exists to design. A `SIMULATED` label on one of those still means "a solver ran and produced a number that looked reasonable," not "a solver ran and we checked the number against something we know is true."*

That is this document's contribution to a codebase-wide claim. What `SIMULATED` still does not mean — for a patterned unit cell, an oblique angle, the NEC2 dipole, the Palace/Floquet path, and every other adapter in `simulation/` — is stated once, for the whole codebase, in `verification/README.md`'s "What `SIMULATED` now means — and where that stops" section, not repeated here.

## Case 4's own limits

Case 4 adds four of its own, and they are worth reading before quoting its pass:

- **The reflected and transmitted shares are not converged; only their difference from one is.** R is ~16 % high and T ~15 % low at this mesh. `A = 1 − R − T` is right to 0.003 because those errors point opposite ways and cancel. Nothing here validates a *reflectance* or a *transmittance* on its own to better than about ±0.06, and any downstream use of R or T separately — a return-loss claim, a shielding-effectiveness claim — is outside what has been checked.
- **It validates the arithmetic and the normalisation much more than the meshing.** The half-power maximum is flat in sheet resistance, so a sheet the grid renders 15 % off still passes comfortably. Read the pass as "the sums, the flux normalisation and the port-count dispatch are right", not as "the mesh is fine".
- **One structure, one frequency, one sum.** It exercises `A = 1 − R − T` at a single 10 GHz point on a bare sheet. It says nothing about a stack with a dielectric behind the sheet, about a band sweep, or about the energy-balance warning path (`R + T > 1`), which no case here has triggered.
- **The 0.7101 collapse figure is a diagnostic, not a defect that survives in the tree.** It had to be asked for on purpose by aiming the ground-backed family's arithmetic at a two-port run; the loop itself refuses that combination. What it establishes is the *size* of the error #216 found, not that the error is still reachable.

The oldest limit is still the important one: **the canonical case is validated, the design case is not yet.** The next reference case should be a patterned cell with a published response.

## Conversions, verified rather than derived-and-trusted

```
sigma_D = sigma_SI * a / (c * eps0 * eps_inf)     # frequency-independent, exact
sigma_D = 2*pi*f_meep * tan_delta                 # pinned at band centre
sigma_SI = 1 / (R_sheet * thickness)              # ohms-per-square -> S/m
```

Both live in `simulation/meep.py` and are re-derived independently inside `verification/meep_absorber_validation.py`, so the validation does not assume the thing it is validating.
