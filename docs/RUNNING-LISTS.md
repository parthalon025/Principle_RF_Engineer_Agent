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
| **MDPI** | HTTP 403 to all automated fetches | Believed to hold the **only quantitative TPU permittivity source**. Also strands absorber and polarisation-converter literature | #127, #110 |
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
fingerprint that gets denied harder than plain `curl`. Assume these stay
human-only.

---

## 2. Questions for the patent's inventors

Lives in its own file: **[`docs/questions-for-the-patent-inventors.md`](./questions-for-the-patent-inventors.md)**.

Ten questions about US12089385B2 that only its authors can settle — two
blocking, three prose-versus-drawing discrepancies, and the rest on fabrication
intent and capability. Add to that file rather than duplicating here.

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
9. **WR-90 waveguide is the wrong fixture to design coupons for.** Its
   22.86 × 10.16 mm aperture gives ~7 × 3 cells at a 3 mm pitch. **Free-space
   measurement with two horns is the documented method, and 11 × 11 cells is a
   demonstrated sufficient sample.**
10. **Aircraft wing, hull and sUAS body are not fixed targets.** They are
    *examples of what a requirement might state*. The host surface is a
    per-requirement input, and treating it as a project constant silently fixes
    the material answer.

### Attribution errors

11. **Costanzo et al., *IJAP* 2019 does not carry the dissimilar-neighbour
    coupling error.** A research pass attributed it there; the paper's coupling
    analysis concerns two frequency bands co-located in **one cell**, not unlike
    neighbours across an array. **The literature gap stands.**
12. **"Phase quantisation is well characterised" — only for beam-forming.**
    Not for absorption or backscatter reduction, which is what this effort
    actually optimises.

### Errors found in published sources

Not our corrections, but ours to route around. Recorded because anyone
adopting these results will hit the same thing.

13. **Huynen (2022) mis-tabulates its own Eq. 7.** Two of five rows reproduce
    exactly; three are **10× too large**. Correcting the arithmetic **reverses
    the paper's own ranking**. Its Table 5 column headed `h_tot norm` also
    contains λ₀ in millimetres, so Eq. 9 is defined in the paper and never
    actually applied. **Adopt its definition of the normalised figure of merit;
    recompute every number.**

---

## 4. Unknowns, ranked by how much they matter

Ranked by *how much a decision changes if the answer changes*, not by how
interesting the question is. The top of this list is where measurement and
enquiry effort should go.

| # | Unknown | Why it ranks here | Where |
|---|---|---|---|
| 1 | **Is there bench access for X-band measurement?** | Decides whether the one genuinely novel claim — a library of individually *measured* elements, which has no prior art anywhere — is achievable or aspirational. Everything RF is capped at `SIMULATED` without it. Now askable under the CRADA rather than researchable | #133, #132 |
| 2 | **Example 3's `h₁`, and FIG. 7G's y-axis** | Corrupts the known-answer test. Reading the axis wrong does not give a wrong answer — it gives a scoring function measuring the wrong thing | #116 |
| 3 | **Minimum line width and thickness-per-pass on the real NOVA** | Sets the alphabet's frequency ceiling and every geometry constraint. Currently literature-extrapolated onto hardware nobody has run | #106 |
| 4 | **Carbon sheet resistance at two passes** | Two passes and one four-point-probe reading either confirms or kills the whole resistive-layer architecture | #106, #128 |
| 5 | **TPU's X-band permittivity** | No data of any provenance exists. TPU is what the most conformal skins want, and without a permittivity it cannot be simulated, so it is silently absent from every ranking | #127 |
| 6 | **The superposition coupling error bar** | No prior art. Determines whether a fast element-library evaluator can state its own uncertainty honestly, or is guessing | #111 |
| 7 | **A super-cell sizing rule from a coupling budget** | No convention exists to inherit — confirmed, not assumed. Genuinely derived work | #130 |
| 8 | **Layer-to-layer registration on the NOVA** | Unpublished anywhere. Suspected to be the real geometric risk, ahead of feature size | #106, #115 |
| 9 | **Does the vacuum table hold silicone?** | Gates the top RF substrate candidate. Voltera's own documentation explicitly does not state it | #106, #114 |
| 10 | **Whether `R = 3T` or IPC-2223's 6× rule governs** | The patent's rule is *twice as permissive* as the flex-circuit industry standard, so enforcing it approves parts bent twice as tight as IPC allows | #115 |

---

## 5. The research agenda — eight items with no prior art

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
3. **A super-cell sizing rule derived from a coupling error budget.** Every
   block size found in the literature is set by beam geometry, control-line
   count or fabrication tolerance — never by managing interference.
4. **An error bar on the superposition fast tier.**
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
