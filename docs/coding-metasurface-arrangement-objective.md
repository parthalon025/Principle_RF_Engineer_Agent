# What Objective Makes a Coding-Metasurface Arrangement Search Non-Degenerate?

**Serves:** [#551](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/551), filed alongside [#550](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/550) (the `DIFFUSIVE` plain-checkerboard scoring spec, which this document does not touch). This is a research-only deliverable — **no implementation code was written or changed**, per the ticket's explicit scope.

**Plain-language summary of the question, before the detail:** a "coding metasurface" is a flat panel tiled with two kinds of small patches, nicknamed "0" and "1", that each reflect radio waves the same way except one flips the wave's phase by 180° (upside-down) relative to the other. Scattering the incoming wave across many small, mixed-up patches — rather than reflecting it as one big flat mirror — spreads the reflected energy out in many directions instead of sending it straight back, which is what "reduces radar cross-section" means in practice. The open question was: if a computer search tries many different arrangements of 0s and 1s to find the best-scattering one, what number should it be trying to make small (or large)? An earlier attempt at an answer turned out to always give "zero energy comes back" for any arrangement with an equal number of 0s and 1s — which cannot be right, because some balanced arrangements clearly scatter better than others. This document traces that failure to its root cause using the original 2014 paper's own text and numbers, and finds that three later papers already independently settled on the correct objective without knowing it fixes this exact problem.

---

## 1. What was re-verified this session, and how

The prior research pass (`docs/example7-coding-metasurface-scoring-recipe.md` §1.1) fetched T. J. Cui, M. Q. Qi, X. Wan, J. Zhao & Q. Cheng, "Coding metamaterials, digital metamaterials and programmable metamaterials," *Light: Science & Applications* **3**, e218 (2014), DOI [10.1038/lsa.2014.99](https://doi.org/10.1038/lsa.2014.99), via the arXiv preprint [1407.8442](https://arxiv.org/pdf/1407.8442), and reported that `pdftotext -layout` and PyMuPDF's plain text extraction both garbled the paper's own Eq. (1)–(3) math typesetting, leaving only Table I (the paper's worked numeric results) cleanly readable.

**This session re-fetched the same PDF and tried a different extraction path, as the ticket asked: rendering pages as images and reading them directly, rather than trusting any text-layer extraction.**

- `ar5iv.labs.arxiv.org/html/1407.8442` and `arxiv.org/html/1407.8442` (arXiv's newer auto-HTML rendering) both **404/redirect to the abstract page** — this 2014 preprint predates arXiv's HTML pipeline and has no rendered HTML mirror. **[verified this session]**
- The PDF was downloaded directly (`arxiv.org/pdf/1407.8442`, 25 pages, 2.06 MB) and rendered page-by-page to PNG images at up to 8x native resolution using PyMuPDF's `get_pixmap`, then read as images rather than as extracted text. **[verified this session]**

**Result: this path worked far better than the two prior text-extraction attempts, but it also surfaced a stronger and more specific finding than "extraction failed."** Eq. (2) (the directivity formula) and Eq. (3) (the RCS-reduction formula) are **fully legible and unambiguous** in the rendered page image — transcribed exactly below. Eq. (1) (the far-field array-factor sum) is a different case: **at 8x zoom, the equation's own exponent term is visibly overlapping/garbled glyphs on the rendered page itself** — not an artifact of any text-extraction tool, but a corruption baked into the PDF's content stream (almost certainly from how the original Word-equation-editor formula was embedded when the publisher or author produced this PDF). This is a materially different, more precise finding than the prior pass's "the math-typesetting characters render out of position in both extraction tools tried": **the ticket's premise that a different extraction path might recover Eq. (1) intact was tested and did not hold — the corruption is in the source file, not in how it was read.**

### 1.1 What was recovered cleanly (Eq. 2 and Eq. 3), verbatim from the rendered page image

**Eq. (2), the directivity formula** — CONFIRMED, transcribed character-for-character from the page image:

```
Dir(θ,φ) = 4π|f(θ,φ)|² / ∫₀^2π ∫₀^(π/2) |f(θ,φ)|² sinθ dθ dφ
```

*Plain reading:* "directivity" at a given direction (θ,φ) is how much stronger the reflected signal is in that one direction compared to spreading the same total power evenly over the whole forward half-space. The paper's own bounds on the integral — θ from 0 to 90°, φ all the way around — mean this is deliberately a **whole-hemisphere** quantity, not a single-direction one. That detail turns out to be the crux of the whole ticket (§3 below).

**Eq. (3), the RCS-reduction formula** — CONFIRMED, transcribed character-for-character from the page image:

```
RCS reduction = λ² / (4π N² D²) · Max_{θ,φ}( Dir(θ,φ) )
```

*Plain reading:* take the single strongest direction the reflected energy goes in (the biggest lobe anywhere in the hemisphere, however "peaky" that lobe is — normal incidence back the way it came included, but not required), scale it by the aperture's physical size (`N²D²`, the panel's area) and wavelength, and that scaled peak is the number the paper reports as "RCS reduction," in dB via `10·log10(·)`. This is a **worst-of-all-directions-you-can't-avoid** metric, not an average and not a shape/flatness measure — it only cares about the single tallest peak, wherever it happens to land.

The surrounding text (also cleanly legible) confirms Table I's own eight numbers **are Eq. (3)'s output**, not a full-wave/measured figure: the sentence "*We notice that better RCS reduction is achieved for larger N. When N=20, the RCS reduction is down to -23 dB...*" appears in the same paragraph as Eq. (3), before any mention of fabrication or CST simulation — the paper's fabricated 8×8 sample (code `00110101`) and its CST/measured curves are introduced only afterward, as a *separate* verification step. Table I is the closed-form Eq. (1)–(3) model's own output on an *idealized*, isotropic-sub-array assumption (the paper states "the `fe(θ,φ)` term has been eliminated" from Eq. (2), meaning the individual tile's own antenna pattern is assumed not to matter — a genuine physical idealization, not an approximation this document introduces).

### 1.2 Eq. (1): confirmed corrupted at the source, best-effort reconstruction only

Eq. (1)'s legible surrounding text reads: *"the far-field function scattered by the metasurface is expressed as: `f(θ,φ) = f_e(θ,φ) Σ_{m=1}^N Σ_{n=1}^N e^{[exponent — illegible in source]}`, in which θ and φ are the elevation and azimuth angles of an arbitrary direction, and `f_e(θ,φ)` is the pattern function of a lattice."* The scattering phase of lattice `(m,n)` is `φ(m,n) ∈ {0°, 180°}`.

**No exact transcription of the exponent is presented here, honoring the same rule the prior pass applied: no reconstructed formula that cannot be verified character-for-character is presented as a transcription.** What follows instead is a **PREDICTED** (ADR-0022 sense — stated with its assumption, not offered as confirmed) reconstruction from standard planar-array-factor theory, cross-checked against the paper's own Appendix Eq. (7)–(10) (a fully legible two-element special case, reproduced below), which is the same approach the GitHub issue's own advisor took, made explicit here:

```
f(θ,φ) = f_e(θ,φ) · Σ_{m=1}^N Σ_{n=1}^N exp{ -i[ φ(m,n) + kD·((m-1/2)·sinθcosφ + (n-1/2)·sinθsinφ) ] }
```

*Plain reading:* each of the `N×N` tiles contributes its own coding phase (`φ(m,n)`, 0 or 180°) plus a position-dependent phase that depends on the tile's physical location on the panel and the direction being looked at (`k = 2π/λ` is the free-space wavenumber, `D` the tile size) — the standard textbook form for how a grid of radiators combines. This is offered as the most defensible reconstruction available, not a verified transcription; **anyone implementing this should re-request the paper's official PDF or a Supplementary-Information copy at higher native resolution rather than trust this reconstruction further.**

---

## 2. How a 1-D code string becomes a 2-D `N×N` lattice — partially answered, one part left open

The ticket's first ask was to find whether Table I's 1-D strings (e.g. `001011` for N=6) map to the 2-D lattice by a diagonal, Kronecker, row-repeat, or other construction. **This was only partially resolved.**

**What the paper states outright (CONFIRMED, verbatim):**
- Discussing Table I: *"the optimized codes for different numbers of lattices (N) are listed in Table I when D is fixed to λ, in which the code sequences along the horizontal and vertical directions are the same."*
- Describing the fabricated N=8 sample (Fig. 3a/b): *"The patterns in Figs. 3a and b are designed symmetrically from the optimized coding sequence 00110101 for N=8 in both horizontal and vertical directions."*

Neither sentence states the combination rule in words (no "XOR," "modulo-2," "Kronecker," or "diagonal" appears anywhere in the paper's body text — checked by full-text search across all 25 pages). "The same sequence governs both directions" and "designed symmetrically" are consistent with several different constructions that all use one 1-D sequence twice, and the paper does not disambiguate them in prose.

**What Figure 3a (the fabricated N=8 panel's actual layout, rendered from the PDF page image) rules out:** the panel's own printed structure — visible directly in the extracted figure — is **not** a set of plain vertical or horizontal stripes; it shows genuine two-dimensional block variation (large and small light/dark rectangular regions in both directions, not a repeated column pattern). This rules out the simplest possible reading — "extrude the 1-D code as stripes across all rows" (i.e., `φ(m,n)` depends only on `n`, constant in `m`) — as the construction Cui et al. actually built and photographed, **even though that same simple construction is the numerically closest match to Table I's N=6 entry** (§3 below) — a genuine tension, named rather than smoothed over.

**A pixel-level reconstruction attempt from the rendered Figure 3a bitmap was made and did not reach a confident result.** The figure was cropped, color-classified (yellow vs. green-textured cells), and downsampled to an 8×8 grid to compare against several candidate constructions (an XOR/modulo-2 combination `φ(m,n) = c(m) XOR c(n)`, a diagonal/Toeplitz shift, and others). The classification was sensitive to exact crop alignment and did not converge on a clean, high-confidence 8-bit-per-row readout at the resolution available from this rendering pass. **This is recorded as a genuine, unresolved gap — not silently forced to an answer** — because the only path to closing it is a higher-resolution source image (the paper's own Supplementary Information PDF, not fetched in this pass, may hold a cleaner version of Fig. S1's construction diagram) or a written construction rule from a later paper by the same group that states the rule in words.

---

## 3. Testing the formula against all 8 rows of Table I

Per the ticket's request, the (PREDICTED) Eq. (1) reconstruction, the CONFIRMED Eq. (2)–(3), and several candidate 1-D→2-D constructions were evaluated numerically against every row of Table I (not just N=6), using `D=λ` as the paper specifies, integrating Eq. (2)'s directivity ratio over the same `θ∈[0°,90°], φ∈[0°,360°)` domain Eq. (2) itself specifies, on a fine angular grid (up to 0.5° steps, refined further where the array's narrower lobes at larger N demanded it).

| N | Code | Balance (ones − zeros) | Paper's Table I (dB) | Boresight-only formula* (dB) | This session's Eq.(1)–(3), XOR construction (dB) | This session's Eq.(1)–(3), row-repeat construction (dB) |
|---|---|---|---|---|---|---|
| 6 | `001011` | +0 | −12.08 | **−∞ (exact null)** | −17.39 | −12.18 |
| 7 | `0011010` | −1 | −14.64 | −33.80 | −19.50 | −12.84 |
| 8 | `00110101` | +0 | −15.82 | **−∞ (exact null)** | −20.25 | −12.82 |
| 10 | `0001010110` | −2 | −18.39 | −27.96 | −20.86 | −13.52 |
| 12 | `001001110101` | +0 | −19.75 | **−∞ (exact null)** | −22.48 | −14.29 |
| 14 | `00111110110101` | +4 | −21.41 | −21.76 | −24.75 | −16.35 |
| 16 | `0011110110101010` | +2 | −22.37 | −36.12 | −24.78 | −15.45 |
| 20 | `01000100110000110101` | −4 | −23.58 | −27.96 | −23.97 | −15.25 |

*\*"Boresight-only formula" is the GitHub issue's own advisor-derived closed form (`20·log10(|N⁻² Σ exp(−iφ(m,n))|)`), i.e. evaluating the array sum only at normal incidence (θ=0), included here as the object the ticket is diagnosing, not as this document's own proposal.*

**No reconstructed construction (XOR, row-repeat, column-repeat, AND, OR, or a diagonal Toeplitz shift — all six tested) reproduces Table I's exact numbers across every row.** The XOR construction tracks the paper's *qualitative trend* best (RCS reduction gets steadily larger in magnitude as N grows, matching the paper's own stated "*better RCS reduction is achieved for larger N*"), converging to within 0.4 dB of the paper's own N=20 figure, but running 2–5 dB off at small N. The row-repeat construction is startlingly close at N=6 (−12.18 dB vs. the paper's −12.08 dB, a 0.1 dB match) but plateaus and falls 8+ dB short by N=20 — consistent with row-repeat effectively being a 1-D array problem (one direction carries all the coding information, the other just multiplies by a constant N), which cannot reproduce a genuinely improving 2-D effect at scale. **This mismatch is classified per the ticket's own request:**

**Classification: the mismatch is NOT balance-specific — it is uniform/systematic, consistent with an unconfirmed construction rule (§2), not with a live degenerate metric in the correctly-implemented formula.** Table I's own real values form a smooth, N-dependent, monotonically-improving curve *regardless of each code's balance* — N=14's code (`00111110110101`, balance +4, one of the most lopsided entries) sits right on the trend line between N=12 and N=16's much more balanced codes. If Table I's quantity were sensitive to code balance the way the boresight-only formula plainly is (column 4 above — exact zero whenever balance is exactly 0, wildly different otherwise, no relationship to N), that smoothness would be a coincidence. It is not: Eq. (3)'s `Max_{θ,φ}` term is a maximum taken *after* the position-dependent phase sweeps through every direction, so it does not carry the balance-driven cancellation that only exists at the single point θ=0.

---

## 4. The central finding: why the advisor's formula degenerates, and why Eq. (3) itself does not — CONFIRMED, construction-independent

This is the direct, checkable answer to the ticket's core question, and it does not depend on resolving §2's open construction-rule gap.

**Claim, proven algebraically, true for *any* arrangement of 0s and 1s whatsoever:** at exactly normal incidence (θ=0), every position-dependent phase term in Eq. (1)'s exponent vanishes — `sinθ = 0` kills the entire `kD(...)` part regardless of what `m` and `n` are — leaving

```
f(0,·) = f_e(0,·) · Σ_{m,n} exp(−iφ(m,n)) = f_e(0,·) · (N₀ − N₁)
```

where `N₀` and `N₁` are simply the *total counts* of "0" and "1" tiles anywhere on the panel. **This sum has no dependence on arrangement at all — moving tiles around the panel does not change it, only the count of each type does.** Whenever a code has an equal number of 0s and 1s (`N₀ = N₁`, "balance" = 0 in the table above), this sum is *exactly* zero, for every single possible arrangement of those tiles — a perfect null, `−∞ dB` under any formula built only from this one value. **This was verified numerically for the three perfectly-balanced Table I rows (N=6, 8, 12) using the XOR construction and confirmed to machine precision** (column 5 above), and the algebraic argument above shows the result is construction-independent — swapping in row-repeat, diagonal, or any other arrangement rule changes nothing about the boresight value, only the arrangement's behavior everywhere else.

*Plain reading, in full:* pointing a formula straight back at the panel (the "did the wave bounce straight back the way it came, at full strength" question) throws away almost all the information about *how* the tiles are arranged — it can only ever see the balance of the count, because looking straight-on erases every difference position makes. A search that only checked this one direction would see every 50/50-mixed arrangement as identically, perfectly invisible — which cannot distinguish a good scattering pattern from a bad one, exactly as the GitHub issue suspected.

**Eq. (3) itself does not have this problem, because it never evaluates only at θ=0 — it searches the entire upper hemisphere for whichever direction has the tallest lobe, and that direction is essentially never boresight.** Across every one of the 8 Table I codes, under every construction tested (XOR, row-repeat, AND, OR, diagonal), the numerically-found peak direction of Dir(θ,φ) was never at θ=0 — it landed anywhere from ~20° to ~90° off axis depending on the code and construction. None of the "Max-hemisphere" columns in the §3 table contain a `−∞`; every single one is a finite, physically sensible number in roughly the same range as the paper's own figures.

**This resolves the ticket's two explanations as follows, at CONFIRMED strength for the mechanism and PREDICTED strength for the exact numeric match:**

- **Explanation 1 ("pure specular-reduction scoring is degenerate") is correct about the *mechanism*, but the degeneracy is a property of evaluating the array sum *only at boresight* — it is not a property of Eq. (3) itself.** Eq. (3), correctly implemented as a maximum over the full hemisphere, is not degenerate for any balanced code tested.
- **Explanation 2 ("Table I is a different quantity than a specular null") is correct in substance: Table I is not, and was never claimed by Cui et al. to be, a pure on-axis specular-null figure — it is `Max_{θ,φ}` of the directivity, a worst-of-all-directions peak-suppression metric that happens to equal the specular value only when the specular direction happens to be where the tallest lobe lands.**

The advisor's formula in the GitHub issue was, in effect, an accidental boresight-only evaluation of the right general idea (an array-factor sum) — not because it used the wrong equation family, but because it implicitly assumed the answer would land at θ=0 rather than searching for it.

---

## 5. What the three follow-on papers' own fitness functions say — and why this settles the objective question directly

The ticket asked whether Ali (2019), Wu (2020), or Ullah (2025) state their own optimizer's objective explicitly, as a more direct answer than re-deriving one. **All three do, and all three state the same structural objective as Eq. (3), independently of each other and without citing an explicit formula from Cui et al.'s paper for it.**

**L. Ali, Q. Li, T. A. Khan, J. Yi & X. Chen, "Wideband RCS Reduction Using Coding Diffusion Metasurface," *Materials* **12**(17):2708 (2019), DOI [10.3390/ma12172708](https://doi.org/10.3390/ma12172708)** — **[verified this session, verbatim, via PMC6747563]**:
> *"The maximum value of the scattering field is employed as a fitness function to operate the scattering waves"* ... *"The fitness function must be minimized by using an algorithm to generate the random round set of a binary sequence."*

**G. Wu, W. Yu, T. Lin, Y. Deng & J. Liu, "Ultra-Wideband RCS Reduction Based on Non-Planar Coding Diffusive Metasurface," *Materials* **13**(21):4773 (2020), DOI [10.3390/ma13214773](https://doi.org/10.3390/ma13214773)** — **[verified this session, verbatim, via PMC7663463]**, their own Eq. (7):
> *"fitness = max AF(θ,φ)"* ... *"The maximum value of the scattered field is employed as the fitness function, to manipulate the scattered wave, and the fitness function must be minimized by using an algorithm that generates a random set of binary sequences."*

**M. U. Ullah, T. A. Latef, M. Othman et al., "Polarization-controlled coding metasurface with phase cancellation and diffusion for enhanced radar cross section reduction," *Scientific Reports* **15**, 38320 (2025), DOI [10.1038/s41598-025-22248-z](https://doi.org/10.1038/s41598-025-22248-z)** — **[verified this session, verbatim, via PMC12583563]**, their own Eq. (19):
> *"a larger fitness value corresponds to a smaller peak of the AF in Eq. (16)"* — i.e. their GA maximizes a fitness score that is monotonically inverse to the array factor's peak value, run with *"a mutation probability of 0.052, a population size of 300, and a crossover probability of 0.8."*

**Plain reading, and why this is the answer to the ticket:** all three papers — using three different search algorithms (a named-but-undescribed "random optimization algorithm," discrete particle-swarm, and a genetic algorithm) — independently landed on the same fitness function: *find the arrangement that makes the single worst (tallest) lobe, anywhere the wave could go, as small as possible.* That is a **minimax objective** (minimize the maximum), not a variance/flatness measure of the whole angular pattern — a more precise characterization than the GitHub issue's own phrasing ("something closer to how flat/diffuse the redirected power's angular spread is"). And critically: **`max_{θ,φ} AF(θ,φ)` is, up to the constant scale factor `λ²/(4πN²D²)` in front of it, the exact same quantity as Cui et al.'s own Eq. (3)** — minimizing the peak array factor and maximizing RCS reduction (Eq. 3) are the same search, just with the sign and the units flipped. **This means Cui et al.'s formula was never the problem — Eq. (3), correctly evaluated as a hemisphere-wide maximum rather than a single boresight value, already is the non-degenerate arrangement objective, and it is the same objective three independent later papers arrived at on their own.** No new "diffusion-flatness" metric needs to be invented; the missing piece was implementation fidelity to Eq. (3) as written (a max over the full domain Eq. (2) integrates over), not a different physical quantity.

None of the three papers' sources, in the material retrieved this session, spell out their fitness function as an explicit closed-form equation reproduced character-for-character the way Eq. (2)–(3) are reproduced in §1.1 above — the quotes above are the paper's own prose description (Ali 2019, Ullah 2025) or a short equation label without its full derivation shown in the retrieved text (Wu 2020's "fitness = max AF(θ,φ)"). This is recorded as **CONFIRMED for the stated objective in words**, not as a character-for-character equation transcription at the same bar as §1.1.

---

## 6. What remains open

1. **The exact 1-D→2-D lattice construction rule is not confirmed** (§2). The paper's own prose ("same sequence, both directions," "designed symmetrically") is consistent with an XOR/modulo-2 combination, a diagonal construction, or another symmetric rule, but does not name one, and a pixel-level readout of the fabricated sample's photo (Fig. 3a) did not reach a confident reconstruction at the resolution available in this pass. This is the one piece of the ticket's ask that a future pass should target directly — ideally via the paper's Supplementary Information PDF (not fetched this session) or a later paper by the same group that states the rule in words.
2. **No single tested construction reproduces all 8 rows of Table I to a tight tolerance** (§3). The mismatch is classified as uniform/construction-related rather than balance-specific (§3's argument), but this is inference from the *shape* of the mismatch, not a confirmed construction rule — closing gap 1 would let this be checked directly rather than inferred.
3. **Eq. (1)'s exact exponent remains unrecoverable from the primary PDF** (§1.2) — confirmed this session to be a source-file corruption, not an extraction-tool failure, which is new information but does not change the bottom line: any exact reconstruction should be treated as PREDICTED, not CONFIRMED, until a cleaner copy of the page is found.
4. **The three follow-on papers' fitness functions were retrieved as prose/short-equation quotes, not full derivations** (§5) — sufficient to confirm the *objective* (minimize the peak array factor / directivity, i.e. Eq. (3)'s own quantity) but not to confirm every implementation detail (e.g., exact integration domain, discretization, or whether any of the three restrict the search to co-polarized directions only).
5. **What this means for building the `COMBINATORIAL` fitness function for `DIFFUSIVE`** (the downstream implementation ticket this research unblocks, once gaps 1–2 are closed enough to trust): the objective is Cui et al.'s own Eq. (3), `Max_{θ,φ}(Dir(θ,φ))`, minimized (or, equivalently, RCS reduction maximized) — **not** a new diffusion-flatness metric, and **not** the boresight-only evaluation that motivated this ticket. This document does not itself propose or write that fitness function in code, per the ticket's explicit research-only scope — it only confirms which quantity it should be.

---

## Sources

**Verified firsthand this session (primary text and equations re-extracted via page-image rendering, not text-layer extraction):**
- T. J. Cui, M. Q. Qi, X. Wan, J. Zhao & Q. Cheng, "Coding metamaterials, digital metamaterials and programmable metamaterials," *Light: Science & Applications* **3**, e218 (2014), DOI [10.1038/lsa.2014.99](https://doi.org/10.1038/lsa.2014.99) — read via the arXiv preprint [1407.8442](https://arxiv.org/pdf/1407.8442), PDF downloaded directly and rendered page-by-page to images with PyMuPDF (`get_pixmap`, up to 8x scale) after confirming no arXiv/ar5iv HTML mirror exists for this preprint (`arxiv.org/html/1407.8442` and `ar5iv.labs.arxiv.org/html/1407.8442` both redirect to the abstract page, 404/307). Eq. (2)–(3) and Table I confirmed legible and transcribed exactly; Eq. (1)'s exponent confirmed genuinely corrupted in the rendered page image itself, not merely in text extraction.

**Verified this session via WebFetch of the primary record (verbatim quotes obtained):**
- L. Ali, Q. Li, T. A. Khan, J. Yi & X. Chen, "Wideband RCS Reduction Using Coding Diffusion Metasurface," *Materials* **12**(17):2708 (2019), DOI [10.3390/ma12172708](https://doi.org/10.3390/ma12172708), via [PMC6747563](https://pmc.ncbi.nlm.nih.gov/articles/PMC6747563/).
- G. Wu, W. Yu, T. Lin, Y. Deng & J. Liu, "Ultra-Wideband RCS Reduction Based on Non-Planar Coding Diffusive Metasurface," *Materials* **13**(21):4773 (2020), DOI [10.3390/ma13214773](https://doi.org/10.3390/ma13214773), via [PMC7663463](https://pmc.ncbi.nlm.nih.gov/articles/PMC7663463/).
- M. U. Ullah, T. A. Latef, M. Othman et al., "Polarization-controlled coding metasurface with phase cancellation and diffusion for enhanced radar cross section reduction," *Scientific Reports* **15**, 38320 (2025), DOI [10.1038/s41598-025-22248-z](https://doi.org/10.1038/s41598-025-22248-z), via [PMC12583563](https://pmc.ncbi.nlm.nih.gov/articles/PMC12583563/). This upgrades the prior pass's "secondary/AI-summarized, not independently re-verified" flag on this source (`docs/example7-coding-metasurface-scoring-recipe.md` §1.1) to a primary-record verbatim retrieval for its fitness-function statement specifically.

**Computation performed this session (not from any external source — original numerical work against the primary sources above):**
- Numerical evaluation of the (PREDICTED) Eq. (1) reconstruction against all 8 rows of Table I, under six candidate 1-D→2-D constructions, at `D=λ` per the paper's own stated condition, integrating Eq. (2)'s directivity ratio over its own stated domain. Script and intermediate outputs are not part of this repository (research-only deliverable, no code changes per ticket scope); the results are reproduced in full in §3–4's tables.
- The algebraic proof in §4 that boresight-only evaluation of Eq. (1) collapses to `N₀ − N₁` (construction-independent) is original derivation from Eq. (1)'s stated structure, not sourced from any paper.

**Reused, not re-fetched (already verified in the cited project document):**
- `docs/example7-coding-metasurface-scoring-recipe.md` (#104/#107/#130/#129-adjacent) — the prior research pass this document extends, cited throughout for what it already established and where it flagged the gap this document addresses.
