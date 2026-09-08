# Meep absorber validation: the first physics this repo has checked

**Date:** 2026-09-08 · **Solver:** pymeep 1.34.0 (conda-forge, the same install path `Dockerfile` uses) · **Issues:** #230, #231, #191

## What changed, in one line

Two reference cases have now been run against a real solver, and checked against answers that exist independently of this code.

> **Correction to this document's first version**, which opened *"until now every simulator adapter here was tested against a hand-built fake."* **That was already false when written.** #210 had driven `simulation/palace.py` against a real compiled Palace binary and found two genuine defects (comma-vs-semicolon column labels, and `specular` returning −158 dB noise where the true reflection was −18.9 dB), recorded in [`docs/palace-floquet-validation.md`](palace-floquet-validation.md). The claim was written on a branch cut before that work merged, and the two branches could not see each other — which is the mundane cause, not an excuse for the claim.

The narrower claim survives, and is the one worth making. The two efforts validated **different halves**, and neither has done both:

| | Adapter path (deck emission, shell-out, parsing) | Physics (does the answer match a known-correct one) |
|---|---|---|
| **#210, Palace** | ✅ validated against a real binary | ❌ its own §4 says the run is "no check at all on the physics" |
| **This work, Meep** | ❌ see the caveat below | ✅ against an exact answer and an independent method |

*In plain terms: #210 proved we can talk to a solver correctly. This proves a solver told us the truth. Those are different claims and both are needed.*

⚠️ **Caveat on the second row.** `verification/meep_absorber_validation.py` deliberately builds `mp.Simulation` objects directly rather than calling `run_meep_simulation()`, and re-derives the unit conversions, so that the validation does not assume the thing it validates. The consequence is that **the adapter's own deck emission and result parsing are not what these numbers check.** The adapter path *was* driven end to end against real Meep during development — through `run_meep_simulation` into a subprocess interpreter, returning 0.9917 at 10 GHz — but that run is not committed as a repeatable artifact. Closing that gap is the obvious next step and belongs with #222.

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

## What this does *not* establish

- **Still `SIMULATED`, not `MEASURED`.** No VNA, no fixture, no bench (#133). Two solvers agreeing is not a measurement, and the provenance ceiling has not moved.
- **Normal incidence only.** `k_point` is zero. Nothing here says anything about oblique angles.
- **Loss tangent pinned at band centre.** Meep's `D_conductivity` is one constant; a loss tangent is not. Exact at centre, slightly off at the edges.
- **These are uniform sheets.** A *patterned* cell is the thing the programme actually designs, and the closed form's grid capacitance — the part these cases deliberately switch off — is exactly what is unvalidated. Costa's eq (10) thin-spacer correction (#190) remains unrecovered and still biases patterned results in a known direction.

That last one is the honest limit: **the canonical case is validated, the design case is not yet.** The next reference case should be a patterned cell with a published response.

## Conversions, verified rather than derived-and-trusted

```
sigma_D = sigma_SI * a / (c * eps0 * eps_inf)     # frequency-independent, exact
sigma_D = 2*pi*f_meep * tan_delta                 # pinned at band centre
sigma_SI = 1 / (R_sheet * thickness)              # ohms-per-square -> S/m
```

Both live in `simulation/meep.py` and are re-derived independently inside `verification/meep_absorber_validation.py`, so the validation does not assume the thing it is validating.
