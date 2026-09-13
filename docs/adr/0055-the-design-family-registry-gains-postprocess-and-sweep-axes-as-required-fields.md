---
status: accepted
---

# The design-family registry gains `postprocess` and `sweep_axes` as required fields

Split out from [ADR-0050](0050-the-registry-carries-post-processing-and-sweep-axes-and-grows-a-transmissive-and-a-shielding-family.md)
for readability; see that file for the shared context (issues #453/#455) and
the four-plug-in family test ([ADR-0027](superseded/0027-the-alphabet-admits-only-printed-letters-and-identity-includes-the-process.md) §5) this decision applies.

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

## Decision

**The registry gains the two ADR-0045 fields it was missing — `postprocess` and
`sweep_axes`, both required with no default.**

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

## Considered and rejected

- **Narrowing ADR-0045's Consequences to three fields** — concluding that
  `analysis_model` *is* the post-processing kind and that the registry needs
  only `sweep_axes`. This was #455's own suggested alternative and it was taken
  seriously, because it is the cheaper answer and would have retired a stale
  "must" instead of growing a dataclass. **Rejected on the three facts above**,
  of which the second is decisive: `ABSORBER_TRANSMISSIVE`
  carries both a closed form and post-solver power arithmetic simultaneously,
  which one field cannot hold.

- **Defaulting `sweep_axes` to `(frequency,)` and `postprocess` to "none".**
  Rejected: both are the modal value and both are silently wrong for the
  families that matter most — the tunable one for the first, the two absorber
  families for the second. `port_count` is allowed a default only because a
  wrong one is caught by a cross-check; ADR-0045 states that no such cross-check
  can exist for these two.

- **Promoting `postprocess` to a fifth plug-in in ADR-0027 §5's family test.**
  It is arguably one: a family needing different arithmetic on the same solver's
  output is doing a different job. Rejected **here** as out of scope, not on the
  merits — ADR-0027 is another decision's document, its §5 was corrected only
  days before this one, and ADR-0056/ADR-0057's membership decisions both rest
  on `analysis_model`, which §5 already names. Flagged for that ADR's owner
  under #453/#455 rather than settled by a file this work does not own.

## Consequences

- **`DesignFamily` now has nine required constructor arguments, and the
  registry has eight members** (once ADR-0056 and ADR-0057 land their two new
  families). Any code constructing a family must supply `postprocess` and
  `sweep_axes`; `tests/test_physical_bounds.py`'s two invariant fixtures were
  updated accordingly. Nothing in `orchestration/`, `rf_tools/` or
  `simulation/` constructs one, so no runtime call site changed.

- **#455 is answered and can be closed against this ADR.** ADR-0045's "must"
  stands at four fields and all four are now shipped. The gap that ADR named and
  no locus in the tree acknowledged is closed, and the reasoning for keeping
  `analysis_model` and `postprocess` apart is recorded on the dataclass itself
  rather than only here.

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

- **Not decided here:** whether `postprocess` belongs in ADR-0027 §5's family
  test as a fifth plug-in (ADR-0050 flags this as open too).
