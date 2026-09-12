# Design-loop baseline: how far each of the 8 families actually gets (issue #531)

## Plain-language summary

The "design loop" (`orchestration/design_loop.py`) is meant to walk one
candidate design through nine fixed stages -- REQUIREMENTS, ARCHITECTURE,
ANALYSIS, SIMULATION, OPTIMIZATION, VERIFICATION, MEASUREMENT, CORRELATION,
REDESIGN_DECISION -- in that order, the same way a human engineer would move
from "what is being asked for" to "here is a number I can defend." This
investigation actually ran that walk, in real Python, for a minimal candidate
of each of the 8 design families this repo currently registers (PATCH,
ABSORBER, ABSORBER_TRANSMISSIVE, REFLECTION_PHASE, DIFFUSIVE,
POLARIZATION_CONVERTER, BANDPASS_FSS, SHIELD), and recorded exactly which
stage each one got to before something stopped it and exactly what stopped
it -- not just what the code *looks like* it should do when read, but what it
*actually did* when executed. "Stalls at ANALYSIS" below means: the loop
asked "how do we work this design out on paper before spending any solver
time on it," and for that family nobody has written the arithmetic yet, so
the program refuses to guess and says so by name, rather than quietly
running a different family's formula and handing back a confident-looking
wrong number. "Stalls at SIMULATION" means the paper calculation succeeded,
but the next stage -- a full-wave electromagnetic solver, a piece of
scientific software that numerically solves Maxwell's equations over the
candidate's exact 3-D shape -- could not run in **this particular sandbox**
because that solver isn't installed here (it is one of the two ways a
"binary" can be missing: not written at all, versus written but not
available on this machine right now; these results distinguish the two
throughout).

**Headline result:** of the 8 families, only **PATCH** can be driven, right
now, end-to-end through all 9 steps to a completed loop -- proven by actually
running the codebase's own existing end-to-end test. **ABSORBER** and
**ABSORBER_TRANSMISSIVE** get one stage further than that framing suggests:
their ANALYSIS stage is a real, working closed-form calculation (no solver
needed), and their SIMULATION stage genuinely reaches and calls the MEEP
solver adapter -- it is not skipped or dead code -- but in this sandbox it
then fails immediately because the `meep` Python package is not installed
here (it is installed in the project's own Docker image, per the
`Dockerfile`, just not in this investigation's shell). The other **5**
families (REFLECTION_PHASE, DIFFUSIVE, POLARIZATION_CONVERTER, BANDPASS_FSS,
SHIELD) all stop one stage earlier, at ANALYSIS, regardless of what solver
they declare -- including REFLECTION_PHASE and DIFFUSIVE, which declare a
real, working solver adapter (PALACE_FLOQUET) that a separate, existing test
proves does function when reached directly. It is simply never reached in a
real run, because ANALYSIS (which runs first) always refuses before
SIMULATION gets a turn.

## Table

Every row is from an actually-executed run in this session (`uv run
python3` / `uv run pytest`, real interpreter, real exceptions caught and
recorded, not read off the registry). See "Method" below the table for how
each row was produced and what was mocked, if anything.

| Family | Last step reached (attempted when it stopped) | Stop reason | Adapter invoked? | Binary required & present? | Notes |
|---|---|---|---|---|---|
| **PATCH** | SIMULATION *(then, separately, all 9 steps -- see Method)* | Driven for real with no fake binary: `FileNotFoundError: [Errno 2] No such file or directory: 'nec2++'`, raised inside `subprocess.run(...)` in `simulation/nec2pp.py`'s `Nec2ppSimulator.run`. Driven again reusing the repo's own `tests/test_design_loop.py::test_end_to_end_full_requirements_to_redesign_cycle` (a fake `nec2++` script standing in for the real binary): **completes all 9 steps, loop reaches `completed=True`.** | **Yes.** `_handle_simulation` -> `_simulate_nec2` -> `run_nec2_simulation` -> `Nec2ppSimulator.run` -> `subprocess.run(["nec2++", ...])` was reached and executed. | **Required: yes** (`nec2++`, resolved from `NEC2PP_BIN` env var or literal `"nec2++"`). **Present in this sandbox: no** (`which nec2++` empty). Present in the project's own Docker image (`Dockerfile` builds `tmolteno/necpp` and confirms `nec2++ -h` at build time). | The raw `FileNotFoundError` is **not** wrapped into this codebase's own `SimulatorError`/`DesignLoopValidationError` vocabulary -- `nec2pp.py` only catches `subprocess.TimeoutExpired`, not a missing executable, so a missing binary currently surfaces as a bare OS-level exception all the way up through `advance_loop_step`. With the binary present (real or faked), the loop is proven, by an actually-executed test, to reach `completed=True` -- there is no further code-path gap after SIMULATION for PATCH. |
| **ABSORBER** | SIMULATION | With a complete, spec-valid MEEP geometry dict (`cell_size_m`, `pml_thickness_m`, `mesh_cell_size_m`, `port{...}`, `reflection_monitor_center_m`, `reference_monitor_center_m` -- all required by `simulation/meep.py`'s `MeepSimulator.run` before it will even attempt an import): `simulation.base.SimulatorError: meep is not installed. MEEP is used as a Python library (import meep), not an external binary -- install it per its own docs...`, raised by the guarded `_import_meep()` in `simulation/meep.py` after catching a real `ModuleNotFoundError`. | **Yes.** ANALYSIS (closed-form `absorber_band_response`, no solver) ran and returned a real worst-in-band absorption number. `_handle_simulation` -> `_simulate_meep_floquet` -> the capability-gap probe (`periodic_absorber_capability_gaps()`, currently empty -- all 3 gaps it used to report are closed) -> `run_meep_simulation` -> `MeepSimulator.run` -> full geometry validation (passed) -> the guarded `import meep` was actually attempted and failed. | **Required: yes** -- but as a Python module (`import meep`), not a shell binary; `MEEP_PYTHON` (unset here) can also point at a separate interpreter that has it, subprocess-delegated. **Present in this sandbox: no** (`python3 -c "import meep"` -> `ModuleNotFoundError`; `MEEP_PYTHON` unset). Present in the project's own Docker image at `/opt/conda/envs/mp/bin/python3` (`Dockerfile` builds `pymeep` via conda-forge and confirms `import meep` at build time; `ENV MEEP_PYTHON` is set there). | ANALYSIS's closed-form result is real, working, and recorded evidence on its own (provenance `CALCULATED`) even though SIMULATION could not complete here -- exactly the two-tier design the module docstring describes. A separate, existing test (`test_absorber_simulation_runs_meep_with_a_periodic_cell`, run in this investigation) proves that with `_run_meep_simulation` mocked to return a plausible result, SIMULATION completes and produces a correctly-formed one-port absorption (`A = 1 - R`). |
| **ABSORBER_TRANSMISSIVE** | SIMULATION | Same shape as ABSORBER: full two-port MEEP geometry (adds `transmission_monitor_center_m`, no ground conductor) reaches the same `SimulatorError: meep is not installed...`. | **Yes**, identically to ABSORBER -- ANALYSIS ran the real `TRANSMISSIVE_ABSORBER_BAND_RESPONSE` closed form first, then SIMULATION passed the two-port transmission-monitor precondition check (`_require_transmission_monitor_for_two_port`) and reached the same guarded `import meep`. | Same as ABSORBER: `meep` Python module, absent in this sandbox, present in the Docker image. | Confirms issue #243's port-count-aware dispatch is live code, not dead: the two-port precondition check (refuses before the solver runs if no `transmission_monitor_center_m` is present) was exercised and passed here because the fixture geometry supplied one. |
| **REFLECTION_PHASE** | ANALYSIS | `designs.design_families.UndeclaredAnalysisModelError` (re-raised as `orchestration.design_loop.DesignLoopValidationError`): *"Design family 'REFLECTION_PHASE' declares no analysis_model... a reflection-phase surface is designed by its per-cell reflection PHASE, and no closed form in rf_tools returns a phase."* | **No.** The loop never leaves ANALYSIS; SIMULATION's handler is never called. | Declares `simulation_adapter=PALACE_FLOQUET` (a settled, coded adapter) -- **but this is moot**, because ANALYSIS (which runs first in `STEP_ORDER`) always raises before SIMULATION is ever reached from a real, undoctored run. Binary check performed anyway for completeness: `palace` **required**, **absent** in this sandbox (`which palace` empty), present in the Docker image (built from source at `/opt/palace/bin/palace`, symlinked to `/usr/local/bin/palace`). | Separately, a pre-existing test in this repo (`test_reflection_phase_and_diffusive_route_to_palace_not_nec2`, run in this investigation) proves PALACE_FLOQUET dispatch itself is real, working code: it deliberately *skips* ANALYSIS via a test-only helper (`_advance_to`, which force-sets `current_step` without running the real handler) and shows SIMULATION then correctly reaches `run_palace_simulation` with a valid `ground_backed`+`pec_patches` geometry. That is a legitimate code-path finding, but not a claim that a real, un-doctored loop run ever gets there -- it does not, today. |
| **DIFFUSIVE** | ANALYSIS | `UndeclaredAnalysisModelError`: *"a coding/diffusive cell is DEFINED by its reflection phase... Its figure of merit... is a second missing model on top of the first."* | **No.** | Declares `simulation_adapter=PALACE_FLOQUET`, same moot status as REFLECTION_PHASE -- ANALYSIS blocks first. `palace` binary: required, absent here, present in Docker image. | Same PALACE_FLOQUET dispatch-is-real-but-unreachable finding as REFLECTION_PHASE. |
| **POLARIZATION_CONVERTER** | ANALYSIS | `UndeclaredAnalysisModelError`: *"polarisation conversion is scored on the CROSS-polarised reflection... every closed form in rf_tools is scalar... None of them can represent an anisotropic cell's two principal-axis responses."* | **No.** | Declares `simulation_adapter=UnsettledSimulationAdapter` (no solver chosen at all -- unlike the two families above, this one has **two** independent reasons SIMULATION could never run: no analysis model AND no settled solver). Not applicable to check a binary; there is no adapter name to resolve one from. | The only family in the registry with *both* ANALYSIS and SIMULATION formally undeclared. |
| **BANDPASS_FSS** | ANALYSIS | `UndeclaredAnalysisModelError`: *"a bandpass FSS is designed by where its aperture resonance sits and how wide it is, and no closed form in rf_tools computes a passband... the equivalent-LC-circuit route... #453 carries the reference; until somebody writes it, this raises."* | **No.** | Declares `simulation_adapter=MEEP_FLOQUET` (settled, same adapter as ABSORBER) -- moot, ANALYSIS blocks first. `meep` module: required, absent here, present in Docker image. | If ANALYSIS were ever filled in, this family's SIMULATION path would reuse the already-proven-working MEEP dispatch (same code as ABSORBER/ABSORBER_TRANSMISSIVE). |
| **SHIELD** | ANALYSIS | `UndeclaredAnalysisModelError`: *"shielding effectiveness is predicted from a conductor's thickness against its skin depth and its sheet resistance -- Schelkunoff's... decomposition... and no closed form in rf_tools returns it. The ingredients exist... and nobody has assembled them."* | **No.** | Declares `simulation_adapter=MEEP_FLOQUET` -- moot, same reasoning as BANDPASS_FSS. `meep` module: required, absent here, present in Docker image. | Same "solver path already proven, analysis model is the actual gap" situation as BANDPASS_FSS. |

**On "can a minimal candidate even be constructed" (item 5 of the brief):**
all 8 families passed ARCHITECTURE -- the registry accepted every family
name, and a syntactically minimal `{decision, rationale, design_family}`
input was sufficient to record an ARCHITECTURE decision for every one of
them. No family failed to reach ANALYSIS for lack of constructible input;
every stop from ANALYSIS onward was the code refusing to proceed
(`UndeclaredAnalysisModelError`) or a missing external dependency (a solver
binary/module), never "there was no way to build a candidate at all."

**On the human-approval gate (item 4 of the brief):** ARCHITECTURE,
MEASUREMENT, and REDESIGN_DECISION are gated
(`orchestration/approval.py`'s `LoopStepApprovalReceipt` mechanism,
GitHub issue #98's "the gate with no key"). None of the 8 families' stops
recorded above were caused by this gate -- every run in this investigation
supplied a real, cryptographically valid receipt (the same
`request_loop_step_approval(..., approval_callback=lambda f: True)` pattern
the repo's own test suite uses) before advancing past ARCHITECTURE, so the
gate was satisfied, not bypassed, and every family got past it identically.
That pattern is only available to a caller with direct Python access to this
process, though: `orchestration/approval.py`'s own docstring states plainly
that **no agent/MCP tool in this codebase wires up an `approval_callback` at
all** -- the only real, human-facing path to a valid receipt is a human
running `orchestration/approval_cli.py` locally. So while the gate is not
what stopped any family in this investigation, it remains a second,
family-independent obstacle for any fully agent-driven (as opposed to
human-in-the-loop-via-CLI) run of *any* family, PATCH included -- issue #98's
subject, not something this investigation resolves.

## Method

- Every row's "last step reached" and "stop reason" come from actually
  executing `orchestration.design_loop.start_design_loop` /
  `advance_loop_step` in a real Python process (`uv run python3`, using this
  repo's own dependency set via `uv sync`/`uv run`), not from reading the
  registry statically. The driver script walked REQUIREMENTS ->
  (approved) ARCHITECTURE -> ANALYSIS -> SIMULATION with real, hand-built
  minimal-but-valid `step_input` dicts per family, catching and recording
  the first exception.
- PATCH's second claim ("completes all 9 steps") and the PALACE_FLOQUET /
  MEEP_FLOQUET "dispatch is real code" claims for REFLECTION_PHASE/DIFFUSIVE
  and ABSORBER are each backed by *actually running* a specific, named,
  pre-existing test in `tests/test_design_loop.py` via `uv run pytest`
  (not by reading the test source and assuming it would pass): respectively
  `test_end_to_end_full_requirements_to_redesign_cycle` (a fake `nec2++`
  executable, real Touchstone file, no mocking of `advance_loop_step`
  itself), `test_reflection_phase_and_diffusive_route_to_palace_not_nec2`
  (mocks `_run_palace_simulation`'s *return value* only, not the dispatch
  logic that routes to it -- and force-skips ANALYSIS via `_advance_to`,
  called out explicitly above as a limitation), and
  `test_absorber_simulation_runs_meep_with_a_periodic_cell` (mocks
  `_run_meep_simulation`'s return value only).
- Solver-binary presence was checked directly in this sandbox with
  `which nec2++`, `which palace`, and `python3 -c "import meep"` /
  `echo $MEEP_PYTHON` -- all four came back empty/absent. The project's
  `Dockerfile` was read (not executed) to confirm these three solvers *are*
  provisioned in the program's intended runtime image
  (`nec2++` built from `tmolteno/necpp`; `pymeep` installed via conda-forge
  into a separate env exposed as `MEEP_PYTHON`; `palace` built from source
  and symlinked to `/usr/local/bin/palace`) -- so their absence here is a
  property of this investigation's bare shell, not of the codebase or of
  the program's normal deployment target. This distinction (missing code
  path vs. missing binary in this one sandbox) is exactly what the brief
  asked not to conflate.
- Every family's row is therefore a genuine dynamic result for the family's
  own steps, with one explicitly-flagged exception: the two PALACE_FLOQUET
  dispatch tests for REFLECTION_PHASE/DIFFUSIVE necessarily skip ANALYSIS
  (using the test suite's own `_advance_to` step-skipping helper) to reach
  SIMULATION at all, since a real, undoctored run never gets there -- that
  limitation is called out in both the table and this section rather than
  presented as an ordinary end-to-end run.

## Adjudicating #229 vs #461

**Both were correct about a real fact at the time they were likely written,
and both read as stale today in different ways -- they are not actually in
tension once "reachable" is read precisely.**

- **Issue #229** ("the loop can design a patch antenna and nothing else --
  1 of 14 simulation adapters and 1 of 6 optimizers reachable") is **stale
  as a description of the code today**, in the specific sense that mattered
  to it: the dispatch-by-name defect it was about (comparing a family's
  *name* against the literal string `"ABSORBER"` to pick an analysis, and
  defaulting every unrecognised family to NEC2) is gone -- `_handle_analysis`
  and `_handle_simulation` both now dispatch on a declared field read from
  the registry, and a family with nothing declared fails loudly by name
  instead of silently borrowing PATCH's formula or NEC2. Concretely, **3**
  of the loop's 3 wired simulation-adapter code paths (NEC2, MEEP_FLOQUET,
  PALACE_FLOQUET -- not 14; this repo has many more simulator *modules* than
  the design loop actually dispatches to) are demonstrably real, working
  code, not stubs -- proven above by actually running them (PATCH/NEC2 to
  full completion; ABSORBER & ABSORBER_TRANSMISSIVE/MEEP_FLOQUET to a genuine
  `import meep` attempt; PALACE_FLOQUET's own dispatch logic via a targeted
  test). That is real progress past "1 of 14 reachable," and #229 read
  literally is no longer an accurate description of the dispatch code.
  However, #229's *practical* headline -- that a real, undoctored candidate
  walked start-to-finish today reaches full completion for **PATCH only** --
  is still **true right now**, for a reason #229 itself did not anticipate:
  5 of the other 7 families are blocked one whole stage *earlier* than
  simulation, at ANALYSIS (no closed-form model declared at all), which
  #229's own framing ("adapters reachable") does not capture, because it is
  not a simulation-adapter problem for those 5 -- REFLECTION_PHASE and
  DIFFUSIVE, in particular, have a perfectly good, tested SIMULATION adapter
  that ANALYSIS keeps them from ever reaching.
- **Issue #461** ("record `run_meep_simulation`'s workdir on
  ABSORBER/ABSORBER_TRANSMISSIVE decisions") presupposes MEEP already runs
  for those two families, and that presupposition is **essentially correct,
  with one environment caveat this investigation surfaced directly**: MEEP
  genuinely *is* invoked for both families -- the loop's SIMULATION step for
  each one reaches `run_meep_simulation`, passes every precondition check
  (geometry completeness, the two-port transmission-monitor requirement for
  ABSORBER_TRANSMISSIVE), and attempts the real `import meep` -- so a
  `workdir` argument genuinely does flow through that call
  (`_simulate_meep_floquet` already threads `step_input.get("workdir")`
  into `run_meep_simulation`, per `orchestration/design_loop_simulation.py`
  line ~414) and is exactly the kind of thing #461 could sensibly record.
  The caveat: in *this* sandbox specifically, the run does not actually
  finish -- it stops at "meep is not installed" -- because the `meep` Python
  package is absent here (present in the project's own Docker image). #461
  is not stale; it is describing the family-level dispatch correctly. It
  would be stale only if read as "MEEP simulation results already exist for
  these two families in every environment," which nobody should conclude
  from it, and which this investigation shows is an environment fact, not a
  code fact.
- **Net read:** #229 and #461 are each right about a different layer.
  #229 was right about the *symptom* (only PATCH completable) at the time,
  wrong (now, and possibly already wrong when #461 was filed) about the
  *cause* it named (adapter dispatch); the actual cause blocking 5 of the
  remaining 7 families is an undeclared ANALYSIS model, not an unreachable
  adapter -- and for the 2 families it blocks by an unreachable adapter
  (PATCH aside), that adapter (`UnsettledSimulationAdapter` for
  POLARIZATION_CONVERTER) is moot anyway, since ANALYSIS blocks first. #461
  is right that the dispatch it is asking about is live and does get
  exercised, and is only "stale" if taken to claim those runs currently
  succeed in every environment, which this document's own evidence says
  they do not, here, for want of one Python package.

## Solver binaries/modules confirmed missing in this investigation's sandbox

- `nec2++` (env override: `NEC2PP_BIN`) -- PATCH's NEC2 adapter. Not on
  `PATH`.
- `meep` Python package (env override for a separate interpreter:
  `MEEP_PYTHON`) -- ABSORBER's, ABSORBER_TRANSMISSIVE's, BANDPASS_FSS's, and
  SHIELD's MEEP_FLOQUET adapter. Not importable in this interpreter;
  `MEEP_PYTHON` unset.
- `palace` (env override: `PALACE_BIN`) -- REFLECTION_PHASE's and
  DIFFUSIVE's PALACE_FLOQUET adapter. Not on `PATH`.

All three are provisioned in the repository's own `Dockerfile` (built from
source or installed via conda-forge, each confirmed working at image-build
time), so their absence is specific to this bare investigative shell, not a
property of the codebase or of how the program is meant to be deployed.
