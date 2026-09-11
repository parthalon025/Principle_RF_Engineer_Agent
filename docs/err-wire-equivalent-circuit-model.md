# A closed-form equivalent circuit for the patent's own ERR-over-wire absorber

**Research date:** 2026-09-11
**Ticket:** `docs/RUNNING-LISTS.md` §5, research-agenda item 7 — "Closed-form
equivalent-circuit models for the patent's own shapes... nothing covers
I-shaped ring resonators." Builds on
[`docs/ishape-interior-tuning.md`](./ishape-interior-tuning.md) (the element's
geometry) and
[`docs/example3-frequency-discrepancy.md`](./example3-frequency-discrepancy.md)
(the unresolved 20% patent-vs-Landy frequency gap).
**Question:** Is there a published closed-form/semi-analytical equivalent
circuit for US12089385B2 Example 3's actual topology — an electric ring
resonator (ERR) coupled to a separate cut-wire resonator, not a plain
electric-LC (ELC) resonator? If not, derive one from coupled two-RLC-branch
circuit theory and check it against Landy et al.'s measured 11.5 GHz and the
patent's own ~9.2 GHz.

Provenance tags follow `CONTEXT.md`'s Provenance ladder — `CALCULATED`,
`LITERATURE-SUPPORTED`, `INFERRED`, `ASSUMED`, never `MEASURED` unless a cited
paper reports a bench result. Every source below was retrieved and read in
this session; nothing is cited from memory.

---

## Bottom line up front

**No published closed form covers this exact topology.** Three independent
checks confirm it: this repo's own equivalent-circuit survey already says so
in as many words (§1); the one paper whose title promises "CW metamaterial
absorbers" is about plain cut-wire *pairs*, has no ERR, and is unreachable in
full text; a second, "wire-based metamaterial absorber" paper is the same
shape again, also unreachable. Nobody has published an equivalent circuit for
an electric ring resonator coupled to a separate wire resonator.

**One is derived here**, built from a citable formula for one branch, a
first-principles network model for how the two branches combine, and a
single-point calibration against Landy et al.'s own measured geometry. It is
a genuinely new closed form, not a citation, and every place it rests on an
assumption rather than a source says so.

**What the model gets right, checked against data it was not fit to.**
Calibrated on nothing but Landy's 11.48 GHz simulated peak, the model's
predicted sensitivity to spacer thickness — **−0.099** in
`d(ln f)/d(ln h)` — lands within 27% of, and the same sign as, Landy's own
**independently reported** −0.135 (from a *different*, three-variable
comparison the model was never shown). That is the honest validation this
document offers: not a perfect fit, a plausibility check the model passed.

**What it cannot do: close the patent-vs-Landy gap, and it says why not.**
Pushing the model's only two free levers — sheet capacitance (interpretable
as an embedding-permittivity change) and spacer thickness — neither reaches
9.2 GHz cleanly. The capacitance route needs a **1.70×** increase, implying
an embedding permittivity around **εr ≈ 8.9** — not FR4, and a *larger* shift
than the **εr ≈ 6.5–6.9** the simpler single-resonator scaling in
`example3-frequency-discrepancy.md` already found insufficient. This is an
**independent corroboration, by a different method, of an existing
conclusion**, not a new explanation. The spacer route does not reach 9.2 GHz
at all inside a physically sensible range. **This closed form is, by
construction, blind to metal thickness** — the one candidate mechanism
`example3-frequency-discrepancy.md` §4.1 flagged with "the right sign,
magnitude unknown" — because the gap-capacitance formula it is built on has
no thickness term. That is a finding, not a gap in effort: it sharpens
*why* a solver is needed, rather than merely restating that one is.

---

## 1. What is already established, and what is genuinely missing

### 1.1 This repo's own survey already answered "does a closed form exist"

`docs/element-library-prior-art.md` §4e surveyed every closed-form
equivalent-circuit source retrieved for this project and built a coverage
table. Quoted verbatim, its bottom row:

> | Shape | Closed-form L/C available? | Source |
> |---|---|---|
> | **I-shaped ring resonator over wire resonator (patent Example 3)** | **NO** | — |

That survey covered patch arrays, strip grids and post arrays (Luukkonen et
al., Marcuvitz), and the absorber-stack transmission-line synthesis for a
*single* FSS layer over a ground plane (Costa, Genovesi, Monorchio & Manara,
arXiv:1211.1902 — already retrieved into this repo and used in
`docs/costa-thin-spacer-correction.md`). None of them is a two-layer,
ground-free ERR-plus-wire stack.

### 1.2 The adjacent closed form this repo already has is for the wrong topology

`docs/ishape-interior-tuning.md` §4.2 already carries
Withayachumnankul, Fumeaux & Abbott's IDC-loaded ELC scaling law
(arXiv:1009.0139), but flags exactly the distinction this document exists to
resolve: their element is a **single** electric-LC resonator — one gap,
electric response only, "essentially poss\[essing\] no magnetic response" in
the authors' own words (quoted below, §2.1) — not the patent's **two
separate, differently-oriented** resonators whose whole design intent, per
the patent's own text (already quoted in that document), is that *"the
electric resonance and magnetic resonance can be tuned to overlap each
other."* Their Eq. (5) scaling law describes how one resonator's own
frequency moves when its own capacitor changes. It says nothing about how
two *different* resonators, on two different layers, combine.

### 1.3 What this document adds

A structural model for **how the ERR branch and the wire branch combine**
(§4.1) plus a citable closed form for the ERR branch's own capacitance
(reused from the same paper, applied correctly this time — §4.2), a
first-principles model for the wire branch (§4.3), and a calibration against
Landy's own measured device (§4.5) that is checked, not merely asserted, by
comparing the model's *predicted* sensitivity against a sensitivity Landy
independently reports (§4.5, and Bottom line above).

---

## 2. The search for an existing closed form, closed out

Three more candidates were checked this session, each retrieved directly
rather than assumed from a title.

**Tao, Landy, Bingham, Zhang, Averitt & Padilla, "A metamaterial absorber
for the terahertz regime: Design, fabrication and characterization," *Opt.
Express* 16(10):7181–7188 (2008), [arXiv:0803.1646](https://arxiv.org/abs/0803.1646).**
Retrieved in full (LaTeX-derived PDF text, 8 pages). This is the THz sibling
of Landy's X-band device — same authors (Landy is a co-author), same
ERR-over-cut-wire topology, scaled up in frequency. It is the single closest
paper in the literature to Example 3's own structure. **It contains no
equivalent circuit, no L, no C, no formula of any kind for either
resonator.** It is a design-and-measurement paper. It does state the design
principle in prose, quoted verbatim because it matters for §3:

> "The magnetic component of light couples to both the center section of the
> electric resonator and the cut wire, thus generating antiparallel currents
> resulting in resonant µ(ω) response. The magnetic response can therefore be
> tuned independently of the electric resonator by changing the geometry of
> the cut wire and the distance between elements. By tuning each of the
> resonances it is possible to approximately match the impedance
> (Z=√(µ/ε)) to free space... and minimize the reflectance at a specific
> frequency."

**Chen, Hou-Tong, "Interference theory of metamaterial perfect absorbers,"
*Opt. Express* 20(7):7165 (2012), [arXiv:1112.5168](https://arxiv.org/abs/1112.5168).**
Retrieved in full (8 pages). This is the paper this repo already knows about
only via Costa's citation network; read directly here for the first time.
**It is not a match either, but for a more interesting reason than absence:
its topology is a single resonator array over a solid ground plane**, not
two coupled resonator layers. Verbatim, its own stated structure:

> "It consists of a cross-resonator array and a ground plane separated by
> d = 10 µm thick polyimide dielectric spacer... Due to the presence of the
> ground plane, the substrate provides the mechanical support only."

Its content is nonetheless the single most important input to §4.1's
structural model, because it is a primary, retrieved source for treating a
metamaterial absorber as **two partially-reflecting sheets linked by
transmission-line multiple reflections**, and because it directly disputes
the "antiparallel currents = magnetic coupling" reading Tao/Landy use,
verbatim:

> "the two layers of metal structure in metamaterial absorbers are linked
> only by multiple reflections with negligible near-field interactions or
> magnetic resonances... the assumed magnetic resonance plays a negligible
> role in the impedance matching of metamaterial absorbers to free space."

This is a real, unresolved tension in the literature between two mechanistic
pictures for the *same class* of device, and it matters directly for how
"the mutual coupling term" the task asked for should be read. See §4.4.

**Wakatsuchi, Paul, Greedy & Christopoulos, "Cut-Wire Metamaterial Design
Based on Simplified Equivalent Circuit Models," *IEEE Trans. Antennas
Propag.* 60(8):3670–3678 (2012), DOI
[10.1109/TAP.2012.2201109](https://doi.org/10.1109/TAP.2012.2201109).**
**STRANDED** — confirmed closed access with **no repository copy anywhere**
(OpenAlex: `is_oa: false`, `any_repository_has_fulltext: false`; same block
pattern this repo's `RUNNING-LISTS.md` §1 already records for IEEE). Its
Crossref-registered abstract, the only text retrievable, is exactly on
point and worth quoting in full because of what it does and does not cover:

> "Effective equivalent circuits are used for the prediction of resonant and
> absorbing behavior of cut-wire-based (CW-based) metamaterials. Firstly, an
> equivalent circuit applicable to electric resonance frequencies of single
> CW metamaterial arrays is considered. Secondly, the equivalent circuit is
> extended for prediction of magnetic resonance frequencies of symmetrically
> paired CW metamaterial arrays and asymmetrically paired CW metamaterial
> arrays. Finally, since the magnetic resonance of the symmetrically paired
> CW arrays is analogous to the resonance of the CW metamaterial absorbers...
> the absorptance peak frequencies of CW metamaterial absorbers are
> estimated. Close agreement is obtained with numerically obtained values,
> the difference being typically 4, 6, 4, and 2% for the single CW,
> symmetrically paired CW, asymmetrically paired CW metamaterials and CW
> metamaterial absorbers, respectively."

This is the closest published equivalent circuit to Example 3's own
"absorber built from a wire resonance" idea, and it is genuinely good — 2%
agreement for CW-based absorbers is a strong result. **But every structure
in it is a plain cut wire or a pair of plain cut wires. There is no ERR, no
electric ring, no second resonator shape anywhere in the abstract.** It
covers the wire branch's own family, not the coupled ERR-plus-wire stack.

**Pang, Cheng, Zhou & Wang, "Analysis and design of wire-based metamaterial
absorbers using equivalent circuit approach," *J. Appl. Phys.*
113:114902 (2013), DOI
[10.1063/1.4795277](https://doi.org/10.1063/1.4795277).**
**STRANDED** — same confirmation, closed access, `any_repository_has_fulltext:
false`. Abstract retrieved via Crossref, quoted in full:

> "Wire-based metamaterial absorbers, as a kind of simple but versatile
> artificial structures, have been widely investigated from microwave to
> optical frequencies. In order to completely understand how the
> constitutive parameters affect the absorption properties, an equivalent
> circuit model is developed in this paper. The analytical, numerical, and
> experimental results show that the absorption frequency is determined by
> the wire length and the spacer electromagnetic parameters, whereas the
> absorption level by the thickness of spacers and losses..."

Same finding: wire-only, no second resonator shape. **Two independent
papers, both unreachable in full text, both confirm the same boundary this
repo's own survey already drew: cut-wire equivalent circuits are published;
ERR-plus-wire equivalent circuits are not.**

**Conclusion of the search.** Five sources checked this session (Tao,
Chen, Wakatsuchi, Pang, plus re-reading Withayachumnankul), on top of the
existing survey in `docs/element-library-prior-art.md`. None covers
Example 3's actual two-resonator, two-layer topology. The gap
`RUNNING-LISTS.md` §5 item 7 names is real, not an artefact of a narrow
first search.

---

## 3. The topology, and the mechanism question a closed form has to take a side on

Per `docs/ishape-interior-tuning.md` §1 (measured off Landy's own figure
files and the patent's FIG. 7E/7F, both already retrieved in this repo)
and the patent's own description, already quoted there:

> "By combining the two different shapes (i.e., electric ring resonator
> (ERR) in the top and wire resonator in the bottom), the electric resonance
> and magnetic resonance can be tuned to overlap each other which results in
> no reflected signal." — US12089385B2, Example 3 description

Two metal layers, separated by a dielectric spacer `h` = 0.72 mm, **with no
ground plane** — established independently in
[`docs/rozanov-bound-primary-source.md`](./rozanov-bound-primary-source.md) §4
and `RUNNING-LISTS.md` corrections 25/26, from the patent's own non-zero
FIG. 7G transmission trace. This is the fact that decides the model's
structure in §4.1: a *ground-backed* absorber closed-form (Costa's,
Chen's original topology) is the wrong shape of network for Example 3, which
is genuinely a **two-port, two-layer** stack.

**Two mechanistic pictures compete in the literature for what links the two
layers**, and this document builds the model to be honest about which one it
assumes:

1. **Near-field magnetic coupling** (Landy/Tao, quoted §2): the E-field
   drives the ERR, the H-field drives antiparallel currents in the ERR's
   central post and the cut wire, and this antiparallel-current loop *is*
   the magnetic resonance. This is a **lumped mutual-inductance** picture —
   the two branches are coupled by a shared magnetic flux, exactly the
   picture a "two RLC branches with a mutual coupling term" model assumes.
2. **Interference / multiple reflections** (Chen, quoted §2): the two
   layers act as two independently-characterisable partially-reflecting
   sheets, linked only by the propagating wave in the spacer between them —
   "negligible near-field interactions or magnetic resonances." This is a
   **distributed transmission-line** picture.

Chen's own paper is explicit that this is a real dispute, not a settled
question, and that it concerns the *ground-backed* topology specifically.
**Nothing retrieved in this session settles which picture is right for the
unbacked, two-layer topology Example 3 actually is.** The model in §4
therefore builds the distributed (Chen-style) coupling into its main
structure, because it is the only one of the two for which a retrieved
primary source already treats a two-metal-layer, no-ground-plane stack
(§4.1), and separately gives the lumped-mutual-inductance alternative in
§4.4 exactly as the task requested, flagged as the *other* live hypothesis
rather than folded into the main result as if the dispute were resolved.

---

## 4. The derivation

### 4.1 Structure: two shunt sheet admittances, cascaded through the spacer

Chen's own multiple-reflection formalism (§2, Eq. 1 in the source) is built
for one resonator sheet over a **short-circuited** transmission line (the
ground plane, reflection coefficient exactly −1). Example 3 has no ground
plane — its second layer is another finite sheet, not a short. The
standard, textbook generalisation (two-port cascaded ABCD matrices for a
loaded transmission line; e.g. Pozar, *Microwave Engineering*, the
conventional reference for this conversion) replaces the short with a
second shunt admittance:

```
M_total = M_Y1 · M_TL(h) · M_Y2

M_Y  = [[1, 0], [Y, 1]]                       (a shunt admittance sheet)
M_TL = [[cos(βh), j·Zc·sin(βh)],
         [j·sin(βh)/Zc, cos(βh)]]              (a dielectric spacer of thickness h)
```

where `Y1(ω)` is the ERR sheet's admittance, `Y2(ω)` the wire sheet's,
`β = k0√εr` the spacer's propagation constant, and `Zc = η0/√εr` its
characteristic impedance. Both faces are air (established §3), so the
network is terminated on both sides in the free-space impedance
`Z0 = η0 ≈ 377 Ω`. Converting the resulting `[A B; C D]` to S-parameters
(standard reciprocal two-port form, Pozar again):

```
S11 = (A + B/Z0 − C·Z0 − D) / (A + B/Z0 + C·Z0 + D)
S21 = 2 / (A + B/Z0 + C·Z0 + D)
```

This is the **coupling term the task asked for, in its distributed form**:
the two branches interact through `βh` — the wave's propagation phase across
the spacer — not through a lumped constant. It is the structural
contribution this document makes: nobody retrieved this session publishes
this exact cascade for this exact topology, but every piece of it (Costa's
shunt-admittance-in-a-transmission-line synthesis for one layer; Chen's
two-layer multiple-reflection picture; the ABCD/S-parameter conversion
itself) is a retrieved, citable, standard result. **Combining them for a
ground-free two-layer stack is this document's own step, `CALCULATED` from
standard network theory, not read off a source that already does it.**

Each `Y(ω)` is modelled as a lossless parallel LC (the "two RLC branches"
the task asked for, minus the R — see §5 for why loss is left out rather
than guessed):

```
Y(ω) = jωC − j/(ωL)
```

### 4.2 The ERR branch's capacitance — a citable closed form, applied correctly

**Withayachumnankul, Fumeaux & Abbott, "Compact electric-LC resonators for
metamaterials," [arXiv:1009.0139](https://arxiv.org/abs/1009.0139);
*Opt. Express* 18(25):25912–25921 (2010).** Retrieved in full this session
(the earlier retrieval behind `docs/ishape-interior-tuning.md` §2.3 only
carried the proportionality, `C₀ ∝ (K(k)/K′(k))·l₀`, not the prefactor —
this session's re-fetch recovers the complete equation). Their Eq. (3),
verbatim:

```
C₀ = εre·10⁻³/(18π) · [K(k)/K′(k)] · l₀      (pF, all lengths in µm)

K(k)/K′(k) = (1/π)·ln[2(1+√k)/(1−√k)]                for 0.707 ≤ k ≤ 1
           = π / ln[2(1+√k′)/(1−√k′)]                 for 0 ≤ k < 0.707

k = tan²[0.25wπ/(w+g)],   k′ = √(1−k²)
```

where `w` is the conductor (strip) width, `g` the gap width, `l₀` the strip
length facing the gap, and `εre` the effective dielectric constant. This is
the standard microstrip-gap capacitance formula (Gupta, Garg, Bahl &
Bhartia, *Microstrip Lines and Slotlines*, cited by Withayachumnankul et al.
as their source), not an invention specific to metamaterials — it is a
citable, general electrostatic result for a coplanar gap between two facing
conductor edges.

**Applying it to the ERR requires one modelling step this document states
plainly rather than hides.** The patent's I-shape ERR (per
`docs/ishape-interior-tuning.md` §1.1) has **two** gaps `G` = 0.6 mm, one in
each side arm, not Withayachumnankul's single central gap. Current driven by
the E-field (along `a₂`, per Landy's stated axis triad) traverses **both**
gaps in series around the loop. `INFERRED`: the loop's total gap
capacitance is therefore two equal gap capacitors in series, `C₀/2`, not
`C₀` itself. This is the one topology-mapping assumption the model leans on
for this branch, and it is flagged here rather than folded silently into a
number.

**Numbers**, using the patent's own stated FR4 constants (`εr` = 4.8, so
`εre = (εr+1)/2 = 2.9`, the same averaging convention already validated
elsewhere in this repo — `docs/element-library-prior-art.md` §4a, Luukkonen
et al.), the FIG. 7F dimensions (`G` = `t` = 0.6 mm), and `l₀ = t` = 0.6 mm
(`INFERRED`: for a plain butt-joint gap between two colinear strips of
width `t`, the facing plate length equals the strip's own width):

```
w = 600 µm, g = 600 µm  →  k = tan²(22.5°) = 0.17157  →  K/K′ = 0.5000
C₀(one gap) = 2.9×10⁻³/(18π) × 0.5000 × 600 = 0.01538 pF = 15.38 fF
C_ERR = C₀/2 (two gaps, series) = 7.69 fF                            CALCULATED
```

### 4.3 The wire branch — the same closed form, a different physical role

No source retrieved this session gives a closed-form capacitance for a
periodic cut-wire array's own end-gap. `INFERRED`: the same coplanar-gap
formula applies, because a cut wire's end and its neighbour's end across the
inter-cell gap are exactly the same electrostatic configuration as a
microstrip gap — two colinear conductor edges of width `w`, separated by a
gap `g`. Using the cut wire's own dimensions (`L` = 1.7 mm as the conductor
width, `H` = 11.8 mm as its length) and the **E-plane** end gap already
established in `docs/ishape-interior-tuning.md` §1.4 (`a₂ − H` = 0.2 mm,
the axis carrying the field, per Landy's Fig. 1(c) axis triad):

```
w = l₀ = 1700 µm, g = 200 µm  →  k = tan²(40.26°) = 0.71734  →  K/K′ = 1.01341
C_wire = 2.9×10⁻³/(18π) × 1.01341 × 1700 = 0.08835 pF = 88.35 fF     CALCULATED
```

**A second honest gap this document does not paper over.** The cell period
`a₂` = 12 mm exceeds `H` = 11.8 mm by exactly 0.2 mm total — split, if the
wire is centred in its cell, into two 0.1 mm half-gaps (one at each end),
not one 0.2 mm gap. This document uses the single 0.2 mm figure as one
lumped effective end-capacitance per cell, because that is the number
`docs/ishape-interior-tuning.md` already tabulates and because the
patent's drawings do not resolve the wire's exact centring (its own §7
already flags "the ERR's height is measured off a drawing, not published").
**`INFERRED`, and flagged as a simplification a solver would need to
check**, not a settled reading.

### 4.4 The coupling term — two forms, not merged into one

**Distributed (used in the computed model, §4.5–4.6).** Already given in
§4.1: the `M_TL(h)` transmission-line section, carrying `βh` — genuinely a
coupling *term*, since setting `h → ∞` decouples the two branches entirely
(`M_TL` becomes a lossless all-pass section with no memory of the far
sheet's own admittance at any finite frequency spacing) and `h → 0` locks
them into a single combined sheet.

**Lumped (the form the task asked for, offered as the explicit
alternative).** Two coupled parallel-LC oscillators sharing a mutual
inductance `M` is standard, textbook two-coupled-oscillator theory (the same
mathematics as two coupled pendulums or two coupled LC tank circuits — not
attributed to a single paper because it is general circuit theory, not a
result specific to this element). Writing `k = M/√(L₁L₂)` as the coupling
coefficient, the normal-mode (avoided-crossing) frequencies are

```
ω±² = (ω₁² + ω₂²)/2  ±  √[ ((ω₁² − ω₂²)/2)² + k²·ω₁²ω₂² ]
```

which, in the degenerate case the patent's own design principle calls for
(`ω₁ = ω₂ = ω₀`, "tuned to overlap"), collapses to `ω± = ω₀√(1 ± k)` — a
**symmetric split around the individually-tuned frequency**, with the split
set entirely by the coupling strength `k`. This is offered as a live,
unresolved alternative to the distributed model above, not a second
confirmation of it: **the two pictures are not obviously equivalent**, and
which one actually governs Example 3 is exactly the dispute Chen's paper
raises for the ground-backed case (§2–§3) and that this session found no
source settling for the ground-free case. `k` itself is not fitted here —
doing so honestly needs a second, independent data point this document does
not have (see §5).

### 4.5 Calibration against Landy's own measured geometry

**Naive calibration, and why it is not good enough on its own.** Setting
each branch's *own, standalone* resonance — `f₀ = 1/(π√(2LC))` for the ERR
(Withayachumnankul's own stated form for their two-inductive-loop topology,
§1 of their paper, applied here on the grounds that the ERR shares that same
two-arm topology) and the simpler single-branch `f₀ = 1/(2π√(LC))` for the
wire (a single strip, one inductance, not two loops in series) — to Landy's
own simulated peak for the fabricated geometry, 11.48 GHz
(`docs/example3-frequency-discrepancy.md` §1.3, quoted there verbatim from
Landy's own text), gives:

```
L_ERR  = 1/(2·C_ERR·π²·f₀²)   = 49.97 nH
L_wire = 1/(4·C_wire·π²·f₀²)  = 2.175 nH
```

**Run through the full cascade of §4.1, these two branches do not
individually add up to a stack matched at 11.48 GHz — they match at
10.02 GHz, 12.7% low.** This is itself a finding, not a bookkeeping slip:
it is direct, quantitative evidence that **the coupling term is not
negligible** at this geometry — loading two individually-tuned branches
together through the spacer measurably pulls the combined system's matching
frequency down from where either branch sits alone. This is exactly the
qualitative behaviour §4.4's distributed picture predicts (closing `h`
couples the branches; here `h` = 0.72 mm is small enough, relative to the
resonators' own size, for the effect to be a real double-digit-percent
correction, not a rounding error).

**Self-consistent calibration.** With `C_ERR` and `C_wire` fixed at their
geometric values (§4.2, §4.3 — these rest on a citable formula and are not
adjusted), a single free scalar `α` applied to both `L_ERR` and `L_wire`
together (preserving the ratio the geometry implies, since nothing retrieved
this session independently fixes that ratio) is solved so that the **full
cascade's** matched frequency lands at 11.48 GHz rather than either branch's
own:

```
α = 0.7607
L_ERR  = 38.01 nH                                                     CALCULATED
L_wire = 1.655 nH                                                     CALCULATED
```

`CALCULATED`, contingent on two stated, flagged assumptions: the
two-gaps-in-series mapping (§4.2), and holding `L_ERR/L_wire` fixed at its
naively-derived ratio rather than fitting both independently. **This is a
one-parameter fit to one data point** — honestly, not a from-scratch
prediction. §5 states what a second data point would buy.

**The check this calibration was not built to pass, and passed anyway.**
Perturbing only the spacer thickness `h` around 0.72 mm, holding
`L_ERR`, `L_wire`, `C_ERR`, `C_wire` fixed, and re-solving for the cascade's
matched frequency at each `h`:

| `h` (mm) | matched f (GHz) |
|---|---|
| 0.60 | 11.694 |
| 0.65 | 11.604 |
| 0.70 | 11.516 |
| **0.72** | **11.480** (the calibration point) |
| 0.75 | 11.428 |
| 0.80 | 11.342 |
| 0.90 | 11.172 |

```
Model elasticity, d(ln f)/d(ln h) over 0.65→0.72 mm:  −0.099          CALCULATED
```

Landy et al.'s own reported sensitivity, over the **same** two spacer
values (0.65 → 0.72 mm, +10.8%), Δf = −1.46%, already quoted in
`docs/example3-frequency-discrepancy.md` §4.3:

```
Landy's reported elasticity:  ≈ −0.135
```

**These are not the same measurement.** Landy's comparison conflates three
changed variables at once (`h`, `W`, `G` all differ between his ideal and
fabricated geometries — that document's own caveat, quoted there
verbatim: *"`W` and `G` also differ between the two, so this is not a clean
sweep"*). The model's −0.099 is a **cleaner, single-variable** test the
paper itself never ran. That the two numbers agree in **sign** and land
within **27%** of each other — with the model's necessarily-smaller
magnitude explained by exactly the missing `W`/`G` contributions Landy's own
comparison bundles in — is the honest validation this document can offer at
this level of effort: a real, independently-stated number the model was not
fitted to, landing in the right place. It is not proof the model is right;
it is evidence it is not obviously wrong.

### 4.6 Running the calibrated model against the patent's 9.2 GHz

With `L_ERR`, `L_wire` fixed at their calibrated values (§4.5), two levers
the model can represent are pushed toward the patent's own reported
~9.2 GHz null (`docs/example3-frequency-discrepancy.md` §2.3, digitised
numerically from two independent documents).

**Capacitance route** (both `C_ERR` and `C_wire` scaled together by a single
factor — the natural proxy for `example3-frequency-discrepancy.md` §4.2's
speculative "the patent's simulation embedded the resonators in dielectric,
raising the effective permittivity they see" candidate):

```
Scale needed to reach 9.2 GHz:  1.705×                                CALCULATED
Implied εre:  2.9 × 1.705 ≈ 4.94
Implied "full" εr, via εre=(εr+1)/2:  ≈ 8.9                           CALCULATED
```

**This corroborates, rather than merely repeats, `example3-frequency-
discrepancy.md` §3.1's finding.** That document's simpler single-resonator
`1/√εr` scaling already showed no FR4 grade closes the gap, needing
`εr ≈ 6.54–6.85` against the patent's stated 4.8. This document's
two-branch, transmission-line-coupled model — built independently, on a
different mechanism (a coupled-sheet cascade rather than a single scaling
exponent) — needs an even **larger** shift (`εr ≈ 8.9`) to reach the same
target. Two different closed forms agree that permittivity alone cannot
carry the gap, and this one's own number is the *more* pessimistic of the
two, not a rescue.

**Spacer-thickness route.** Holding `C_ERR`, `C_wire` fixed and sweeping `h`
well beyond any physically sensible range for a 0.72 mm-stated device:

```
h = 0.72 mm → 11.48 GHz (the calibration point, both documents agree on h)
h = 20 mm   → 13.51 GHz — the WRONG direction past a certain point, never reaching 9.2 GHz
```

**This lever does not reach 9.2 GHz at all inside the model, in either
direction that makes physical sense.** It is reported rather than pruned
from the writeup, per this repo's "warn, never block" and "name the missing
measurement" principles — a lever that visibly fails is worth recording,
not silently dropping.

**What the model cannot test, and why that is itself the finding.** The
strongest candidate `example3-frequency-discrepancy.md` §4.1 identifies —
the patent's Example 3 uses 0.15 mm metallisation against Landy's 17 µm,
8.8× thicker, adding sidewall capacitance across every gap — **cannot be
represented in this closed form at all.** The Gupta/Garg/Bahl/Bhartia gap
formula both branches are built on (§4.2, §4.3) is a purely planar,
two-dimensional electrostatic result; metal thickness does not appear in it
as a parameter. Deriving this closed form all the way through therefore
**sharpens** that document's own honest conclusion — "the magnitude cannot
be established without a solver" — into a slightly stronger statement:
*no closed form in this entire family (coplanar-gap-capacitance-based
equivalent circuits) can settle it either, because the whole family is
blind to metal thickness by construction.* A solver is not merely the
cheapest way to check this candidate; for this class of model, it is the
only way.

---

## 5. Honest limits

- **Loss is not modelled.** Every `Y(ω)` in §4 is a lossless parallel LC.
  The lossless cascade of §4.1 therefore cannot show an absorption peak at
  all (`A = 1 − |S11|² − |S21|² ≡ 0` for any lossless two-port) — what is
  computed and reported throughout §4.5–4.6 is the frequency of **minimum
  reflection** (impedance matching), used as a proxy for where a loaded
  version of the same network would peak, exactly the quantity Costa's own
  method (§4b of `docs/element-library-prior-art.md`) and Chen's (§2) both
  center on. Costa's own dielectric-loss resistor `R_D ≃ (1+εr′/εr″)/(ωC₀)`
  and ohmic-loss resistor `R_O ≈ (2/δσ)(1/L)(D²)` are the natural
  extension — already retrieved into this repo — but neither has been
  validated for a ring or wire shape by any source this session found; §4b
  of that document already flags Costa's own stated scope limit ("valid up
  to the first resonance" for a *patch*). Adding them here without that
  validation would be presenting a guess as a result.
- **`L_ERR` and `L_wire` are not independently determined.** §4.5's
  calibration fixes their *ratio* from a geometric assumption and their
  *scale* from one data point (Landy's 11.48 GHz). A second, independent
  calibration constraint — e.g. Landy's own ideal-versus-fabricated
  geometry pair, run as a genuine two-variable fit rather than the
  single-lever perturbation §4.5 used for validation only — would let both
  inductances be solved independently rather than tied together. That is
  the next cheapest thing this model could use, not a guess to make now.
- **The two-gaps-in-series (§4.2) and single-lumped-end-gap (§4.3) topology
  mappings are this document's own reading of the drawings**, consistent
  with `docs/ishape-interior-tuning.md`'s own geometry but not independently
  checked against a solver or a second source. Both are stated as
  `INFERRED` rather than folded silently into a `CALCULATED` number.
- **The distributed-versus-lumped coupling question (§4.4) is not settled
  here, and this document does not pretend it is.** Chen's paper disputes
  the near-field/magnetic-coupling picture for a *ground-backed* absorber;
  nothing retrieved this session tests either picture for a ground-free,
  two-layer stack like Example 3. The model built and run in §4.5–4.6 uses
  the distributed picture because it is the one a retrieved primary source
  (Chen) actually builds for a two-layer case; the lumped-`M` alternative
  is given in full but not fitted, for lack of a second data point to fit
  it against.
- **The capacitance-route "embedding permittivity" interpretation (§4.6) is
  a proxy, not a claim about the patent's actual simulation setup.** Scaling
  both sheet capacitances by one factor is the cheapest way to ask "how
  much more capacitance would it take," not a statement that the patent's
  authors actually embedded the resonators in a higher-permittivity medium.
  `example3-frequency-discrepancy.md` §4.2 already flags embedding as
  speculative and unconfirmed by the patent's own boundary-condition
  statements (it states none for Example 3).
- **This document does not resolve #142's 20% frequency discrepancy.** It
  was never expected to — the task was a closed form for the topology, not
  a re-litigation of an already-thoroughly-researched open discrepancy. What
  it contributes there is a second, independently-built method that agrees
  with the existing conclusion (permittivity alone is not enough) and
  narrows, rather than widens, the open hypothesis space by ruling out a
  spacer-thickness explanation more decisively than before.

---

## 6. What would upgrade this

- **One Floquet/full-wave solve of Example 3's actual FIG. 7F geometry**,
  at 17 µm and at 0.15 mm metal thickness, is the single highest-value next
  step — it is what `example3-frequency-discrepancy.md` §4.1 already named,
  and §4.6 above shows this whole closed-form family cannot substitute for
  it on the thickness question.
- **A second calibration point** — Landy's own ideal-geometry simulation
  (11.65 GHz null, `a₁`=4.2, `a₂`=12, `W`=3.9, `G`=0.606, `h`=0.65 mm) run
  through the exact same pipeline as §4.5 — would let `L_ERR` and `L_wire`
  be solved independently rather than tied to one ratio, and would turn
  §4.5's single-point calibration into a genuine two-point fit.
- **Costa's `R_D`/`R_O` loss terms**, validated against one full-wave run of
  this specific geometry, would let the model predict an actual absorbance
  peak (not just a matching frequency) — the missing piece flagged in §5.
- **Resolving §4.4's distributed-versus-lumped question** for a ground-free
  two-layer stack specifically (nobody retrieved this session has done
  this) would settle which of the two coupling pictures this element
  actually obeys, rather than leaving both live.

---

## 7. Provenance summary

| Claim | Value | Tag |
|---|---|---|
| No closed form for ERR-plus-wire exists in this repo's own prior survey | quoted verbatim, §1.1 | `LITERATURE-SUPPORTED` |
| Tao et al. 2008 contains no equivalent circuit | full text searched, none found | `LITERATURE-SUPPORTED` negative finding |
| Chen 2012's topology is ground-backed, one resonator layer | quoted verbatim | `LITERATURE-SUPPORTED` |
| Chen 2012 disputes near-field magnetic coupling for MPAs | quoted verbatim | `LITERATURE-SUPPORTED` |
| Wakatsuchi et al. 2012 covers cut-wire only, no ERR | Crossref-registered abstract, quoted in full | `LITERATURE-SUPPORTED` (abstract-level; full text STRANDED) |
| Pang et al. 2013 covers wire-based absorbers only, no ERR | Crossref-registered abstract, quoted in full | `LITERATURE-SUPPORTED` (abstract-level; full text STRANDED) |
| Gap-capacitance formula, Eq. (1)–(3) | full prefactor recovered, verbatim | `LITERATURE-SUPPORTED` |
| ERR two-gaps-in-series topology mapping | this document's own reading | `INFERRED` |
| `C_ERR` = 7.69 fF | `CALCULATED`, on the `INFERRED` mapping above | `CALCULATED` |
| Wire single-lumped-end-gap mapping | this document's own reading | `INFERRED` |
| `C_wire` = 88.35 fF | `CALCULATED`, on the `INFERRED` mapping above | `CALCULATED` |
| Two-shunt-admittance transmission-line cascade structure | this document's own synthesis of Costa + Chen + standard ABCD/S theory | `CALCULATED` |
| Naive (uncoupled) calibration mismatches the coupled stack by 12.7% | `CALCULATED` | `CALCULATED` |
| Self-consistent `L_ERR` = 38.01 nH, `L_wire` = 1.655 nH | `CALCULATED`, one-parameter fit to one data point | `CALCULATED` |
| Model spacer-thickness elasticity ≈ −0.099 | `CALCULATED` | `CALCULATED` |
| Landy's own reported elasticity ≈ −0.135 | quoted/derived in `example3-frequency-discrepancy.md`, itself `CALCULATED` from `LITERATURE-SUPPORTED` numbers | `CALCULATED` |
| Capacitance-route scale to reach 9.2 GHz: 1.705×, implied εr ≈ 8.9 | `CALCULATED` | `CALCULATED` |
| Spacer-route cannot reach 9.2 GHz in a sensible range | `CALCULATED` | `CALCULATED` |
| Model is structurally blind to metal thickness | property of the source formula, verified by inspection | `CALCULATED` |
| Lumped mutual-`M` coupled-oscillator equations | standard textbook circuit theory | `LITERATURE-SUPPORTED` (general result, no single-paper citation) |

---

## 8. Sources and routes tried

**Retrieved and read in full this session:**

1. Tao, H., Landy, N. I., Bingham, C. M., Zhang, X., Averitt, R. D. &
   Padilla, W. J., "A metamaterial absorber for the terahertz regime:
   Design, fabrication and characterization," *Opt. Express* 16(10):
   7181–7188 (2008), [arXiv:0803.1646](https://arxiv.org/abs/0803.1646).
   Via `arxiv.org/pdf/0803.1646`, extracted with PyMuPDF.
2. Chen, H.-T., "Interference theory of metamaterial perfect absorbers,"
   *Opt. Express* 20(7):7165 (2012), [arXiv:1112.5168](https://arxiv.org/abs/1112.5168).
   Via `arxiv.org/pdf/1112.5168`, extracted with PyMuPDF.
3. Withayachumnankul, W., Fumeaux, C. & Abbott, D., "Compact electric-LC
   resonators for metamaterials," *Opt. Express* 18(25):25912–25921 (2010),
   [arXiv:1009.0139](https://arxiv.org/abs/1009.0139). Via
   `arxiv.org/pdf/1009.0139`, extracted with PyMuPDF — a full re-fetch, since
   the earlier retrieval behind `docs/ishape-interior-tuning.md` did not
   carry Eq. (3)'s prefactor.
4. Dolling, G., Enkrich, C., Wegener, M., Zhou, J. F., Soukoulis, C. M. &
   Linden, S., "Cut-wire pairs and plate pairs as magnetic atoms for optical
   metamaterials," *Opt. Lett.* 30(23):3198–3200 (2005),
   [arXiv:physics/0507045](https://arxiv.org/abs/physics/0507045). Retrieved
   and read; confirms the qualitative SRR→cut-wire-pair LC picture but
   contains no closed-form L or C — background only, not load-bearing for
   §4's numbers.

**Confirmed closed access, no repository copy anywhere (OpenAlex
`any_repository_has_fulltext: false`, same standard this repo already
applies in `RUNNING-LISTS.md` §1) — abstract-level only:**

5. Wakatsuchi, H., Paul, J., Greedy, S. & Christopoulos, C., "Cut-Wire
   Metamaterial Design Based on Simplified Equivalent Circuit Models,"
   *IEEE Trans. Antennas Propag.* 60(8):3670–3678 (2012),
   [10.1109/TAP.2012.2201109](https://doi.org/10.1109/TAP.2012.2201109).
   IEEE Xplore behind the same block this repo's `RUNNING-LISTS.md` §1
   already records; abstract retrieved via Crossref.
6. Pang, Y., Cheng, H., Zhou, Y. & Wang, J., "Analysis and design of
   wire-based metamaterial absorbers using equivalent circuit approach,"
   *J. Appl. Phys.* 113:114902 (2013),
   [10.1063/1.4795277](https://doi.org/10.1063/1.4795277). AIP, same block
   pattern this repo already records for AIP sources; abstract retrieved
   via Crossref.

**Already in this repo, re-used and cited rather than re-derived:**

- Costa, F., Genovesi, S., Monorchio, A. & Manara, G., "A Circuit-based
  Model for the Interpretation of Perfect Metamaterial Absorbers,"
  [arXiv:1211.1902](https://arxiv.org/abs/1211.1902); *IEEE Trans. Antennas
  Propag.* 61(3):1201–1209 (2012) — the shunt-admittance-in-a-transmission-
  line-stack synthesis method, applied here to a second sheet instead of a
  ground plane. See `docs/costa-thin-spacer-correction.md`.
- N. I. Landy, S. Sajuyigbe, J. J. Mock, D. R. Smith & W. J. Padilla, "A
  Perfect Metamaterial Absorber," [arXiv:0803.1670](https://arxiv.org/abs/0803.1670);
  *Phys. Rev. Lett.* 100:207402 (2008) — the geometry and measured/simulated
  frequencies this document calibrates and checks against. See
  `docs/example3-frequency-discrepancy.md`.
- US Patent US12089385B2, Example 3 description and FIG. 7E/7F/7G.
- `docs/ishape-interior-tuning.md` — the element's measured geometry
  (loop footprint, gaps, axis orientation) this document's numbers are
  built on.
- `docs/element-library-prior-art.md` §4 — the existing closed-form survey
  this document's §1–2 extends rather than repeats.

**Numerical work.** All arithmetic in §4 (gap-capacitance evaluations, the
ABCD/S-parameter cascade, the calibration solve, the sensitivity sweeps) was
carried out in Python (NumPy) in this session and is reproducible from the
equations stated in §4; no numeric result in this document is asserted
without the formula that produced it stated alongside it.
