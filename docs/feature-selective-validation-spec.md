# Feature Selective Validation (FSV), recovered and specified

**Date:** 2026-09-13
**Ticket:** [#168](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/168) — part of [#104](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/104); the mechanism was chosen on [#110](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/110) and recorded as [ADR-0041](./adr/0041-absorber-score-is-worst-in-band-minimax-with-fsv-comparison.md) point 5; the frequency disagreement it has to survive is [#142](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/142)'s.
**Question:** What exactly are FSV's ADM/FDM/GDM formulas, its six grading bins, and its GRADE/SPREAD summary — and how does a method whose headline output is a word fit a project that scores everything else as one reversible-default number?

---

## Bottom line up front

**All five of #168's sub-questions are answered.** The IEEE standard's own text is
still unread — it is paywalled and no free copy exists (§9) — but that no longer
matters much, because **the equations were recovered three times over from three
independent documents, two of them written by FSV's own authors and one of which
states plainly that it is transcribing IEEE Std 1597.1 itself.** All three agree
on every constant.

| # | #168 asked | Answer | Where |
|---|---|---|---|
| 1 | The exact ADM/FDM/GDM formulas | **Recovered verbatim, three independent transcriptions, no disagreement on any constant.** The decomposition is a **Fourier** three-band split (DC / Lo / Hi) — **not** a wavelet transform, contrary to what the secondary description on #110 said | §1–§4 |
| 2 | The six bin boundaries | **0.1 / 0.2 / 0.4 / 0.8 / 1.6.** Identical in all three sources | §5 |
| 3 | How GRADE and SPREAD are computed | **Recovered from the developers' own tool manual.** GRADE = how many bins, counting up from *Excellent*, hold 85% of the point-by-point verdicts. SPREAD = how many bins, counting down from the *most populated*, hold 85%. Two published sources state this backwards; §6 shows which is right and how it was settled | §6 |
| 4 | How a qualitative result folds into a single reversible-default number | **It barely needs to.** The word is derived from a number; the number is the primary output — and FSV even publishes its own monotonic value→1-6 conversion, so no mapping has to be invented. Recommendation: score **GDM directly as an ordinary `AT_MOST` requirement target**, reversible default **GDM ≤ 0.4**, no new scoring code at all — and carry ADM, FDM and SPREAD alongside it rather than folding them in | §8 |
| 5 | Does an implementation already exist | **Two.** The authors' own reference tool is still online and downloadable, but it is a **compiled, encrypted Windows binary** — not source. A **real, correct, LGPL-2.1 Python implementation** exists in a third-party repo. And **this repo already has a throwaway prototype whose formulas are wrong** | §7 |

**One thing this changes that nobody asked for.** Re-running this repo's own
`prototype/fsv-feasibility/fsv_prototype.py` with the corrected equations
**overturns its headline finding.** That prototype reported the disputed
patent-vs-Landy pair as `GDM = 0.37, "Good"` and concluded FSV "saturates early
and stops" discriminating. With the published formulas the same curves give
**`GDM = 1.018, "Poor"`**, and GDM rises monotonically across the whole offset
sweep instead of plateauing. FSV does the job it was chosen for. §9.

*In plain terms: FSV is a way of scoring "do these two graphs look the same?"
that splits the question in two — "are they at the same height?" and "are the
wiggles in the same places?" — because that is what an engineer's eye actually
does. On the argument this project cares about, it gives the answer an engineer
would give: the two curves sit at the same level (that half scores "Excellent")
but the dip is in the wrong place (that half scores "Poor"). One averaged error
number cannot say that, which is the whole reason the method exists.*

---

## 1. The three-band decomposition — Fourier, not wavelet

Every source agrees, and this corrects a small error carried by
`docs/absorber-scoring-decision-confirmation.md` §5.2 and by ADR-0041 point 5,
both of which say the feature component comes "via wavelet or Fourier
decomposition." **There is no wavelet anywhere in FSV.** It is a plain DFT, a
three-way split of the spectrum, and an inverse DFT.

Verbatim, from the FSV authors' own conference paper:

> "3. Filter into three ranges. This is done by Fourier Transforming the data
> and the 'DC' set is the DC term plus the lowest four data points. The 'Lo'
> region is from the next point to the approximate location where 40% of the
> total area under the transformed curve occurs. The 'Hi' region is everything
> else. These regions are then transformed back to the original domain."
> — Sasse, Duffy & Orlandi, *"Applying the Feature Selective Validation (FSV)
> method to quantifying rf measurement comparisons,"* ARMMS RF & Microwave
> Society conference paper, [armms.org/media/uploads/1259320006.pdf](https://www.armms.org/media/uploads/1259320006.pdf),
> §3, step 3

The developers' own tool manual gives the same split in more operational detail
— and adds two things the conference paper leaves out:

> "b. Obtain a 40% location by summing the data from the DC+1 point (i.e.
> ignoring the near-DC data) until the total reaches 40% of the total value
> calculated in step 3a. The '40%' location used by the FSV is the lowest of
> the two resulting numbers (from the two original data sets). A 'break-point'
> five data points above this is returned — a value that allows a comfortable
> transition window between the low and the high results.
> c. Window the transformed data for both data sets by taking a linearly
> decreasing envelope from two points below the break-point to two points above
> it."
> — *1D FSV Manual*, UAq EMC Laboratory, University of L'Aquila,
> [ing.univaq.it/uaqemc/FSV_4_0_3L/1DFSV_Manual.pdf](http://ing.univaq.it/uaqemc/FSV_4_0_3L/1DFSV_Manual.pdf),
> §1.1 step 3

The two extras — **the break point is the lower of the two curves' 40% points,
plus five bins**, and **the band edge is a linear taper across ±2 bins, not a
hard cut** — are not in any of the published papers. They matter for
reproducibility and are the kind of detail a from-scratch implementation gets
wrong silently.

Steps 1 and 2, also verbatim from ARMMS §3: *"Determine the region of overlap
for the two data sets to be compared and ignore everything outside this window"*
and *"Resample the data to the lowest point density such that the data points of
the two data sets to be compared are coincident."*

*In plain terms: chop both curves down to the frequency range they share,
resample them onto the same grid, then run a Fourier transform on each and cut
the result into three slices — a "DC" slice (the average level), a "low" slice
(the slow, overall shape) and a "high" slice (the fast wiggles and resonances).
Transform each slice back. Everything after this compares slices against slices.*

`LITERATURE-SUPPORTED` — two independent documents, both by the method's authors.

---

## 2. ADM — the Amplitude Difference Measure

**Point by point**, at data point *i*:

```
    ADM_i(i)  =  ADM_old(i)  +  ( c_m · ODM_i(i) · e^( c_m1 · ODM_i(i) ) )      (1.1)
```

```
                     ‖ |Lo₁(i)| − |Lo₂(i)| ‖
    ADM_old(i)  =  ───────────────────────────                                  (1.2)
                    (1/N) Σᵢ₌₁ᴺ ( |Lo₁(i)| + |Lo₂(i)| )
```

```
                     ‖ |DC₁(i)| − |DC₂(i)| ‖
    ODM_i(i)    =  ───────────────────────────                                  (1.3)
                    (1/N) Σᵢ₌₁ᴺ ( |DC₁(i)| + |DC₂(i)| )
```

```
    c_m  and  c_m1  are weighting coefficients set equal to 1                   (1.4)
```

**Single figure:**

```
    ADM  =  (1/N) Σᵢ₌₁ᴺ ADM(i)                                                  (1.5)
```

### Every symbol

| Symbol | Meaning | Source |
|---|---|---|
| `Lo₁`, `Lo₂` | The low-pass ("trend") components of curve 1 and curve 2, back in the original domain | §1 |
| `DC₁`, `DC₂` | The DC components (first four transform bins, inverse-transformed) | §1 |
| `N` | Number of points in the resampled overlap window | Manual §1.1 step 6 |
| `‖ · ‖` | Absolute value of the whole bracketed difference — so the numerator is the absolute difference of two absolute values, never negative | Manual eq (1.2)/(1.3), read from typeset math |
| `ODM` | **Offset Difference Measure** — the penalty for the two curves sitting at different average levels. Added to FSV in 2008, after the original 2006 papers | Duffy, Orlandi & Sasse, *IEEE Trans. EMC* **50**(2), pp. 413–415, 2008 (cited in ARMMS as ref [4]) |
| `c_m`, `c_m1` | Both fixed at 1 in the reference implementation | Manual eq (1.4), verbatim |

**Sanity of the form.** If the two curves are identical, every numerator is zero,
so `ADM_old = 0` and `ODM = 0`, and `0 · e⁰ = 0` — the measure is exactly zero.
Verified numerically: feeding the same curve twice returns `ADM = FDM = GDM =
0.0` exactly (§9). The exponential is what makes a *level* mismatch hurt more
than linearly: a curve sitting twice as far off in average level costs more than
twice as much.

### Provenance of this transcription

`LITERATURE-SUPPORTED`, at an unusually strong tier for something whose primary
standard is unread, because **three documents were read and all three agree**:

1. **The developers' own tool manual** (UAq EMC Laboratory, University of
   L'Aquila — Orlandi's group), eqs (1.1)–(1.5), read from a **4× typeset render
   of the PDF page**, not from an error-prone text layer. This is the
   specification of the reference implementation itself.
2. **The ARMMS conference paper** (Sasse, Duffy, Orlandi — De Montfort
   University plus L'Aquila, i.e. both originating labs), eq (1), read the same
   way. Written with `α/β/χ/δ` placeholders; algebraically identical.
3. **Bongiorno & Mariscotti**, *"Uncertainty and Sensitivity of the Feature
   Selective Validation (FSV) Method,"* MDPI *Electronics* **11**(16):2532
   (2022), [doi:10.3390/electronics11162532](https://doi.org/10.3390/electronics11162532),
   eqs (5)–(6). This one matters most: it states verbatim that
   *"Equations (5)–(12) are taken from the IEEE Std. 1597.1 [10], and are
   slightly reshaped for clarity"* — so it is a third party's direct
   transcription **of the standard text**, from authors who had read it.

Where a difference of notation exists it resolves to nothing: ARMMS writes the
offset term as `|χ/δ|·exp{|χ/δ|}` with `χ` signed; MDPI writes `ODM_i·exp^ODM_i`
with the absolute value already inside `ODM_i`'s own definition. Both are
`(|χ|/δ)·e^(|χ|/δ)`. Same equation.

---

## 3. FDM — the Feature Difference Measure

```
                     | Lo₁′(x) | − | Lo₂′(x) |
    FD_I(x)    =  ─────────────────────────────────                             (1.6)
                   (2/N) Σ ( |Lo₁′(x)| + |Lo₂′(x)| )
```

```
                     | Hi₁′(x) | − | Hi₂′(x) |
    FD_II(x)   =  ─────────────────────────────────                             (1.7)
                   (6/N) Σ ( |Hi₁′(x)| + |Hi₂′(x)| )
```

```
                     | Hi₁″(x) | − | Hi₂″(x) |
    FD_III(x)  =  ─────────────────────────────────                             (1.8)
                  (7.2/N) Σ ( |Hi₁″(x)| + |Hi₂″(x)| )
```

```
    FDM(x)  =  2 · | FD_I(x) + FD_II(x) + FD_III(x) |                           (1.9)
```

Single figure: the mean over the window, exactly as for ADM.

| Symbol | Meaning |
|---|---|
| `′` , `″` | First and second derivative with respect to the swept variable |
| `2`, `6`, `7.2` | Fixed empirical constants, identical in all three sources |

**Two details a re-implementation will get wrong without being told.**

- **The derivatives are differences, not difference quotients.** Verbatim:
  *"Derivatives in FDM_i are calculated as a difference, using an index interval
  that is ±2 for 'lo' and ±3 for 'hi', but without dividing by the differential
  of the independent variable, which would make these terms difference
  quotients. This may be identified as a little pitfall"* (MDPI §2.2). The
  manual gives the shorter form `Lo'(i) = Lo(i+1) − Lo(i−1)`, i.e. a ±1 span —
  **so the two sources disagree on the derivative span.** Recorded, not
  resolved; the third-party Python implementation in §7 flags the same
  disagreement independently.
- **The `2`, `6`, `7.2` sit in the *denominator*, dividing the normaliser.** A
  larger constant makes that FDM term *smaller*. Getting this inverted is the
  easiest available mistake.

**Where the sources genuinely differ, and what to do:**

| Point | Manual | ARMMS | MDPI | Adopt |
|---|---|---|---|---|
| Outer absolute value in (1.9) | absent — `FDMi = 2*(FD_I+FD_II+FD_III)` | present — `2(|…|)` | present — `2|…|` | **Present.** Two against one, and without it FDM can go negative, which the six-bin scale has no room for |
| Denominator of (1.8) | `7,2/(N*M)` — an extra `M`, and a comma decimal | `7.2/N` | `7.2/N` | **`7.2/N`.** The stray `M` is a leftover from the 2-D version of the same manual; the comma is Italian typing |

*In plain terms: ADM asks "are the two curves at the same height?" FDM asks "are
the bumps in the same places?" — and it asks that by comparing slopes and
curvatures, because a bump that has moved sideways shows up as a slope that
disagrees long before the heights do.*

`LITERATURE-SUPPORTED`, same three-source basis as §2.

---

## 4. GDM — the Global Difference Measure

**Point by point, unweighted** (all three sources agree):

```
    GDM(n)  =  √( ADM(n)² + FDM(n)² )
```

Single figure: the **mean** of the point-by-point values.

> A note against one source. MDPI's eq (12) prints `GDM = Σᵢ GDM_i` with **no
> `1/N`**. That is a typesetting slip, not a variant: the manual (eq 1.5, and
> step 15 — *"These variables are the average of the point-by-point values"*)
> and ARMMS (*"The average value of these provides single value summaries"*)
> both say mean, and a plain sum over ~1000 points could not land in a 0–1.6
> scale. **Use the mean.** `CALCULATED` (arithmetic sanity check on the source's
> own worked example).

**Optionally, weighted by SPREAD.** ARMMS §3 step 9 gives an algorithm for
letting the more *reliable* of ADM and FDM count for more:

```
    If   Spread_ADM < Spread_FDM :   K_ADM = 1 ;  K_FDM = Spread_ADM / Spread_FDM
    Elif Spread_ADM > Spread_FDM :   K_FDM = 1 ;  K_ADM = Spread_FDM / Spread_ADM
    Else                          :  K_ADM = 1 ;  K_FDM = 1

    GDM  =  √( (K_ADM · ADM)²  +  (K_FDM · FDM)² )
```

The manual's eq (1.10) writes the same idea with the `k`s multiplying the
**squares** rather than the values, and with a spurious summation sign over the
whole frequency range. That form is inconsistent with its own step 20 and with
ARMMS; **adopt the ARMMS form above.** `INFERRED` for the choice between them —
flagged, not hidden.

**Recommendation for this project: use the unweighted GDM.** The weighted form
makes the roll-up depend on SPREAD, which is precisely the quantity §8 wants to
keep visible and separate as a confidence flag. Weighting it in buries it.

---

## 5. The six bins — the numbers, not just the names

**Identical, to the digit, in all three sources.** No interpolation, no
disagreement, nothing to resolve.

| FSV value (quantitative) | Interpretation (qualitative) | Visual six-point scale |
|---|---|---|
| Less than 0.1 | Excellent | 1 |
| Between 0.1 and 0.2 | Very good | 2 |
| Between 0.2 and 0.4 | Good | 3 |
| Between 0.4 and 0.8 | Fair | 4 |
| Between 0.8 and 1.6 | Poor | 5 |
| Greater than 1.6 | Very poor *(the manual says "Extremely Poor")* | 6 |

— *1D FSV Manual* Table 1.1 (the third column is the manual's own addition);
ARMMS Table I; MDPI Table 1, which states it as *"The IEEE Std. 1597.1 requires
classification of the FSV GDM values with an interpretation scale."*
`LITERATURE-SUPPORTED`.

The bins double in width each step, which is the giveaway that they are meant to
be read as a rough logarithmic quality ladder rather than as calibrated
thresholds.

**A warning from the method's own authors, which §8 has to answer to:**

> "These descriptions are only helpful categorisations and **not indications of
> levels to be set for agreement**."
> — ARMMS §4, verbatim, emphasis added

Read that literally: *the standard's own developers say do not turn these bins
into a pass/fail line.* §8's recommended default threshold therefore has to be
labelled a project decision, not a standard.

---

## 6. GRADE and SPREAD — and the two sources that state them backwards

Both are integers from **1 (best) to 6 (worst)**, computed from the *confidence
histogram* — the proportion of the point-by-point ADM/FDM/GDM values falling in
each of the six bins. Each of ADM, FDM and GDM gets its own GRADE/SPREAD pair.

Verbatim, from the *1D FSV Manual*, §1.1 steps 17 and 18:

> "**The GRADE value** is computed by taking the number of classes, starting
> from the best (Excellent) to the worst (Extremely Poor), which include a user
> defined amount (named 'threshold' and set at 85 % by default) of the total
> samples of the data sets to be compared. GRADE value ranges from 1 (best
> quality) to 6 (worst quality)."
>
> "**The SPREAD** is computed by taking the number of classes, starting from the
> most populated to the lowest one, which includes a user defined amount (named
> 'threshold' and set at 85 % by default) of the total samples of the data sets
> to be compared. SPREAD ranges from 1 (best quality) to 6 (worst quality)."

And what each one *means*, from the same manual's overview:

> "The GRADE is a direct indication of the **quality** of the comparison. The
> smaller it is, the better the comparison."
> "The SPREAD indicates the level of **reliability** of the outputs. The smaller
> it is, the higher is the reliability of the results."

*In plain terms. Sort the point-by-point verdicts into six buckets from
"Excellent" to "Very poor". **GRADE** counts how many buckets you have to walk
through, starting at the Excellent end, before you have covered 85% of the
points — so a big GRADE means most of the curve landed in the bad buckets.
**SPREAD** counts how many buckets you need if you are allowed to take the
fullest ones first — so a big SPREAD means the verdicts are scattered all over
the place and the single headline number is not really representing them.*

### Two published sources get this backwards. Here is how it was settled.

| Source | What it says | Verdict |
|---|---|---|
| **1D FSV Manual**, steps 17–18 + overview | GRADE = from Excellent; SPREAD = from most-populated | **Correct.** It is the specification of the reference implementation |
| **Di Febo, de Paulis & Orlandi**, European IBIS Summit 2011, [ibis.org/summits/may11/di_febo.pdf](https://ibis.org/summits/may11/di_febo.pdf), slide 15 | *"Grade: number of categories starting from 'Excellent' to contain 85%… Spread: number of categories around the highest value category to contain 85%"* | **Agrees on GRADE.** On SPREAD it says "around the highest value category", i.e. a contiguous window centred on the mode, where the manual says "most populated to the lowest", i.e. take fullest-first regardless of adjacency. **A real, unresolved difference** — the two give different answers on a bimodal histogram |
| **ARMMS**, §3 step 9 | *"The Grade is the number of adjacent categories that include at least 85%… and Spread is the number of categories (starting with Excellent)…"* | **Swapped.** The same paper's own §4 then interprets its results the other way round — *"there is a lot of difference between the two data sets (Grade)"*, and *"the Spread… is only three categories, indicating a relatively high level of confidence"* — which matches the manual, not its own step 9. A drafting error in the paper |
| **MDPI** §2 | *"the spread term measures the spread of the distribution, and the grade term is similar to skewness"* | **Agrees with the manual.** Counting from one fixed end is a skewness-like statistic; width around the peak is a spread-like one |

So: three sources against one on which is which, and the odd one out contradicts
itself two pages later. `LITERATURE-SUPPORTED` for the manual's definitions;
`INFERRED` for choosing the manual's fullest-first SPREAD over Di Febo's
centred-window SPREAD, on the grounds that the manual is the tool's own spec.

**Both also carry a "range".** *"The GRADE range is given by considering the
range of the classes included in the GRADE value computation"* — i.e. alongside
the count, the tool reports *which* bins were used. Worth keeping; it is the
difference between "5 bins" and "5 bins, and they were Good through Very Poor".

**A recorded ambiguity, not a solved problem.** Bongiorno & Mariscotti published
a whole paper on this class of problem — *"Variability and Consistency of Feature
Selective Validation (FSV) Method Implementation,"* *IEEE Trans. EMC* **59**(5),
pp. 1474–1481 (2016/17), [doi:10.1109/TEMC.2016.2613830](https://doi.org/10.1109/TEMC.2016.2613830)
— described by its own authors as *"identifying implementation flaws and
ambiguities in the FSV method."* It is IEEE-paywalled and was **not read**
(§9, Stranded). Anyone implementing FSV here should expect their numbers to
differ from another tool's in the third digit, and should not claim otherwise.

---

## 7. Existing implementations — two real ones, and one wrong one in this repo

### 7.1 The authors' own reference tool — alive, downloadable, and not source

The UAq EMC Laboratory's FSV Tool is **still online**, at an unlinked Apache
directory index, files dated 2009:

| URL | Contents |
|---|---|
| [`ing.univaq.it/uaqemc/FSV_4_0_3L/`](http://ing.univaq.it/uaqemc/FSV_4_0_3L/) | 1-D FSV v4.0.3L: `fsv1d.exe` (11 KB), `fsv1d.ctf` (173 KB), **`1DFSV_Manual.pdf` (1.7 MB — the source of §1–§6 above)**, `data_examples/` |
| [`ing.univaq.it/uaqemc/FSV_2D_2_0_6L/`](http://ing.univaq.it/uaqemc/FSV_2D_2_0_6L/) | 2-D FSV v2.0.6L plus its own manual |
| [`ing.univaq.it/uaqemc/V-FSV_1_0_0/`](http://ing.univaq.it/uaqemc/V-FSV_1_0_0/) | Vector FSV, 9.3 MB zip |
| [`ing.univaq.it/uaqemc/mcrinstaller.exe`](http://ing.univaq.it/uaqemc/) | MATLAB Compiler Runtime, 100 MB — required to run any of them |

**It is a MATLAB-compiled Win32 binary.** The `.ctf` archive was downloaded and
unpacked: it contains 51 files with promising names — `libo/get_grade_spread.m`,
`libo/xDMconfidence.m`, `libo/xDMpwconv.m`, `libo/AVG_xDMconf.m` — but **every
`.m` file is MATLAB-Compiler-encrypted** (each begins
`V1MCC4000MEC1000MCR1000` followed by ciphertext). There is no readable source.
The archive also contains `libo/policies/infolicense.m` and `policies.m`, also
encrypted, so **the licence terms are unknown**; the 2011 IBIS slide deck says
only *"Free (at present) upon request."* `MANUFACTURER-SPECIFIED` for what the
tool is; `UNKNOWN` for whether it may be redistributed or ported.

**What is genuinely valuable here is not the binary — it is `data_examples/`.**
It contains `survey_data/1` … `survey_data/8`, each a pair of curve files
(`chart1a_mlab.txt` / `chart1b_mlab.txt`). Eight numbered curve pairs is exactly
the shape of the validation set behind Orlandi *et al.*'s "Part II — Assessment
of FSV Performance", where groups of engineers rated the same comparisons by
eye. Plus `parallel_data/` (one curve against six progressively perturbed
versions of itself — a ready-made monotonicity test), `combined/`
(magnitude+phase), and analytic sine/cosine/rectangle cases. **These are
reference vectors a from-scratch implementation can be regression-tested
against**, and they cost nothing to fetch. `INFERRED` that `survey_data` is the
Part II survey set — the naming and count fit, the manual does not say so.

### 7.2 A correct, open-source Python implementation exists

`tests/fsv.py` in [`mishka-zz/freecad-microwave`](https://github.com/mishka-zz/freecad-microwave) —
284 lines, numpy only, **SPDX-License-Identifier: LGPL-2.1-or-later**,
copyright 2026 Mike Volokhov. Verified by reading the file, not by trusting the
search hit: it carries the FFT DC/Lo/Hi split with an adaptive 40% break point,
the ADM offset term with its exponential, the FDM derivative terms with the
**correct 2.0 / 6.0 / 7.2 constants and the outer ×2**, `GDM = √(ADM²+FDM²)`
point-by-point plus means, the six-bin classifier and a confidence histogram.

Its own docstring is refreshingly honest about the same problem this document
has: *"Read from restatements of the standard rather than from the standard,
which is not open… and those disagree with each other in places — the span a
derivative is taken across is one."* That is independently the same
disagreement §3 found.

**Limits:** it stops at the confidence histogram — **no GRADE, no SPREAD**, no
`xDM_conf`, no piecewise visual conversion. And LGPL-2.1-or-later is copyleft;
`docs/LICENSE_MATRIX.md` already tracks LGPL components (Elmer, CSXCAD) with the
note *"review obligations if redistributed."* Importing one file of LGPL code
into an otherwise-unpublished internal tool is low-risk, but it is a licence
decision, not a technical one.

### 7.3 This repo already has an FSV prototype, and its formulas are wrong

`prototype/fsv-feasibility/fsv_prototype.py` (with its own README, both marked
THROWAWAY) was written for #168's *other* question — does FSV discriminate at
all when the curves are five resonance-widths apart? — and it says so honestly:
*"a BEST-EFFORT reconstruction… exact weighting constants inside FDM are a
best-effort reading."* Against the equations now recovered, the specific
deviations are:

| Prototype | Published | Consequence |
|---|---|---|
| `ADM = ((lo₁−lo₂) + (dc₁−dc₂)) / (rms(lo₁)+rms(dc₁))` | eqs (1.1)–(1.3): absolute values throughout, normaliser is the mean of **both** curves' magnitudes, offset term is `ODM·e^ODM` | Signed, so positive and negative excursions cancel; no exponential offset penalty; wrong normaliser |
| `FDM` term 1 built from `Hi` itself | `FD_I` is built from **`Lo′`** — the derivative of the *trend* band | Wrong band entirely |
| Three terms averaged: `(f₁+f₂+f₃)/3`, no constants | `2·|FD_I + FD_II + FD_III|`, with 2 / 6 / 7.2 inside the denominators | Under-reports FDM by roughly 6× |
| SPREAD = symmetric window around the modal bin | Manual: fullest bins first, adjacency not required | Diverges on any bimodal histogram (§6) |

**This is not a criticism of the prototype** — it named every one of these as a
best-effort reading at the time, which is exactly the right behaviour. But its
printed conclusion is now known to be wrong, and §9 says by how much.

### 7.4 Two things that look like hits and are not

- **MATLAB File Exchange "Feature Selection Library" (FSLib)** — its "FSV" is
  *Feature Selection via concaVe minimization*, a machine-learning
  variable-selection algorithm. Nothing to do with electromagnetics. A pure name
  collision, recorded so nobody re-finds it and downloads it.
- **A GitHub repository search** for FSV/electromagnetics returns **zero**
  repositories. The only code hits anywhere are §7.2's single file and this
  repo's own prototype.

---

## 8. The design question: how a word becomes a number here

**#168 framed this as "how does a qualitative GRADE/SPREAD result integrate into
a project that scores everything else as a single reversible-default number."
The framing overstates the problem, and the reason matters.**

FSV's primary output is **not** qualitative. `GDM = 1.018` is the output; *"Poor"*
is a label looked up from it in a fixed table. The genuinely qualitative,
genuinely awkward outputs are GRADE and SPREAD — two small integers describing
the *shape of a histogram*, not the size of a disagreement. So the question
splits cleanly, and the two halves get opposite answers.

### The recommendation

> **Score GDM as an ordinary `AT_MOST` requirement target, unit `"FSV GDM"`,
> reversible default `value = 0.4`, no tolerance. Report ADM, FDM, the
> confidence histogram, GRADE and SPREAD alongside it, and never fold them into
> the number. When SPREAD ≥ 5, attach a `note` saying the single figure is
> unrepresentative — but still return the score.**

Concretely, against the code as it stands today:

```python
# designs/requirement_targets.py -- unchanged, no new comparator needed
target = propose_target(
    value=0.4,
    comparator="AT_MOST",
    unit="FSV GDM",
    reason="Reproduction-fidelity check for Example 3 against Landy et al. "
    "2008, per ADR-0041 pt 5 / #168. NOT a customer requirement.",
)

# designs/success_score.py -- unchanged, no new formula needed
result = success_score(
    step="correlation",
    target=target,
    actual_value=gdm_total,
    actual_unit="FSV GDM",
    note=None
    if spread_gdm < 5
    else "SPREAD=%d: 85%% of the point-by-point "
    "verdicts do not fit in fewer than %d of the six bins, so this single "
    "figure is a poor summary of them -- read the histogram." % (spread_gdm, spread_gdm),
)
```

**Nothing in `success_score.py` or `requirement_targets.py` has to change.** That
is the strongest argument for this shape and it is worth stating plainly: the
existing `AT_MOST` path already does the right thing on a dimensionless
lower-is-better quantity.

### Why each part

**Why `AT_MOST` on raw GDM, and not a grade→percentage lookup table.** A lookup
(Excellent = 100%, Very Good = 80%, …) would throw away the continuous number
the standard already hands you and replace it with six figures nobody published.
It would also make `GDM = 0.11` and `GDM = 0.19` identical while making
`GDM = 0.099` and `GDM = 0.101` a 20-point cliff.

### Two other single numbers FSV already publishes — and why neither is the one to score

Both come from the *1D FSV Manual* and neither appears in any of the papers, so
they are easy to miss. Both are honest candidates for "the single number", and
both were considered and rejected.

**(a) The piecewise visual conversion, `ADM_pw` / `FDM_pw` / `GDM_pw`** — Table
1.2, verbatim, where `y` is the single-figure ADM, FDM or GDM:

```
    If  y ≤ 0.1                Then  V = 1    + 10   (y)
    If  y > 0.1  and  y ≤ 0.2  Then  V = 2    + 10   (y − 0.099)
    If  y > 0.2  and  y ≤ 0.4  Then  V = 3    +  5   (y − 0.199)
    If  y > 0.4  and  y ≤ 0.8  Then  V = 4    +  2.5 (y − 0.399)
    If  y > 0.8  and  y ≤ 1.6  Then  V = 5    +  1.25(y − 0.799)
    If  y > 1.6                Then  V = 6
```

This is **a published, monotonic map from the FSV value to a continuous 1–6
scale** — precisely the shape #168's fourth bullet asked whether one could be
invented. It does not have to be invented; it exists. It also stretches each bin
to unit width, so equal steps on `V` mean equal steps of perceived quality
rather than equal steps of GDM. `LITERATURE-SUPPORTED`.

*A transcription check.* Each branch slightly overruns its own integer at the
top — `y = 0.2` gives `V = 3.01`, `y = 0.4` gives `4.005` — because of the
`0.099` / `0.199` offsets. The overshoot halves at each step and is under 0.01
throughout; it is a rounding artifact of the published constants, not a
different scale. `CALCULATED`.

**Rejected as the scored quantity, for one reason: it saturates.** Everything
above `GDM = 1.6` maps to exactly 6. GDM does not saturate, and §9's disputed
pair sits at 1.018 — close enough to the ceiling that a slightly worse
reproduction would stop being distinguishable from a catastrophic one. Score raw
GDM; **report `V` alongside if a 1–6 number reads better to a non-RF reader**,
which is a presentation choice, not a scoring one.

**(b) The confidence-weighted figure, `xDM_conf`** — Manual eq (1.11):

```
    xDM_conf  =  [ 1·(#EX) + 2·(#VG) + 3·(#G) + 4·(#F) + 5·(#P) + 6·(#EP) ] / N
                                                             with x = A, F, G
```

where `#` counts the point-by-point values falling in each bin. This is the
population-weighted mean bin index — also a continuous 1–6 number, but computed
from the *histogram* rather than from the mean. **Rejected** because it is a
lossy re-derivation of GDM: it quantises every point to its bin before
averaging, so it discards exactly the within-bin resolution the raw mean keeps.
Worth computing only if the histogram is being reported anyway, as a cheap
cross-check that `xDM_conf` and the binned `GDM` tell the same story.

**Why the decay scale is right by accident.** `score_threshold` with
`tolerance=None` uses `abs(target_value)` as its decay scale — here 0.4. So a
failing GDM decays from 100% at 0.4 to 0% at 0.8, which is **exactly the width
of the Fair bin**. `GDM = 0.6` scores 50%. The published bin structure and the
module's existing fallback line up without either being bent to fit.
`CALCULATED`.

**Why 0.4, and why it is honestly a decision.** 0.4 is the Good/Fair boundary,
and it is the only bin edge that FSV's own authors have been observed using as
an accept/reject line: *"anything higher than the 0.4 line (as in [8]) is a good
enough indication"* (ARMMS §4, verbatim — though used there to confirm curves
*differ*, the opposite direction). Against that stands the same paper's warning
in §5: the bins are *"not indications of levels to be set for agreement."* So:
**the scale is the standard's, the threshold is this project's.** It is a
reversible default in exactly ADR-0038's sense — recorded, `PROPOSED` not
`CONFIRMED`, prunes for one pass, and reversible the moment anyone states a
better number. `ASSUMED`.

**Why GRADE and SPREAD stay out of the number.** They are ordinal counts of
bins. Folding an ordinal count into a percentage requires an exchange rate
between "one more bin of scatter" and "so many points of score", and no source
publishes one. They are also not monotone in GDM: §9's run has `GDM = 0.076`
with `GRADE = 2`, and `GDM = 0.285` with `GRADE = 4`. Two different things.

**Why SPREAD gates the *reading* of the score and not the score itself.** SPREAD
is defined by its own authors as *"the level of reliability of the outputs"*.
A high SPREAD means the histogram is nearly flat, so the mean that produced GDM
is summarising a distribution it does not represent — the statistical equivalent
of quoting an average with a huge variance. That is precisely a warning under
the charter's test: it names **what is assumed** (that the mean represents the
points), **what it costs if wrong** (a "Fair" verdict standing in for a curve
that is Excellent in half its span and Very Poor in the other half), and **the
cheapest way to find out** (look at the histogram, which is already computed).
And per "warn, never block", the score is still returned. The `note` field on
`success_score` already exists for this and already tags itself `INFERRED`.

**Why report ADM and FDM separately — the single most valuable thing here.** For
the disputed pair, §9's run gives **ADM = 0.050 (Excellent)** and **FDM = 1.014
(Poor)**. In words: *the two curves sit at the same level and have the same
overall envelope; the resonance is in the wrong place.* That is #142's finding,
recovered automatically from the curves, by a standard method, without anyone
being told to look for it. One GDM number cannot say it and one RMS number
certainly cannot. **The reported verdict for Example 3 should be the ADM/FDM
pair, with GDM as the roll-up — not GDM alone.**

**Why only GDM should be a *scored step*, though.** `orchestration/solver.py`
rolls a candidate's scored steps up by taking the **minimum** (its
`worst_of_scored_steps` rule). Since `GDM ≥ max(ADM, FDM)` always, feeding all
three in would let GDM's score win the minimum anyway — but ADM and FDM are not
independent of GDM, so scoring all three would be double-counting the same
evidence. Score GDM; carry ADM and FDM as reported values.

**Why it must not look like a customer requirement.** ADR-0041 point 5 already
says this check is *"a separate mechanism entirely from real-design scoring
(points 1–4)"*. Reusing `requirement_targets` as machinery risks blurring that.
Three cheap guards: the unit string `"FSV GDM"` matches no physical unit
anywhere in this repo, so `success_score`'s existing exact-string unit refusal
turns any mix-up into an exception rather than a silent wrong answer; the target
stays `PROPOSED` forever, since no customer will ever confirm it; and the
`reason` string says so in words.

### What this does not settle

- **The compared quantity is upstream of FSV and is still open.** Per
  `docs/absorber-scoring-decision-confirmation.md` §5.4, Example 3 is two-port,
  so the curve fed to FSV must be `A = 1 − |S₁₁|² − |S₂₁|²`, never bare
  reflectance. FSV compares whatever two curves it is given; choosing them
  correctly is not FSV's job.
- **The blocking input is digitization, not the algorithm.** A repo-wide check
  recorded in the prototype found **no point-by-point digitized curve for either
  Landy's Fig. 4 or the patent's FIG. 7G** anywhere in this repo — only scalar
  anchors (centre frequency, FWHM, peak depth). FSV needs both full curves.
  **That is the missing measurement**, and it is cheap: both figures exist and
  Landy's arXiv source carries figure files.
- **Whether ADM/FDM get their own thresholds.** The recommendation scores only
  GDM. If the ADM/FDM split turns out to be the thing the reader actually acts
  on, a second reversible default on FDM alone would follow the same pattern.
  Not proposed here, because nothing yet needs it.

---

## 9. Re-running this repo's prototype with the corrected formulas

`prototype/fsv-feasibility/fsv_prototype.py` was re-run in a scratch copy with
§2–§6's equations swapped in — **same synthesized curves, same band split, same
bins, same sweep**, so the only variable is the FSV maths. `CALCULATED`, on
inputs that remain `ASSUMED` (the curves are Lorentzian stand-ins, not digitized
data — the prototype's own caveat carries over unchanged).

| Offset (× Landy's FWHM) | RMS error (dB) | ADM | FDM | **GDM** | Grade | Spread |
|---|---|---|---|---|---|---|
| 0.05 | 0.177 | 0.002 | 0.076 | **0.076** Excellent | 2 | 2 |
| 0.25 | 0.813 | 0.012 | 0.284 | **0.285** Good | 4 | 4 |
| 0.50 | 1.349 | 0.022 | 0.431 | **0.432** Fair | 5 | 5 |
| 1.00 | 1.829 | 0.035 | 0.480 | **0.484** Fair | 5 | 5 |
| 2.00 | 2.075 | 0.029 | 0.748 | **0.750** Fair | 5 | 5 |
| 3.00 | 2.134 | 0.025 | 0.893 | **0.895** Poor | 6 | 5 |
| 5.00 | 2.167 | 0.033 | 1.025 | **1.027** Poor | 6 | 5 |
| **Patent Ex. 3 vs Landy** | **2.364** | **0.050** Excellent | **1.014** Poor | **1.018 Poor** | **6** | **6** |

Sanity checks, both passed: two identical curves give `ADM = FDM = GDM = 0.0`
exactly; an amplitude-only change (one curve scaled by 0.85, no frequency shift)
raises ADM to 0.169 while leaving FDM at 0.131 — the measure that is supposed to
notice a level change is the one that notices it.

**Three findings.**

1. **The prototype's headline number was wrong, and in the direction that
   mattered.** It reported the disputed pair as `GDM = 0.3677, "Good"` and
   worried in print that *"a consumer reading only GDMc = 0.37, Good would be
   misled."* The corrected value is **1.018, "Poor"** — a whole two bins worse.
   The gap traces almost entirely to §7.3's FDM errors, which suppressed the
   feature term by roughly the factor its missing constants imply.
2. **FSV does not saturate.** The prototype concluded *"GDMc alone saturates
   early and stops [discriminating]… plain RMS error is the metric that keeps
   discriminating."* With the published equations GDM rises **monotonically
   across the entire sweep**, 0.076 → 1.027, while RMS in dB is the one that
   flattens out (2.08 → 2.13 → 2.17 dB over the last three rows). **The
   conclusion reverses.** `CALCULATED`.
3. **#116's challenge is answered, and the answer is better than either side
   expected.** The worry recorded on `docs/absorber-scoring-decision-confirmation.md`
   §5.4 was that at five resonance-widths apart *"FSV may report near-total
   disagreement just as bluntly as RMS error would, which would undercut the
   stated reason for preferring it."* It does not. It reports **Poor, not Very
   Poor** — and it splits that verdict into `ADM = Excellent` and `FDM = Poor`,
   which is the informative answer: the two curves agree on everything except
   where the resonance is. **The reason FSV was chosen over RMS on #110 stands,
   though not quite for the reason given.** #110 argued FSV would avoid
   over-penalising a small frequency shift. What it actually does here is
   *localise* the penalty into the half of the comparison that deserves it. That
   is more useful than the argument that was made for it.

**Caveats, load-bearing.** The curves are synthesized Lorentzians, so these
numbers characterise the *method*, not the patent. The band-split retains the
prototype's approximation of the 40% rule (it lacks the manual's "+5 bins" and
±2-bin taper, §1). The derivative span follows MDPI's ±2/±3 rather than the
manual's ±1 (§3). Any of these could move the third digit. None of them can move
a two-bin gap or reverse a monotonic trend, which is all conclusions 1–3 rest on.

---

## 10. Every route tried

**Succeeded:**

| Route | Result |
|---|---|
| **ARMMS conference paper**, direct download with a browser user-agent (WebFetch got 403; `curl` with a UA got 200) | The whole method: procedure, eqs (1)–(3), Table I bins, GRADE/SPREAD, the SPREAD-weighted GDM. **By FSV's own authors** |
| **4× typeset render of the ARMMS equation pages** (`pymupdf`) | Decisive. The text layer scrambles the maths beyond use; the render is unambiguous |
| **MDPI *Electronics* 11(16):2532**, via the University of Genova repository mirror (`iris.unige.it`) — mdpi.com itself returned 403 | **Eqs (5)–(12) stated verbatim as transcribed from IEEE Std 1597.1.** The single most valuable source: a third party's direct reading of the standard |
| **UAq EMC Laboratory FSV Tool directory**, found by following a search-result mention of a 2009 URL | Still live. **`1DFSV_Manual.pdf`** — the reference implementation's own 54-page specification, and the only source for the +5-bin break point, the ±2-bin taper, GRADE/SPREAD ranges, `xDM_conf`, and Table 1.2 |
| **`fsv1d.ctf`**, downloaded and unzipped | Confirms the reference tool is MATLAB-compiled and **encrypted** — a definite negative, not a failure to fetch |
| **`data_examples/` directory listing** | 8 survey curve pairs + a 6-step perturbation series + analytic cases. **Reference vectors for a re-implementation** |
| **IBIS Summit 2011 slides** (Di Febo, de Paulis, Orlandi) | Independent confirmation of the pipeline and bins; the clean GRADE definition; and the tool's existence and distribution terms |
| **GitHub code search** | Found `mishka-zz/freecad-microwave` `tests/fsv.py` — a correct LGPL-2.1 Python implementation — **and this repo's own prototype**, which the ticket did not mention |
| **Unpaywall on Duffy *et al.* 2006 Part I** (`10.1109/TEMC.2006.879358`) | `is_oa: false`, `oa_status: "closed"`, `has_repository_copy: false`, `oa_locations: []`. A positive finding that no free copy exists |
| **Re-running the repo prototype with corrected maths** | Overturned its conclusion (§9) |

**Failed, and why:**

| Route | Outcome |
|---|---|
| **IEEE Std 1597.1-2008/2022 and 1597.2-2010** | Behind IEEE. **Still unread.** Every formula here is from a restatement. Stays in `RUNNING-LISTS.md` §1, but its blocking weight is now much lower — MDPI's transcription is a direct reading of it, and the developers' own manual agrees with that transcription |
| **Duffy, Martin, Orlandi, Antonini, Benson & Woolfson (2006), Part I** | **Closed access, no repository copy exists** — Unpaywall, positively. The ticket's hoped-for author-page preprint does not exist |
| **Orlandi, Duffy, Archambeault, Antonini, Coleby & Connor (2006), Part II** | Same, not independently confirmed. `academia.edu` hosts scans of both Parts; every `academia.edu` URL returned **403**, as it did on the prior pass |
| **Bongiorno & Mariscotti (2016/17), "Variability and Consistency of FSV Method Implementation"** | IEEE-paywalled; no `iris.unige.it` mirror found, unlike their 2022 paper. **The one source that would settle §3's and §6's remaining ambiguities.** → `RUNNING-LISTS.md` §1 |
| **Orlandi, Antonini, Ritota & Duffy (2006), "Enhancing FSV interpretation… with Grade-Spread"** | IEEE ISEMC, paywalled. The original GRADE/SPREAD paper; the manual substitutes adequately |
| **`scholarsmine.mst.edu`** (Missouri S&T repository, an Archambeault FSV paper) | **403** both via WebFetch and via `curl` with a browser UA — unlike ARMMS, where the UA was enough |
| **`mdpi.com` direct PDF** | 403. The `iris.unige.it` mirror worked. **Worth trying institutional mirrors first for MDPI** |
| **`hal.science` mirror of the same MDPI paper** | Returned an HTML landing page, not the PDF, despite a `.pdf` URL |
| **MATLAB File Exchange** | No FSV implementation. The one apparent hit is an unrelated ML algorithm sharing the initials (§7.4) |
| **`orlandi.ing.univaq.it`** (the lab site the 2011 slides give as the contact address) | **503.** The files survive only at the bare `ing.univaq.it/uaqemc/` directory index, which nothing links to. **Mirror anything wanted from there** |

**A tooling note worth carrying.** Three of the four decisive documents were
403 to `WebFetch` and 200 to `curl` with an ordinary browser user-agent, and two
of them needed a **typeset page render** rather than text extraction to read
their maths. The pattern from `docs/costa-thin-spacer-correction.md` §8 repeats
exactly: for equation-bearing PDFs, `curl -A` then `pymupdf` render, and read the
picture.

---

## 11. Register updates

**For `RUNNING-LISTS.md` §1 — one entry to soften, one to add:**

> **IEEE Std 1597.1-2008/2022 & IEEE Std 1597.2-2010** — still behind IEEE and
> still unread, but **no longer blocking #168**. `docs/feature-selective-validation-spec.md`
> recovers every ADM/FDM/GDM equation, all six bin boundaries and both
> GRADE/SPREAD definitions from three independent sources, one of which
> (Bongiorno & Mariscotti 2022, MDPI *Electronics* 11:2532) states verbatim that
> its equations are transcribed from IEEE Std 1597.1 itself. What the standard
> would still settle: the FDM derivative span (±1 or ±2/±3), and whether eq
> (1.9) carries its outer absolute value.

> **Bongiorno, J. & Mariscotti, A. (2016/17)**, *"Variability and Consistency of
> Feature Selective Validation (FSV) Method Implementation,"* *IEEE Trans. EMC*
> **59**(5), pp. 1474–1481, [doi:10.1109/TEMC.2016.2613830](https://doi.org/10.1109/TEMC.2016.2613830)
> — Behind IEEE; no institutional mirror found, unlike the same authors' 2022
> paper. It is a published catalogue of exactly the ambiguities
> `docs/feature-selective-validation-spec.md` §3 and §6 had to resolve by
> majority vote among sources. Bears on #168 and on whatever ticket implements
> FSV.

**For whoever implements this (a separate ticket — #168 specs, does not build):**

- The formulas are §2–§4; the bins are §5; GRADE/SPREAD are §6; the integration
  shape is §8 and needs **no change to `success_score.py` or
  `requirement_targets.py`**.
- **Regression-test against `data_examples/` from §7.1**, and against
  `parallel_data/` for monotonicity. Mirror them; the host is an unlinked 2009
  directory index on a server whose sibling hostname already returns 503.
- **`prototype/fsv-feasibility/fsv_prototype.py` should not be the starting
  point** — §7.3 lists four substantive deviations. Either port §7.2's LGPL-2.1
  Python file (a licence decision, and it has no GRADE/SPREAD) or write it from
  §2–§6.
- The blocking input is **digitized curves for Landy Fig. 4 and the patent's FIG.
  7G**, which this repo does not have (§8).

**Closes:** all five of #168's sub-questions. The one thing it cannot close is
the standard's own text, and §10 records why that no longer blocks anything.
