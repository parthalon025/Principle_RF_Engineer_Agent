# A research pass over all twelve open grilling tickets

**Date:** 2026-09-05
**Scope:** every open `wayfinder:grilling` issue — [#111](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/111), [#112](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/112), [#115](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/115), [#116](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/116), [#124](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/124), [#125](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/125), [#129](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/129), [#133](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/133), [#150](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/150), [#151](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/151), [#152](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/152), [#153](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/153).
**Method:** 48 research agents across four passes — code ground-truth, primary-source hunt, external prior art, and existing-implementation search. Nothing here closes a ticket; every entry is material for the human who will.

---

## Bottom line up front

**The most valuable output of this pass is not new evidence. It is that eleven
load-bearing premises turned out to be wrong**, and several tickets are asking
a question the code or the sources have already answered differently.

Three findings are worth reading before anything else:

1. **Two of this repo's own documents contradict each other about whether the
   reproduction anchor has a ground plane** — and it decides the fixture, the
   cost, and whether a physical bound applies at all. §1.
2. **`8.5–10.5 GHz` is a plot axis, not a requirement**, and it has propagated
   into three documents and every headroom number on #129. §2.
3. **Homogenisation is invalid near resonance for extracting material
   parameters, but remains valid for predicting scattering** — which is
   exactly and only what #111's fast tier needs. §3.

---

## 1. Is Example 3 ground-backed? Two documents, opposite answers

| Document | Says | Evidence given |
|---|---|---|
| [`seven-example-design-unknowns.md`](./seven-example-design-unknowns.md):184–186, 202, 345 | **Two-port, Floquet both faces, no ground plane** | "FIG. 7G plots a non-zero Transmission trace, so the structure is not metal-backed" |
| [`absorber-scoring-conventions.md`](./absorber-scoring-conventions.md):14, 48, 62, 349 | **Ground-backed**, so `A = 1 − \|S₁₁\|²` | "`LITERATURE-SUPPORTED`, and unanimous" |

**In plain terms.** If there is solid metal behind an absorber, nothing gets
through, so measuring what bounces back tells you everything. If there is not,
you must also measure what passes through — a different, more expensive
measurement needing two ports instead of one.

**The drawing reading should win.** Landy et al.'s device suppresses
transmission with a cut wire, not a ground plane, and reports both reflection
and transmission; a non-zero transmission trace in FIG. 7G is consistent with
that and inconsistent with a metal backing. This repo's standing rule — *read
the drawings, not just the prose* — has settled two such disputes already.

**How it happened, most likely.** ADR-0017 makes skins *this project builds*
print their own reflector, so the programme's own designs genuinely are
one-port. The scoring document applied that default to the **reproduction
anchor**, which is somebody else's device. A category error, not a slip.

**What it changes:**

- **#133** concluded a normal-incidence reflection measurement is a one-port
  `.s1p` that `rf_tools/touchstone.py` parses unmodified, "no new format
  needed," and priced a chamber at US$2,300–4,800 on that basis. Two-port
  changes the fixture, the format question, and the quote.
- **#129** — Rozanov's bound requires a perfectly reflecting backing. Now
  confirmed from the original, verbatim: *"overlying a perfectly reflecting
  plane and illuminated at normal incidence."* See
  [`rozanov-bound-primary-source.md`](./rozanov-bound-primary-source.md).
- **#110** (closed) built absorber scoring on `A = 1 − |S₁₁|²` being "the form
  the loop needs."

---

## 2. `8.5–10.5 GHz` is a plot axis being used as a requirement

The patent's own prose, retrieved verbatim this pass:

> "The plot of FIG. 7G shows simulated scattering performance of the EM skin
> 700 over **select frequencies ranging from 8.5-10.5×10⁹ Hz (a sub-band of
> the X-band)**." — US12089385B2, Example 3

That describes **what was plotted**. It does not say the device is required to
absorb across it. But the figure now appears as a specification in:

- `absorber-scoring-conventions.md:374` — *"The requirement is '≥90% absorption across 8.5–10.5 GHz'"*
- `absorber-scoring-conventions.md:189, 376, 390`
- `HANDOFF-metamaterial-printing-grill.md:73` — filed in a band column
- `absorber-thickness-bandwidth-bound.md:39, 301, 304, 774–775` — **every headroom number**

**Rozanov's bound is linear in Δλ**, so every one of those figures scales
one-for-one with a number that may be an axis label.

**This is the second instance of a failure mode this repo has already
documented.** #130 caught a ±22.5° phase budget borrowed from beam-forming
that silently encoded a 14.2 dB requirement nobody stated. The rule that came
out of it applies unchanged: *a number read off a plot is not a requirement.*

---

## 3. Per-ticket refinements

### #111 — two-tier EM modelling

**The premise survives, but only in a narrower form than stated.**
Homogenisation genuinely fails near resonance — which is exactly where an
absorber works. Alù (*Phys. Rev. B* 84, 075153, 2011; [arXiv:1012.1351](https://arxiv.org/abs/1012.1351))
finds NRW-style inversion "often provides constitutive parameters with
nonphysical frequency dispersion, in particular near the inclusion
resonances," and that this happens **even for electrically small cells**,
because the wavelength *inside the array* — not in free space — shrinks to the
lattice period right at resonance.

**But Alù's conclusion rescues the fast tier**: retrieved parameters remain
usable for predicting reflection and transmission of the finite structure, and
"should not be used to deduce the permittivity and permeability of the array."

**In plain terms.** The cheap model can still tell you *how much bounces off
and how much gets through* — which is all an absorber score needs. What it
cannot do is tell you what the material "is." So the fast tier must be framed
as a **scattering surrogate**, never as a material-parameter extractor; the
moment a retrieved ε_eff is fed into a mixing rule or compared between
materials, it is being used invalidly.

Supporting: Koschny, Markos, Smith & Soukoulis (*Phys. Rev. E* 68, 065602(R),
2003; [arXiv:cond-mat/0307361](https://arxiv.org/abs/cond-mat/0307361)) show
antiresonance and negative imaginary permittivity near resonance are
**intrinsic to finite periodicity, not numerical artefacts**. Menzel et al.
([arXiv:0908.2393](https://arxiv.org/abs/0908.2393)) give a quantitative
criterion — a wavelength-to-period ratio for ≤5% retrieval error near
resonance — which is the error budget this ticket needs.

**Solver reality, from the implementation sweep:** openEMS has **no native
Floquet/periodic boundary**, only PMC planes (normal incidence with symmetry).
Meep *is already a dependency*, ships `meep.adjoint`, and `simulation/meep.py`
currently sets no Bloch `k_point` at all — extending it beats adding a solver.
`EMerge` (native `FloquetPort`/`PeriodicCell`, last commit 2026-08-23, 279
stars) is the alternative.

### #112 — weakest-link provenance

**Four premise problems.** (a) The ticket presumes score inputs carry
distinguishable provenance rungs a weakest-link rule could read; they do not —
`success_score()` receives `actual_value` as an opaque number and captures
nothing about its origin. (b) **No total order over the eight rungs exists
anywhere in the code.** `knowledge/provenance.py`'s rank table covers three of
them plus `INTERNAL_HISTORY`, which is not in CONTEXT.md's ladder at all.
`min()` over an incomplete order is undefined. (c) The ticket treats
weakest-link as new — `solver.py` already ships it as
`convergence_rule: "worst_of_scored_steps"`, explicitly rejecting best-of and
mean-of for the same reasoning. (d) **Weakest-link is blind to sensitivity**:
an `ASSUMED` input the answer barely depends on and one that single-handedly
decides it get an identical tag.

**Prior art contradicts the obvious answer.** NASA-STD-7009B **explicitly
forbids** collapsing orthogonal credibility factors into one figure —
precisely to prevent the failure the ticket names, where one low factor drags
every candidate to a shared floor and ranking stops discriminating. GRADE does
use a real weakest-link rule ("the lowest rating among critical outcomes
generally provides an upper limit") but grades one body of evidence rather
than ranking rivals. Provenance semirings (Green, Karvounarakis & Tannen,
PODS 2007) validate weakest-link for AND-composition, which score inputs
genuinely are.

**Two traps flagged:** GUM's quadrature combination presupposes every
contributor is a standard uncertainty of the *same* quantity in *one*
equation. Dempster–Shafer exists to reconcile conflicting readings of the same
proposition. Neither is this problem.

**Converged recommendation:** carry a profile; weakest-link at most as one
derived summary column, never the sole ranking key; treat a score as a dated
snapshot re-issued by explicit recomputation.

### #115 — the feature floor

`NanoComp/imageruler` (MIT, last commit 2026-08-01, real tests, algorithm
published in *JOSA B* 42, A161–A176) measures minimum solid **and** void
feature size by morphological opening/closing plus binary search. **Adopt it**
for the check. Caveat: it measures pixels, so the rasterisation must be fine
enough that pixel size is not itself the accuracy limit.

Premises to re-examine: whether a single "50 µm figure" about the NOVA exists
at all (the ticket's first question assumes one does, needing disambiguation
between feature resolution, placement accuracy and layer-thickness control);
and whether `R = 3T` and IPC-2223's 6× are two competing *rules* or the same
strain formula at two assumed strain limits — if the latter, "which rule
governs" is the wrong question and picking either silently encodes an
unstated strain limit.

### #116 / #142 — the reference curve and the 20% disagreement

**The leading hypothesis is dead by arithmetic.** The patent states its own
simulation inputs verbatim: *"a 0.87 mm-thick absorber metamaterial layer
using FR4 dielectric layer of permittivity of 4.8 and loss tangent of 0.017."*
Resonant frequency scales roughly as 1/√ε_eff, so the observed 11.5/9.2 = 1.25
ratio needs an effective-permittivity ratio of 1.5625. FR4's **entire**
documented X-band spread (≈3.8–5.5) gives at most 1.447 → a 20.3% shift under
an unrealistic 100%-field-in-substrate assumption; a realistic 4.8-vs-4.3
comparison gives **5.7%**. Not enough.

**Also ruled out:** misattribution or redrawing from another example — the
FIG. 7G caption ties its assumptions explicitly to EM skin 700.
**Also ruled out:** measurement-versus-simulation noise — Landy's own
simulated and measured peaks agree to 0.2% (11.48 vs 11.5 GHz).

**Genuine absence, routes documented:** no figure-generation methodology
appears anywhere in the patent for Example 3 — no solver, boundary condition,
periodicity, mesh or port setup. Searched the full text via FreePatentsOnline
for "boundary", "periodic", "Floquet", "infinite array", "CST", "HFSS",
"solver"; none appear near Example 3.

**A method problem #110 and #168 should know about.** FSV was chosen over RMS
error specifically because it would not over-penalise this frequency
disagreement, described as "a small resonance-frequency shift." **Landy's
resonance is 4% wide (FWHM), so a ~20% shift is roughly five linewidths** —
the curves barely overlap, and FSV may report near-total disagreement just as
RMS would. The stated reason for the choice needs re-testing.

**Also:** Landy's stack is FR4 / adhesive / FR4 / adhesive / FR4, not the
homogeneous 0.72 mm FR4 at εr 4.8 a reproduction would model.
**No FSV implementation exists in any language** — and IEEE's own FSV
committee page says no reference implementation ships with the standard.
A properly established absence; #168 is building something genuinely absent.

### #124 — material search under the ARCHITECTURE gate

**The question largely dissolves on reading the code.** `_handle_architecture`
(`design_loop.py:421–435`) requires only `{decision, rationale, design_family}`
— **there is no material or substrate field in the ARCHITECTURE schema at
all**, so material commitment is not gated there. Meanwhile `eps_r` is a
*required* ANALYSIS field and required again at OPTIMIZATION, both ungated.
**An overnight run can already vary material; it does so every run.**

Two citation errors to fix: `design_loop.py:136` is the `ARCHITECTURE` enum
member, not `GATED_STEPS` (that is lines 160–162) — **and the same wrong
citation appears in the map, #104**. And the ticket quotes ADR-0014's
*pre-correction* wording including CORRELATION in the ungated span; the live
ADR says ANALYSIS/SIMULATION/OPTIMIZATION and documents the removal explicitly.

**Prior art:** Set-Based Concurrent Engineering (Ward, Sobek, Liker &
Cristiano) is the structural match — keep alternatives alive in parallel,
narrow gradually, and let the human review *be* the narrowing act.

### #125 — the morning handover

**One-line prerequisite before anything else.** `tooling.py:223` hardcodes
`"alternatives": []` regardless of what the step carried. A comment claims
`decision_records.alternatives` "already stores rejected options but is
write-only" — on this path it is unconditionally **empty**. No proposed ledger
can read back what was considered until that line changes.

**Prior art.** I-PASS (Starmer et al., 9 hospitals, 10,740 admissions) shows a
mandated structure with an explicit read-back beats a free-form dump for
exactly this night-shift-to-morning-shift problem. EEMUA 191 / ISA-18.2 give
real ceilings on what a human can process — but transfer as a *principle*, not
a number, and ISA-18.2's own 2016 retreat from a fixed per-day KPI warns
against picking a magic top-N. ClusterFuzz supplies the deduplication
discipline; BuildSheriff (ICSE 2022) the diff-against-last-run shape.

**The cautionary precedent is A-Lab** — 17 days unattended, and independent
reanalysis found its self-report was a judgment the machine got wrong that
nobody could catch *because of the shape of the artifact it produced*. For
calibration on how often this goes wrong: independent evaluation of Sakana's
AI Scientist found **4 of 7 manuscripts (57%) contained incorrect or
hallucinated numerical results, and 5 of 12 experiments (42%) failed from
coding errors**.

### #129 — the bandwidth-versus-thickness bound

Now settled from the original — see
[`rozanov-bound-primary-source.md`](./rozanov-bound-primary-source.md).
Headline: the bound holds at **normal incidence, metal-backed, linear and
causal**; ultimate `d/Δλ` at −10 dB is **1/13.9** for the best possible
non-magnetic narrow-band absorber against **1/3.2** for a plain Dallenbach
screen; and **magnetic materials are the only way to move the limit**.

Three ticket premises need revising: the band input (§2), the 0.87 mm
thickness (superseded by #116's drawing measurement), and applicability to an
unbacked anchor (§1). Plus two smaller ones: **REQUIREMENTS is not an
advanceable loop step** (`design_loop.py:751–759`), so nothing can "live" at
it; and the solver already *has* a stopping condition
(`solver.py:306–307`, `1139–1143`), so "no principled stopping condition at
all" overstates the gap.

**Build, don't reuse:** no maintained standalone implementation of Rozanov,
Chu, Bode-Fano or Gustafsson–Sjöberg bounds as a pre-simulation feasibility
function exists. One READ-only borrow: `sparameterviewer`'s Bode-Fano integral
(MIT, active) — but it computes from a measured sweep, not from a spec.

### #133 — provenance ceiling with no instruments

Beyond §1's port-count consequence: **`SIMULATED` does not currently mean
*validated* simulation in this repo** — CONTEXT.md's "Reference case" entry
says passing a reference case is what would earn that word, and no such corpus
exists. That is the honest ceiling today.

**Adopt** `uncertainties` and `SALib` (both small, pure-Python, no paid
solver) for propagation and sensitivity rather than hand-rolling. OpenTURNS if
calibration becomes relevant; `mogp-emulator` is READ-only (unmaintained ~3
years).

**A market-wide finding that strengthens the ticket:** the "publishes
attenuation only" gap is not Laird-specific. MAST Technologies' five flexible-
absorber families and ARC/Hexcel's foam lines do the same. **No commercial
flexible absorber checked can be simulated from its datasheet** — vendors
publish what a purchaser needs (dB of attenuation), never the four numbers
(ε′, ε″, µ′, µ″ at the frequency of use) a model needs.

### #150 — cross-run simulator-trust ledger

**"Thrown away when that loop ends" is false.** `_flush_decisions` persists
correlation results durably to `engineering_results` at every
REDESIGN_DECISION boundary. The real gap is sharper: `design_family` is
required in `step_input` but **`_flush_target_for` drops it when persisting**,
and `decision_records` has no such column — so the proposed grouping key does
not exist as queryable data. (Filed separately as #167.)

**The literature's own author wrote the warning.** Kennedy & O'Hagan (*JRSS-B*
2001) formalise exactly this proposal as a model-discrepancy term. Then
**Brynjarsdóttir & O'Hagan (2014), by one of the same authors**, proved such a
correction silently degrades to meaningless outside the region it was fitted
on, **with no built-in signal that it has**. ASME V&V 20 independently
declines to certify accuracy anywhere but the validated point. Koziel's
antenna-surrogate "domain confinement" is the RF-native precedent and never
transfers a correction across geometry families.

**In plain terms.** *"Our simulator runs 3% high" learned on one shape can be
quietly worthless on the next one, and nothing tells you.* Any ledger needs a
hard validity boundary, not a soft one.

### #151 — geometry-result cache and whether it needs an ADR

The ADR test the literature converges on is **reversibility**, not size:
Nygard's "affects interfaces or construction techniques," sharpened by AWS's
one-way/two-way door. The cache *mechanism* is a two-way door; **the boundary
of what is cacheable at all** is not.

**Snakemake is the closest real precedent** — it keys cached results on a hash
over code, parameters, **software stack** and inputs, so a solver version bump
invalidates by default. Direct consequence: `geometry_signature` **must**
include the solver version, or a cached result from an older solver becomes a
silently wrong answer.

Correction: the boundary language the ticket's comment attributes to ADR-0018
is not in ADR-0018 — that ADR is about design families being an open
interface, and contains no occurrence of "cache", "reuse", "success_score" or
"geometry_signature". It is #151's own body recommendation cited back as
settled. Separately, `design_family` **is** already a required ARCHITECTURE
field, added by #161 explicitly as a grouping key for #150 and #151.

**Unreachable:** `F:\data\pipeline` (CorpusIndex) — a Windows drive on the
author's machine. Repo-wide grep for `CorpusIndex`, `DesignHistoryIndex` and
`geometry_signature` found nothing.

### #152 — pub/sub seam at the persistence boundary

**Three premises are wrong, and they dissolve the ticket.** Only **one** flush
moment exists, not the two named — a CORRELATION decision is batched into the
same REDESIGN_DECISION flush, not saved separately. ADR-0015's material
library takes its own connection from a human-entry path and **never routes
through this boundary**. ADR-0018 is a design-family registry, **not** the
Element/Coding-Alphabet library the ticket calls it, and no such library exists.
**Zero of the named candidate consumers exist in code.**

**Verified absence by grep:** no pub/sub, event-bus, hook-registry, outbox or
`LISTEN/NOTIFY` machinery anywhere in the repo's Python or SQL.

**The Rule of Three settles it** — Fowler, attributing to Don Roberts, puts
the trigger at the *third* occurrence. This is occurrence one. And **the
outbox pattern is the clearest trap in this whole pass**: it solves atomic
dual-write across a distributed broker, whereas `tooling.py` writes to one
database in one transaction. The objective test the literature would apply is
change-coupling analysis — but it is a lagging indicator needing history that
does not yet exist.

**One crux the ticket states as free but is not:** "no subscriber may block or
alter the flush" sits in direct tension with ADR-0011's fail-loud,
all-or-nothing transaction guarantee.

### #153 — finished design into searchable precedent

**The "automatic vs human-offered" framing is the wrong axis.** Case-base
maintenance research gives a better test: **competence contribution**. Smyth &
Keane's *swamping problem* — "larger case-bases mean more expensive retrieval
stages" — and their competence footprint rank cases pivotal / spanning /
support / **auxiliary**, where auxiliary means already fully covered by what
exists. Zhu & Yang flip this to the *addition* side, exactly this ticket's
decision point, and can place a lower bound on competence that deletion-based
policies cannot.

**In plain terms.** *Keep every finished design and the search box gets worse:
twenty near-identical accepted patch antennas bury the one unusual design
somebody needed. The test is not "was it accepted" or "was it good" — it is
"does this cover ground nothing else covers."*

Aamodt & Plaza (*AI Communications* 7(1):39–59, 1994, DOI
10.3233/AIC-1994-7104) supply the trigger and the content: RETAIN fires
automatically at the post-Revise moment (`accept_design` here), and keeps the
*reasoning path* and the *failures*, not just the winner — "an explanation or
another form of justification of why a solution is a solution to the problem
may also be marked for inclusion." **Their retain-everything default does not
transfer**: in CBR the case base's only consumer is the system, and a bad case
is corrected by the next Revise cycle. Here the consumer is a human, there is
no repair loop, and per ADR-0002 a document can only be SUPERSEDED by an
explicit human act.

**Implementation facts:** `ingest_document()` takes a **filesystem path**
only — no dict/string entry point — so a design record must be materialised as
a real file first. And `license`/`classification` are mandatory, non-defaulted
arguments (ADR-0001) with no obvious source on a `designs` row.

---

## 4. Method, and what this pass did not do

**48 agents in four passes.** Code ground-truth (Sonnet, reading the actual
files); primary-source hunt (Sonnet, multi-route); external prior art
(Sonnet); existing implementations (Sonnet). Scope and the hardest synthesis
ran on Opus.

**Two honest defects in the run itself:**

1. One prior-art agent (#153) returned literal placeholder text — `"test"` in
   every field — satisfying the schema without doing the work. Caught on
   review and re-run on Opus, which produced the §3 material above. **A
   schema-valid result is not evidence of a completed task.**
2. A key-name bug meant most source-hunt agents were told their assigned route
   was `"undefined"`. Their substantive briefs were intact and distinct, and
   findings counts stayed healthy (4–9 each), but the deliberate blindness
   between routes was weaker than designed — so cross-route corroboration in
   this pass is worth slightly less than it looks.

**Not done:** nothing here is a decision, and no ticket was closed. Four
`#111` source routes were still running at write-up and are not reflected.
MDPI, IEEE Xplore, Wiley, ScienceDirect and incose.org remained blocked
throughout; **JOSA B / Optica is a newly-found block** (Smith & Pendry's 2006
field-averaging paper was not read in full) and belongs in `RUNNING-LISTS.md` §1.
