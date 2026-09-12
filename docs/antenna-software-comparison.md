# Commercial and amateur antenna software, read against this repo

**Date:** 2026-09-12
**Question asked:** "Can any of these programs or tools help improve or enhance this repo?
What do they do right that I am doing wrong?" — against a list naming Ansys HFSS, MATLAB
Antenna Toolbox, CST Studio Suite, Cadence/Remcom XFdtd, 4NEC2, MMANA-GAL, openEMS and
EZNEC.
**Scope:** two separate answers. §1 is the tool-by-tool verdict (short: almost nothing new
to adopt). §2 is the part worth reading — four *practices* those tools have that this repo
measurably does not, each checked against the code rather than against a planning doc.

**Provenance of this document.** Every claim about *this repo* below was checked by opening
the file named and is cited `path:line`. Claims about the commercial tools are
`LITERATURE-SUPPORTED` from vendor documentation and standard practice, not re-derived
here; where a vendor claim is load-bearing for a recommendation it is flagged.

---

## Bottom line up front

**On the tools: there is nothing on that list to go and install.** Every free tool named is
either already wired into this repo or is a Windows GUI wrapper around a solver kernel the
repo already drives headless. Every paid tool named is already covered by an explicit
decision — HFSS has a working adapter (`simulation/hfss.py`) held deliberately off the
default path by ADR-0012, and CST/XFdtd/ADS sit in the same category with nothing to add
that openEMS, MEEP, Palace, OpenParEM, Elmer, gprMax and NEC2++ do not already cover.
`docs/FREE_AND_OPEN_SOURCE_TOOLING.md` already did this survey and the adapters were built
from it.

**On the practices: there are four, and the first two are real holes.**

1. **They refuse to solve a model that violates the solver's own validity rules. This repo
   passes the caller's numbers straight through.** This is the biggest one, and it is in
   direct tension with the repo's own "warn, never block" charter — which asks for a
   warning, not silence.
2. **They will not report a number until the mesh has stopped changing it. Nothing here
   ever varies a mesh.** Every mesh in the tree is a hardcoded coarse default, two of them
   annotated in their own source as not convergence-verified. A `SIMULATED` tag can
   therefore currently be attached to a number that is wrong purely because the
   discretisation was too coarse, and the existing conservation checks cannot catch it.
3. **One geometry model feeds every solver. Here each adapter has its own bespoke geometry
   dict.** This is why the two-solver cross-check in #223 is harder than it looks: without a
   shared geometry, a disagreement between two solvers cannot distinguish "the methods
   disagree" from "you built two different objects."
4. **They ship a catalog of parameterised starting geometries that are already roughly
   right.** This repo has one (the patch) and one named objective built on it.

Items 3 and 4 are already ticketed in substance (#223/#507, #229/#213/#211). Items 1 and 2
are not ticketed anywhere, and item 2 is the one that touches the repo's core claim.

---

## 1. The tools, one at a time

| Tool named | Verdict | Why |
|---|---|---|
| **openEMS** | Already wired | `simulation/openems.py`, with real FFT-computed S-parameters from port probe dumps and NF2FF far-field/gain (issue #269). |
| **4NEC2** | Nothing to install | Windows GUI wrapper around the NEC-2 kernel. This repo already drives **NEC2++** headless (`simulation/nec2pp.py`) — a double-precision C++ reimplementation of the same kernel with none of the original's array limits. *Its diagnostics are worth stealing; see §2.1.* |
| **EZNEC** | Nothing to install | Same NEC-2 kernel. Free of charge since v7.0, but a Windows GUI with no documented CLI — the same reason `docs/FREE_AND_OPEN_SOURCE_TOOLING.md` already rejected Sonnet Lite ("not automatable into this repo's subprocess-adapter pattern"). |
| **MMANA-GAL** | Nothing to install | MININEC-derived kernel, GUI-driven, wire-antenna oriented. Strictly less capable than NEC2++ for this repo's purposes and equally unautomatable. |
| **Ansys HFSS** | Already decided | `simulation/hfss.py` is real, working, license-confined code, deliberately off the free path (ADR-0012). Nothing to change. |
| **CST Studio Suite** | No action | Paid. Its role — 3D full-wave plus system-level integration — is covered on the free path by openEMS/MEEP (FDTD), Palace/Elmer/OpenParEM (FEM) and NEC2++ (MoM). |
| **Cadence / Remcom XFdtd** | No action | Paid FDTD/MoM. Same argument as CST. |
| **MATLAB Antenna Toolbox** | No adapter; **one idea worth copying** | Paid, and needs a MATLAB licence on top. Its `design(element, frequency)` pattern — a catalog of parameterised elements each carrying a closed-form starting dimension — is the single most transferable idea on this list. See §2.4. |

**The one capability genuinely absent from both lists.** Nothing here — free or paid-but-
unadopted — covers **installed / platform performance**: what the antenna does once it is
on the vehicle, the aircraft, the wall. That is asymptotic-solver territory (HFSS SBR+,
XFdtd's hybrid solvers, physical optics), and the charter's opening paragraph is *about* a
host surface. No free tool identified covers it, so this is named as a gap, not as a
proposal. **Characteristic mode analysis** (in both HFSS and MATLAB, and arguably the most
useful single technique for an antenna on a conducting host body) is in the same position:
no free route to it was identified in this pass, and asserting one without checking would
be exactly the guess this repo exists to avoid.

---

## 2. What they do right

### 2.1 They check the model before they solve it. This repo checks only the answer afterwards.

*In plain terms: every solver is only valid inside a box — wires can't be chopped too
coarsely, cells can't be too fat, a mesh can't be thinner than the material it's modelling.
Outside that box the solver still returns a confident-looking number, and the number is
wrong. Professional tools know their own box and say so. This repo hands the solver
whatever it is given.*

**The evidence.** `generate_nec2_deck` (`simulation/nec2pp.py:125`) validates exactly one
thing: that the caller supplied the eight required fields per wire
(`simulation/nec2pp.py:181-194`). It then formats them straight into a `GW` card. None of
NEC's own standing validity rules is checked — not segment length against wavelength, not
segment length against wire radius (the thin-wire kernel's own limit), not radius against
wavelength, not segment-length matching at junctions. A search of the whole tree for any
segment-length-versus-wavelength test returns nothing.

**Worse, the diagnostic is already in hand and is thrown away.** NEC's Average Gain Test is
the standard self-check: for a lossless antenna in free space, average power gain must come
out at 1.0, and a departure from it means the model is bad. `parse_nec2_output` already
extracts that number (`simulation/nec2pp.py:412-413`) and returns it as
`average_power_gain_linear`. Every consumer of that field treats it as just another number:
the solver can select it as a `result_field` to *score against a requirement*
(`orchestration/solver.py:325`), and `orchestration/lab_test_plan.py` carries it along.
**Nothing anywhere interprets it as a validity signal.** 4NEC2 puts it on screen with a
verdict; here it is a float with no meaning attached, and a reader could score a design
against it as though it were a performance figure.

**Why this matters more here than it would elsewhere.** The repo's own ADR-0028 ("warn,
never block") does not say *don't check* — it says check, then hand the candidate over with
the warning attached. `simulation/conservation_checks.py` is that discipline done properly:
power balance, passivity and reciprocity, each returning a numeric margin, each annotated
with what is assumed, what it costs if the assumption is wrong, and the cheapest way to find
out. That module is a **post-solve** check on the answer. There is no **pre-solve** check on
the model. And a passivity check cannot catch a badly segmented NEC model: a coarse model is
usually perfectly self-consistent — it conserves energy beautifully while describing the
wrong antenna.

**The shape of the fix, if it is wanted.** A per-adapter `validity` block on the returned
result, in the same assumption/cost/cheapest-test shape `conservation_checks` already uses,
populated from each solver's own documented limits and from the diagnostics the solver
already prints. Nothing blocks. Start with NEC2++, where the rules are published and the AGT
number is already parsed.

### 2.2 They do not report a number until the mesh has stopped changing it.

*In plain terms: a simulator chops the model into little cells. Too few cells and the answer
is wrong; add more and the answer moves, until at some point it stops moving — and only then
is it worth believing. HFSS does this automatically and refuses to converge until successive
passes agree to a stated tolerance. Nothing in this repo ever changes a mesh.*

**The evidence, adapter by adapter.**

- **openEMS** requires the caller to hand in explicit mesh lines and refuses only if they
  are missing: `geometry['mesh'] must supply non-empty 'x_lines_m'/'y_lines_m'/'z_lines_m'`
  (`simulation/openems.py:696-699`). There is no λ/N mesher, no check that line spacing is
  fine enough for the highest permittivity in the stack, no edge refinement. Whatever the
  caller — in practice, a language model — writes down is what gets solved.
- **Elmer** defaults its maximum element size to `min(extents) / 10.0`
  (`simulation/elmer.py:523`), described in its own docstring as "a coarse heuristic, **not
  a mesh-convergence-verified value** — override for real use" (`simulation/elmer.py:507-509`).
- **Palace** defaults to 2 elements per feature interval, which its own module documents as
  "deliberately coarse" (cited at `simulation/conservation_checks.py:50-52`).

Nothing in the tree runs the same problem at two mesh densities and compares. A search for
any convergence-study, refinement-sweep or Richardson-extrapolation machinery returns
nothing.

**Why this is the serious one.** The repo's central claim is that a `SIMULATED` number
outranks a `CALCULATED` one because a solver computed it. Today that tag is attached without
anything having established that the number is converged — and the tolerance discussion in
`simulation/conservation_checks.py:30-70` shows the project already knows discretisation
error is the dominant term, because the whole tolerance band is derived from it. The
knowledge is in the tree; the check is not. Two of the three adapters above **tell you in
their own source** that their default is not trustworthy for real use, and there is nothing
that acts on that.

**The shape of the fix.** A convergence sweep is not new physics and not a new solver: run
the same job at 1×, 1.5× and 2× mesh density, report how far the answer moved, and attach
that movement to the result as its own uncertainty figure. Once that number exists, it is
the honest error bar on every `SIMULATED` claim, and it can feed the same
assumption/cost/cheapest-test warning shape as everything else. It also gives #335's
simulator-trust ledger something real to record.

### 2.3 One model, many solvers — which is what makes a cross-check mean anything.

HFSS, CST and MATLAB all keep one parametric geometry and let you change the solver
underneath it. Here, every adapter has its own geometry vocabulary: openEMS takes explicit
mesh lines and primitive dicts, Palace takes `mesh.nx/ny/nz` plus `pec_patches`, Elmer takes
`domain`/`excitation`, gprMax takes `domain_m`/`resolution_m`, NEC2++ takes `wires`.

`geometry/unit_cell.py` is the one place this was done right — it emits primitives in
openEMS's shape and is explicitly simulator-agnostic by design — but it stops at openEMS.
Issue #507 already records the consequence ("primitive shape-parsing duplicated across
meep.py, palace.py, and openems.py"), and issue #223 wants a Palace-FEM-versus-FDTD
cross-check on one unit cell.

**The point worth adding to those tickets:** without a shared geometry, a cross-check is
epistemically weak. If the two solvers disagree, you cannot tell whether the methods
disagree or whether the two hand-authored geometries were different objects. A shared
geometry intermediate representation is not a tidiness refactor — it is what converts #223
from "two numbers that differ" into evidence.

### 2.4 They hand you a starting geometry that is already roughly right.

MATLAB's Antenna Toolbox ships roughly sixty parameterised elements, each with a `design()`
call that takes a frequency and returns a dimensioned object close enough to optimise from.
That catalog, not the solver, is what makes the optimiser useful: an optimiser started from
a good analytic guess converges; one started from nothing burns its budget finding the
resonance.

This repo has the closed-form patch synthesis (`rf_tools/patch_synthesis.py`,
`patch_resonant_frequency_hz` and neighbours) and exactly one named objective built on it —
`optimization/rf_objectives.py`, whose own docstring is candid that it is "one concrete case,
not a speculative menu." Issue #229 records the downstream effect: "the design loop only
reaches the patch-antenna tools; most of what is built is unreachable from it." Issue #211
records the same shortfall on the metamaterial side: no objective function joins a unit-cell
geometry to the Floquet solve, so the optimisers have nothing to optimise.

The charter already names this as step one ("filling the alphabet is step one"). The lesson
from MATLAB is narrower and worth stating precisely: **the catalog entry is not just a
shape, it is a shape plus the closed form that dimensions it.** `designs/element_alphabet.py`
stores measured letters; what makes a letter *usable by an optimiser* is an analytic seed
that gets it to the right neighbourhood before the first solve.

---

## 3. Where the comparison runs the other way

Stated because the question deserves a fair answer, not a flattering one in either
direction. Four things here are better than the commercial default:

- **Conservation checks as a first-class returned margin.** `simulation/conservation_checks.py`
  returns power-balance, passivity and reciprocity margins on every parsed S-parameter
  result, as numbers rather than pass/fail. In a commercial tool passivity checking is
  something you go and ask for, usually on a fitted model, usually after you have already
  believed the result.
- **Provenance on every number.** No commercial tool tells you whether the figure on screen
  was measured, simulated, calculated or assumed. Here it is a hard vocabulary with no path
  from an LLM estimate to a `CALCULATED` tag.
- **Reference cases validated against published physics, with the tolerance justified.**
  `verification/simulator_reference_cases.py` checks the deck-generation, the solve and the
  parser together against results published independently of this codebase, and states
  plainly which cases have actually been executed and which have not.
- **Refusing to invent an unread bound.** `UnreadPhysicalBound`
  (`designs/design_families.py`) raises with a citation to go and read rather than offering
  a plausible formula. That distinction — "no bound exists" versus "a bound exists and we
  have not read it" — has no equivalent in any tool on the list.

---

## 4. What this suggests filing

Nothing here is filed by this document; it is a reading, not a decision.

| Finding | Status | Suggested ticket |
|---|---|---|
| §2.1 pre-solve model-validity checks, starting with NEC2++'s published rules and the already-parsed AGT | **Not ticketed** | New — bug-shaped: `average_power_gain_linear` is currently scoreable as a performance figure |
| §2.2 mesh/discretisation convergence as the error bar on every `SIMULATED` claim | **Not ticketed** | New — feeds #335 |
| §2.3 shared geometry IR as the precondition for a meaningful cross-check | Partly ticketed | Comment on #223 and #507 |
| §2.4 analytic seeds alongside catalog entries | Partly ticketed | Comment on #229 / #211 |
| Installed/platform performance and characteristic mode analysis | **Not ticketed**, no free route identified | Research ticket, if wanted |
