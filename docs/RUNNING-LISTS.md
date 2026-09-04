# Running lists

Five standing registers for the printed-metamaterial effort. Each accumulates
rather than being rewritten, so a stale entry gets struck through and dated,
never deleted.

Wayfinder map: [#104](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/104).

**Maintenance.** Add to these as work lands. When an entry resolves, mark it
resolved with a pointer to where the answer lives — an unbroken record of what
was once unknown is worth more than a tidy list of what still is.

---

## 1. Sources needing a human with a browser

Automated fetching is blocked at several publishers. Each entry says **why it
matters**, so a browsing session can be prioritised rather than exhaustive.

| Source | Status | What is stranded behind it | Bears on |
|---|---|---|---|
| **`pp.bme.hu`** (Periodica Polytechnica) | DNS failure, then 502 through the proxy — **unreachable**, not merely blocked | Split-cylinder measurements of **Kapton HN, Mylar A and PEN at ~10 GHz**. The highest-value stranded item for substrate data | #114, #127 |
| **MDPI** | HTTP 403 to all automated fetches — but **PMC mirrors it**, which is not blocked | ~~The only quantitative TPU permittivity source~~ — **resolved 2026-09-03 via the PMC mirror**. Still strands absorber and polarisation-converter literature not carried by PMC | #127, #110 |
| **IEEE IMWS-AMP 2016**, Moscato et al. — NinjaFlex characterised 2–20 GHz | Behind IEEE; no repository copy found | A second independent X-band curve for a **named, orderable** TPU filament. The highest-value stranded item now that TPU has one source. A library login closes it | #127, #114 |
| **DTIC Public Search** | **Service offline** — "offline while we enhance the capability" | Any unpublished ARL technical report on the patent's skin would live here, and nowhere else. A Crossref sweep of the `10.21236` prefix is a partial substitute and came back empty | #116 (closed), #107 |
| **ScienceDirect** | HTTP 403 | An article raised in discussion, PII `S1546221822014060` — never read | unassessed |
| **IEEE Xplore** | HTTP 418 | PDMS's X-band loss tangent, currently `INFERRED` from a published curve rather than read directly | #114 |
| **Wiley** | HTTP 403 despite open access | ~~Costanzo et al., *IJAP* 2019~~ — **resolved**, retrieved manually 2026-09-03 | #133, #130 |
| **Laird Eccosorb BSR/MFS datasheets** | Publishes attenuation only; sibling datasheets use custom font subsetting that defeats text extraction | No ε′, ε″, µ′ or µ″ at any frequency, so **Eccosorb cannot be simulated at all** despite being sold for compound curves | #127 |
| **incose.org** | HTTP 403 | INCOSE *Guide to Writing Requirements* V4. Rule text was never quoted first-hand, so its rule numbers are deliberately not asserted anywhere | #122 |
| **ISO/IEC/IEEE 29148** | Paywalled | The civil-side requirements standard | #122 |
| **2021 JCIDS Manual, DoDI 5000.85, CRS IF12817** | HTTP 403 | Current editions. Threshold/objective is quoted from the **2009 and 2012** editions instead | #122 |
| **Rozanov (2000)**, "Ultimate thickness to bandwidth ratio of radar absorbers" | Behind IEEE | The original statement of the thickness/bandwidth bound. Its result is verified through two independent open-access restatements that agree with each other, but **the original was never read** | #129, #110 |
| **A 2025 Wiley paper on absorber quality criteria** | HTTP 403 | Explicitly on this subject. The critique of `RL_min` as a scoring metric currently rests on **secondary summaries** of it | #110 |

**Environment note.** A headless browser was set up and reaches sites through
the agent proxy with `--disable-quic --ssl-version-max=tls1.2`. It does **not**
defeat Akamai/Cloudflare bot management: the proxy relay requires TLS 1.2, and
a TLS 1.2 handshake sent with a Chrome user agent is a self-contradicting
fingerprint that gets denied harder than plain `curl`. Assume the *publisher's
own site* stays human-only.

**Routes around a block that do work** — established while closing the TPU
entry, recorded in `docs/tpu-xband-permittivity.md` §10. **Try all of these
before recording an absence:**

- **PubMed Central mirrors MDPI** and is not bot-blocked.
- **University repositories hold IEEE post-prints.** The corroborating TPU
  measurement came from Pavia's repository after Xplore returned 403.
- **`pymupdf` is installed** and extracts text, fonts and embedded figures. One
  "unextractable" datasheet turned out to use a custom font subset with a fixed
  **+29 character-code offset** — recoverable, not lost.
- **Digitise the figure** when the running text gives only a range. The TPU
  per-frequency numbers came off Figure 9a; the prose said only "between 2.5
  and 3."

> **The standing rule this produced.** *"No data exists"* is a claim about the
> world; *"we could not fetch it"* is a claim about us. #114 recorded the first
> when it meant the second, and the correction cost **one fetch and no new
> measurement**. Record an absence only with the routes tried written beside it.

---

## 2. Questions for the patent's inventors

Lives in its own file: **[`docs/questions-for-the-patent-inventors.md`](./questions-for-the-patent-inventors.md)**.

Ten questions about US12089385B2 that only its authors can settle — three
prose-versus-drawing discrepancies, one erratum, and the rest on fabrication
intent and capability. Add to that file rather than duplicating here.

**Two of them stopped being blocking on 2026-09-03.** #116 settled `h₁` and the
FIG. 7G y-axis by measuring the drawings, so those questions now read *"here is
our reading and the arithmetic behind it — confirm or correct"*. A question
with a proposed answer attached is a much cheaper thing to ask someone.

---

## 3. Corrections to earlier claims

Kept so nobody inherits a superseded number. **Four came from the handoff
document; the rest were made during analysis, several of them mine.**

### Inherited from `HANDOFF-metamaterial-printing-grill.md`

1. **Example 1's permittivity: εr = 310 → ε₁ = 250 − 1.25j.** The prose figure
   is not what the examples were simulated with; FIG. 5C carries a loss term
   the prose omits. Example 2 is 294 − 0.5j.
2. **"Sub-wavelength cells land right at the machine's floor" → they do not.**
   Minimum feature across all seven examples is **0.2 mm**, which is 2–6×
   *above* the NOVA's floor.
3. **The cure-compatibility matrix marks silver ✗ on PET and TPU — wrong.**
   Silver cures at 120 °C/30 min on PET, and Intexar PE874 (on Voltera's own
   materials list) at 130 °C on TPU film. **What prunes silver is whether the
   part can leave the host for an oven, not substrate class.** This narrowed
   MXene's decisive advantage to in-situ printing on hosts that cannot be baked.
4. **"MXene behaves as a copper ~85× lossier" is a DC ratio applied at 10 GHz.**
   Above ~3 skin depths surface resistance goes as **1/√σ**, so the real RF
   penalty is **~9× versus copper and ~3.8× versus silver** — roughly an order
   of magnitude less than every comparison had assumed.

### Made during analysis

5. **"Each letter has a frequency ceiling of ~1.7× its design frequency" —
   wrong premise.** That assumed naive scaling against the printer's floor.
   Good high-frequency designs are not scaled-down low-frequency ones: a
   published 28/38 GHz cell has a **0.22 mm minimum feature** because fractal
   miniaturisation folds a longer resonator into a smaller cell while keeping
   features coarse. **The ceiling is set by topology choice, not arithmetic.**
6. **"200 meandered squares gives 200× the resistance" — DC reasoning at
   10 GHz.** A meandered line is an *inductor* at microwave frequencies, and a
   30 mm line is about one guided wavelength — a distributed structure, not a
   lumped element. The correct mechanism is a **resonant element whose own
   ohmic loss damps it**.
7. **"Print a thin, lossy MXene layer" — not achievable.** The machine's
   minimum film is ~10 µm, already ~1.65 skin depths at 10 GHz, so MXene is
   effectively opaque there. **Thickness is a dead knob.** ACI SC1502 carbon
   ink reaches 377 Ω/sq at 15.9 µm — about two passes — and is the answer
   instead.
8. **"Print both sides of one substrate for free registration" — not on this
   machine.** Double-sided is a **V-One** feature using drilled-hole mechanical
   registration on rigid FR1, and does not transfer to a compliant sheet. The
   architecture survives only because the reflector is unpatterned and has
   nothing to align to.
9. ~~**WR-90 waveguide is the wrong fixture to design coupons for**, and
   11 × 11 cells is a demonstrated sufficient sample.~~ **Superseded
   2026-09-03 — both halves were wrong.**
   - **A coupon is specified in wavelengths, not cells.** 11 × 11 was carried
     across from a 28 GHz paper where it measured 55 mm ≈ **5.1 λ**. At X-band
     the same count is 33 mm ≈ **1.1 λ**, which no free-space method can
     measure. NPL good practice requires **> 20 λ unfocused (600 mm at
     10 GHz — impossible on a 220 × 300 mm bed) or 6 λ focused (180 mm — fits)**.
     Revised spec: **≈ 180 × 180 mm, ≈ 60 × 60 cells at 3 mm pitch.**
   - **WR-90 was dismissed too fast.** A *waveguide simulator* images a few
     cells into a virtual infinite array, and at 2.54 mm pitch gives exactly
     9 × 4 cells. It measures **element phase under oblique incidence sweeping
     55° → 33°**, not broadside absorption — a different measurement, not a
     cheaper one.
10. **Aircraft wing, hull and sUAS body are not fixed targets.** They are
    *examples of what a requirement might state*. The host surface is a
    per-requirement input, and treating it as a project constant silently fixes
    the material answer.
11. ~~**TPU has no X-band data of any provenance.**~~ **Superseded 2026-09-03.**
    It has two independent sources. Solid ester-based TPU measures **εr 2.71 /
    tanδ 0.099 at 10 GHz** in a WR-90 waveguide ([Vong et al., *Materials*
    15(9):3320](https://doi.org/10.3390/ma15093320)), corroborated at 2.4 GHz by
    a ring-resonator measurement of NinjaFlex from a different lab (εr 3.00 /
    tanδ 0.060) — consistent, since permittivity falls and loss rises with
    frequency in a polymer. Honest uncertainty **εr 2.7 ± 0.3, tanδ 0.10 ± 0.01**,
    the ± being the authors' own print-to-print repeatability.
    **The error was a fetch failure recorded as an absence** — MDPI 403'd and no
    PDF extractor was to hand. See the standing rule in §1.
    Consequences: TPU's loss is **~5.8× FR4's** and level with silicone, so it is
    a *lossy* flexible substrate and #114's "flexible need not cost dissipation"
    gets a second example; and it beats silicone practically — already on
    Voltera's NOVA substrate list, no low-surface-energy adhesion problem,
    Intexar PE874 cures on it at 130 °C.
    **Two traps that invert the conclusion**: three papers report TPU at
    εr 1.5–2.4 across X-band and **all are foams** (Vong measured 2.8 solid vs
    1.8 foamed — and print infill below 100 % makes a foam whether you meant one
    or not), and Vong et al. call the material the *"lossless filament"* meaning
    only *no magnetic filler*. **Still missing:** any X-band figure for a named,
    orderable grade or for hard D-grade TPU; BASF Elastollan's unfilled range
    spans tanδ 0.040–0.140 at 1 MHz, a 3.5× spread inside one product line.

### Attribution errors

12. **Costanzo et al., *IJAP* 2019 does not carry the dissimilar-neighbour
    coupling error.** A research pass attributed it there; the paper's coupling
    analysis concerns two frequency bands co-located in **one cell**, not unlike
    neighbours across an array. ~~**The literature gap stands.**~~
    **Half-superseded 2026-09-03:** the *DOI* was wrong, not the paper. The
    number lives in `10.1155/2019/**4890710**` — same authors, same journal,
    same year, different article — which publishes **max reflection-phase error
    against element pitch at 10 GHz for three element shapes**, 12° to 85°. The
    gap this recorded was never real.
13. **"Phase quantisation is well characterised" — only for beam-forming.**
    Not for absorption or backscatter reduction, which is what this effort
    actually optimises.
14. **Costanzo et al. *IJAP* 2019 is not "numerically validated only".** A
    research pass concluded this from the abstract alone, Wiley having blocked
    the full text. The paper's **Section 4 is an experimental validation** —
    an 11 × 11 array on DiClad 880, two horns, a VNA, broadside far-field.
    Verified from the manually-retrieved PDF. **A conclusion drawn from an
    abstract is not a conclusion about the paper.**
15. **Cole et al.'s "11% frequency error" is not the unlike-neighbour number.**
    #131 and #104 both recorded it as the cost of ignoring dissimilar
    neighbours. Re-reading the source: the 0.89 THz-versus-1.0 THz shift is
    near-field coupling **between the three metal layers stacked inside one
    cell**, measured against a transmission-line model — an *intra-cell*
    composition error, which maps onto Example 3's multi-layer stack, not onto
    neighbour coupling at all. Cole et al.'s unlike-neighbour statement is real,
    prominent and correct, but **qualitative** — "some evidence that the optimal
    frequency is shifted." No number attaches to it.
    **Propagated 2026-09-03** to #104's decision log and #130. #111's starting
    magnitude should be re-filed as an intra-cell stack-modelling figure; the
    coupling error bar is Costanzo's 12–85°.

20. **The super-cell sizing rule's own phase budget was borrowed from the wrong
    problem.** `docs/supercell-sizing-rule.md` as first published gated on
    **±22.5°**, the half-step of 3-bit phase quantisation — a **beam-forming**
    convention, applied to a **backscatter-reduction** design. That is precisely
    the trap item 13 above records, written by the same pass that then fell into
    it. Its companion constant, a 30° minimum scattering angle, was picked
    rather than derived.
    **Corrected 2026-09-04 by deriving both from the objective.** A chessboard
    reduces RCS by cancellation, so the surviving echo is `sin(δ/2)` and
    `RCSR_dB = 20·log₁₀(sin(δ/2))`, which inverts to
    `δ_budget = 2·arcsin(10^(−RCSR_dB/20))` — **36.9° at 10 dB**, not 22.5°
    (and 22.5° silently corresponds to a 14.2 dB requirement nobody stated).
    The ceiling's real floor is the panel's own specular lobe, ≈ `λ/(2L)` —
    **4.8°** for a 6 λ coupon, **0.95°** for a 30 λ panel.
    **Consequence: the headline claim "three of six element families have no
    feasible block size" does not survive.** At 10 dB all six are feasible. The
    rule bites at demanding reduction levels — at 20 dB the size-tuned square
    patch at 0.4 λ pitch has no feasible N — and what interior tuning buys is
    **headroom and spatial resolution** (N = 2 versus N = 9 at 10 dB, so
    4.5× finer control), not the difference between possible and impossible.
    **The durable lesson: define failure against the purpose, not against an
    internal metric.** A threshold in degrees is not a requirement. Every
    threshold in this loop should be traceable to something a customer would
    write down, and a constant that cannot be traced that way is a smuggled
    assumption.

21. **The same error is queued up in #110, and has not fired yet.**
    `docs/absorber-scoring-conventions.md` §1 lists **"the threshold is 90 %
    absorption, equivalently −10 dB reflectivity"** among four things that can be
    **"adopted without argument"**. That is a *journal reporting convention* —
    the document says so itself, noting IEEE Std 1128 stops at 5 GHz and
    standardises measurement rather than scoring — and adopting it as a
    pass/fail line is the same move that put ±22.5° into the super-cell rule.
    It also contradicts **#117's already-settled "silence is permissive"**:
    a convention adopted as a threshold converts a silence into a hard prune, on
    the authority of a literature the customer never cited.
    **Not yet an error — #110 is open.** Recorded here so it is decided rather
    than absorbed. See `docs/requirement-derived-thresholds.md` for the full
    audit and the A/B/C classification it proposes.

22. **"No measurement of Example 3 exists anywhere" — wrong, and it was the
    important half of that finding.** #116 was closed on it. **Example 3 is
    Landy, Sajuyigbe, Mock, Smith & Padilla, "A Perfect Metamaterial Absorber",
    *Phys. Rev. Lett.* 100:207402 (2008)** ([arXiv:0803.1670](https://arxiv.org/abs/0803.1670)),
    reproduced number for number: the patent's FIG. 7F table is Landy's
    *fabricated* set verbatim — `a1=4.2, a2=12, W=4, G=0.6, t=0.6, L=1.7,
    H=11.8` mm on FR4, elements *"separated by 0.72mm"*. Verified against the
    primary source. And it was **measured**: *"our experiments demonstrate a
    peak absorbance greater than 88 % at 11.5 GHz"*, from complex S-parameters
    on a large planar sample.
    **The search was right; the inference was wrong.** The inventors genuinely
    never published Example 3 — 22 publications, none an absorber, confirmed by
    the patent's own "Other References". The error was concluding from *"the
    inventors did not publish it"* that *"nobody published it"*. The patent
    reproduces someone else's published device, so the search was scoped to the
    wrong authors. **An exhaustive search of the wrong set is still exhaustive,
    and still tells you nothing about the right one.**
    Consequences: the anchor's reference is `LITERATURE-SUPPORTED` from a
    `MEASURED` original, not capped at `SIMULATED`; this was ranked **#1–2** in
    §4's unknowns. And it opens a new discrepancy — the patent's ~9.2 GHz
    against Landy's measured **11.5 GHz for identical dimensions** (#142).
23. **The 0.2 mm gap in Example 3 is on the H-plane, not the E-plane.** Noted
    here because it was mine, and because the arithmetic was right while the
    inference was not. `W` = 4 mm in `a₁` = 4.2 mm does leave **0.2 mm =
    0.0067 λ**, tighter than Costanzo's tightest — but Landy's Fig. 1(c) puts
    **E along `a₂`**, where the resonators sit **8.0 mm = 0.267 λ** apart,
    looser than Costanzo's *loosest*. Coupling is strongest on the E-plane, so
    the tight gap is on the axis that matters least. There *is* a 0.2 mm gap on
    the E-plane — the **cut wire on the underside** — which nobody had noticed.
    **Check which axis carries the field before reading a gap as tight.**
24. **`docs/supercell-sizing-rule.md` assumed a square cell, and the anchor is
    not square.** 4.2 × 12 mm is an aspect ratio of 2.86. On that cell **N = 2
    is evanescent — it redirects nothing** — and the smallest radiating block is
    **5 × 2 cells**. Because blocks of 4–5 and up are *forced*, `f(N)` drops
    below 1 and the block genuinely averages, which runs **opposite** to the
    document's "grouping averages nothing" headline. The rule also **omitted a
    panel-fit constraint** (`2·N·p ≤ L`) that turns out to bind first on a
    coupon, making "no feasible N" a statement about part size rather than about
    the alphabet. Amended in §5.5; see #138.

### Errors found in published sources

Not our corrections, but ours to route around. Recorded because anyone
adopting these results will hit the same thing.

16. **Huynen (2022) mis-tabulates its own Eq. 7.** Two of five rows reproduce
    exactly; three are **10× too large**. Correcting the arithmetic **reverses
    the paper's own ranking**. Its Table 5 column headed `h_tot norm` also
    contains λ₀ in millimetres, so Eq. 9 is defined in the paper and never
    actually applied. **Adopt its definition of the normalised figure of merit;
    recompute every number.**
17. **US12089385B2's stated 0.87 mm total skin thickness for Example 3 is an
    arithmetic slip.** FIG. 7D's drawn strata measure 16.3 / 70.1 / 13.7 %,
    matching a **0.15 / 0.72 / 0.15 mm** metal-dielectric-metal stack to
    **0.5 pt** — total **1.02 mm**. The prose counted the 0.15 mm conductor once
    and forgot the underside that FIG. 7C plainly shows. The tempting
    `0.72 + 0.15 = 0.87` coincidence is the *cause* of the slip, not evidence
    for reading `h₁` as a second dielectric. `INFERRED`, from measuring the
    drawing. Settled in #116.
18. **FIG. 7G's y-axis is mixed and unlabelled as such.** Reflectance and
    Transmission are field magnitudes (`|S₁₁|`, `|S₂₁|`); Absorbance is a power
    (`1 − |S₁₁|² − |S₂₁|²`). Reading the whole axis as power gives **negative
    absorbance at three frequencies**, which is impossible. The axis is labelled
    with a bare `S`, and both conventions live in 0–1, so the error would never
    announce itself. **Never square the Reflectance trace before comparing.**
    Settled in #116.
19. **Vong et al. (2022) call their material the "lossless filament."** They
    mean *no magnetic filler added*. It measures tanδ 0.099 at 10 GHz — lossier
    than FR4 by ~5.8×. A skim-reader records the opposite of what the paper
    measured.

---

## 4. Unknowns, ranked by how much they matter

Ranked by *how much a decision changes if the answer changes*, not by how
interesting the question is. The top of this list is where measurement and
enquiry effort should go.

| # | Unknown | Why it ranks here | Where |
|---|---|---|---|
| 1 | **Is there bench access for X-band measurement?** | Decides whether the one genuinely novel claim — a library of individually *measured* elements, which has no prior art anywhere — is achievable or aspirational. Everything RF is capped at `SIMULATED` without it. Now askable under the CRADA rather than researchable | #133, #132 |
| ~~2~~ | ~~**Example 3's `h₁`, and FIG. 7G's y-axis**~~ | **Resolved 2026-09-03.** `h₁` is a **conductor on both faces**, dielectric stays **0.72 mm**; FIG. 7G's axis is **mixed** — R and T are field magnitudes, A is a power. Both `INFERRED`, from measuring the drawings, and a score computed against them inherits that ceiling | #116, closed |
| 3 | **Minimum line width and thickness-per-pass on the real NOVA** | Sets the alphabet's frequency ceiling and every geometry constraint. Currently literature-extrapolated onto hardware nobody has run | #106 |
| 4 | **Carbon sheet resistance at two passes** | Two passes and one four-point-probe reading either confirms or kills the whole resistive-layer architecture | #106, #128 |
| ~~5~~ | ~~**TPU's X-band permittivity**~~ | **Resolved 2026-09-03** — εr 2.71 / tanδ 0.099 at 10 GHz, two independent sources, `LITERATURE-SUPPORTED`. What remains is narrower and ranks lower: **no X-band figure for a named, orderable grade**, and grade spread inside one product line is 3.5× on loss | #127, #114 |
| 6 | **The superposition coupling error bar** | ~~No prior art.~~ **Partly resolved** — Costanzo et al. publish **12–85° max phase error against pitch at 10 GHz** for three element shapes. What has no prior art is the error bar *for our own alphabet*, which still has to be derived | #111 |
| ~~7~~ | ~~**A super-cell sizing rule from a coupling budget**~~ | **Derived 2026-09-04** — `supercell-sizing-rule.md`. It turned into a **gate on the alphabet** rather than a size: block size is pinned to N = 2 by the scattering requirement, where grouping buys no averaging at all. What replaces it is narrower and ranks lower — **our own alphabet's Δφ_max, measured rather than borrowed**, which needs the bench | #130, #132 |
| 8 | **Layer-to-layer registration on the NOVA** | Unpublished anywhere. Suspected to be the real geometric risk, ahead of feature size | #106, #115 |
| 9 | **Does the vacuum table hold silicone?** | Gates the top RF substrate candidate. Voltera's own documentation explicitly does not state it | #106, #114 |
| 10 | **Whether `R = 3T` or IPC-2223's 6× rule governs** | The patent's rule is *twice as permissive* as the flex-circuit industry standard, so enforcing it approves parts bent twice as tight as IPC allows | #115 |
| 11 | **Whether Example 7's element is the one three 2020–21 papers publish under its own name** | Would supply an independent description — and possibly measurements — for the first Tier B family charted. `INFERRED` match from title and element name; needs IEEE access | #104 |

**Two entries left this table on 2026-09-03, and both left the same way.** Not
by measurement — by reading something that was already published. Worth
remembering before ranking the next unknown as expensive.

---

## 5. The research agenda — nine items with no prior art

Established by [#131](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/131)'s survey. Originally recorded as risk;
**re-read as the joint research agenda** now that a CRADA is in place. The list
does not change — what it is *for* does.

1. **A per-letter `MEASURED` element library.** Every published library is
   simulated. In this literature, measurement validates the *assembled
   article*, never the individual elements. **The strongest differentiator and
   the least proven.**
2. **A per-element response *band* rather than a curve.** Nobody publishes a
   band, and nothing anywhere addresses how bands compose under superposition.
   Nearest precedent is Marcuvitz's practice of publishing an error bound and
   validity box for every entry.
3. ~~**A super-cell sizing rule derived from a coupling error budget.**~~
   **Derived 2026-09-04** — [`supercell-sizing-rule.md`](./supercell-sizing-rule.md),
   settled on #130. Every block size in the literature is still set by beam
   geometry, control-line count or fabrication tolerance rather than by managing
   interference, so there was nothing to adopt; this is our own.
   **It did not come out as a sizing formula.** Two constraints pull opposite
   ways — the coupling error falls only as 1/N, while the scattering angle a
   coded surface exists to produce collapses much faster as blocks coarsen — so
   the allowed block size is usually **exactly N = 2**, and at N = 2 every cell
   touches a foreign block and the block averages nothing. The rule therefore
   collapses into **a gate on the alphabet**: an alphabet whose worst-case
   unlike-neighbour phase error exceeds the budget on its own cannot be rescued
   by grouping. **Three of six literature element families have no feasible
   block size at all**, the variable-size square patch — the field's workhorse —
   among them. Remains derived work in the sense that nobody has published it;
   it is now written down rather than open.
4. **An error bar on the superposition fast tier — for *our* alphabet.**
   Narrowed 2026-09-03: the generic error bar *does* exist. Costanzo et al.
   publish **max reflection-phase error against element pitch at 10 GHz** for
   three element shapes (12° best, 85° worst), and An et al. publish the only
   error-versus-neighbour-count curve. What nobody publishes is
   *"superposition of independently characterised letters is accurate to ±X° at
   block size N"* for an alphabet of one's own. **Still derived work — but it
   starts from published numbers rather than from nothing.**
   > **The actionable finding underneath it**, which changes what the alphabet
   > should look like: a variable-size square patch tunes its phase by changing
   > its own outline, which changes the **gap** to its neighbour — 0.009λ to
   > 0.19λ across one alphabet, a **twentyfold swing** in coupling capacitance.
   > A shape tuned from its *interior*, holding its edges fixed, shows about
   > **4× less error** (25° / 21° / 12° at half-wavelength pitch for square,
   > Minkowski, fixed-edge). **Prefer letters that differ without changing what
   > they present to their neighbours.**
5. **Admission-by-printability** — an element entering the library only after
   printing successfully, which would make any design built from it printable
   by construction.
6. **A re-characterisation policy** — what invalidates a characterised element.
7. **Closed-form equivalent-circuit models for the patent's own shapes.**
   Existing closed forms cover square patches, strip grids and the absorber
   stack, but **nothing covers I-shaped ring resonators**.
8. **A combinatorial optimiser over band-carrying elements under a printability
   constraint.**
9. **A quantitative agreement metric between simulated and measured curves.**
   Added by #110's survey: the absorber literature compares the two in
   **qualitative prose only** — "good agreement" — with nothing quantitative
   anywhere. This matters directly, because reproducing Example 3 as a
   known-answer test needs a number for *how well* the reproduction matched,
   and there is nothing to adopt.

**What is *not* on this list, because it is standard practice:** the element
library architecture itself, organising by shape family, characterising blocks
as units, and phase quantisation levels. Those are adopted, not invented — see
#131.
