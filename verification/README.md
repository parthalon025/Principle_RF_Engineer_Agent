# Verification

Every serious design needs a verification matrix.

Minimum fields:

| Field | Description |
|---|---|
| requirement_id | Stable requirement identifier |
| requirement | Human-readable requirement |
| method | analysis / simulation / measurement / inspection / test |
| expected | threshold or expected behavior |
| actual | measured/calculated result |
| status | PASS / CONDITIONAL PASS / FAIL / NOT VERIFIED / BLOCKED |
| evidence | file/report/measurement reference |
| notes | limitations |

A release recommendation must not be PASS if a critical requirement is NOT VERIFIED.

---

## Verification corpus (issue #144)

The matrix above verifies a *design*. This package also verifies the *system*:
two harnesses that check the tools still produce good answers, not merely that
they run.

The distinction matters. Before these, you could change the embedding model,
the chunking, or the ranking, destroy retrieval quality, and watch the whole
suite stay green — because no test knew what a good result looked like.

### `retrieval_eval.py` — knowledge-base retrieval quality

A **golden query** is a question plus the documents that ought to answer it.
`golden_queries.json` holds six of them over the real corpus in
`knowledge/corpus/`, each verified against the source text before being
committed. `tests/test_retrieval_gate.py` runs them through the real search
and fails if mean recall drops below its threshold.

Measured baseline in CI: **recall 1.000, precision 1.000, reciprocal rank
1.000** across all six — every expected document comes back as the first
result. The gate is therefore set at 1.0, and any drop is a regression rather
than noise.

Three metrics, in plain terms:

| Metric | Question it answers |
|---|---|
| **Recall@k** | Of the documents that should have come back, how many appeared in the top k? |
| **Precision@k** | Of the results returned, how many were relevant? |
| **Reciprocal rank** | How far down the list was the first correct hit? |

Recall is what the gate decides on; the others are reported for context.

Two honest limits. The gate needs Postgres, so it runs in CI and not locally.
And CI configures no embedding backend, so search degrades to its lexical path
— meaning the gate measures **lexical** retrieval there. That is a real floor
and the half a chunking or ranking change breaks, but it is not the whole
picture. It is also why the queries read as keywords rather than questions:
lexical search ANDs every term, so a natural-language query only matches if one
chunk contains all of its content words.

### `simulator_reference_cases.py` — solver adapter validation

The simulator adapters are tested against fakes: they confirm we write the
right input deck and parse the output we are handed. Nothing confirms the
solver told us the truth. A **reference case** is a problem whose answer is
published independently of this codebase, so running it end to end tests the
physics rather than the plumbing.

The first case is a centre-fed thin half-wave dipole, whose feed impedance
(≈ 73 + j42.5 Ω — a 73-ohm resistor in series with a small inductor, which is
why 75-ohm coax exists) is among the most reproduced numbers in antenna
engineering.

**Status: the three MEEP cases have been executed; the NEC2 case has not.**

`salisbury-screen-10ghz` and `free-standing-resistive-sheet-10ghz` were run
against a real pymeep 1.34.0 and reproduced their expected values -- 0.4971
against an exact 0.5000, and agreement with `rf_tools/absorber.py` to within
0.001 across 6-14 GHz. Numbers, method and limits in
`docs/meep-absorber-validation.md`; re-run via
`verification/meep_absorber_validation.py`.

`free-standing-resistive-sheet-two-port-10ghz` is the same sheet again, and
deliberately so: the runner above builds its own Meep objects, so the
adapter and the design loop are untested by it. This case is posed *through*
`simulation/meep.py` and scored by `orchestration/design_loop.py`'s two-port
sum `A = 1 - R - T`, and it returned 0.4971 against the same exact 0.5000
(R = 0.2899, T = 0.2130). Re-run via
`verification/meep_two_port_absorption_check.py`. The same run scored by the
ground-backed collapse `A = 1 - R` gives 0.7101 -- **1.43x** the truth, which
is what a two-port surface filed under the one-port family would have
reported. That script and
`verification/meep_adapter_transmittance_check.py` are the two that drive
the committed adapter rather than around it.

`half-wave-dipole-300mhz` needs nec2++, which CI does not install, so
`tests/test_simulator_reference_cases.py`'s real-solve test still skips there.
It is **unrun, not unrunnable**: the Dockerfile builds nec2++, so it is
takeable in the container. Tracked by #222.

**Two case families #222 asks for on the Palace/Floquet path are not
registered at all yet:** a bare dielectric slab against Fresnel's equations
(a degenerate, patternless case of the same mesh and Floquet ports a real
metasurface uses, with an exactly-known answer), and Mie scattering from a
sphere (an exact infinite series, and the prerequisite for ever scoring the
patent's Mie-resonant Examples 1 and 2, #220). Neither has geometry, expected
values, or a runner script written. Building and *running* either needs a
compiled Palace binary; the Dockerfile builds one from source inside the
Linux container this repo publishes, with the build workarounds recorded in
`docs/palace-floquet-validation.md`. No `palace` binary is on `PATH` in the
native-Windows session that wrote this paragraph, and building one from
source on Windows was out of scope for that session. Palace's own
native-Windows support status is **UNVERIFIED** here -- the only signal on
hand is `simulation/meep.py`'s sourced citation that Meep, a sibling
scientific-computing tool, has no supported native Windows install path at
all ("Native Windows installation is currently unsupported"), and that is
not itself evidence about Palace. Registering the geometry without running it
would repeat the exact mistake #222 was filed to fix (see
`docs/meep-absorber-validation.md` case history and #144) -- scaffolding for
a test nobody has executed -- so neither is added here until a session with
a real Palace binary can also run it.

A case declares which adapter can pose it (`ReferenceCase.solver`), and
runners must filter on that. A case is only meaningful to the solver its
geometry is written for: a wire list means nothing to an FDTD grid, and an
absorber stack means nothing to a thin-wire method-of-moments code.

## What `SIMULATED` now means -- and where that stops (issue #222, criterion 4)

CONTEXT.md's evidence hierarchy has always ranked *validated* simulation
above a bare one. Before the Meep absorber work
(`docs/meep-absorber-validation.md`) there was no such thing anywhere in the
codebase to point at -- every `SIMULATED` tag meant only "an adapter shelled
out to a solver and parsed something back," never "and the number it parsed
was checked against a truth this codebase did not produce." That is what
changed, and precisely this much of it changed:

**What it now means, and only for this:** for a bare or ground-backed
*uniform, unpatterned* resistive sheet, hit at *normal incidence*, with any
dielectric's loss tangent read at *band centre*, solved by Meep FDTD at 10
GHz -- `SIMULATED` means the returned number was checked against an answer
this codebase did not produce (an exact closed form, or an independent
equivalent-circuit model), to the tolerances in
`verification/simulator_reference_cases.py`. The physics of the first two
MEEP cases is checked against known-correct answers while the adapter's own
deck emission and parsing are not what those numbers check; the third and
fourth cases (`free-standing-resistive-sheet-two-port-10ghz` and its
transmittance check) extend that same claim to the adapter itself -- the
deck emission, the subprocess handoff and the result parsing were exercised
too, not only the physics. Full numbers and method:
`docs/meep-absorber-validation.md`.

**What it still does not mean, for everything else a `SIMULATED` tag can be
attached to:**

- **`MEASURED`.** No VNA, no fixture, no bench (#133). Two solvers agreeing
  is not a measurement, a closed form agreeing with a full-wave run is not a
  measurement, and the provenance ceiling has not moved for any of the four
  cases.
- **A patterned unit cell** -- the family this programme actually designs,
  printed elements and gaps included. Every case above uses `gap_m=None`
  specifically to switch off the grid capacitance a real printed pattern has;
  validating the uniform limit says nothing about the patterned one. Costa's
  eq (10) thin-spacer correction (#190) remains unrecovered and still biases
  patterned results in a known direction.
- **Anything off normal incidence.** `k_point` is zero in every MEEP case
  above; nothing here says anything about oblique angles.
- **A dielectric away from band centre.** The loss-tangent conversion is
  exact at one frequency and drifts either side of it; nothing here bounds
  that drift.
- **The NEC2 half-wave-dipole path.** `half-wave-dipole-300mhz` is
  registered with its published values transcribed but has never been run --
  it needs nec2++, which no environment this has been attempted in has
  installed. Its `SIMULATED` tag, when it is eventually produced, is
  unchecked until that case runs.
- **The Palace/Floquet periodic-grating path** (`simulation/palace.py`,
  #210). That work drove the adapter against a real compiled Palace binary
  and reproduced Palace's *own published output* for its worked
  dielectric-grating example to 0.056 dB -- proof the deck, the mesh and the
  parser are right. It is not a reference case in this module's sense: the
  truth it checked against is a simulated result from the same class of
  tool, not an independent closed form or measurement, and its own §4 says
  the run is "no check at all on the physics." A `SIMULATED` grating result
  from that adapter today carries the adapter-path guarantee and none of the
  physics guarantee the Meep cases above carry.
- **Every other adapter in `simulation/`** not named above -- openEMS, HFSS,
  gprMax, Elmer, Xyce, ngspice, KiCad/gerber2ems, LTspice, OpenParEM, and
  Qucs -- has no reference case at all yet. A `SIMULATED` tag from any of
  them means exactly what it meant before this section existed.

*In plain terms: this work earned the word "validated" for one narrow shape
-- a plain, flat, uniform sheet hit head-on -- not for the actual printed
metasurfaces this programme exists to design, not for any other solver
adapter, and not for measurement. A `SIMULATED` label on anything outside
that one shape still means "a solver ran and produced a number that looked
reasonable," not "a solver ran and we checked the number against something
we know is true." None of it moves the provenance ceiling: two methods
agreeing is still not a measurement.*
