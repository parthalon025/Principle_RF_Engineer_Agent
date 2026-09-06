---
status: accepted
---

# The patent's seven examples are candidate solution architectures, scored per requirement

US12089385B2 describes seven worked examples. Ticket #107 charted all seven
into the design-family registry, splitting them by simulation tier rather
than by shape. Ticket #108 then researched whether each could actually be
built here, and recorded a disposition table: **3, 6 and 7 printable today;
1 and 2 excluded on process; 4 excluded as a materials-physics conflict,
"likely permanent"; 5 excluded as a materials-sourcing gap, revisable.**

#108 was careful about the status of that table — *"None of 1/2/4/5 land in
the map's 'Out of scope' section — they're excluded from candidate
selection today with the reason stated, same treatment as #127's
missing-permittivity-data precedent, revisable without redrawing the
destination."* But it still left a **standing, programme-level verdict**
sitting on a map, and ADR-0017 then hardened it into something stronger
than #108 ever claimed: *"the only such examples in the patent (1 and 2)
are already excluded from this programme on fabrication-process grounds."*

Three findings make that untenable.

- **The exclusion rationale was over-generalised.** Examples 1 and 2 are
  excluded because they are **solid 3D ceramic pieces**, which nothing here
  can print. ADR-0017 turned that into "transmissive designs do not exist
  in this programme." Ticket #188 found a printable bandpass frequency-
  selective surface is flat printed conductor with every feature clearing
  the 0.2 mm floor — so the class ADR-0017 believed empty is not.
- **The limits doing the excluding were customer specs, not physics.**
  Ticket #128's bench failed designs against the patent's 0.87–2.00 mm
  thickness as though it were a law, and found *"the plain carbon square
  that 'failed' reaches 100% absorption the moment a customer allows
  3.6 mm."* The same error had already fired once on the band, where
  FIG. 7G's 8.5–10.5 GHz plot axis stood in for a requirement nobody
  stated.
- **#108's own settled half already says fabricability is per-run.**
  It made fabrication a **configured** capability in three independent
  stages — print, cure (gated by whether the part can reach an oven, not by
  the printer's own warmer) and laminate. If "can we make it" is answered
  per configuration, freezing its answer on a map contradicts the same
  ticket that produced it.

**Decision: each of the seven examples is a candidate solution
architecture that the loop scores against a customer requirement. There is
no standing list of selectable and unselectable examples.**

Fabricability is evaluated **per requirement, against the configured
capability**, at scoring time — never fixed in a document. A candidate the
configuration cannot build in this pass is **reported in the ranked output
with its reason attached**, per #127, not deleted from it. Per #117, a
machine-proposed threshold removes a candidate for one pass only; **only a
human-confirmed threshold removes one for good.**

*In plain terms: the seven examples are seven ways of solving a customer's
problem, and the loop's job is to work out which one fits this customer. A
list saying "we don't do those four" answers that question before the
customer has asked it.*

Band, thickness, cell size and host geometry arrive as **customer
requirements**, carrying a threshold and optionally an objective. The only
constants are physics, the machine and the material
(`docs/requirement-derived-thresholds.md`).

An example is **not** a design family. Families are the registry's members
(ADR-0018); an example is a concrete architecture belonging to one, and
several examples can share a family. The simulation-tier split from #107
(Tier A: 1, 2, 3, 6 — one Floquet solve is the whole evaluation; Tier B:
4, 5, 7 — the cell solve only populates a phase lookup) is a cross-cutting
field, unaffected by this decision.

## Considered and rejected

- **Keep the disposition table, restated as per-requirement pruning
  defaults.** Nearly right, and it still leaves the map asserting an answer
  the loop is supposed to compute. The reason #127 gives against silent
  exclusion applies to a written-down one too: *"Silent exclusion is not a
  conservative default; it is the option that makes its own errors
  permanently invisible."* Four dispositions have already been corrected
  once — Example 5's original reason repeated the oven-ceiling mistake
  #105 had already fixed for silver, and Example 6 *"looked disqualifying
  but isn't."*
- **Make each example its own design family.** Collapses two axes that
  #107 and ADR-0018 deliberately separated, and would put seven
  near-duplicate entries in a registry whose members are meant to differ in
  *kind* — an absorber's physical bound is Rozanov's, a steering surface's
  is Gustafsson & Sjöberg's, and #129 found polarisation conversion has no
  published bandwidth bound at all.
- **Drop the research behind the dispositions.** Rejected — it is good
  work and it stays, as scoring input rather than as a gate. "No published
  material combines εr ≈ 100 with real flexibility at microwave frequency"
  is a **Family fallback bracket** miss under ADR-0015, which is exactly
  the machinery for scoring a candidate whose material data does not exist.

## Consequences

- ADR-0017 is amended under ADR-0020 — its Consequences paragraph cited
  this exclusion as the reason no transmissive conflict existed.
- #108's disposition table stops being map content and becomes an expected
  **per-run output**: for a given requirement and a given configured
  capability, which of the seven are reachable, each with its reason.
- Examples 1 and 2 remain unbuildable on today's configured capability — a
  solid 3D ceramic block has no route on a direct-ink-write machine. That
  is now a **verdict a configuration produces**, and it changes by itself
  if a capability is ever added, rather than needing a document edited.
- Example 4 becomes a scored candidate carrying a wide, cited material
  bracket rather than a deletion, and #127's per-run toggle already lets a
  conservative pass exclude bracket-guessed candidates — visibly, with the
  reason listed.
- #129's per-family physical-bound table already assumes this: it assigns
  Rozanov to the absorber (3), Gustafsson & Sjöberg to beam steering
  (4, 5) and AMC-checkerboard backscatter (7), and records that
  polarisation conversion (6) has no bandwidth bound. That table only makes
  sense if 4, 5, 6 and 7 are live.
- The map's **Not yet specified** entry "how the other six patent examples
  get charted" gains urgency: charting them is now required for the loop to
  score them, not optional enrichment.
- This is a plan-only decision (issue #104's map is explicitly plan-only);
  no code changes accompany it.
