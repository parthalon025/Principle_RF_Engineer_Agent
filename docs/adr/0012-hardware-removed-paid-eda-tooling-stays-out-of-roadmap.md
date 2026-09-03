---
status: accepted
---

# Physical-instrument control is removed from the codebase; paid EDA tooling stays as working code but leaves the roadmap's primary path

`/grill-with-docs` on the continuous requirement → prototype → external-test
→ iterate loop (see ADR-0013/ADR-0014 for the rest of that session's
decisions) settled the scope of two different things this project had been
carrying as "optional": physical lab instruments, and paid EDA software.
They turned out to need different treatment.

**Physical-instrument control (`measurement/` package) is deleted, not left
dormant.** `measurement/vna.py`, `spectrum_analyzer.py`,
`signal_generator.py`, `power_meter.py`, and `base.py`'s shared SCPI/VISA
instrument-actuation approval gate go, along with their agent/MCP tool
wiring, `policies/tool_policy.yaml`'s instrument-approval category,
`.env.example`'s VISA/SCPI block, and the six associated test files
(`test_vna.py`, `test_measurement_base.py`, `test_spectrum_analyzer.py`,
`test_signal_generator.py`, `test_power_meter.py`, `test_pyvisa_sim.py`).
Considered and rejected: leaving this code in place but unused ("dormant"),
the same treatment paid EDA tooling gets below. Rejected because hardware
control is categorically different from a licensed software adapter — there
is no lab instrument this system could reach even if the code stayed, so an
unused instrument-actuation gate is not a dormant capability waiting for its
owner to come back to it, it is dead weight describing a capability that
does not exist for this project right now. "Hardware is out of scope for
now" is explicitly a scope decision for the present, not a permanent one; if
physical measurement control re-enters scope later, it is rebuilt then,
against whatever this system's shape is at that point, rather than carried
forward speculatively.

**Paid EDA tooling (Ansys AEDT/HFSS + PyAEDT, Keysight ADS) is removed from
the roadmap narrative only — the code stays.** `docs/BUILD_PLAN.md` Phase 8,
`docs/ROADMAP.md` 0.5, and README's development-order/optional-requirements
framing stop presenting a paid license as part of the path to a working,
verified design; the free/OSS stack (NEC2++, openEMS+CSXCAD, OpenParEM,
Elmer, Qucs-S/qucsator_rf, ngspice, Xyce, Palace, gprMax, MEEP,
KiCad+kicad-python, FreeCAD, gerber2ems, gerbv) becomes the complete,
explicit default path end to end, with no paid-tool step required to reach
it. `simulation/hfss.py` itself — a real, working `HfssSimulator` built
against PyAEDT, gated by `check_hfss_workstation_confinement` — is left
exactly where it is, along with its `.env.example`/`pyproject.toml` config
and `test_hfss.py`. Unlike the hardware case above, there is a real,
functioning system here that someone holding an AEDT license could use
today; deleting tested, working code to make a point about the *roadmap's*
narrative would be destroying a capability, not retiring an assumption. The
distinction is exactly "is this something we could still reach" (yes, for
HFSS, given the license; no, for a lab instrument this system was never
actually connected to).

**Also corrected in this pass:** `CONTEXT.md` contradicted itself about
HFSS's own status — one passage said HFSS was "an intentionally
unimplemented boundary pending a licensed AEDT host," another said "HFSS/ADS
adapters are now implemented." The second is accurate (`simulation/hfss.py`
is real code); the first was stale and is corrected as part of this
documentation pass, independent of the roadmap-narrative change above.

## Consequences

- `orchestration/design_loop.py`'s `MEASUREMENT` step no longer has a
  live-instrument branch to fall back to — see ADR-0013 for what replaces
  it. This is not an independent design choice; it falls directly out of
  `measurement/vna.py` no longer existing.
- Anyone wanting physical-instrument control back needs to rebuild
  `measurement/`'s adapters and `base.py`'s actuation gate from scratch
  (or from this ADR's git history) — nothing about this decision makes that
  harder than it would otherwise be, but nothing preserves it as a shortcut
  either.
- `simulation/hfss.py` remains real, callable, tested code with no roadmap
  phase pointing at it — a future contributor with an AEDT license can use
  it today; a future contributor without one is not misled into thinking
  they need it to reach a working system.
