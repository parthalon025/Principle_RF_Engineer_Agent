---
status: accepted
---

# Filter physical realization is a closed-form stepped-impedance extension of `filter_synthesis.py`, not a simulator hand-off or the Qucs-S wizard

Issue #286 named three candidate paths from a `synthesize_filter()` ladder's
ideal henries/farads to an actual microstrip layout, and made picking one the
ticket's own first deliverable rather than a prerequisite tracked elsewhere
(mirroring how #257 named its patent-search-backend question as the
deliverable):

- **(a)** drive `qucsator_rf`'s Filter Synthesis capability headlessly from
  `simulation/qucs.py`;
- **(b)** add microstrip-realization formulas natively to
  `rf_tools/filter_synthesis.py`, sourced from a textbook the way
  `butterworth_g_values`/`chebyshev_g_values` are;
- **(c)** hand a synthesized `FilterNetwork` to a simulator that already
  models real geometry (`simulation/openems.py`/`simulation/hfss.py`).

**Decision: (b).** `rf_tools/filter_synthesis.py` now has a fourth function,
`realize_lowpass_stepped_impedance_microstrip`, implementing the classic
"Hi-Z, Lo-Z" stepped-impedance method (Pozar, "Microwave Engineering" 4th
ed., sec. 8.6) for the lowpass case, backed by new general-purpose microstrip
line synthesis/analysis formulas, originally added to `rf_tools/calculations.py`
and since moved to `rf_tools/microstrip_line.py` (issue #521)
(`microstrip_effective_permittivity`, `microstrip_characteristic_impedance_ohm`,
`microstrip_synthesize_width_m`, Pozar Table 3.2).

## Why not (a)

*In plain terms: Qucs-S's filter wizard is a form you fill in and click a
button on -- there's no way to ask it for the same answer without opening
that window, so this repo's script-only tools can't drive it.*

Investigated at the source level, not just inferred from `docs/tools/qucs.md`'s
existing framing. The wizard is not a feature bolted onto `qucsator_rf` (the
already-CLI-drivable simulation kernel this repo's `simulation/qucs.py`
already shells out to) -- it is a separate Qt binary, `qucsfilter`, built
from `qucs-filter/qucsfilter.h` in the `ra3xdh/qucs_s` source tree. That
header declares exactly one class, `QucsFilter`, and it inherits
`QMainWindow`: every public member is a constructor/destructor, every other
member is a `QComboBox`/`QLineEdit`/`QLabel` GUI widget, and the actual
synthesis routine -- `QString *calculateFilter(struct tFilter *)` -- is
**private**, wired directly to those widgets' values with no accompanying
library target or documented API surface. The man page's own SYNOPSIS is
`qucsfilter [OPTION]...` with no OPTIONS section and no batch/headless mode
documented anywhere: the tool's own description is "by use of an input
dialog the user can create a filter which is then copied into the system-wide
clipboard" for pasting into the schematic editor. There is no scriptable
equivalent to reach for -- the GUI *is* the only interface, all the way down
to the class that does the arithmetic.

## Why not (c)

Handing a synthesized ladder's L/C values to openEMS/HFSS would answer a
different, harder question (how does a *specific hand-drawn* microstrip
geometry behave) rather than the one #286 actually asks (what geometry
*realizes* this ladder in the first place) -- something would still have to
propose the trace widths and lengths for the solver to evaluate, which is
exactly the gap this ticket exists to close. It also swaps a `CALCULATED`
answer, checkable against a closed-form textbook procedure in milliseconds,
for a `SIMULATED` one requiring a full-wave mesh and solve per candidate --
a large cost increase for a first-pass sizing step that Pozar's own
literature says a closed form already handles to about 1% accuracy. Full-wave
verification of a candidate stepped-impedance layout remains valuable and is
explicitly named as a follow-up in the new function's own docstring; it is
the right tool for confirming a design, not for proposing one.

## Why (b), and why it stopped at lowpass

`rf_tools/calculations.py` already had the template this ticket needed:
`patch_effective_permittivity`/`patch_length_extension_m` (originally in
`rf_tools/calculations.py`, since moved to `rf_tools/patch_synthesis.py`,
issue #522) are exactly "a closed-form microstrip-geometry result, sourced
from a named textbook section, with an explicit validity box" -- the same
shape
`butterworth_g_values`/`chebyshev_g_values` already established for the g-value
side of `filter_synthesis.py`. Extending that existing pattern needed no new
module and no new architectural seam, per this repo's own "improve before
adding" convention -- `rf_tools/filter_synthesis.py` already owns the
`FilterNetwork`/`FilterElement` data shape the realization step consumes, so
the new `realize_lowpass_stepped_impedance_microstrip` function and its
`MicrostripLineSection` result type live there, next to what they operate on;
the new `microstrip_effective_permittivity`/`microstrip_characteristic_impedance_ohm`/
`microstrip_synthesize_width_m` primitives it composes originally lived in
`rf_tools/calculations.py`, next to the (differently-scoped) patch formulas
they parallel -- since moved to their own `rf_tools/microstrip_line.py`
(issue #521).

Only the **lowpass** band is realized. The stepped-impedance method itself
has no equivalent for the other three bands: it works by approximating a
short high-impedance line as a series inductor and a short low-impedance
line as a shunt capacitor, and a lowpass ladder's branches are exactly those
two things (`FilterElement.topology` is always `"L"` or `"C"`) and nothing
else. A highpass ladder's branches are the *opposite* pairing (series C,
shunt L) with no comparably standard short-line stand-in; a bandpass/bandstop
ladder's branches are two-element `LC_SERIES`/`LC_PARALLEL` resonators, which
this method was never meant to realize as a single transmission-line section
at all -- those need coupled-line or stub-resonator geometry, a genuinely
different design procedure. This is exactly the scope the issue's own
acceptance criteria asked for ("at least the lowpass case"), stated here so
it is a recorded choice rather than a silent gap: highpass/bandpass/bandstop
physical realization is still open, tracked the same way
`rf_tools/filter_synthesis.py`'s own top-of-file docstring already tracked
"physical realization" in general before this ticket.

Two published worked examples of this exact stepped-impedance procedure
(Bostic & Dittman, "Designing Microstrip ISM Low-pass Filter"; Le, Nguyen &
Truong, "Stepped-impedance Lowpass Filter") were checked by hand against the
new formulas before trusting them -- both restate Pozar's own
`beta*l = g*R0/Z_high` (series)/`beta*l = g*Z_low/R0` (shunt) pair verbatim,
and the implementation's own output matches Bostic & Dittman's 5th-order
Butterworth table (`tests/test_filter_synthesis.py`) to within that table's
own rounding.

## Consequences

- **Provenance is `CALCULATED`**, per the acceptance criteria: every value
  the new function returns is deterministic textbook arithmetic on the
  caller's inputs, matching `synthesize_filter_prototype`'s own tagging, not
  `SIMULATED` (which would only apply to path (a)/(c)).
- **A new MCP/agent tool**,
  `realize_lowpass_stepped_impedance_microstrip_filter`, composes
  `synthesize_filter` and the new realization function in one call; its
  docstring states the method and its limits (short-line approximation,
  quasi-static/non-dispersive `eps_eff`, no discontinuity reactance at width
  steps), matching `synthesize_filter_prototype`'s own disclosure of what its
  ideal lumped-element result does not cover.
- **openEMS/HFSS full-wave verification of a stepped-impedance candidate is
  still open** -- the new function proposes a layout; nothing here confirms
  one against a mesh yet. That is future work, not a gap in this decision.
- **Highpass/bandpass/bandstop physical realization is still open** (see
  above) -- a future ticket, not blocked on anything this one introduces.
