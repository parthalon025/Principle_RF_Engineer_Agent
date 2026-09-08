# The patent and Landy disagree by 20% on the same geometry — why?

**Research date:** 2026-09-08
**Ticket:** [#142](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/142) — decides an input to [#116](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/116); follows [#138](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/138)'s identification of Example 3 as Landy et al.; part of [#104](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/104).
**Question:** US12089385B2's Example 3 and Landy et al. (2008) describe a metamaterial absorber with **every dimension matching to the digit**, yet report it at **~9.2 GHz** and **11.5 GHz** respectively. Which number should #116 score a reproduction against, and what explains the gap?

Provenance tags are `CONTEXT.md`'s ladder — `MEASURED` → `SIMULATED` → `CALCULATED` →
`MANUFACTURER-SPECIFIED` → `LITERATURE-SUPPORTED` → `INFERRED` → `ASSUMED` → `UNKNOWN`.

Every source below was **retrieved and read in this session**. Nothing is cited from memory,
and nothing is cited from a secondary write-up. §6 lists what could not be fetched.

---

## Bottom line up front

**1. The gap is real, it is 19.9%, and none of the four candidate explanations survives.**
Landy's *simulated* and *measured* peaks are both at 11.5 GHz. The patent's FIG. 7G null
digitises to **9.200 GHz** in *both* the granted patent and the pre-grant publication. The
geometry is identical in all eight dimensions **including the 0.72 mm layer separation**.

**2. Explanation 2 — "the patent redrew Landy's simulation, not his measurement" — is dead,
and it died cheaply.** Landy states both numbers outright: simulated **11.48 GHz**, measured
**11.5 GHz**. They agree with each other to 0.2%. And reading his *original figure files* —
recovered from the arXiv e-print tarball, not a scan — shows the exclusion is far stronger than
a mismatch of peak positions. **At 9.2 GHz all three of Landy's curves show near-total
reflection and essentially zero absorbance.** The band 8–11 GHz is featureless in every one of
them. The two documents do not disagree about *where a peak sits*; at 9.200 GHz they disagree
about *which way the device behaves* — the patent absorbs ~95%, Landy reflects ~96%. See §1.5.

**3. Explanation 1 — "different FR4 permittivity" — cannot carry the gap, and Landy never
states a permittivity to compare against.** The word "FR4" appears five times in Landy;
a value for it appears **zero** times. Meanwhile the arithmetic caps the mechanism: moving
from a typical FR4 `εr` = 4.4 to the patent's asserted 4.8 explains **21% of the gap**
(11.48 → 10.99 GHz), not all of it. Closing it entirely would need the patent's substrate to
be `εr` ≈ **6.85**, which is not FR4 and is not what the patent says.

**4. Explanations 3 and 4 are excluded by direct re-reading.** FIG. 7G is tied to Example 3
by three separate paragraphs of prose, and the digitisation was re-done from scratch here,
numerically rather than by eye, landing on 9.200 GHz in two independent documents.

**5. The patent does not cite Landy — anywhere.** The complete 18-entry "Other References"
list was retrieved. Landy et al. is absent from it, absent from the examiner's US patent
references, and absent from the description's in-text citations, which cite three *other*
absorber papers at exactly the point where Landy would belong.

**6. One new candidate emerged that the ticket did not list, and it has the right sign.**
The patent's metallisation is **0.15 mm thick**; Landy's was **17 µm** — 8.8× thinner. Thicker
metal adds sidewall capacitance across the resonator's 0.6 mm gaps and across the 0.2 mm gap to
the neighbouring cell, and more capacitance means a *lower* resonance. The direction is right.
**The magnitude cannot be established without a solver, and this document does not guess it.**

**7. Recommendation for #116: score against the patent's FIG. 7G (9.2 GHz), not Landy's
11.5 GHz.** Reasoning in §5. The short version: #116 is reproducing *the patent's Example 3*,
the patent never claims to be reproducing Landy, and a target you can trace to the document
under reproduction beats a better-provenanced number describing a device the patent may not
actually have simulated.

---

## 1. What Landy actually says

**Source retrieved:** the authors' own LaTeX source for arXiv:0803.1670, downloaded from
`https://arxiv.org/e-print/0803.1670` and extracted (`text_preprint.tex`, 770 lines). This is
the most primary form available short of the journal's typesetting — it is the manuscript as
the authors wrote it. Only **one version (v1)** exists on arXiv. Published as *Phys. Rev.
Lett.* **100**, 207402 (2008).

### 1.1 There are two geometries in the paper, not one

This is the detail that reframes the whole question, and it is easy to miss.

**The ideal (simulated-only) absorber**, verbatim:

> "The simulated metamaterial had the dimensions, in millimeters, of: a₁=4.2, a₂=12, W=3.9,
> G=0.606, t=0.6, L=1.7, H=11.8, and the metamaterials elements were separated by 0.65 in the
> ẑ direction."

> "The reflectance is large ~97% near the bounds of the plot, 9GHz and 14GHz, but there is a
> minimum of 0.01% at ω₀≡11.65GHz."

**The fabricated absorber**, verbatim:

> "we fabricated a metamaterial which deviated slightly from the ideal absorber and had the
> dimensions, in millimeters, of: a₁=4.2, a₂=12, W=4, G=0.6, t=0.6, L=1.7, H=11.8."

> "The end results was that the metamaterials elements were separated by 0.72mm in the ẑ
> direction."

**The patent's FIG. 7F table matches the *fabricated* set, not the ideal one** — `W` = 4 not
3.9, `G` = 0.6 not 0.606, `h` = 0.72 not 0.65. Whoever produced Example 3 was working from the
fabricated device's numbers. `LITERATURE-SUPPORTED`.

*In plain terms: Landy designed one absorber on the computer, then built a slightly different
one because his print shop could not hold the finer dimensions. The patent copied the numbers
of the one he built.*

### 1.2 Landy's substrate: FR4, with no permittivity ever stated

Verbatim, the complete substrate description:

> "Each metallization was fabricated on a FR4 substrate with a thickness of 0.2mm.
> Metamaterials were fabricated using standard optical lithography. Photosensitized half-ounce
> copper-clad FR-4 circuit board formed the substrate material with an 17 µm copper thickness."

> "These boards where then sandwiched (using an adhesive with 0.06mm thickness) about another
> 0.2mm thick FR4 blank substrate to obtain the correct spacing."

The stack closes exactly: 3 × 0.2 mm FR4 + 2 × 0.06 mm adhesive = **0.72 mm**, which is the
stated element separation. `CALCULATED`, and it confirms the reading that the metal sits on the
two *outer* faces with 0.72 mm of dielectric wholly between them.

**On permittivity, the paper is silent.** A search of the full source for `εr`, "dielectric
constant", "loss tangent", or any numeric near them returns **no value**. The only occurrence
of "dielectric constant" in the entire paper is this, from the closing paragraph:

> "By incorporating a substrate with a highly consistent dielectric constant, we will be able
> to optimize the design at the correct resonant frequency."

That sentence is worth pausing on. It is the authors saying, in print, that **their FR4's
dielectric constant was not consistent**, and that this is *why* the design did not land where
they intended. It is an admission of substrate uncertainty — but it supplies no number, and it
cites no datasheet or reference for one. `LITERATURE-SUPPORTED` (that no value is stated).

*In plain terms: Landy tells us the board was FR4 and complains that FR4's electrical
properties wander, but never tells us what value he used. So there is no Landy permittivity to
compare with the patent's 4.8. The comparison the ticket hoped to make cannot be made from the
source, because one side of it does not exist.*

### 1.3 Landy's simulated and measured peaks — both at 11.5 GHz

Verbatim:

> "The simulated A(ω) peaks at 96% at 11.48 GHz and has a FWHM of 4% with respect to its center
> frequency."

> "Both the simulated and experimental R(ω) reach a minimum at approximately 11.5 GHz, but
> experimentally the minimum is 11%, as opposed to the simulated value of 3%."

> "The simulated and experimental curves have maximum absorbance at the same frequency,
> ω_max=11.5 GHz."

And from the abstract:

> "our experiments demonstrate a peak absorbance greater than 88% at 11.5 GHz."

`MEASURED` for 11.5 GHz; `SIMULATED` for 11.48 GHz. The two differ by **0.2%**.

### 1.4 Landy on what moves the frequency

Verbatim:

> "it is expected that the frequency location of the absorbance peak depends significantly upon
> the separation between the electric ring resonator and the cut-wire, since this distance
> determines the frequency location of the magnetic resonance."

He then reports a spacing sensitivity study around 0.72 mm with **σ = 20 µm**, and concludes:

> "Thus assembly errors in the metamaterial spacing of only 5% can easily account for the
> disagreement between the simulation and experiment"

Note the scale being discussed: a 5% spacing error broadens and shifts the curve *slightly*.
Nothing in Landy's own sensitivity analysis is remotely capable of a 20% frequency move.

### 1.5 The curves themselves, read from Landy's original figure files

The e-print tarball contains the authors' **actual figure files** — `1.jpg` … `5.jpg`, the
images the paper was built from, at up to 1223 × 948 px. These are not a scan of a printed
page and not a rasterised PDF; they are the source artwork. Reading them is the closest thing
available to looking at the authors' own plots.

Values below are read off those plots by eye and are therefore **`INFERRED`**, even though the
images are clean — the stated numbers in §1.3 remain the `LITERATURE-SUPPORTED` ones.

**What is happening at 9.2 GHz in each of Landy's three datasets:**

| Landy curve | Figure | Reflectance at 9.2 GHz | Absorbance at 9.2 GHz |
|---|---|---|---|
| Ideal geometry, simulated (d = 0.65 mm) | Fig. 2 (`2.jpg`) | ≈ **0.96** | ≈ **0.01** |
| Fabricated geometry, simulated (d = 0.72 mm) | Fig. 3(a), 4 (`3.jpg`, `4.jpg`) | ≈ **0.96** | ≈ **0.01** |
| Fabricated geometry, **measured** | Fig. 3(a), 4 (`3.jpg`, `4.jpg`) | ≈ **0.87** | ≈ **0.10** |

**Against the patent's FIG. 7G at the same frequency:** Reflectance ≈ **0.02**, Absorbance
≈ **0.95**, Transmission ≈ **0.13**. `INFERRED`.

*In plain terms: at 9.2 GHz the patent's drawing says this surface swallows almost all the
radio energy hitting it. Landy's own plots say the very same surface bounces almost all of it
straight back. That is not a peak in a slightly different place — it is the opposite
behaviour.*

Three further observations from the figure files, all `INFERRED`:

1. **There is no second resonance.** Landy's Fig. 4 plots absorbance across the full
   **8–12 GHz** span — which contains 9.2 GHz — and both the simulated (red) and measured (blue)
   traces are smooth and featureless below ~10.5 GHz, rising to a **single** peak at 11.5 GHz.
   Fig. 2 covers **9–14 GHz** and is likewise featureless from 9 to ~10.7 GHz. So the patent's
   9.2 GHz feature is not a secondary mode of Landy's structure that the patent happened to
   plot instead of the main one. **There is nothing there to plot.**
2. **The measured baseline absorbance is ~0.10, not zero**, across 8–10.5 GHz — visible as the
   blue trace's gentle ripple in Fig. 4. That is the loss floor of the FR4 plus measurement
   artefact, and it is the *only* thing Landy's device does at 9.2 GHz.
3. **The transmission levels disagree too, and independently.** Landy's simulated transmission
   (Fig. 3(b)) falls from ≈ 0.04 at 8 GHz to ≈ 0.00 near 11.3 GHz, and his measured from
   ≈ 0.06 to ≈ 0.00. The patent's FIG. 7G transmission sits at **≈ 0.13–0.17 right across
   8.5–10.5 GHz** — roughly **four to eight times higher**, and rising where Landy's falls.
   This is a second, independent signal that the object the patent simulated is **not**
   electromagnetically the object Landy built, whatever their dimension tables share.

Observation 3 deserves weight in #116's decision. A frequency shift can be argued away as a
material constant; a four-to-eightfold disagreement in how much energy passes *through* the
structure, over a whole band, cannot be. **Two structures that leak this differently are not
the same structure.**

---

## 2. What the patent actually says — re-read from scratch

**Sources retrieved:** the granted patent PDF (`US12089385B2`, 32 pages, 2,455,797 bytes) and
the pre-grant publication PDF (`US 2022/0192066 A1`, 31 pages, 2,423,105 bytes), both fetched
this session from `https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/…`. The
front-page bibliographic data and full reference list came from FreePatentsOnline
(`https://www.freepatentsonline.com/12089385.html`, HTTP 200).

### 2.1 The prose

Paragraph [0078], verbatim (extractor spacing preserved):

> "The plot of FIG . 7G shows simulated scattering performance of the EM skin 700 over select
> frequencies ranging from 8.5-10.5x10⁹ Hz ( a sub - band of the X - band ) . The simulated data
> assumed a 0.87 mm - thick absorber metamaterial layer using FR4 dielectric layer of
> permittivity of 4.8 and loss tangent of 0.017 ."

Paragraph [0073], verbatim:

> "The total thickness of the EM skin 700 is 0.87 mm ."

Paragraph [0075], verbatim:

> "functional inserts 752E₁ and 752E₂ were designed for operation in the X - band , frequency
> range of about 8.0-12.0 GHz ."

Two things follow. First, **8.5–10.5 GHz is a plot range, stated as such** — "over select
frequencies ranging from" — not a performance claim. This confirms `RUNNING-LISTS.md`
correction 27 against the source. Second, the patent's own *design* band statement is the
whole X-band, 8–12 GHz, which contains both 9.2 and 11.5 GHz and therefore discriminates
nothing.

### 2.2 The figures, read directly from the grant

FIG. 7E/7F/7G are on **Sheet 12 of 20** (PDF page 14). Rendered from the scan and read
visually. **FIG. 7F**, the Example 3 dimension table, reads:

| Symbol | Value | Landy's fabricated device |
|---|---|---|
| a₁ | 4.2 mm | a₁ = 4.2 ✅ |
| a₂ | 12 mm | a₂ = 12 ✅ |
| t | 0.6 mm | t = 0.6 ✅ |
| G | 0.6 mm | G = 0.6 ✅ |
| W | 4 mm | W = 4 ✅ |
| L | 1.7 mm | L = 1.7 ✅ |
| H | 11.8 mm | H = 11.8 ✅ |
| h | 0.72 mm | "separated by 0.72mm" ✅ |
| h₁ | 0.15 mm | (no counterpart; Landy's copper is 17 µm) |

`INFERRED` (read off a drawing). **Eight of nine values match Landy's fabricated device
exactly**, including the z-separation. This independently re-confirms #138's identification.

**FIG. 7D** settles what `h` and `h₁` label: `h` brackets the full dielectric slab; `h₁` is a
thin band at the top edge — the metallisation. This agrees with #116's conclusion (recorded in
`example3-inventor-publications.md` §5) that `h₁` = 0.15 mm is **conductor on both faces**, and
that the patent's stated 0.87 mm total is arithmetically inconsistent with its own drawing
(0.72 + 2 × 0.15 = **1.02 mm**, not 0.87). The important consequence for *this* ticket:
**the dielectric between the two metal layers is 0.72 mm in the patent and 0.72 mm in Landy.**
The spacer hypothesis is closed before it opens.

### 2.3 FIG. 7G re-digitised numerically

The earlier pass measured the traces by eye. This pass did it arithmetically, from pixels, in
both documents independently.

Method: render the FIG. 7G region at 150 dpi; locate the plot frame and the four gridlines by
column darkness; map pixel-x to frequency linearly from the 8.5 and 10.5 GHz frame edges; find
the column at which the solid Reflectance trace reaches closest to the S = 0 axis, excluding
gridline columns.

Gridlines were found at pixel x = 349, 824.5, 1305.5, 1782.5, 2258.5 — spacings of 475.5,
481, 477, 476 px, even to **1.2%**, confirming a linear axis with ticks at 8.5 / 9 / 9.5 / 10 /
10.5 GHz.

| Document | Reflectance null | Span of deepest columns |
|---|---|---|
| US12089385B2 (grant), Sheet 12 | **9.200 GHz** | 9.191 – 9.208 GHz |
| US 2022/0192066 A1 (pre-grant), Sheet 12 | **9.200 GHz** | 9.191 – 9.208 GHz |

`INFERRED`. The two agree exactly — the frame coordinates were pixel-identical, so the two
documents carry the same drawing. **The earlier ~9.2 GHz digitisation is confirmed**, and
explanation 4 (bad digitisation) is excluded.

The x-axis is also independently corroborated by the pre-grant publication's *text layer*,
which extracts the axis labels as `8.5 9.5 / f ( Hz ) x109` — machine-readable text drawn on
the figure page, not pixels measured by anyone. That is a stronger read than digitisation.

### 2.4 The patent does not cite Landy

The complete "Other References" list from the granted patent's front page — **18 entries**,
retrieved in full — contains:

- one manufacturing textbook (Kalpakjian et al.);
- ten third-party papers (Lai/Chen/Yen; Jahani & Jacob; Staude et al.; Wang et al.; **Gu et
  al.**, "A broadband low-reflection metamaterial absorber"; **Ghosh et al.**,
  "Bandwidth-enhanced polarization-insensitive microwave metamaterial absorber"; **Singh et
  al.**, "Single and dual band 77/95/110 GHz metamaterial absorbers on flexible polyimide
  substrate"; Huang/Yang/Yang; Grady et al.; Ma et al.);
- seven of the inventors' own papers (Nguyen, Zaghloul, Weiss, Anthony, Adler, Mencagli,
  Engheta), none about absorption — as `example3-inventor-publications.md` §2 already found.

**Landy et al. is not among them.** Nor does "Landy", "Sajuyigbe", "Padilla", "Perfect
Metamaterial Absorber", "Phys. Rev. Lett. 100" or "207402" appear anywhere in the retrieved
full text of either document. `LITERATURE-SUPPORTED`.

~~The absence is pointed rather than neutral. Paragraph [0077] cites **three** metamaterial
absorber papers — Gu, Ghosh and Singh — precisely where a reader would expect the source of the
design to be named.~~ The one paper whose numbers Example 3 reproduces digit for digit is the one
that is not cited.

> **CORRECTED 2026-09-08 (#246).** The struck sentence overstated where those citations sit.
> Read directly at lines 1020–1027, the patent cites Gu, Ghosh and Singh in a generic
> *"**See, e.g.**"* attached to *"**In other embodiments**, the functional inserts might also
> include **other combinations such as electrically coupled LC resonator (ELC) and split ring
> resonators (SRRs)**"* — topologies the patent explicitly did **not** use — one sentence after
> stating that Example 3 is ERR-on-top plus wire-resonator-underneath. They are cited as
> **alternatives it did not build**, not as the design's source, and the sentence closes with
> incorporation-by-reference boilerplate.
>
> **The absence of Landy is unaffected and still real.** What changes is the inference that was
> hung on the three citations' *position*. #246 read all three papers on the strength of it and
> excluded all three — see [`example3-cited-absorber-papers.md`](./example3-cited-absorber-papers.md).
>
> **All three cite Landy themselves**, and Gu's authors are Duke ECE — Landy's own department —
> so the patent's cited literature leads straight to him while its own reference list omits him.

*In plain terms: the patent lists eighteen references, including three other papers about
exactly this kind of absorber, but not the paper whose absorber it appears to have copied.*

---

## 3. The four candidate explanations, tested

### 3.1 Candidate 1 — different substrate permittivity. **Not supported, and capped by arithmetic.**

Two independent reasons it fails.

**It cannot be checked**, because Landy states no permittivity (§1.2). The comparison the
ticket proposed — "check what Landy actually states" — has the answer *he states nothing*.

**And it could not carry the gap even if it could be checked.** Taking resonance ∝ 1/√εr, with
Landy's simulated 11.48 GHz and the patent's 9.200 GHz (`CALCULATED` throughout):

| Assumed Landy `εr` | Shift factor √(4.8/εr) | Predicted patent frequency | Share of the 2.28 GHz gap explained |
|---|---|---|---|
| 4.2 | 1.0690 | 10.74 GHz | 32.5% |
| 4.3 | 1.0565 | 10.87 GHz | 26.9% |
| 4.4 | 1.0445 | 10.99 GHz | 21.4% |
| 4.5 | 1.0328 | 11.12 GHz | 16.0% |
| 4.6 | 1.0215 | 11.24 GHz | 10.6% |

Running it the other way: to land on 9.200 GHz from 11.48 GHz, the patent's substrate would
have to be `εr` = **6.54** (if Landy's were 4.2) or **6.85** (if 4.4). The patent says 4.8.

And to reach the patent's 9.200 GHz from 11.48 GHz by permittivity alone requires an `εr` ratio
of **1.557** — i.e. Landy's board would have to be `εr` ≈ **3.08** against the patent's 4.8.
No FR4 grade is 3.08; that is Rogers-laminate territory, and Landy says FR4 twice by name.

**The 1/√εr model is itself generous here**, which strengthens the conclusion. The resonators
sit on the *outer* faces with air above and below, so the field is only partly in the
dielectric and the true sensitivity to `εr` is *weaker* than 1/√εr. The real explained share is
therefore **lower** than the table's, not higher.

*In plain terms: FR4 grades vary by roughly 4.2 to 4.8, and that whole range is worth about
half a gigahertz. The disagreement is 2.3 GHz. Permittivity cannot buy the other 1.8.*

### 3.2 Candidate 2 — the patent redrew Landy's *simulation*. **Excluded outright.**

This was the cheap one, and it resolves against the hypothesis twice.

**By the stated numbers:** Landy's simulated absorbance peaks at **11.48 GHz** and his measured
at **11.5 GHz**; his ideal-geometry simulation nulls at **11.65 GHz**. All three Landy curves —
ideal simulation, fabricated simulation, measurement — sit within 1.5% of each other.
`SIMULATED` and `MEASURED`, both stated outright in §1.3.

**By the curves:** §1.5 reads the original figure files and finds Landy's simulation
**reflecting ~96% and absorbing ~1% at 9.2 GHz**, with no feature anywhere in 8–10.7 GHz. The
hypothesis requires a Landy simulated curve that peaks near 9.2 GHz. **No such curve exists in
the paper** — not as the main resonance, and not as a secondary one.

### 3.3 Candidate 3 — FIG. 7G belongs to a different example. **Excluded.**

FIG. 7G is bound to Example 3 by [0020] ("FIGS. 7A-7G show an electromagnetic skin and
performance characteristics for Example 3"), by [0072] ("FIG. 7G is a plot showing simulated
scattering performance of the skin 700"), and by [0078] (which names skin 700 and gives its
0.87 mm thickness and FR4 parameters). Its y-axis legend — Reflectance / Transmission /
Absorbance — is an absorber's legend, and no other example in the patent plots that triple.

### 3.4 Candidate 4 — the digitisation is wrong. **Excluded, twice over.**

Re-digitised numerically from pixels in two independent documents: 9.200 GHz both times
(§2.3). Cross-checked against the pre-grant publication's *text layer*, which carries the axis
labels 8.5 and 9.5 as machine-readable text. And cross-checked against the prose, which states
the 8.5–10.5×10⁹ Hz range in words.

---

## 4. What survives

**Nothing on the ticket's list.** The discrepancy is real and, on the evidence retrieved, unexplained.

Two mechanisms remain live. Neither is settled here, and both are named precisely rather than
guessed at.

### 4.1 Metallisation thickness — new, right sign, magnitude unknown

The one geometric difference between the two structures is the conductor:

| | Landy (fabricated) | US12089385B2 Example 3 |
|---|---|---|
| Metal thickness | **17 µm** (half-ounce copper, stated) | **0.15 mm** (FIG. 7F `h₁`, drawing) |
| Dielectric between layers | 0.72 mm | 0.72 mm |

That is **8.8× thicker metal**. It matters not for conduction — as
`example3-inventor-publications.md` §3 correctly notes, both are hundreds of skin depths and
electromagnetically identical *as a surface* — but for **capacitance**, which depends on the
facing sidewall area of every gap, and sidewall area is proportional to metal thickness. The
I-shape has two 0.6 mm gaps of its own, and the cells sit **0.2 mm apart** on the a₁ axis
(#138 §3). Thickening the metal 8.8× thickens every one of those capacitor plates by the same
factor. More capacitance lowers the resonance — **the direction needed**.

**The magnitude cannot be established by reading or by arithmetic.** Edge capacitance in a
resonator with fringing fields is not a closed-form quantity at the accuracy required to
distinguish "a few percent" from "twenty percent". **Settling this requires simulating the
Example 3 stack twice — once with 17 µm metal, once with 0.15 mm — and this document declines
to guess the answer.** That is the cheapest next measurement, and it is a solver run, not a
reading task.

### 4.2 The dielectric environment the patent assumed

Landy's resonators are air-clad on both outer faces. The patent describes inserts "attached to
the top and bottom surfaces of the pliable thin film" but also, in the same document, an EM
skin whose elements are "incorporated into and/or on" the film. If Example 3's simulation
*embedded* the metal — dielectric above as well as between — the effective permittivity seen by
the resonator would rise substantially beyond the bulk-4.8-versus-4.4 comparison of §3.1, and
the 1/√εr cap computed there would no longer bound the shift.

This is **speculation constrained by the source**, not a finding: the patent never states its
boundary conditions, and FIG. 7D's three-band drawing shows metal on the outer faces, which
argues *against* embedding. It is recorded because it is the only other mechanism with the
right sign, and because it too would be settled by the same solver run as §4.1.

### 4.3 A sensitivity datum from Landy himself, for calibration

Landy's two geometries differ in separation, and he reports a frequency for each. Treating it
as a crude one-variable sweep (`CALCULATED`, and **caveated**: `W` and `G` also differ between
the two, so this is not a clean sweep):

- d = 0.65 mm → 11.65 GHz; d = 0.72 mm → 11.48 GHz
- Δd = **+10.8%**, Δf = **−1.46%**, elasticity ≈ **−0.135**

*In plain terms: pushing the two metal layers 10% further apart moved the frequency about 1.5%.
Geometry in this structure is a weak lever. To move 20% by spacing alone you would need to change
the separation by something like 150%, and both documents agree the separation is 0.72 mm.*
This is the strongest quantitative argument that **the gap is not geometric**.

---

## 5. Recommendation for #116

**Score the reproduction against the patent's FIG. 7G — the ~9.2 GHz curve — and not against
Landy's 11.5 GHz measurement.**

This recommends the *worse-provenanced* number, so the reasoning has to be explicit.

**1. #116 is reproducing the patent, not Landy.** The blind fixed test asks whether this
program can re-derive Example 3 of US12089385B2. The answer key for that test is the patent's
own published curve. Substituting a different document's number changes what is being tested.

**2. The patent never claims to be reproducing Landy.** It does not cite him (§2.4). Absent a
citation, treating Landy's measurement as "the true value of Example 3" is an inference by this
program, not a statement by either source. The two documents describe structures that agree in
eight dimensions and disagree in one (metal thickness, 8.8×) and in one asserted material
constant (`εr` = 4.8 versus unstated). **They may not be the same object** — and §1.5's
transmission comparison is positive evidence that they are not, since the patent's structure
leaks **four to eight times** more energy straight through than Landy's does, right across the
band. Dimensions alone do not make two structures the same; behaviour does, and the behaviour
differs.

**3. Landy's number is better-provenanced but describes a device the patent may not have
simulated.** `MEASURED` beats `INFERRED` by two rungs *only when the two describe the same
thing* — the ticket's own condition. §3 and §4 establish that this condition is **not
demonstrated**, and §4.1 identifies a concrete physical difference between the two structures.
A high-provenance number for the wrong object is worse than a low-provenance number for the
right one.

**4. Scoring against 11.5 GHz would bake in an unexplained 20% error.** A reproduction that
correctly re-derived what the patent simulated would be marked *wrong* — and the program would
have no way to tell that failure apart from a genuine one.

**What to record alongside the choice.** #116 should carry the disagreement explicitly, not
silently pick a side:

- Target: **9.2 GHz**, `INFERRED` from FIG. 7G, digitised twice, numerically, from two
  documents (§2.3).
- Flagged: the same geometry was **measured at 11.5 GHz** by Landy et al., `MEASURED`, and the
  20% disagreement is **unexplained**.
- The warning this earns, in the terms `CLAUDE.md` requires — *what is assumed*: that the
  patent's FIG. 7G describes the geometry its own FIG. 7F tabulates. *What it costs if wrong*:
  the entire known-answer test is calibrated 20% off, and every absorber the program scores
  against it inherits the error. *The cheapest way to find out*: one solver run of the Example 3
  stack at 17 µm and 0.15 mm metal thickness (§4.1) — which discriminates between "the patent's
  figure is right and the structures differ" and "the patent's figure is wrong".

**Secondary use for Landy, which is the real prize here.** Landy's 11.5 GHz should not be
discarded — it should be promoted to a *second, independent* fixed test. It is a
**`MEASURED`, fully-specified, open-access** X-band absorber with complex S-parameters, and
this program has been looking for exactly that. Reproducing Landy's 11.5 GHz from Landy's
stated dimensions is a cleaner known-answer test than Example 3 will ever be, because its
answer key was measured on a bench rather than read off a drawing. #116's difficulty is an
argument for **adding** that test, not for merging the two.

---

## 6. Routes tried, and what could not be fetched

Recorded per `CLAUDE.md`: "no data exists" is a claim about the world; "we could not fetch it"
is a claim about us.

**Retrieved successfully this session:**

| Source | Route | Result |
|---|---|---|
| Landy et al., arXiv:0803.1670 | `arxiv.org/e-print/0803.1670` | LaTeX source, 770 lines, read in full |
| Landy et al., **original figure files** | same tarball: `1.jpg`–`5.jpg` | Authors' own artwork, up to 1223×948 px, read directly |
| Landy et al., PDF | `arxiv.org/pdf/0803.1670v1` | 6 pages |
| arXiv version history | `arxiv.org/abs/0803.1670` | **v1 only** — no revised version exists |
| US12089385B2, full scan | `image-ppubs.uspto.gov/…/12089385` | 32 pages, figures rendered and read |
| US 2022/0192066 A1, full scan | `image-ppubs.uspto.gov/…/20220192066` | 31 pages, figures rendered and read |
| US12089385B2 front page + references | `freepatentsonline.com/12089385.html` | HTTP 200, complete 18-entry list |
| US 2022/0192066 A1 text layer | in-repo `knowledge/corpus/us_patent_pub_20220192066A1.txt` | prose and figure-page text |

**Could not be fetched — named explicitly:**

| Source | Route tried | Failure |
|---|---|---|
| **PRL published version**, *Phys. Rev. Lett.* 100, 207402 | `journals.aps.org/prl/abstract/10.1103/PhysRevLett.100.207402` | **HTTP 403**. Paywalled/anti-bot. Not read. |
| **PRL supplementary material**, if any | same page | Unreachable for the same reason. **Whether a supplement exists is UNKNOWN** — this is an absence in our access, not an established absence in the world. |
| Google Patents copy of the grant | `patents.google.com/patent/US12089385B2/en` | **HTTP 503** on both WebFetch and curl — anti-bot block on this datacenter IP, as `us_patent_pub_20220192066A1.txt` already documents. Routed around via USPTO and FPO. |

**The one gap that matters.** The PRL version could, in principle, state an `εr` the preprint
omits. Two things bound the risk. First, the preprint is the authors' own complete manuscript
including the full experimental section, and PRL's length limit makes a *longer* materials
description in the published version unlikely. Second, and decisively, **§3.1's arithmetic does
not depend on Landy's `εr` at all** — no value in the physical FR4 range closes a 2.28 GHz gap.
A PRL-stated permittivity would sharpen the table; it would not change the verdict.

---

## 7. Provenance summary

| Finding | Value | Tag |
|---|---|---|
| Landy measured absorbance peak | 11.5 GHz, >88% | `MEASURED` |
| Landy simulated peak, fabricated geometry | 11.48 GHz, 96% | `SIMULATED` |
| Landy simulated null, ideal geometry | 11.65 GHz, R = 0.01% | `SIMULATED` |
| Landy substrate | FR4, 0.72 mm total, 17 µm copper | `LITERATURE-SUPPORTED` |
| Landy substrate `εr`, tanδ | **not stated anywhere in the paper** | `UNKNOWN` |
| Landy R / A at 9.2 GHz, simulated (orig. figure files) | ≈ 0.96 / ≈ 0.01 | `INFERRED` |
| Landy R / A at 9.2 GHz, measured (orig. figure files) | ≈ 0.87 / ≈ 0.10 | `INFERRED` |
| Patent R / A / T at 9.2 GHz (FIG. 7G) | ≈ 0.02 / ≈ 0.95 / ≈ 0.13 | `INFERRED` |
| Landy transmission across 8.5–10.5 GHz | ≈ 0.04 → 0.00 (sim), ≈ 0.06 → 0.00 (meas) | `INFERRED` |
| Patent transmission across 8.5–10.5 GHz | ≈ 0.13–0.17, i.e. 4–8× Landy's | `INFERRED` |
| Second resonance in Landy near 9.2 GHz | **none — band is featureless 8–10.7 GHz** | `INFERRED` |
| Patent asserted substrate | FR4, `εr` = 4.8, tanδ = 0.017 | `LITERATURE-SUPPORTED` |
| Patent FIG. 7G plot range | 8.5–10.5 × 10⁹ Hz, stated as a plot range | `LITERATURE-SUPPORTED` |
| Patent FIG. 7G reflectance null | 9.200 GHz (span 9.191–9.208) | `INFERRED` |
| Patent FIG. 7F dimensions | a₁ 4.2 / a₂ 12 / t 0.6 / G 0.6 / W 4 / L 1.7 / H 11.8 / h 0.72 / h₁ 0.15 mm | `INFERRED` |
| Dimensional match to Landy's fabricated device | 8 of 9, including 0.72 mm separation | `CALCULATED` |
| Size of the disagreement | 2.28 GHz = **19.9%** of 11.48 GHz | `CALCULATED` |
| Share explainable by FR4 `εr` spread (4.4 → 4.8) | **21.4%** of the gap | `CALCULATED` |
| `εr` the patent would need to reach 9.2 GHz | 6.54–6.85 | `CALCULATED` |
| Landy cited by the patent | **No** — absent from all 18 references and from the text | `LITERATURE-SUPPORTED` |
| Cause of the 20% gap | **unexplained** | `UNKNOWN` |
