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
| ~~**Rozanov (2000)**, "Ultimate thickness to bandwidth ratio of radar absorbers"~~ | ~~Behind IEEE~~ — **resolved 2026-09-05**, retrieved outside Xplore and read directly | ~~The original statement of the thickness/bandwidth bound, never read~~ — now read first-hand. Equations (6), (7), (9), (10), (14), all constants and **all four stated assumptions** are quoted verbatim in [`rozanov-bound-primary-source.md`](./rozanov-bound-primary-source.md). The decisive one the restatements did not carry: the bound assumes the absorber is **"overlying a perfectly reflecting plane"** at **normal incidence** | #129, #110, #133 |
| **A 2025 Wiley paper on absorber quality criteria** | HTTP 403 | Explicitly on this subject. The critique of `RL_min` as a scoring metric currently rests on **secondary summaries** of it | #110 |
| **IEEE Std 1597.1-2008/2022 & IEEE Std 1597.2-2010** (Feature Selective Validation) | Behind IEEE | The actual standard #110/#168 chose for judging Example 3's reproduction against Landy's curve — read only through consistent secondary-source description, never the primary text. #168's exact ADM/FDM/GDM implementation waits on this | #110, #168 |
| **Weile, D. S., Michielssen, E. & Goldberg, D. E. (1996)**, "Genetic algorithm design of Pareto optimal broadband microwave absorbers," IEEE Trans. EMC 38(3):518–525 | Behind IEEE | The foundational GA-minimax absorber paper backing #110's worst-in-band objective; read only via secondary-source description | #110 |
| **Michielssen, E., Sajer, J.-M., Ranjithan, S. & Mittra, R. (1993)**, "Design of lightweight, broad-band microwave absorbers using genetic algorithms," IEEE Trans. MTT 41(6):1024–1031 | Behind IEEE | A second, independent minimax-absorber-optimization precedent for #110; read only via secondary-source description | #110 |
| **JOSA B / Optica** | Not previously recorded as blocked; full text unreachable this pass | Smith & Pendry, "Homogenization of metamaterials by field averaging" (2006) — the field-averaging basis for effective-parameter retrieval. Not on arXiv, not on the Duke group page. #111's homogenisation-validity case currently rests on Alù, Koschny and Menzel instead, which agree with each other | #111 |
| **ScienceDirect**, a 2015 waveguide characterisation of **BASF Elastollan 1185A** | HTTP 403 (same block as the existing ScienceDirect row) | An X-band (8.2–12.3 GHz) permittivity measurement for a **named, orderable TPU grade**. This is the repo's oldest standing substrate-data complaint — every TPU figure held today is for generic or unnamed material, against a BASF unfilled range spanning tanδ 0.040–0.140 at 1 MHz | #114, #127 |
| **Tretyakov & Simovski (2003)**, "Dynamic model of artificial reactive impedance surfaces," *J. Electromagn. Waves Appl.* **17**(1) 131–145 | Closed access. **Confirmed by two independent indexes that no repository copy exists**: Unpaywall `is_oa:false, has_repository_copy:false, oa_locations:[]`; Semantic Scholar `CLOSED` | Costa's ref [35] — the **original statement of eq (10)**, the thin-spacer capacitance correction. Three things are stranded behind it: (a) whether the prefactor is `2Dε₀/π` (as the 2013 paper prints) or `2Dε₀ε_r/π` (as Costa & Borgese 2021 restate it, citing the same source) — **a factor of `ε_r` on the size of the bias the fast tier carries**; (b) whether an **inductance** correction was ever written, asserted three times across the Costa papers and published nowhere; (c) eq (10)'s stated validity range in the author's own words. Equation, symbols and a recomputation are in [`costa-thin-spacer-correction.md`](./costa-thin-spacer-correction.md), read off a 400 dpi render | #190, #128, #111 |
| **APS / Physical Review Letters**, Landy et al. (2008), "Perfect Metamaterial Absorber," *PRL* **100**:207402 | HTTP 403 to automated fetch. **Routed around**: the arXiv e-print carries the authors' LaTeX source and original figure files, which is a better source than the typeset PDF for this purpose | Whether the published version has **supplementary material** the preprint lacks — `UNKNOWN`, an absence in our access rather than in the world. Bounded risk: the arithmetic in [`example3-frequency-discrepancy.md`](./example3-frequency-discrepancy.md) does not depend on it, since **no** `εr` in the FR4 range closes the 2.28 GHz gap. Landy states no permittivity in the preprint at all | #142, #116 |

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
- **`pymupdf` extracts text, fonts and embedded figures.** (**Corrected 2026-09-05:** it is *not* pre-installed in every session — a research agent found it absent and `pip install`ed it without trouble. The capability holds; the "already there" claim does not.) One
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

25. **`docs/absorber-scoring-conventions.md` says Example 3 is ground-backed.
    Three other places in this repo say it is not, and they are right.**
    That document asserts it at lines 14, 48, 62 and 349, and collapses
    absorptivity to `A = 1 − |S₁₁|²` on the strength of it — calling the result
    *"the single most useful simplification in this document"*, tagged
    `LITERATURE-SUPPORTED, and unanimous`. It is not unanimous.
    `docs/seven-example-design-unknowns.md` lines 184–186, 202 and 345 record
    Example 3 as **two-port, Floquet on both faces, no ground plane**, with the
    reason stated: *FIG. 7G plots a non-zero Transmission trace, so the
    structure is not metal-backed*. **Correction 18 above independently agrees**
    — it settles FIG. 7G's y-axis as carrying a `|S₂₁|` Transmission trace and
    absorbance as `1 − |S₁₁|² − |S₂₁|²`, which is the two-port form. And Landy
    et al.'s device suppresses transmission with a **cut wire**, not a ground
    plane, which is why a transmission trace exists at all.
    **The likely cause is a category error, not a slip.** ADR-0017 makes skins
    *this programme builds* print their own reflector, so our own designs really
    are one-port. Example 3 is **somebody else's device**, used as the blind
    reproduction target, and the programme's default was applied to it.
    **Consequences, both live:** #133's fixture, format and cost conclusions
    (one-port `.s1p`, "no new format needed", US$2,300–4,800 chamber) were
    scoped for the wrong measurement; and Rozanov's bound requires a
    perfectly reflecting backing (correction 26), so #129's Example 3 headroom
    figures rest on an assumption that example does not satisfy.

    **Landed in the document 2026-09-08** (#203, under ADR-0024): all four
    sites corrected in `absorber-scoring-conventions.md`. The general
    convention was left standing — the one-port collapse really is valid for
    a ground-backed absorber, and ADR-0017 makes the programme's own skins
    exactly that. What was removed is the claim that the **anchor** is one of
    them. Because the error is re-derivable (anyone applying the programme's
    own default would make it again), the corrected passage carries an inline
    inoculation naming ADR-0017 and this entry, per ADR-0024's format. §5.3's
    dependent conclusion — *"the Rozanov limit is not binding for Example 3"* —
    was re-aimed rather than deleted: it is sound for a ground-backed skin and
    was never a fact about the anchor, which Rozanov does not govern at all
    (correction 26).
26. **Rozanov (2000) has now been read first-hand, and it is metal-backed by
    assumption.** The bound's own opening sentence, verbatim: *"We consider a
    slab of thickness d, permittivity ε = ε′ − iε″, and permeability
    μ = μ′ − iμ″, **overlying a perfectly reflecting plane** and illuminated at
    **normal incidence** by a monochromatic plane wave."* Eq. (6) is stated for
    *"any **metal-backed** magnetodielectric layer"*. Two open-access
    restatements had been used in its place and neither carried this as
    prominently. Full equations, constants and the four stated assumptions are
    in [`rozanov-bound-primary-source.md`](./rozanov-bound-primary-source.md).
    Also recovered, and absent from the restatements: the ultimate `d/Δλ` at
    −10 dB is **1/13.9** for the best possible non-magnetic narrow-band
    absorber against **1/3.2** for a plain Dallenbach screen — so clever design
    buys a factor of ~4.3 and no more, and **magnetic materials are the only
    way to move the limit at all**.

27. **`8.5–10.5 GHz` is FIG. 7G's plot axis, and it is being used as Example 3's
    requirement band.** The patent's own prose, retrieved verbatim: *"The plot
    of FIG. 7G shows simulated scattering performance of the EM skin 700 over
    **select frequencies ranging from 8.5-10.5×10⁹ Hz (a sub-band of the
    X-band)**."* That describes what was plotted. Nothing states the device is
    required to absorb across it. It nonetheless now appears as a specification
    in `docs/absorber-scoring-conventions.md:374` — *"The requirement is
    '≥90% absorption across 8.5–10.5 GHz'"* — and at :189, :376, :390, in
    `docs/HANDOFF-metamaterial-printing-grill.md:73`'s band column, and behind
    **every headroom number** in `docs/absorber-thickness-bandwidth-bound.md`
    (:39, :301, :304, :774–775). **Rozanov's bound is linear in Δλ**, so each of
    those scales one-for-one with an axis label.
    **This is correction 20's failure mode, second instance — and correction 21
    predicted it in this exact file.** 21 recorded the −10 dB threshold as
    "not yet an error, #110 is open". The band is the same move and it has
    already fired. The rule stands unchanged: *a number read off a plot is not
    a requirement.*

    **Landed in the documents 2026-09-08** (#203, under ADR-0024).
    `absorber-scoring-conventions.md`: the two scoring recommendations no
    longer state a band for the anchor, and §5.3's worked figures are re-aimed
    at a ground-backed skin. `absorber-thickness-bandwidth-bound.md`: a
    governing note in the bottom line, and every prose claim about "where
    Example 3 sits" re-aimed — that document also fails its **own** stated
    assumption 4 (*"Backed by a perfect electric conductor"*) when applied to
    the anchor, which correction 26 established after it was written. Its
    literal script output is left verbatim as the record of what the script
    printed, with the block labelled. `HANDOFF-metamaterial-printing-grill.md`
    is marked in its own `~~struck~~ **corrected**` house style rather than
    rewritten: ADR-0024 exempts it as an explicit historical record of what
    was believed when. **The arithmetic was correct throughout and none of it
    changed** — only what it is about.
28. **The FR4-permittivity explanation for the patent-vs-Landy 20% frequency gap
    is dead by arithmetic.** The patent states its own simulation inputs:
    *"a 0.87 mm-thick absorber metamaterial layer using FR4 dielectric layer of
    permittivity of 4.8 and loss tangent of 0.017."* Resonance goes as
    `1/√ε_eff`, so the observed `11.5/9.2 = 1.25` needs an effective-permittivity
    ratio of **1.5625**. FR4's *entire* documented X-band spread (≈3.8–5.5,
    Djordjević et al., IEEE T-EMC 43(4):662–667, 2001) gives at most **1.447**,
    i.e. a 20.3% shift under an unrealistic 100%-field-in-substrate assumption;
    a realistic 4.8-vs-4.3 comparison gives **5.7%**. Also ruled out: figure
    misattribution (the FIG. 7G caption ties its assumptions explicitly to
    EM skin 700), and measurement-versus-simulation scatter (Landy's own
    simulated and measured peaks agree to **0.2%** — 11.48 vs 11.5 GHz).
    **Genuine absence, routes stated:** the patent contains no figure-generation
    methodology for Example 3 — full text searched via FreePatentsOnline for
    "boundary", "periodic", "Floquet", "infinite array", "CST", "HFSS",
    "solver"; none appear near Example 3. #142 stays open with a much smaller
    hypothesis space.

29. **FSV was chosen for #116/#168 on the grounds that the frequency
    disagreement is small. It is about five linewidths.** #110 selected Feature
    Selective Validation over RMS error specifically because FSV *"avoids
    over-penalizing"* the patent-vs-Landy shift, and #168 restates it as *"a
    small resonance-frequency shift."* **Landy's own resonance is 4% wide
    (FWHM)**, so a ~20–25% offset separates the two curves by roughly five of
    their own widths — they barely overlap, and a feature-matching metric may
    report near-total disagreement exactly as RMS would. The choice may still be
    right for other reasons; the stated reason needs re-testing before #168
    builds on it. Related: **no FSV implementation exists in any language**, and
    IEEE's own FSV committee page states no reference implementation ships with
    the standard — a properly established absence, not a failed search.

### Found while grilling the map itself (2026-09-06)

Four corrections about the map's own text rather than about the domain. The
map is an index of decisions; when an index starts asserting what was *built*,
it rots exactly the way `CLAUDE.md`'s preamble warns.

30. **Map #104's Decisions-so-far claimed a field had shipped that does not
    exist.** The entry for #112 read *"Ships now as an additive
    `input_provenance` field on `success_score()`'s output."* The string
    `input_provenance` **occurs nowhere in the repository** — not in
    `designs/success_score.py`, not in any test, not in any document. The
    result dict (`success_score.py:568–584`) carries `provenance`,
    `target_provenance`, `target_status` and `note_provenance`; the measured
    value itself arrives at line 448 as a bare `actual_value: float` with no
    provenance tag at all. The same sweep found #117's two *blocking* model
    changes equally unbuilt: `TargetComparator` (`requirement_targets.py:113`)
    still has exactly `EQUALS` / `AT_LEAST` / `AT_MOST` at lines 129–131, so
    there is **no `ONE_OF` comparator**, and no optional second (objective)
    value anywhere in the module. **The decisions are sound and remain
    recorded; only the claim that they shipped was false.** Rule adopted on the
    map as a result: *Decisions-so-far records the decision, never the
    implementation status.* Contrast #148's Material-property library, which
    genuinely is built, in `designs/material_properties.py`.

31. **The `GATED_STEPS` citation was wrong, and the ungated-step count it
    implied was wrong with it.** The map's standing preference cited
    `orchestration/design_loop.py:136`. **Line 136 is
    `ARCHITECTURE = "architecture"`**, a `DesignStep` enum member;
    `GATED_STEPS` is assigned at **lines 160–161** and contains exactly three
    members — `ARCHITECTURE`, `MEASUREMENT`, `REDESIGN_DECISION`. The
    preference also credited ADR-0014 for the gating, which governs something
    else: `orchestration/solver.py:405` defines `_ORDERED_UNGATED_SPAN` as
    `(ANALYSIS, SIMULATION, OPTIMIZATION)` — **CORRELATION deliberately
    excluded**, with the reason in the module's own comment at `solver.py:78`
    and `:89`. So four steps are *ungated* but the solver drives only three:
    correlation compares a simulation against a measurement and has nothing to
    work on until a gated `MEASUREMENT` has run. *In plain terms: an overnight
    run reaches three steps, not four, and cannot compare itself to reality.*
    Bears on #125, which is about what such a run hands the morning reviewer.

32. **The map's Destination has been contradicted by shipped code since PR #86
    merged, and the map recorded it nowhere.** The Destination requires a
    periodic-surface degree of freedom "rather than patch length."
    `orchestration/design_loop.py` calls `patch_resonant_frequency_hz` at lines
    503 and 513 inside `_handle_analysis` (line 497), and
    `optimize_patch_length_for_target_frequency` at line 613 inside
    `_handle_optimization` (line 605) — both rectangular microstrip patch
    antenna formulas. `_STEP_HANDLERS` (line 751) is a flat one-handler-per-step
    table with **no family dimension**, and `design_family` appears only as an
    unvalidated string recorded at ARCHITECTURE (line 434), a fact the code's
    own comment at 424–433 states outright. *In plain terms: the loop still
    tunes a design by stretching a rectangle, and a printed metamaterial has no
    rectangle to stretch.* Raised in a comment on the map in September with a
    proposed fog entry; **the entry was never added**, so for three months the
    map neither knew nor said. Now ticketed.

33. **Correction 7 and #111's thickness correction disagree about MXene's skin
    depth by ~1.8×, and neither cites a conductivity.** Correction 7 above says
    a ~10 µm printed film is *"already ~1.65 skin depths at 10 GHz"*, hence
    opaque, hence *"thickness is a dead knob."* Map #104's 2026-09-05
    correction to the conductor-thickness preference says MXene's **3δ is
    ≈33 µm**, i.e. δ ≈ 11 µm, which puts the same 10 µm film at **~0.9 δ** —
    below the regime where thickness stops mattering, making thickness *linear*
    in sheet resistance and the strongest lever the process has. Both cannot be
    right: δ goes as `1/√σ`, so a 1.8× disagreement in δ is a ~3.3×
    disagreement in the assumed conductivity, and MXene's printed conductivity
    genuinely spans that much between grades and ages (see the ink-handling
    figures on the map). **Recorded, not resolved** — it needs one stated
    conductivity at one stated frequency, and it changes whether MXene has a
    thickness knob at all. Note both routes still converge on #128's finding
    that for a *lossy* element the aspect ratio, not the film thickness, is the
    knob that reaches the target — so this is a live discrepancy about MXene,
    not a threat to that conclusion.

### Found by reading every comment on every ticket (2026-09-06)

Six more, from a sweep of the comment threads on all thirty-seven tickets
rather than their bodies. Most were already written down *somewhere* — on
the ticket that found them — and had never reached the map, a document, or
this list.

34. **The patent names neither MXene, nor silver, nor "ink."** Full-text
    checks of US12089385B2 from two independent sources return **NOT
    PRESENT** for `MXene`, `silver`, `ink` and `conductive material`; the
    only conductors named are **copper and gold**. So any argument of the
    form "the patent allows silver, copper, or MXene" is unsupported. #105's
    decision is untouched — MXene is a candidate scored on merit, which
    never needed the patent's endorsement — but the justification must not
    lean on the patent. Confirmed present and verbatim in the same checks:
    1–2 mm thickness, 8.0–12.0 GHz, `R = T(50/r − 1)`, `R = 3T`. Found on
    #113.

35. **`docs/mxene-voltera-nova-printability.md` attributes its central
    printability figures to the wrong paper, about six times.** The 120 µm
    line width and the 6,260 → 6,900 S/cm conductivity are **Shao et al.
    2022**, cited throughout as "Song et al." Worse in the same document:
    MXene's widely-quoted **"3 µm" figure is a line *gap*, not a line
    *width*** — the achievable width is 120 µm, forty times larger. *In
    plain terms: one number says how finely two printed lines can be
    separated, the other how thin a single line can be, and they were being
    used interchangeably.* They are enforced at different points in a
    design rule, so the conflation is not cosmetic. Found on #115.
    **Landed in the document 2026-09-08** (#203, under ADR-0024): all ten
    citations corrected. The attribution was verified first-hand against
    PMC9184614 rather than taken from this entry — that record confirms
    **Shao** as first author of *Nat. Commun.* **13**, 3223 (2022),
    DOI 10.1038/s41467-022-30648-2, and confirms all three figures
    (120 µm line width; "line gaps ranging from 3 to 30 μm"; 6260 S cm⁻¹ at
    N = 2, rising to 6900 in low humidity). Everything in the original
    citation except the surname was already correct. The gap-versus-width
    half of this correction was **already** handled in the document at
    :8, :79 and :90, and needed no change.

36. **Rejected alternatives are destroyed, not merely unindexed.**
    `orchestration/tooling.py:223` hardcodes `"alternatives": []` into every
    decision record regardless of step input, so what a design considered
    and rejected never reaches the database at all. #125's own earlier
    comment claimed the field "already stores rejected options today but is
    write-only" and then falsified itself. Three tickets (#125, #150, #151)
    assume that data survives. Related and separately filed as ~~**#167**:
    `design_family` is *required* by the state machine
    (`design_loop.py:434`) and then **dropped before the database** —
    `_flush_target_for` (`tooling.py:216–227`) does not carry it and
    `decision_records` has no such column (`db/schema.sql:101–112`).~~ —
    **resolved 2026-09-07**: `decision_records.design_family` (a nullable
    column, `db/schema.sql`) plus `_flush_target_for`/`_flush_decisions`
    (`orchestration/tooling.py`) now persist it for every
    architecture_decision/redesign_decision row, carrying the value
    forward onto a REDESIGN_DECISION row that states no design_family of
    its own. The **rejected-alternatives-destroyed** finding above this one
    is untouched by this fix.

37. **Landy's real build is a five-part laminate, not a single slab.** The
    fabricated device is **FR4 / adhesive / FR4 / adhesive / FR4**, with
    ~0.06 mm adhesive layers — not the one 0.72 mm sheet of εr 4.8 FR4 that
    a reproduction modelled from the patent's own stated simulation inputs
    would build. Anyone reproducing Example 3 from the patent therefore
    models a different physical object from the one that was measured.
    Bears directly on #142's ~20% frequency discrepancy and on #168's
    curve-comparison spec. Found on #116.

38. **"At a 10 dB requirement every element family surveyed is feasible" is
    contradicted by #138 and was being carried as settled.** #130's
    corrected super-cell rule produced that headline. #138 then found that a
    0.4 λ square patch has **no feasible N on a 6 λ coupon even at 10 dB** —
    it becomes feasible only on a panel around 30 λ. The map recorded the
    *cause* of the correction ("no feasible N is a statement about part
    size, not about the alphabet") while still stating the conflicting
    headline as fact. The panel-fit constraint `2·N·p ≤ L` binds first on a
    coupon, so feasibility is a claim about a **part size**, and quoting it
    without one is the same "measurement without its box" failure this list
    records elsewhere.

39. **Six ticket resolutions were written into comment threads and never
    recorded as decisions.** #124 (material commitment is not gated at
    ARCHITECTURE — *"the premise does not survive contact with the
    schema"*), #152 (defer: **zero** named consumers exist in code, and two
    of the four it named are positively misidentified), #129 (dead as
    posed; the surviving question has a worked recommendation), #113 (a
    glossary edit, nothing to decide), #98 (investigated, correctly
    blocked), and #128 (a full proposed resolution awaiting acceptance).
    *In plain terms: the answers existed; nothing had promoted them from a
    comment into anything a later session would read.* This is the failure
    the map's "a decision is an ADR, or a correction to one" rule exists to
    close, and it is why the frontier looked far wider than it was.
40. **`rf_tools/calculations.py`'s `patch_effective_permittivity` guard named
    the material, not the formula.** Its `eps_r <= 1` check raised *"Substrate
    dielectric constant eps_r must be > 1"* — stated as a physical law about
    substrates, when the real constraint is that Hammerstad's fringing-field
    fit (the formula this function evaluates) is only defined for `eps_r > 1`,
    the same file naming its own W/h validity limit correctly eight lines
    below. Fixed in PR #196: the message now names the formula. Found by
    PR #196's own analysis of `docs/fabrication-capability-and-ink-library-spec.md`.
41. **`docs/requirement-derived-thresholds.md` claimed the Python hardcodes
    no thresholds — false.** The tree hardcodes roughly 25 bounds, in the one
    document whose purpose is stopping exactly that. `success_score.py`
    itself doesn't (it takes `target_value`/`tolerance` from its caller), but
    that's a narrower claim than the document made. Corrected in PR #196; a
    full enumeration of the ~25 bounds is not yet done and is fog, not a
    ticket, until someone has reason to need the list.
42. **`CONTEXT.md` said a process change "invalidates" alphabet entries;
    #132 said entries never go stale. Both were on the page.** The
    glossary's Element/Coding-Alphabet library entry read *"a pitch or
    validity-box change invalidates the whole alphabet's entries, not one
    symbol's"*, while #132 read *"this run does not produce results that
    later 'go stale'; it produces entries that are valid for exactly the
    conditions they were printed under, and a different condition is a
    different entry."* One expires entries, the other says they merely
    stop matching. **ADR-0027 adopts #132's model** and corrects the
    glossary. *In plain terms: an old letter is not wrong now — it is
    still right, about a machine you no longer own.*

    **A second defect fell out of the same reading: the key could not
    express the rule #132 calls mandatory.** It was `(element family,
    substrate stack, frequency band, incidence-angle range)` — carrying
    no ink, film thickness, cure or machine — so the carbon and MXene
    versions of one shape, which #132 insists are *"two letters, not one
    letter under two conditions"*, collided on a single key. The store
    also could not answer "which entries came from the old printer," the
    one question that matters when equipment changes. ADR-0027 adds a
    **Process record** and keys on a reference to it.

### Found by searching for the formula rather than trusting our own recomputation (2026-09-08)

43. **Costa's eq (10): the two published forms differ by `ε_r/ε_eff` = 1.487,
    not by `ε_r` = 2.9 — the "triples the bias" claim was wrong.**
    `costa-thin-spacer-correction.md` §7, #190's resolution comment, #234 and
    the #245 spec all reported the 2021 `ε₀ε_r` form as **+6.28%** capacitance
    and a **−3.01%** frequency shift (9.699 GHz), against **+2.17%** / −1.07%
    for the 2013 `ε₀` form. The correct figures are **+3.22%** and **−1.57%**
    (9.843 GHz).

    **The transcription was never wrong; the composition was.** The 2013 form
    substitutes into the **unloaded** `C₀`, which eq (6) then multiplies by
    `ε_eff = (ε_r+1)/2`. The 2021 form subtracts from the **already-loaded**
    capacitance, so no `ε_eff` ever reaches it. Computing the 2021 correction
    as a fraction of the *unloaded* `C₀` — as §7 did — double-counts the
    permittivity. Net effect on the loaded capacitance is `ε_eff·δ` for 2013
    and `ε_r·δ` for 2021, where `δ` = 1.4940 fF is the shared base term.

    *In plain terms: both papers say the same thing about how much extra
    charge the cell stores. They disagree about whether the substrate's
    permittivity has already been applied by the time you add it, and we
    applied it twice.*

    **What makes this a documentation failure rather than a research one:**
    §3 of `costa-thin-spacer-correction.md` **already stated it correctly** —
    *"Their eqs (7)–(8) also apply the correction to an already-loaded
    capacitance, so no later `ε_r` arrives"* — and §7 of the same document
    then computed it the other way. The document contradicted itself for a
    day, and the wrong half was the half that got quoted into three issues
    and a spec.

    Settled from the 2021 paper's **LaTeX source** (arXiv:2102.10666,
    `paper_arxiv_v2.tex`), which states both the correction and the equation
    consuming it verbatim — `LITERATURE-SUPPORTED`, an upgrade on the eye-read
    400 dpi render the equation itself rests on. **A web-search summary of the
    same paper dropped the `ε_r` entirely**, which would have sent the
    correction the other way; the source settled it and the summary did not.
    *Search results are a pointer to a primary source, never a substitute for
    reading it.*

    **It also narrows #234 and tilts it.** The dispute is worth 1.49×, not 3×.
    And the physical argument now has a mechanism behind it: a patch-to-ground
    capacitance whose field lies wholly inside the substrate should carry
    `ε_r`, where the air-straddling gap capacitance carries `ε_eff` — the two
    entering the circuit at different points is exactly what that asymmetry
    predicts, which is a point in the 2021 form's favour rather than a coin
    flip.

44. **Two of three author lists in `example3-inventor-publications.md` were
    invented, under a label claiming they came verbatim from the patent.**
    The doc recorded the patent's three cited absorber papers as *"Gu, Chen,
    Zhang, Xu, Ma, Wang, Zhang & Zhao"*, *"Ghosh, Bhattacharyya, Chaurasiya &
    Srivastava"* and *"Singh, Tyler, Zhang, Azad & Chen"*, labelled **"Cited
    verbatim from the patent's References Cited."** Checked against Crossref's
    publisher-deposited metadata (#246):

    | Paper | Recorded | Actual |
    |---|---|---|
    | Gu | Gu, Chen, Zhang, Xu, Ma, Wang, Zhang & Zhao | **Gu, Barrett, Hand, Popa & Cummer** (Duke ECE) |
    | Ghosh | …**Chaurasiya**… | …**Kaiprath**… (other three correct) |
    | Singh | Singh, Tyler, Zhang, Azad & Chen | **Singh, Korolev, Afsar & Sonkusale** (Tufts) |

    **The label was wrong twice over.** The patent prints only *"Gu et al."*,
    *"Ghosh et al."* and *"Singh et al."* — **no author lists at all**, at
    either `us_patent_12089385B2.txt` line 83 or line 1022. So names described
    as cited verbatim from it could not have come from it. Titles, journals,
    volumes, issues, pages and years were all correct; only the authors, the
    one field the patent never supplied, were wrong.

    *In plain terms: where the source said nothing, the note filled the gap in
    and then claimed the source for it.*

    **The failure is the label, not the names.** A wrong author list is a
    nuisance; a wrong list wearing a provenance claim is a trap, because the
    next reader has no reason to re-check it. The substituted names are
    plausible — "Chaurasiya" is a real frequent co-author of Ghosh,
    Bhattacharyya and Srivastava on other papers, and "Azad & Chen" are real
    co-authors on the patent's *Grady et al., Science* reference two lines
    away — which is exactly what makes them survive a skim.

    **Blast radius, recorded because it is the argument for the rule.** The
    error propagated into issue #246's body and was then briefed to three
    research agents as fact. Two of them independently found it while
    verifying their own paper. Nothing downstream depended on the names, so
    the cost was one wasted access route — a sibling agent hunted OSTI and
    LANL for Singh on the strength of the fabricated "Azad & Chen" Los Alamos
    attribution, for a Tufts paper with no DOE tie.

    Fixed at the claim with the wrong lists struck through and DOIs added, per
    **ADR-0024**.

45. **The patent's three cited absorber papers are cited as alternatives it
    did *not* build, not as Example 3's source.** `example3-frequency-
    discrepancy.md` §2.4 said they sit *"precisely where a reader would expect
    the source of the design to be named"*, and #246 was written on that
    premise. Read directly at `us_patent_12089385B2.txt` lines 1020–1027, the
    citation is a generic *"See, e.g."* hung on *"In other embodiments… other
    combinations such as electrically coupled LC resonator (ELC) and split
    ring resonators (SRRs)"* — topologies the patent explicitly did not use —
    one sentence after it states Example 3 is ERR-plus-wire-resonator.

    *In plain terms: we read the footnote as pointing at where the design came
    from. It was pointing at things the patent considered and didn't do.*

    **The absence of Landy is unaffected and still real**; what fell is the
    inference hung on the citations' position. #246 read all three papers
    anyway and excluded all three on frequency and topology, so the premise
    error cost nothing but confirmed the ticket's own stated counterweight —
    *citation is not derivation* — which had been written in as a caution and
    turned out to be the answer.

    Two findings survive the correction and cut the other way: **all three
    cited papers cite Landy** (Gu ref 9, Ghosh ref 3, Singh ref 1, each
    verified by DOI), and **Gu's authors are Duke ECE — Landy's own
    department**. The patent adopts all three *"in their entireties"*, so its
    cited literature leads straight to Landy while its reference list omits
    him.

    Fixed at the claim in `example3-frequency-discrepancy.md` §2.4 per
    ADR-0024. Full account: `example3-cited-absorber-papers.md`.

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
