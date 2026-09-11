# MXene's skin depth at 10 GHz: the 1.8× disagreement traced to a 3.3× conductivity gap, and which conductivity survives

**Date:** 2026-09-11
**Ticket:** `docs/RUNNING-LISTS.md` §3 item 33 (open since 2026-09-06); bears on ADR-0033, [#104](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/104), [#383](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/383), [#382](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/382).
**Question:** Correction 7 says a ~10 µm printed MXene film is "already ~1.65 skin depths at 10 GHz." A 2026-09-05 correction to map #104 says MXene's 3δ is ≈33 µm — δ ≈ 11 µm, putting the same film at only ~0.9 δ. Both cannot be right (δ ∝ 1/√σ, so this is really a conductivity disagreement). Which conductivity does this repo's own retrieved literature support, and what is the one number to use going forward?

---

## Bottom line up front

**The two sides were never using different conductivities. One of them mislabelled a number.** Backing a conductivity out of each claim (§2) shows correction 7 implies σ = 6.90×10⁵ S/m — which matches this repo's own best-evidenced extrusion-printed figure (Shao et al. 2022) to three significant figures. The map's implied σ = 2.09×10⁵ S/m matches **no conductivity anywhere in this repo's literature**, printed or otherwise (§3). The likely mechanism (§4): the "33 µm" figure is this repo's own **5-skin-depth** figure at the *bottom* of X-band (8 GHz), divided by 3 instead of 5.

**Settled conductivity: σ ≈ 6.9×10⁵ S/m at 10 GHz** — Shao et al., *Nat. Commun.* 13, 3223 (2022), DOI [10.1038/s41467-022-30648-2](https://doi.org/10.1038/s41467-022-30648-2), `LITERATURE-SUPPORTED`. This is the only source in this repo measuring conductivity **on the actual manufacturing route the program uses** — room-temperature extrusion printing, DC (the measurement instrument is not stated in the excerpts of that paper retrieved for this repo). The higher, better-evidenced *in-band RF* figures that also exist in this repo's literature (1.20–1.43×10⁶ S/m, §5) do **not** displace it, because they were measured on a different, thinner, differently-fabricated film (spray-coated, tens of nanometres) — and the one paired DC/RF comparison this repo holds for MXene (§3(b) below) shows RF conductivity runs *flat to slightly below* DC, never above, so there is no physical basis in this repo's own sources for assuming the printed trace's real RF conductivity is higher than its measured DC value.

Recomputed from the settled figure, `CALCULATED`:

| Quantity | Value at 10 GHz | Change from correction 7 / ADR-0033(b) |
|---|---|---|
| Skin depth δ | **6.06 µm** | None — same number |
| 10 µm printed film, in skin depths | **1.65 δ** | None — confirmed, not "strengthened" or "weakened" |
| 3δ (the "electrically thick" threshold) | **18.2 µm** | Corrects the map's spurious "33 µm" |
| 3δ across X-band (8–12 GHz) | **16.6–20.3 µm** | New — was never previously stated correctly |

*In plain terms: both documents were right about the conductivity and both were computing skin depth correctly. One of them just picked up the wrong number for "three skin depths" — 33 microns, which is actually what five skin depths looks like at the low end of the band, not three. The real three-skin-depth mark is 18 microns. A 10-micron printed film is genuinely most of the way to opaque, exactly as correction 7 said, and thickness genuinely is a weak lever for MXene at the machine's floor thickness.*

---

## 1. Every distinct MXene conductivity figure found in `docs/` and `knowledge/`

`knowledge/` holds no MXene data — only a search-keyword reference in `literature_search.py`. Everything below is from `docs/`. Grepped for `S/m`, `S/cm`, and conductivity figures near "MXene"/"Ti₃C₂Tₓ".

| σ (S/m) | Fabrication route | Measurement | Source | Where cited in this repo |
|---|---|---|---|---|
| 0.307 | DIW extrusion, low-viscosity ink, polyimide | as-printed, no treatment | Frontiers 2026, DOI 10.3389/fmars.2026.1843170 | `mxene-voltera-nova-printability.md:55,92` — flagged as an **outlier**, not representative |
| 4,119–5,323 | DIW extrusion, porous macro-lattice + AlOOH crosslink + freeze-dry | post-treatment | Zhao et al., PMC8219826 | `mxene-voltera-nova-printability.md:52,91` — different regime (porous, not a dense film); not comparable |
| 1.2×10⁵ | Not stated (search-snippet only) | cross-validation figure, δ=24.57 µm @ 3.5 GHz | "Investigation of MXene nanosheets…skin depth effect," *Nano Research*, DOI 10.1007/s12274-023-6127-7 | `mxene-voltera-nova-printability.md:117` — full text never retrieved, one figure sourced from a search snippet |
| **6.26×10⁵** | **Extrusion printing, room temp, no anneal, as-printed** | DC (instrument not stated in the excerpts retrieved for this repo) | **Shao et al. 2022**, DOI 10.1038/s41467-022-30648-2 | `mxene-voltera-nova-printability.md:51,90`, `fabrication-capability-and-ink-library-spec.md:253` |
| **6.9×10⁵** | **Extrusion printing, 4 h @ ~10% RH, no heat** | DC (instrument not stated) | **Shao et al. 2022** (same paper, conditioned sample) | This repo's standing default — `voltera-multilayer-capability.md:463,476`, `mxene-voltera-nova-printability.md:99`, ADR-0033 amendment (b) |
| 1.2×10⁶ | Spray-coated on PET, 1.0–4.3 µm | contactless capacitive fixture, S-parameter curve-fit, 1–10 GHz | AlHassoon et al. 2020, *Appl. Phys. Lett.* 116:184101, DOI 10.1063/5.0002514 | `mxene-rf-band-electrical-properties.md` §1.1 |
| 1.20×10⁶ (AC, Fig. 3 endpoints) / 1.30×10⁶ (AC, Fig. 4 slope) | Spray-coated on glass, 4–40 nm | WR-90 waveguide, TRL-calibrated VNA, 8.2–12.4 GHz — **direct in-band measurement** | Rakhmanov et al. 2023, *Appl. Phys. Lett.* 123:204105, DOI 10.1063/5.0176575 | `mxene-rf-band-electrical-properties.md` §1.2 |
| 1.43×10⁶ | Same films as above | 4-point probe, DC (paired cross-check) | Rakhmanov et al. 2023 | `mxene-rf-band-electrical-properties.md` §1.2 |
| 1.4×10⁶ | Vacuum-filtered freestanding-adjacent film, percolating network | not stated in the excerpt available here | Mirkhani, Zeraati et al., *ACS Appl. Mater. Interfaces* 2019 | `flexible-high-permittivity-composites.md:70,190` |
| 1.5×10⁶ | Spray-coated antenna film on PET | measured, room temp | PMC9119193 | `mxene-voltera-nova-printability.md:53,93` |
| up to 1.93×10⁶ | Blade-coated, 2.2–11.5 nm | vacuum anneal 180 °C, 4 h | PMC9979651 | `mxene-voltera-nova-printability.md:54,94` — anneal temperature exceeds the NOVA's 40 °C ceiling |
| up to 2.0×10⁶ | Freestanding, theoretical ceiling | not a fabrication route | PMC9119193 | `mxene-voltera-nova-printability.md:53` |

**The two conductivities that matter for this reconciliation are bolded**: 6.26–6.9×10⁵ S/m is the only figure measured on an **extrusion-printed** trace — the process this program's equipment (Voltera NOVA) actually performs. Every conductivity at or above 1.2×10⁶ S/m is measured on a **spray-coated or blade-coated film**, a different, much thinner (nm-scale, not µm-scale), differently-processed sample. `docs/fabrication-capability-and-ink-library-spec.md:86` already flags this as a "hidden constant" — "σ = 6.26–6.9×10⁵ S/m: one MXene ink, from one paper" — and that caution is exactly right; it does not, however, license swapping in a higher number measured on an entirely different process.

---

## 2. Backing a conductivity out of each side of item 33

Inverting δ = 1/√(π f µ₀ σ) gives σ = 1/(π f µ₀ δ²). At f = 10 GHz, `CALCULATED`, independently recomputed here (not copied):

| Side | Its claim | Implied δ | **Implied σ** |
|---|---|---|---|
| Correction 7 (`RUNNING-LISTS.md` §3, inherited from the handoff doc) | a 10 µm film is "already ~1.65 skin depths at 10 GHz" | 10/1.65 = **6.061 µm** | **6.90×10⁵ S/m** |
| Map #104's 2026-09-05 correction, as quoted by item 33 | MXene's "3δ is ≈33 µm" | 33/3 = **11.0 µm** | **2.09×10⁵ S/m** |

```
π f µ₀ = π × 10×10⁹ × 4π×10⁻⁷ = 3.9478×10⁴
σ = 1 / (3.9478×10⁴ × δ²)
δ = 6.061 µm → σ = 1/(3.9478×10⁴ × (6.061×10⁻⁶)²) = 6.896×10⁵ S/m  ✓
δ = 11.0  µm → σ = 1/(3.9478×10⁴ × (11.0×10⁻⁶)²)  = 2.093×10⁵ S/m  ✓
```

**Correction 7's implied conductivity reproduces this repo's own 6.9×10⁵ S/m figure to three significant figures.** Item 33 was right that correction 7 never cites a conductivity, but the number it produced is exactly what 6.9×10⁵ S/m gives.

**The map's implied 2.09×10⁵ S/m matches nothing in §1's table** — not the as-printed extrusion figure, not any spray- or blade-coated figure, not even the low-confidence *Nano Research* snippet figure (1.2×10⁵ S/m, off by nearly 2×). No paper retrieved anywhere in this repo reports a MXene conductivity near 2×10⁵ S/m. That absence is itself the diagnostic: a real competing literature value would show up somewhere in §1's table, and it does not.

---

## 3. Why 6.9×10⁵ S/m is the defensible choice, not 1.2×10⁶ S/m or higher

Three questions, answered from this repo's own retrieved sources:

**(a) Which conductivity was measured on the process this program will actually use?** Only Shao et al. 2022. It is a room-temperature, pneumatic extrusion dispenser — "mechanically the same class of machine as the NOVA" per `mxene-voltera-nova-printability.md` §1 — printing a viscoelastic MXene paste at Voltera-compatible viscosity (~250,000 cP). Every source at 1.2×10⁶ S/m or above is spray-coated (AlHassoon, Rakhmanov, PMC9119193) or blade-coated (PMC9979651) — processes that lay down a film 3–5 orders of magnitude thinner (nm, not µm) and with a correspondingly different flake microstructure. Substituting one process's measured conductivity for another's is exactly the kind of "quoted without its box" error `fabrication-capability-and-ink-library-spec.md` §1.1 already warns about generally, applied here to a specific number.

**(b) Does going from DC to RF push MXene's conductivity up or down?** Rakhmanov et al. 2023 is the one paper in this repo's literature that measured *both* on the *same* films: AC (in-band, 8.2–12.4 GHz) = 1.20×10⁶ S/m against DC (four-point probe) = 1.43×10⁶ S/m — **AC 16% below DC**, not above. Their own Drude-relaxation model, fitted to the same data (τ ≈ 2.3 ps), predicts the gap should be only about 1% at 10 GHz; the paper attributes the larger observed gap to measurement error and surface roughness rather than a real frequency effect (`mxene-rf-band-electrical-properties.md` §1.2 works this arithmetic in detail). Either way, **nothing in this repo's literature shows RF conductivity exceeding DC conductivity for MXene.** So even granting that some of the 1.7–2.1× gap between Shao's 6.9×10⁵ S/m and Rakhmanov's ~1.3×10⁶ S/m might be a genuine DC-to-RF effect, the direction is wrong: RF should be flat-to-lower, and the observed gap runs the other way. The simplest explanation consistent with the paired measurement is that the gap between Shao and Rakhmanov/AlHassoon is a fabrication-process difference (spray-coated films vs. an extruded paste), not a frequency effect.

**(c) What does that make the honest RF conductivity of a printed trace?** `UNKNOWN` in the strict sense — nobody has measured an extrusion-printed MXene trace in-band. But the best-supported estimate, and the only one this repo can currently defend without conflating fabrication routes, is Shao's own DC figure carried forward unchanged, since the only evidence bearing on the size and direction of a DC-to-RF shift for this material (Rakhmanov's paired measurement) says that shift is small and, if anything, negative. **Recommendation: keep σ = 6.9×10⁵ S/m (conservative floor 6.26×10⁵ S/m, the as-printed-before-conditioning figure) as this repo's one settled printed-trace conductivity at 10 GHz until #383 closes the gap with an actual in-band measurement of the printed ink.**

*In plain terms: there's a genuine, well-measured, higher conductivity number in the literature — but it was measured on a completely different way of putting MXene onto a surface (a fine spray, not a printed paste), and the one experiment that actually checked whether radio-frequency conductivity differs from a plain electrical-meter reading found that it doesn't, much — if anything it comes in a little lower. So there's no evidence to justify assuming the printed material conducts better at radio frequency than the meter already says it does at DC.*

---

## 4. Corrected skin-depth and δ-multiple table, at the settled conductivity

σ = 6.9×10⁵ S/m, δ = 1/√(π f µ₀ σ), `CALCULATED`, recomputed independently here:

| f (GHz) | δ (µm) | 10 µm film, in δ | 3δ (µm) | 5δ (µm) |
|---|---|---|---|---|
| 8 | 6.774 | 1.48 | 20.3 | 33.9 |
| 10 | 6.059 | **1.65** | **18.2** | 30.3 |
| 12 | 5.531 | 1.81 | 16.6 | 27.7 |

**This is the reconstruction of where the map's "33 µm" came from**, and it checks to better than 3%: `mxene-voltera-nova-printability.md:106` states a 3–5 skin-depth target of "roughly 17–34 µm" across X-band. Its two endpoints are **3δ at 12 GHz = 16.6 µm** (the range's low end) and **5δ at 8 GHz = 33.9 µm** (the range's high end) — not, as the map's correction implies, 3δ at any single frequency. Dividing 33 µm by 3 instead of 5 produces exactly the spurious δ ≈ 11 µm and σ ≈ 2.09×10⁵ S/m found in §2. **Provenance of this reconstruction: `INFERRED`** — it is a plausible account of how the number was produced, not a confirmed one, because the original 2026-09-05 comment on map #104 that first stated "3δ ≈ 33 µm" is no longer present in the issue's body or comments as of this writing (also noted independently in `mxene-rf-band-electrical-properties.md` §4). Two things support the reconstruction: the numeric match is within 3%, and no conductivity anywhere in this repo's literature produces δ = 11 µm at any plausible frequency in-band.

**What survives, stated flatly:**

- **Correction 7's conclusion is confirmed as originally stated** — a 10 µm printed film is 1.65 δ at 10 GHz, genuinely most of the way into the opaque regime, and thickness is a weak lever at the printer's floor thickness. It is neither "strengthened" nor weakened by this reconciliation; the number does not move.
- **The map's "3δ ≈ 33 µm" and its consequence — that MXene "never reaches the electrically-thick regime at printable thickness" and thickness stays a strong, linear lever — do not survive.** There was never a competing conductivity behind that claim; the correct 3δ mark at 10 GHz is 18.2 µm, comfortably within the 20–35 µm the printability document already identifies as reachable in a small number of extrusion passes.
- **ADR-0033's own amendment (b)** (lines 226–253) already uses σ = 6.9×10⁵ S/m and already states the 1.65 δ figure — it required no change and is confirmed correct by this document.
- **#128's finding is untouched either way** — for a genuinely *lossy* element, aspect ratio, not film thickness, is the knob that reaches the 11–90 Ω/sq target window. Item 33 said so and nothing here disturbs it.

---

## 5. What this does and does not say about the higher, RF-band figures

The 1.20–1.43×10⁶ S/m figures from AlHassoon and Rakhmanov are real, well-measured (Rakhmanov's is a direct in-band VNA measurement in a TRL-calibrated WR-90 fixture — about as good as evidence gets in this repo, see `mxene-rf-band-electrical-properties.md` §1.2), and useful — but for a different question than the one item 33 asks.

**What they settle:** that MXene's conductivity is, to within a small and possibly negative margin, frequency-independent from DC to 12.4 GHz — the physical question behind whether a DC four-point-probe reading (#106) can stand in for an RF measurement at all. That answer is "yes, for a film this thin" (`mxene-rf-band-electrical-properties.md` §5 works out exactly where that boundary falls, in microns of thickness).

**What they do not settle:** the conductivity of an actual printed trace, because none of the three papers behind those numbers printed one. Using 1.2×10⁶ S/m in place of 6.9×10⁵ S/m for a printed-trace skin-depth calculation swaps in a different material sample, not a different frequency regime — exactly the trap `mxene-rf-band-electrical-properties.md` §3 itself names ("The 1.2×10⁶ figure is not measured on a printed trace… A printed trace's own σ is `UNKNOWN` at RF, which is what #383 exists to fix"). That document's own §4, however, goes on to use 1.2×10⁶ S/m anyway to argue correction 7's conclusion is "strengthened" and the map's is "weakened" — which reopens exactly the substitution its own §3 warns against. §6 below flags this as the one claim in that document that should change.

---

## 6. What should change, and where — per ADR-0024 ("a correction lands at the claim")

**Not editing these here** — reporting exactly what should change and why, for whoever picks this up.

1. **`docs/RUNNING-LISTS.md`, §3 item 33 (lines 497–513).** Currently ends "Recorded, not resolved — it needs one stated conductivity at one stated frequency." Should be marked resolved: settled σ = 6.9×10⁵ S/m at 10 GHz, correction 7's 1.65 δ confirmed unchanged, the map's implied conductivity identified as a mislabelled 5δ-at-8GHz figure rather than a genuine second measurement (`INFERRED`, per §4 above). Per ADR-0024's two shapes, this is an "ordinary correction" — state the resolved version once; the register already holds what came before.

2. **`docs/RUNNING-LISTS.md`, item 52 (lines 857–875), specifically the closing sentence at line 869**: "The still-open ~1.8× conductivity disagreement in section 3 item 33 means even this narrower range is not the last word." This sentence should be struck or updated once item 33 resolves — the 1.48–1.81 δ range for a 10 µm film across 8–12 GHz (item 52's own table) is the settled range, not a provisional one pending resolution.

3. **`docs/fabrication-capability-and-ink-library-spec.md` §5.1 (lines 303–319).** The passage "the right answer for printed MXene at 10 µm is 0.145 Ω/sq or 0.22–0.31 Ω/sq depending on a conductivity nobody here has measured" should be updated: at the settled σ = 6.9×10⁵ S/m, a 10 µm film is 1.65 δ — solidly inside the finite-thickness regime, not the thin-film one — so the applicable figure is the finite-thickness branch (≈0.22 Ω/sq at 10 GHz), not an open choice between the two. The section's broader methodological point — that `R_s` must be derived from `(σ, t, f)` rather than stored, because the formula choice has a validity gate — is untouched and needs no change; only the specific hedge tied to item 33 does.

4. **`docs/mxene-rf-band-electrical-properties.md` §4 (lines 532–545).** This document already independently reaches the same mislabelling explanation as §4 above (its own §4, lines 498–514) and this document concurs with that reconstruction. But its two follow-on bullets — "correction 7's conclusion is strengthened" and "the map's conclusion is weakened" — both computed at σ = 1.2×10⁶ S/m (lines 535–545) — should be corrected to use the settled σ = 6.9×10⁵ S/m instead, consistent with its own §3 caveat two sections earlier ("the 1.2×10⁶ figure is not measured on a printed trace"). At the settled figure: correction 7's conclusion is **confirmed exactly as stated** (not strengthened — the number is unchanged at 1.65 δ), and the map's conclusion **does not survive at all**, under either conductivity — it was never a valid competing figure at any σ this repo has evidence for.

5. **No change needed** to `docs/voltera-multilayer-capability.md:463,476`, `docs/mxene-voltera-nova-printability.md:96–125`, or ADR-0033's amendment (b) (lines 226–253) — all three already use σ = 6.9×10⁵ S/m and already state the 1.65 δ (or 1.48–1.81 δ across-band) figures this document confirms as settled.

---

## 7. What is still genuinely open, and the cheapest way to close it

Per this repo's own warning discipline: what is assumed, what it costs if wrong, and the cheapest way to find out.

**What is assumed.** That an extrusion-printed MXene trace's RF conductivity at 10 GHz equals its measured DC conductivity (6.9×10⁵ S/m), on the strength of a DC-to-RF comparison performed on a *different* film (Rakhmanov's spray-coated sample), not the printed trace itself.

**What it costs if that is wrong.** If a printed trace's real RF conductivity instead sits near the spray-coated figure (~1.2–1.4×10⁶ S/m), δ at 10 GHz drops to 4.2–4.6 µm and a 10 µm film moves from 1.65 δ to 2.2–2.4 δ — deeper into the opaque regime, not out of it. In that direction the error only strengthens correction 7's "thickness is a dead knob" conclusion (§4 already shows this). If instead the true value runs *below* 6.9×10⁵ S/m — plausible, since a thick extruded trace has far more flake-to-flake junctions than a few-flake-thick spray-coated film, and junction resistance is exactly the kind of loss mechanism `mxene-rf-band-electrical-properties.md` §1.2 flags as unquantified for a thick trace (`UNKNOWN`) — δ grows and the film could fall closer to the 3δ "electrically thick" boundary (18.2 µm) than assumed, which is the direction that would matter for #128's aspect-ratio-not-thickness conclusion. **The assumption is load-bearing in that one direction and unverified in it.**

**The cheapest way to find out.** #383 already exists for exactly this: an in-band (8–12 GHz) sheet-resistance measurement of the actual cured, extrusion-printed ink at a known thickness — the same waveguide-discontinuity or four-point-probe method Rakhmanov et al. used, run on this program's own printed sample rather than borrowed from a paper. Given `mxene-rf-band-electrical-properties.md` §5's finding that a DC four-point probe (#106, already available) is exact to well under 1% for any film below about 1.3 µm at 12 GHz, and that a 10–35 µm printed trace is far outside that regime, closing this specific gap needs the in-band measurement, not just the DC probe.
