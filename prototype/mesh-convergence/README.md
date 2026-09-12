# Resolution-convergence sweep prototype (THROWAWAY)

Answers one design question raised by `docs/antenna-software-comparison.md`
§2.2: **does sweeping a solver's grid resolution produce a usable,
machine-readable error bar on a `SIMULATED` result?**

**This is a throwaway prototype, not production code.** It is not wired into
`simulation/`, is not imported by anything else in this repo, and does not
implement a convergence check for the MEEP adapter — only a feasibility check
with runnable numbers. See the top-of-file docstring in
`mesh_convergence_prototype.py` for exactly what is real and what is invented.

Run:

```
uv run python prototype/mesh-convergence/mesh_convergence_prototype.py
uv run python prototype/mesh-convergence/mesh_convergence_prototype.py --json
```

No dependencies beyond the standard library. `--real` drives the committed
MEEP adapter instead of the fake solver and **needs Meep installed** (see
`verification/meep_absorber_validation.py`'s header); it has never been
executed — the environment this was written in has no Meep.

## The verdict

**Yes, and the error bar must be per-field.** Run against a synthetic solver
carrying the convergence signature `docs/meep-absorber-validation.md`
documents by hand, the sweep recovers that same finding mechanically:

```
  field               finest   last move   still shrinking     verdict
  --------------------------------------------------------------------
  reflectance         0.2896      0.0396               yes      MOVING
  transmittance       0.2125      0.0375               yes      MOVING
  absorptance         0.4979      0.0021               yes   converged
```

That is the document's "the absorbed total is converged, the split is not,"
arrived at from the numbers rather than from a person reading them. A single
scalar `converged: yes/no` for the whole solve would have erased it.

Three design decisions came out of building it, and they are the part worth
keeping:

1. **Per field, never one verdict for the solve.** Different outputs of the
   same run converge at different rates — that is the whole documented
   finding, and a global flag destroys it.
2. **The error bar is the last successive difference, with no Richardson
   extrapolation.** Extrapolating buys a tighter bar only by assuming a
   convergence order, and a resistive sheet six pixels thick with subpixel
   smoothing is exactly where that assumption is worth least. Refusing to
   assume over-states the uncertainty, which is the safe direction.
3. **The knob is pixels across the thinnest feature, not raw resolution.**
   This falls out of a confound in the existing evidence: the two
   absorptance numbers in `docs/meep-absorber-validation.md` (0.4999 at 80
   px/mm with a 0.2 mm sheet, 0.4971 at 60 px/mm with a 0.1 mm sheet) changed
   resolution *and* thickness together, so they cannot separate the two. A
   clean sweep — one geometry, grid only — has never been run in this repo.

## What it does not answer

Whether MEEP's real convergence looks anything like the fake signature. That
needs `--real` under an interpreter with Meep, and until someone runs it the
three decisions above rest on a synthetic case, not on this solver.

It also measures **discretisation error only** — how much the answer still
moves as the grid refines. A converged wrong answer is still wrong; nothing
here checks the model, the materials, or the adapter.
