# Stacked Dual-Band FSS at GPS L-Band: Thickness Feasibility

**Research date:** 2026-09-12
**Question:** Can two patterned-conductor FSS layers, stacked with a thin
sub-wavelength spacer, produce two independent, clean passbands — GPS L1
(1575.42 MHz) and GPS L2 (1227.60 MHz) — inside a thin, conformal-skin
thickness budget? This repo's X-band absorber work targets **0.87–2.0 mm**
total stack thickness
(`docs/voltera-multilayer-capability.md`), but that number was derived for
8–12 GHz absorbers on a specific host, not 1–2 GHz bandpass filters. No
GitHub issue names this requirement yet (searched; none found) — this
document is exploratory groundwork, not a response to a filed ticket.

Provenance tags are `CONTEXT.md`'s nine-value set — `MEASURED`, `SIMULATED`,
`CALCULATED`, `MANUFACTURER-SPECIFIED`, `LITERATURE-SUPPORTED`,
`INTERNAL-HISTORY`, `INFERRED`, `ASSUMED`, `UNKNOWN` — used exactly, never a
parallel confidence scale.

---

## Bottom line up front

**Six findings.** The short version: the worry in the ticket framing is
*half* right. A spaced two-layer stack (an air or foam gap between two
separately-backed FSS sheets — the mental picture a "Salisbury-adjacent"
worry conjures) really does cost tens of millimetres at L-band, confirmed by
two published examples that operate at almost exactly this frequency. But
that is not the only way to build a two-conductor-layer dual-band FSS, and
the other way — two differently-tuned conductor patterns printed on the
**front and back faces of one thin substrate**, no separate spacer layer at
all — is published, measured, and gives a genuinely independent two-band
response at a fraction of a millimetre of substrate, in a material class
this programme has already measured. Scaled to GPS L-band, that route
plausibly lands under 1 mm. Nobody has built it at GPS frequencies, and the
literature that comes closest to GPS's *own* band separation (L1/L2 are only
28% apart — closer than any design read in full below) could not be
retrieved.

1. **Quarter-wave inter-layer spacing is not a physical requirement for a
   stacked bandpass FSS — that requirement is specific to the Salisbury-screen
   absorber geometry the ticket's own comparison invokes, and it does not
   carry over.** Multiple published cascaded/stacked bandpass FSS designs use
   gaps well under λ/4 (as low as ~0.03–0.15λ across the read sources, §2) and
   still report clean, well-defined, angularly-stable passbands. `Ebrahimi et
   al.` (2018) state this explicitly for their own 2-layer design: the
   fractional-bandwidth-preserving cascade uses "a sub-wavelength air gap,"
   not a quarter-wave one (`LITERATURE-SUPPORTED`, §2.1).

2. **But at GPS L-band the wavelength is so long that even a generous
   fractional saving barely moves the absolute number.** L1's free-space
   wavelength is 190.3 mm and L2's is 244.2 mm (`CALCULATED`, §1) — roughly
   20–25× longer than the X-band wavelengths (25–37.5 mm) this programme's
   own 0.87–2.0 mm absorber budget was built around. A gap of even 5–15% of
   an L-band wavelength is *still* 10–35 mm in absolute terms. This is not a
   hypothetical: it is exactly what the two genuinely-L-band multilayer FSS
   papers read in full actually built — a **30 mm** PMI spacer (Wang et al.,
   *Materials* 2025, PMC12471704, operating 1.26–1.9 GHz) and **33–34 mm**
   foam gaps (a 2025 *Scientific Reports* L/S/C-band filter, PMC12290089,
   with a rejection band spanning 1.2–2.62 GHz) (`LITERATURE-SUPPORTED`, §3).
   Neither reaches within an order of magnitude of "a few mm."

3. **A different, thinner architecture exists and is measurement-validated,
   though not at GPS frequencies: two differently-tuned conductor patterns on
   the front and back faces of one thin substrate, with no separate spacer
   layer at all.** Rahmani-Shams et al. (*J. Appl. Phys.* 2018) build a
   genuinely two-independent-band FSS (2.28–4.66 GHz and 5.44–11.3 GHz, each
   independently tunable) on a **single 0.422 mm** Rogers RO4350B substrate
   (εr = 3.48) — **0.0032λ** at the lower band. Payne (2022, arXiv:2211.07396)
   does the same at S/C-band (2.4/5.8 GHz) on a 0.635 mm substrate
   (εr = 10.2) — **λ/200 = 0.005λ**. Both are read in full below (§4);
   neither uses an air gap between the two conductor layers at all — the
   "spacer" *is* the substrate the two patterns are printed on.

4. **RO4350B is already in this programme's own measured substrate shortlist**
   (`docs/xband-absorber-substrate-shortlist.md` #11: εr 3.48 ± 0.05,
   tanδ 0.0037 at 10 GHz, `MANUFACTURER-SPECIFIED`, single-ply 0.17–1.52 mm)
   — the same electrical regime Rahmani-Shams' design used, at a thickness
   this programme already stocks. **But that same shortlist entry marks it
   "Rigid — no bend," host regime `A` only** — a large-radius rigid host, not
   the tight/compound-curvature conformal skin this programme's charter
   targets. The programme's own flexible, `A+B`-rated substrate closest in
   electrical regime is Kapton 500HN — εr 3.2 ± 0.03, tanδ 0.012 ± 0.004,
   `MEASURED` (same shortlist, #2) — close enough in εr that the same
   architecture is plausible on it, but nobody has built or simulated that
   combination (`INFERRED`, §6).

5. **Scaling the Rahmani-Shams ratio to GPS L-band, arithmetically, lands
   under 1 mm** — 0.61 mm at L1, 0.78 mm at L2 (`CALCULATED`, §6) — comfortably
   inside any "a few mm" reading of a conformal-skin budget. This is a
   straight proportional extrapolation of one paper's own thickness-to-
   wavelength ratio, not a citation of anyone building this at GPS frequency,
   and it says nothing about whether the same geometry, decoupling trick, and
   bandwidth requirement still work at 1/1.5–1/4 the frequency it was
   demonstrated at. Treat it as a plausibility signal, not a design.

6. **The physical mechanism that makes any of this work — near-field
   capacitive/inductive coupling between the two conductor layers through the
   dielectric between them — is exactly the mechanism that can blur two
   different-frequency layers into each other if it isn't deliberately
   managed**, and every source that demonstrates genuine independence does so
   only after adding a specific decoupling degree of freedom (§5). GPS L1/L2
   sit only **28% apart** in frequency (1575.42/1227.60 = 1.283) — closer
   together than any of the fully-read sources (ratios 1.85–2.42, §5.3) —
   and the one search result whose title matches GPS's own regime most
   closely, an "ultra-thin **closely spaced** dual-band" FSS (Yang et al.,
   *Electronics Letters* 2017, 8.2/11.4 GHz, ratio 1.39), was **paywalled and
   could not be read** (§7). **Verdict: physically plausible via the
   single-substrate front/back architecture, not via a spaced two-layer
   stack — but unverified at GPS frequencies, unverified at GPS's own tight
   band separation, and unverified on this programme's own flexible
   substrates.** It is a real, testable design direction, not a settled one.

---

## 1. The thickness budget, redone for L-band

All `CALCULATED`. `c = 299,792,458 m/s`.

| Quantity | L1 (1575.42 MHz) | L2 (1227.60 MHz) |
|---|---|---|
| Free-space wavelength `λ0 = c/f` | **190.29 mm** | **244.21 mm** |
| Free-space quarter-wave `λ0/4` | 47.57 mm | 61.05 mm |
| Guided λ at εr = 2.9 (silicone, measured) | 111.74 mm | 143.41 mm |
| Guided quarter-wave at εr = 2.9 | 27.94 mm | 35.85 mm |
| Guided λ at εr = 3.2 (Kapton, measured) | 106.38 mm | 136.52 mm |
| Guided quarter-wave at εr = 3.2 | 26.59 mm | 34.13 mm |

This reproduces the ticket's own arithmetic (27–35 mm quarter-wave spacing
at εr ≈ 3) and confirms it. **What it also shows, and what motivates this
whole document**: 8–12 GHz free-space wavelengths are 25–37.5 mm, so
X-band's own quarter-wave spacer is a few mm — small enough that this
programme's 0.87–2.0 mm absorber budget and X-band quarter-wave spacing are
the *same order of magnitude*, which is exactly why sub-quarter-wave
"closely spaced" tricks buy a large *relative* win there. At L-band the
free-space wavelength is **20–25× longer** than at X-band (recompute:
190.3 mm / 8.5 mm ≈ 22.4×, using 10 GHz's own 30 mm halved for an 8 GHz
comparison point is unnecessary — the ratio against this programme's own
X-band λ0 = 30 mm at 10 GHz is 190.3/30 = 6.3× at L1 and 244.2/30 = 8.1× at
L2). Either way, the arithmetic in §2–3 below shows this ratio is what
erases most of the benefit of "closely spaced" cascading in absolute terms.

**No host curvature was supplied with this requirement**, so "a few mm" is
carried forward from the ticket's own framing (`ASSUMED`, not a
Requirement-derived constraint per `CONTEXT.md`'s own definition of that
term — a real bend-radius number would derive one). The existing
0.87–2.0 mm / `T ≤ 2mm` figures the design-family registry carries as a
spine-field default trace to the X-band absorber patent's own worked
examples (`docs/voltera-multilayer-capability.md` §6); nothing in this
document asserts that specific numeric range transfers to an L-band
bandpass family, and this section's own arithmetic is why it should not be
assumed to.

---

## 2. What the general (non-L-band) literature says about inter-layer spacing

Two genuinely-read primary sources (arXiv author manuscripts, full text
extracted via `pdftotext`, not a search-engine paraphrase) establish that
**quarter-wave spacing is a choice, not a requirement**, for stacking
bandpass FSS layers.

### 2.1 Ebrahimi, Baum, Scott & Ghorbani (2018), arXiv:1802.07454

*"Narrowband Bandpass Frequency Selective Surface with Miniaturized
Elements,"* RMIT University. **Read in full.**

Their own words on the conventional approach, stated as the alternative
they are *not* using: *"the FSS layers can be cascaded by using quarter
wavelength (λ/4) spacers acting as impedance converters between them."*
Instead: *"a second-order FSS has been implemented here by cascading two
layers of the FSS implemented in the previous section with a **sub-
wavelength air gap** between them."*

| Parameter | Value | Provenance |
|---|---|---|
| Center frequency | 2.7 GHz | `LITERATURE-SUPPORTED` |
| Air gap `h1` | 10 mm | `LITERATURE-SUPPORTED` |
| `λ0` at 2.7 GHz | 111.03 mm | `CALCULATED` |
| `h1 / λ0` | **9.0%** | `CALCULATED` |
| Fractional bandwidth achieved | 8.5% | `LITERATURE-SUPPORTED` |
| Angular stability | stable to 45°, both TE/TM | `LITERATURE-SUPPORTED` |

This is a **same-band** second-order cascade (raising the filter *order* of
one passband, not producing two different passbands), but it is direct
evidence against the premise that stacking FSS layers requires λ/4: **9% of
a wavelength, not 25%, and the result is a clean, angularly-stable
passband.** Scaled to GPS frequencies (same 9.0% fraction, `CALCULATED`,
not a citation): 17.14 mm at L1, 22.0 mm at L2 — still tens of mm, because
L-band's wavelength is so long. This is the pattern that recurs through
§3: the *fraction* really is small; the *absolute number* at L-band is not.

### 2.2 Other same-genre findings (`LITERATURE-SUPPORTED`, via automated fetch-and-summarize of the published HTML/abstract — not independently re-read against the raw source, flagged per §7)

| Design | Bands | Layers/spacer | Total thickness |
|---|---|---|---|
| Li et al. (2021), quasi-elliptical bandpass FSS | single band, 2nd-order | 2 layers, air spacer | **0.053λ** |
| Broadband 2nd-order bandpass FSS (PMC11130335, *Sci. Rep.* 2024) — read in full, §3.4 below | dual **different** bands, 19.42/42.78 GHz | 3 metal layers, F4B-M 0.45 mm ×2 | **0.05λ0** total profile |
| Dual-band FSS, nested apertures (PMC11205420) | 8.45/12.76 GHz | **single** patterned layer, no stack at all | not addressed by stacking at all — see §4.3 |

The consistent range across every stacked-bandpass design found, at every
frequency, is **roughly 0.03–0.15λ** for the electrical thickness of the
inter-layer separation — well under λ/4 in every case. **The physics does
not force quarter-wave spacing for a bandpass FSS the way it forces it for
a Salisbury absorber** (a genuinely different geometry — see
`docs/bandpass-fss-physical-bound-primary-source.md` for why Bode–Fano
itself does not even apply to a free-standing bandpass FSS). What the
physics *does* force is a floor set by the fraction needed for adequate
mutual coupling between the two resonant structures (§5) — and that floor,
expressed in wavelengths, does not shrink just because the operating
frequency is lower.

---

## 3. Direct L-band and GPS-adjacent evidence

Two sources operate at frequencies overlapping or bracketing GPS L-band and
were read from raw fetched HTML (PMC full text, stripped of markup and
grepped directly — not summarized by an intermediate tool).

### 3.1 Wang et al. (2025), *Materials* 18(18):4414, PMC12471704 — genuinely L-band, genuinely two cascaded layers

*"A Dual-Layer Frequency Selective Surfaces with Tunable Transmission and
Fixed Absorption Bands."* **Read from raw PMC HTML.**

Quoted verbatim: *"The proposed double-layer FSSs are composed of two
cascaded metal pattern layers... A 30-mm-thick polymethacrylimide (PMI)
layer is used as the support between the two layers of structure."* Each
metal layer sits on its own 0.2 mm FR4 backing.

| Parameter | Value |
|---|---|
| Tunable transmission band | **1.26–1.9 GHz** — directly overlaps GPS L2 (1227.6 MHz sits just below this range) and reaches past L1 |
| Fixed absorption band | 5.56–5.72 GHz |
| Spacer | **PMI foam, 30 mm** |
| Substrate (per layer) | FR4, 0.2 mm |
| Total stack | ≈ 30.4 mm |
| Own reported figure of merit | **0.103 λL** (λL = free-space λ at the lowest operating frequency, per their own Table 1 footnote) |
| Cross-check (`CALCULATED`) | 30 mm / λ(1.26 GHz, 237.93 mm) = **0.126λ**; 30 mm / λ(1.9 GHz, 157.79 mm) = **0.190λ** — the paper's own 0.103λ does not land inside this range from either band edge, a discrepancy this document could not resolve (their λL definition may reference a different frequency point than either printed edge) |

Their own explanation of *why* the response drifts with frequency, quoted
verbatim: *"The difference around 5.5 GHz is mainly caused by the coupling
capacitance between the double-sided FSS. Under the condition that the FR4
thickness remains unchanged, the higher the frequency, the greater the
equivalent coupling capacitance. To reduce the difference, the thickness of
the FR4 layer can be reduced as much as possible."* This is direct, named
evidence of the coupling mechanism §5 discusses — and it is the layers'
*own* thin backing that couples, not the 30 mm PMI gap, which is there to
keep the two resonant structures far enough apart that they behave as
separately-tunable circuits rather than one merged one.

**Their own comparison table (Table 1) is independently useful** — it
tabulates thickness-as-λL for seven prior tunable FSS designs, `LITERATURE-
SUPPORTED` via their own citation and read directly from the raw text:

| Ref. | Bands (GHz) | Thickness (λL) |
|---|---|---|
| [26] | 7.4–12.1 | 0.13λL |
| [27] | 6.92–13.02 | 0.114λL |
| [11] | 3.8–5.2 | 0.107λL |
| [28] | 2.92–4.66 | 0.122λL |
| **[29] Ma, Wang, Yu & Zhao (2022), *IEEE TAP* 70(12):12381–12386** | **1.14–1.35 and 2.01–2.61** | **0.006λL** |
| [30] | 1.8–4.5 | 0.04λL |
| [15] | 3–4.55 | 0.005λL |
| This work | 1.26–1.9 | 0.103λL |

**Reference [29] is the single most relevant citation found in this entire
search and could not be retrieved.** Its lower band, **1.14–1.35 GHz,
directly contains GPS L2 (1227.60 MHz)**, it is explicitly a genuinely
**dual-band** design (two separate bands, not one tuned band), titled
*"Design of Dual-Band Frequency-Selective Surfaces with **Independent
Tunability**,"* and its reported thickness is **0.006λL** — at λL =
263.0 mm (free space at 1.14 GHz), that is **1.58 mm**. If this figure
holds up under a direct read, it would be the strongest available evidence
that a genuinely independent, genuinely-in-band dual-band FSS at
essentially GPS L-band can be built inside a few mm. **This document did
not retrieve IEEE TAP 70(12):12381–12386 — it is cited here only as it
appears in another paper's comparison table, `LITERATURE-SUPPORTED` at one
remove, not independently confirmed** (§7).

### 3.2 A 2025 *Scientific Reports* L/S/C-band filter, PMC12290089

*"Multi-layer Frequency Selective Surface Wideband Filter with High
Selectivity Operating in L, S, and C Bands."* **Read from raw PMC HTML.**

This is a **wideband bandpass filter** (−3 dB passband 2.79–6.65 GHz, 90%
fractional bandwidth) whose **rejection** band, not passband, covers
1.2–2.62 GHz — i.e. GPS L-band is where this design deliberately blocks
transmission, the opposite of what a GPS filter needs. It is included here
purely for its **structural numbers**, because it is a real, physically
built multi-layer FSS operating with L-band-scale wavelengths:

| Layer | Substrate | Gap to next layer |
|---|---|---|
| 1 — Meandered Square Loop | 0.5 mm FR4 | 33 mm (foam) |
| 2 — Grid | 2.24 mm FR4 | 34 mm (foam) |
| 3 — Patch | 2.24 mm Isola ITERA45 | — |
| **Total** | | **67 mm** |

At λ(1.2 GHz) = 249.83 mm (`CALCULATED`), the two gaps are **0.132λ** and
**0.136λ** — again squarely inside the 0.03–0.15λ range §2 establishes, and
again tens of millimetres in absolute terms. Their own stated design
rationale, quoted verbatim: *"optimal performance is achieved by precisely
adjusting the interlayer spacing, which is critical for minimizing
undesired coupling effects."* — the spacer's job is explicitly to control
coupling, not simply to hold the layers apart.

### 3.3 A GPS-frequency filter that is the wrong device class: PLOS ONE 10.1371/journal.pone.0224478

Bhattacharya, Roy et al., *"Left-handed metamaterial bandpass filter for
GPS, Earth Exploration-Satellite and WiMAX frequency sensing applications."*
Targets **1.55 GHz** (close to but not L1's 1575.42 MHz), on a single
1.575 mm Rogers RT-5880 substrate (εr = 2.2, **0.034λ**), and reports
**three** passbands (1.55/2.70/3.60 GHz) from one layer.

**This is not the same device class as a free-space FSS.** It is described
as *"a microstrip framework consisting of a dual mode double negative (DNG)
metamaterial based bandpass filter"* — a guided-wave, two-port microstrip
circuit filter, not a periodic free-space array illuminated at normal (or
oblique) incidence the way `BANDPASS_FSS` in `designs/design_families.py`
is defined. Its thinness (1.575 mm, itself coincidentally inside a "few mm"
budget) does not transfer to the free-space FSS question this document is
answering, and it is flagged here specifically so it is not mistaken for
supporting evidence for a spatial-filter radome design.

### 3.4 A genuinely dual-different-band 3-layer stack, read in full: PMC11130335 (*Sci. Rep.* 2024)

*"A broadband second-order bandpass frequency selective surface for
microwave and millimeter wave application."* **Read from raw PMC HTML.**

Two genuinely different bands (19.42 GHz and 42.78 GHz — not the same band
sharpened), 3 metal layers, F4B-M substrate (εr = 2.65, tanδ = 0.0013,
h = 0.45 mm ×2). Their own comparison table, read directly: *"This work
19.42/42.78 ... 0.05 [λ0 profile] 0.14 [periodicity, λ0]"* — confirming a
total profile of **0.05λ0** relative to the lower band's center frequency.
Their own circuit description states the coupling is deliberate: *"This
circuit is a second-order coupled-resonator bandpass filter (BPF) with
inductive coupling."* Scaled to GPS L-band (`CALCULATED`, not a citation):
9.51 mm at L1, 12.21 mm at L2 — again tens of mm, consistent with §2–3's
pattern for any *spaced-layer* architecture.

---

## 4. The architecture that actually gets thin: front-and-back-of-one-substrate, not spaced layers

Every design in §2–3 shares one structural feature: **a distinct spacer (or
electrically-thick backing) sits between the two resonant conductor
layers**, and its job — explicitly stated by two of the sources above — is
to control how strongly the layers couple. That architecture's floor is
0.03–0.15λ, which is tens of mm at L-band.

Two sources, both read in full, use a **different architecture entirely**:
two differently-tuned conductor patterns on the **front and back faces of
one thin substrate**, with no separate spacer layer of any kind — the
substrate itself is the entire separation.

### 4.1 Rahmani-Shams, Mohammd-Ali-Nezhad, Nooraei Yeganeh & Sedighy (2018), *J. Appl. Phys.* 123, 235301

*"Dual band, low profile and compact tunable frequency selective surface
with wide tuning range."* **Read in full**, arXiv:1806.08494 (published
version, same content). Quoted verbatim: *"The proposed FSS is composed of
two metallic layers printed on both sides of the substrate... The loaded
varactors between the grids and the cross strips with a designed bias
network achieve two independent tunable pass bands."*

| Parameter | Value | Provenance |
|---|---|---|
| Substrate | Rogers RO4350B, **0.422 mm**, εr = 3.48 | `LITERATURE-SUPPORTED` |
| Copper thickness | 0.018 mm, both faces | `LITERATURE-SUPPORTED` |
| Low band (tunable) | 2.28–4.66 GHz | `LITERATURE-SUPPORTED` |
| High band (tunable) | 5.44–11.3 GHz | `LITERATURE-SUPPORTED` |
| `λ0` at 2.28 GHz | 131.49 mm | `CALCULATED` |
| Substrate thickness / λ0 | **0.0032λ (≈ λ/312)** | `CALCULATED` |
| Angular stability | stable to 60°, TE and TM | `LITERATURE-SUPPORTED` |
| Independence mechanism | separately-biased varactor groups on geometrically distinct resonators (small/large cross strips); explicit mutual-coupling terms `k1`, `k2` in their own equivalent circuit | `LITERATURE-SUPPORTED` |

**RO4350B, at exactly this thickness range, is already in this programme's
own measured shortlist** (`docs/xband-absorber-substrate-shortlist.md`,
entry #11: εr 3.48 ± 0.05, tanδ 0.0037 at 10 GHz, `MANUFACTURER-SPECIFIED`,
stocked 0.17–1.52 mm single-ply). **But that entry is rated "Rigid — no
bend," host regime `A` only** (large-radius rigid hosts). It is not a
conformal-skin material by this programme's own definition. The nearest
`A+B`-rated (flexible) material in the same shortlist at comparable εr is
**Kapton 500HN — εr 3.2 ± 0.03, tanδ 0.012 ± 0.004, `MEASURED`** (same
document, entry #2) — close enough electrically that the Rahmani-Shams
architecture is plausible on it, but this is this document's own inference
(`INFERRED`), not anything demonstrated in the read literature.

### 4.2 Payne (2022), arXiv:2211.07396 — the higher-εr, thinner-still version

*"Low-Profile Dual Band-pass Frequency Selective Surface with independent
bands of operation."* **Read in full** via `pdftotext` extraction.

| Parameter | Value | Provenance |
|---|---|---|
| Substrate | Rogers RT/duroid 6010, **0.635 mm**, εr = 10.2, tanδ = 0.0023 | `LITERATURE-SUPPORTED` |
| Low band | 2.4 GHz (measured 2.45 GHz) | `LITERATURE-SUPPORTED` |
| High band | 5.8 GHz | `LITERATURE-SUPPORTED` |
| `λ0` at 2.4 GHz | 124.91 mm | `CALCULATED` |
| Substrate thickness / λ0 | **λl/200 = 0.005λ** | `LITERATURE-SUPPORTED` (their own stated figure) / `CALCULATED` (cross-check: 124.91/200 = 0.625 mm ≈ 0.635 mm — matches) |
| Measured insertion loss | 0.6 dB both bands | `LITERATURE-SUPPORTED` |
| 3 dB bandwidth | 18.5% (low), 32% (high) | `LITERATURE-SUPPORTED` |
| A separate 3-layer "higher-order" enhancement | 5 mm total = **λl/25** | `LITERATURE-SUPPORTED` |

The paper is explicit about *why* it avoids the conventional cascade,
quoted verbatim: *"Traditional methods cascade multiple FSS layers with
quarter wavelength between each layer in order to achieve higher order
responses. This method may be useful for application that operate in high
frequencies. But at low frequency, this approach becomes problematic as it
results in more weight and thickness of the structure. The latter approach
leads to a deterioration of the filter performance for wave impinging at
oblique incidence."* **This is the same concern the GPS ticket raises,
stated independently by an unrelated author about a different low-frequency
band (S/C), and resolved the same way**: not by finding a thinner spacer,
but by abandoning the spaced-layer architecture altogether.

The paper is equally explicit that the naive version of this architecture
does *not* give independent control for free — see §5.2.

### 4.3 The escape hatch that avoids the question entirely: one patterned layer, two resonances

PMC11205420 (dual-passband FSS, 8.45/12.76 GHz) achieves two passbands from
a **single** patterned conductor layer with two nested/concentric resonant
apertures per unit cell, rather than stacking two layers at all. This
sidesteps the inter-layer coupling question completely — there is no
second layer to couple with — at the cost of packing two independently-
sized resonant features into one unit cell, which becomes harder as the two
target frequencies get closer together (more feature crowding at similar
scale) rather than easier. Whether this scales to GPS L1/L2's 1.283
frequency ratio is not addressed by anything read for this document
(`UNKNOWN`) — worth flagging to the design loop as a third option alongside
the two stacked architectures above, not evaluated further here.

---

## 5. The coupling mechanism, and the detuning risk (research question 3)

**Mechanism.** Every equivalent-circuit model read for this document
represents the two conductor layers as coupled resonant circuits — a
parallel-LC "tank" or hybrid resonator on each layer, joined by a mutual
inductance or capacitance term whose magnitude depends on how close the
layers sit and how much near-field overlap their unit cells have
(Ebrahimi's Fig. 1(a) hybrid resonator with a transmission-line stub;
Rahmani-Shams' Fig. 7 with explicit `k1`/`k2` coupling coefficients; Payne's
Fig. 2/9 parallel-tank-plus-series-resonator networks). Physically: each
patterned conductor's evanescent (non-propagating) near field extends past
the plane of the pattern by roughly a unit-cell-period's worth of distance,
and if the second conductor sits inside that field it experiences an
induced current that was not part of its own isolated design — the layers'
resonances shift and mix rather than adding independently. This is the same
physical fact §2's own sources use *productively* (cascading a same-tuned
layer to raise filter order) and the same fact §4's sources must
*deliberately suppress or route around* to keep two differently-tuned
layers from smearing into one shared response.

**Does closeness risk detuning/blurring? Yes, explicitly documented, in
both directions:**

- Payne's own account of the technique she improves on (Lockyer et al.'s
  complementary FSS), quoted verbatim: *"This design... does not allow
  flexible control of the passband or transmission zero locations as the
  constituting L and C cannot be independently controlled. The reason
  behind this limitation is that both layers are counterparts to each
  other."* — a naive complementary stack genuinely does couple the two
  bands together into one non-independent response; her whole paper's
  contribution is the specific geometric fix (an added separation-gap
  parameter, `s1`, that decouples them) that undoes this.
- Rahmani-Shams' own account of what changing one resonator does to the
  other, quoted verbatim (about the small-cross resonance): *"Since the
  high pass grids affect the small cross resonance frequency... the
  inductor mutual coupling is modeled by k1."* — again, coupling is real
  and modeled, and independence is achieved only by a deliberately added
  degree of freedom, not by default.
- Wang et al.'s account of the same effect at the *layers'* backing
  thickness rather than the big spacer, quoted verbatim in §3.1: reducing
  FR4 thickness is their prescribed fix for excess coupling capacitance.

**What is *not* established by anything read here**: whether the specific
decoupling techniques demonstrated (Payne's separation-gap parameter,
Rahmani-Shams' independently-biased varactor branches) still work at GPS
L1/L2's much closer frequency ratio. All three read designs that achieve
demonstrated independence (§4.1, §4.2, and reference [29] as tabulated but
unread, §3.1) separate their two bands by a factor of roughly **1.85–2.42**
in frequency. GPS L1/L2 separate by only **1.283**. Mutual coupling between
two resonant circuits generically gets *harder* to null out as their
resonant frequencies converge (the coupling term's effect on each
resonance is largest when the two resonances are close, by ordinary
coupled-mode reasoning) — so extrapolating "independence was achievable at
a 2× ratio" to "independence is achievable at a 1.28× ratio" is not safe,
and nothing read here tests that regime directly.

---

## 6. Extrapolating to GPS L1/L2 specifically (`CALCULATED`, flagged as extrapolation)

Scaling Rahmani-Shams' own thickness/wavelength ratio (0.422 mm /
131.49 mm = 0.00321) directly to GPS frequencies, holding the ratio fixed:

| | L1 (1575.42 MHz) | L2 (1227.60 MHz) |
|---|---|---|
| `λ0` | 190.29 mm | 244.21 mm |
| Scaled substrate thickness (0.00321 × λ0) | **0.611 mm** | **0.784 mm** |

And Payne's ratio (1/200):

| | L1 | L2 |
|---|---|---|
| Scaled substrate thickness (λ0 / 200) | 0.951 mm | 1.221 mm |

Both land comfortably under any reading of "a few mm." **What this
arithmetic is, and is not:**

- It **is** a proportional extrapolation of a real, measured design ratio —
  legitimate as a plausibility check, in the same spirit as this
  programme's own `Family fallback bracket` reasoning for an unmeasured
  material (`CONTEXT.md`).
- It **is not** a claim that either paper's specific geometry, decoupling
  technique, bandwidth, or insertion loss reproduces at 1/1.5–1/4.6 the
  frequency it was demonstrated at. Neither paper's authors targeted GPS
  L-band, and §5's own finding — that the decoupling techniques used were
  demonstrated only at wider band-ratio separations than L1/L2's own 1.283
  — is the load-bearing caveat on this whole section.
- If the arithmetic holds even approximately, a Kapton-substrate (or
  equivalent flexible, εr ≈ 3, low-tanδ) front/back GPS L1/L2 FSS would need
  on the order of **7–13 plies of 127 µm Kapton** (per this programme's own
  25–127 µm-per-ply figure, `docs/xband-absorber-substrate-shortlist.md`) to
  reach 0.6–1.2 mm — well inside the lamination stack sizes already
  demonstrated elsewhere in this programme's own multi-layer capability
  work (`docs/voltera-multilayer-capability.md`'s NOVA `Plan` feature,
  validated to 4 stack-up layers, footnoted as extendable).

---

## 7. What could not be verified

Stated plainly, without smoothing:

| Question | Status |
|---|---|
| Ma, Wang, Yu & Zhao (2022), *IEEE TAP* 70(12):12381–12386, "Design of Dual-Band Frequency-Selective Surfaces with Independent Tunability" — the single most on-point citation found (dual bands 1.14–1.35 & 2.01–2.61 GHz, directly overlapping GPS L2, at a reported 0.006λL) | **Not retrieved.** IEEE Xplore paywalled from this environment. Known only via its own citation entry in another paper's comparison table — `LITERATURE-SUPPORTED` at one remove, not independently confirmed. This is the paper to chase first if this design direction proceeds. |
| Yang, Chen, Bai & Fu (2017), *Electronics Letters* 53(24):1583–1585, "Design of ultra-thin closely spaced dual-band bandpass frequency selective surface" — bands 8.2/11.4 GHz, ratio 1.39, the closest published band-separation ratio to GPS L1/L2's 1.283 found in any search result | **Not retrieved.** IET Digital Library returned HTTP 403. No thickness, spacer, or substrate numbers recovered from any secondary source. |
| A closely-spaced dual-band FSS for 5G, ScienceDirect S003040262400439X | **Not retrieved.** Paywalled; not attempted beyond the initial search-result summary. |
| Any GPS-L1/L2-specific (1575.42/1227.60 MHz) free-space FSS design, radome, or metasurface filter | **None found.** Searched directly by frequency value and by "GPS L1 L2 ... frequency selective surface" phrasing; nothing returned matches both the exact frequencies and the free-space periodic-array device class. This would be new engineering, not a literature lookup. |
| Whether Rahmani-Shams' or Payne's decoupling techniques hold at a 1.28× band-ratio separation (GPS L1/L2's own regime) rather than the 1.85–2.42× ratios they demonstrated | **Not addressed by any source read.** Flagged in §5 as the load-bearing open question for this whole design direction. |
| Wang et al.'s own reported 0.103λL figure against this document's independent 0.126λ–0.190λ cross-check (§3.1) | **Discrepancy unresolved.** Their λL definition (their Table 1 footnote says "free space wavelength at lowest operating frequency") does not reconcile with either band edge in this document's own arithmetic; possibly a rounding artifact or a different reference frequency inside their tunable range not stated in the retrieved text. |
| PMC11130335 (broadband 2nd-order dual-band FSS), PMC11205420 (nested-aperture dual-band FSS), and the PLOS ONE GPS-adjacent filter's finer details beyond what is quoted here | §3.4, §4.3 and §3.3 respectively draw on a mix of raw-HTML grepping (PMC11130335 — high confidence) and an automated fetch-and-summarize tool for the rest — treat any number in this document not accompanied by a verbatim quote as one step below a source this document's author read directly. |
| Whether a flexible, GPS-band-relevant permittivity substrate this programme has *not* already measured (something between Kapton's 3.2 and RO4350B's 3.48, but genuinely flexible) exists commercially | **Not searched.** Out of scope for this pass; a `Material-property library` gap if this design direction proceeds. |

---

## 8. Primary sources

**Read in full (own extraction — `pdftotext` or raw HTML grep, not a
fetch-and-summarize tool):**

- A. Ebrahimi, T. Baum, J. Scott & K. Ghorbani, "Narrowband Bandpass
  Frequency Selective Surface with Miniaturized Elements,"
  [arXiv:1802.07454](https://arxiv.org/abs/1802.07454) (2018)
- K. Payne, "Low-Profile Dual Band-pass Frequency Selective Surface with
  independent bands of operation,"
  [arXiv:2211.07396](https://arxiv.org/abs/2211.07396) (2022)
- Y. Rahmani-Shams, S. Mohammd-Ali-Nezhad, A. Nooraei Yeganeh & S. H.
  Sedighy, "Dual band, low profile and compact tunable frequency selective
  surface with wide tuning range," *J. Appl. Phys.* **123**, 235301 (2018),
  doi:[10.1063/1.5023449](https://doi.org/10.1063/1.5023449); read via
  [arXiv:1806.08494](https://arxiv.org/abs/1806.08494)
- [PMC12471704](https://pmc.ncbi.nlm.nih.gov/articles/PMC12471704/) —
  "A Dual-Layer Frequency Selective Surfaces with Tunable Transmission and
  Fixed Absorption Bands," *Materials* **18**(18):4414 (2025), raw HTML
  fetched and grepped directly
- [PMC12290089](https://pmc.ncbi.nlm.nih.gov/articles/PMC12290089/) —
  "Multi-layer Frequency Selective Surface Wideband Filter with High
  Selectivity Operating in L, S, and C Bands," *Sci. Rep.* (2025), raw HTML
  fetched and grepped directly
- [PMC11130335](https://pmc.ncbi.nlm.nih.gov/articles/PMC11130335/) —
  "A broadband second-order bandpass frequency selective surface for
  microwave and millimeter wave application," *Sci. Rep.* **14** (2024),
  raw HTML fetched and grepped directly

**Read via automated fetch-and-summarize (WebFetch tool over the source's
own HTML/abstract; quotes as extracted, not independently re-verified by
this document's author against the raw page):**

- [PMC11205420](https://pmc.ncbi.nlm.nih.gov/articles/PMC11205420/) —
  "A Dual-Passband Frequency Selective Surface with High Angular Stability
  and Polarization Insensitivity"
- Li et al. (2021), "A quasi-elliptical bandpass frequency selective
  surface with low-profile and miniaturization characteristics,"
  *Int. J. RF Microw. Comput.-Aided Eng.*,
  doi:[10.1002/mmce.22621](https://onlinelibrary.wiley.com/doi/abs/10.1002/mmce.22621)
- Bhattacharya et al., "Left-handed metamaterial bandpass filter for GPS,
  Earth Exploration-Satellite and WiMAX frequency sensing applications,"
  *PLOS ONE*,
  doi:[10.1371/journal.pone.0224478](https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0224478)
  (2019)

**Cited but not retrieved (stranded, paywalled — see §7 for detail):**

- Ma Y.-H., Wang D.-W., Yu Y. & Zhao W.-S., "Design of Dual-Band
  Frequency-Selective Surfaces with Independent Tunability,"
  *IEEE Trans. Antennas Propag.* **70**(12):12381–12386 (2022)
- Yang S.L., Chen Q., Bai J.J. & Fu Y.Q., "Design of ultra-thin closely
  spaced dual-band bandpass frequency selective surface,"
  *Electronics Letters* **53**(24):1583–1585 (2017)

**Repo context (this programme's own prior work, cited for its own
provenance tags, not re-derived here):**

- `docs/voltera-multilayer-capability.md` — the 0.87–2.0 mm X-band absorber
  thickness budget this document explicitly does not extend to L-band
- `docs/xband-absorber-substrate-shortlist.md` — measured/manufacturer-
  specified εr and tanδ for silicone (#1), Kapton (#2), and RO4350B (#11),
  and each substrate's host-regime (`A`/`A+B`) flexibility rating
- `docs/bandpass-fss-physical-bound-primary-source.md` — why classical
  Bode–Fano does not bound a free-standing bandpass FSS at all, and what
  does (Ludvig-Osipov et al.'s perforated-screen sum rule); referenced in
  §2 to distinguish this document's inter-layer-spacing question from that
  document's single-layer-bandwidth question — the two are different
  physical limits on the same design family
- `designs/design_families.py` — `BANDPASS_FSS`'s existing registry entry,
  which currently has no simulation adapter or analysis model for a
  two-layer coupled case; this document's findings would require extending
  both if this design direction is pursued (not attempted here — out of
  scope for a research-only pass)

---

## 9. Provenance summary

| Claim | Provenance |
|---|---|
| L1/L2 free-space wavelengths, quarter-wave figures at εr 2.9/3.0/3.2 | `CALCULATED` |
| Ebrahimi et al.'s 10 mm air gap, 2.7 GHz, 9.0% of λ, and their own "sub-wavelength air gap" framing | `LITERATURE-SUPPORTED` (read in full) |
| Scaling that 9.0% fraction to GPS frequencies | `CALCULATED` (extrapolation, not a citation) |
| Wang et al.'s 30 mm PMI spacer, 1.26–1.9 GHz band, and their own coupling-capacitance explanation | `LITERATURE-SUPPORTED` (raw HTML read) |
| The independent cross-check of their 0.103λL figure | `CALCULATED`, with the discrepancy stated, not resolved |
| Ma et al. (2022)'s 0.006λL, dual-band 1.14–1.35/2.01–2.61 GHz figure | `LITERATURE-SUPPORTED` at one remove — cited in another paper's table, not independently read |
| PMC12290089's 33–34 mm gaps, L/S/C-band, and their coupling-minimization rationale | `LITERATURE-SUPPORTED` (raw HTML read) |
| Rahmani-Shams et al.'s 0.422 mm RO4350B substrate, 0.0032λ, dual independent tunable bands, and their `k1`/`k2` coupling terms | `LITERATURE-SUPPORTED` (read in full) |
| Payne's 0.635 mm substrate, λ/200, dual independent bands, and her account of naive-CFSS coupling | `LITERATURE-SUPPORTED` (read in full) |
| RO4350B and Kapton's εr/tanδ and host-regime ratings | `MANUFACTURER-SPECIFIED` / `MEASURED` respectively, per `docs/xband-absorber-substrate-shortlist.md`'s own tags |
| Scaled substrate thickness estimates for GPS L1/L2 (§6) | `CALCULATED`, explicitly flagged as an unverified extrapolation |
| The overall feasibility verdict (§ Bottom line, item 6) | `INFERRED` — this document's own synthesis; no single source states it, and it is falsifiable by the exact gaps named in §7 |
| Absence of any GPS-L1/L2-specific free-space FSS design in the accessible literature | `UNKNOWN` — searched directly, not found; does not prove none exists |
