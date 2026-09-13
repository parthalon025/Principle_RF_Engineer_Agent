# Non-volatile (latching) metasurfaces at RF — prior art, self-writing, and what the latch would actually save

**Scope.** Electromagnetic domain only, microwave/mm-wave emphasis. The acoustic/mechanical
version of the same idea is a separate agent's work and is not touched here. Optical-frequency
results appear only where they set a number the microwave question needs (§2).

**The idea under test.** Today's reconfigurable surfaces in this repo's world — e.g.
US12089385B2 Example 5, the BST-tunable reflectarray (`docs/example4-5-beam-steering-scoring-recipe.md`
§Ex5) — are *volatile*: every cell holds its phase state only while a bias voltage is held on it,
so every cell needs a wire, a driver, and a share of a standing power budget. A **latching**
surface would retain its state after writing and need none of that to *hold* the pattern. The
speculative extra step is whether the **incident field itself** could do the writing.

---

## Direct answers, before the detail

**1. Does a non-volatile RF metasurface already exist?**
**Yes — but not the one this idea needs.** Three tiers, and the distinction between them is the
whole finding:

- **Components: solved and commercial-grade.** GeTe phase-change RF switches are latching,
  measured, and good: `0.1–0.24 dB` insertion loss over `0–40 GHz`, `>10⁶` switching cycles
  reported, and no power at all to hold either state. Magnetic-latching RF MEMS (MagLatch) is a
  shipped product at `DC–6 GHz`, `<0.5 dB` insertion loss, `≥40 dB` isolation, zero hold power.
- **A whole printed metasurface: demonstrated once, small, and measured.** Xiao *et al.*,
  *Nature Communications* **15**:10591 (2024) — a **fully printed, zero-static-power, coded
  reconfigurable microwave metasurface**, `6×6 = 36` switches, measured `0.3–12 GHz`, on-resistance
  `≈10 Ω`, on/off ratio `6×10⁵`, insertion loss `<0.7 dB`, set/reset at `+1.75 V / −1.1 V`.
  This is the single closest precedent to this repo's own build route (printed, flexible,
  low-voltage) and it is *not* a chalcogenide — it is a printed Ag/MoS₂/Ag memristive switch.
- **A large, individually-addressed, non-volatile reflectarray/RIS: nobody has built one.**
  The closest published design, a D-band GeTe transmitarray with per-cell bias (Gharbieh *et al.*,
  *Sci. Rep.* **14**:2966, 2024), is explicitly **simulation only** — the authors state prototyping
  "is under development." The one microfabricated mm-wave RIS that uses a phase-transition material
  (arXiv:2605.07311, VO₂, `26–40 GHz`, measured) is **volatile**: it is held ON by a constant
  `20 V` bias, `≈17 mW` per element.

*Plain reading: the switch that remembers exists and works well. A whole surface made of them
exists once, in a 36-cell printed demo. A big steerable antenna made of them exists only on paper.*

**2. Is field self-writing plausible at microwave?**
**Your suspicion is confirmed for the direct route and refuted for the indirect one — and the
difference decides the whole question.**

- **Direct** (the wave's own field flips the chalcogenide): **excluded.** Amorphous chalcogenide
  needs `5–42.5 MV/m` to threshold-switch (simulated range; measured literature values `8.1–94 MV/m`).
  A free-space wave carrying `10 MV/m` is `≈1.3×10¹¹ W/m²`, and `10 MV/m` is *above the ~3 MV/m
  breakdown field of air* — you ionise the air in front of the surface before you switch the cell.
- **Thermal** (the wave heats the cell until it crystallises): **excluded, and for a reason that
  is specific and measured.** Amorphous GeTe's conductivity at 10 GHz is `0.63×10⁻² S/m`
  (measured, Sensors 2018). A 100 nm film of that is `≈1.6×10⁹ Ω/sq` — it absorbs roughly
  `2×10⁻⁷` of an incident wave. The state you need to write *from* is very nearly transparent to
  the very thing you want to write with.
- **Indirect** (the wave is rectified into a DC bias that then does the writing): **already
  demonstrated at microwave, at very modest power.** A self-biased PIN-diode metasurface flips
  its own coding state at `≈10 dBm` per cell — with an 11 mm cell that is `≈83 W/m²`, about
  **nine orders of magnitude** below the direct-field route.

*Plain reading: the wave cannot kick the material hard enough to change it, and cannot warm it
either because the material is nearly invisible to the wave. But the wave can be turned into a
little DC voltage by a diode, and that voltage is easily enough. So "the wave writes the surface"
is realistic only as "the wave charges a rectifier that writes the surface."*

**Consequence for the charter's novelty labels (`CLAUDE.md`, "What may be proposed"):** this is
**not a new mechanism**. It is a **new arrangement** of two known parts — a rectifying
self-biasing cell (demonstrated at microwave, in simulation) and a latching switch element
(demonstrated in hardware) — plus **one new element**, the combined cell, which nobody has built.
That is a much cheaper claim to make and a much cheaper thing to test.

---

## 1. Prior art — non-volatile reconfigurable metasurfaces at RF/microwave

### 1.1 What is measured, and at what frequency

| Device | Freq. | Built & measured? | Retains state with **no** bias? | Key measured numbers |
|---|---|---|---|---|
| GeTe latching microwave switch (Wang & Rais-Zadeh, APL 2014) | `0–40 GHz` | Yes | **Yes** | IL `0.1–0.24 dB` over `0–40 GHz`; thermal pulse `0.1–1.5 µs`; crystalline resistivity `3.1×10⁻⁴ Ω·cm` |
| GeTe RF switch (review benchmark, Micromachines 2024) | to `20 GHz` | Yes (survey of measured devices) | **Yes** | `R_on = 0.9 Ω`, `R_off = 35.3 kΩ`; IL `<0.5 dB`, isolation `>18 dB` to 20 GHz; switching time `2 µs` |
| GeTe X-band absorber (Jeong *et al.*, Sensors 2018) | `8.0–12.4 GHz` | Yes | **Yes** (but written by oven, whole-surface) | Absorption peak moves `10.23 GHz → 9.6 GHz`; σ `0.63×10⁻² S/m` (amorphous) → `3.2×10⁵ S/m` (crystalline) at 10 GHz |
| Printed MoS₂-switch coded metasurface (Xiao *et al.*, Nat. Commun. 2024) | `0.3–12 GHz` | **Yes, 6×6 array** | **Yes** | `R_on ≈ 10 Ω`, on/off `6×10⁵`, IL `<0.7 dB`; set `1.75 V`, reset `−1.1 V`; retention extrapolated `>10 years`; `300` cycles shown |
| D-band GeTe transmitarray, per-cell bias (Gharbieh *et al.*, Sci. Rep. 2024) | `110–170 GHz` | **No — simulated** | Yes (by material) | IL `<1.5 dB` over 27% band; `10×10` elements; W microheater per cell |
| VO₂-switched RIS (arXiv:2605.07311) | `26–40 GHz` | Yes, `10×20 = 200` cells | **No — volatile** | Held ON at constant `20 V`; `≈17 mW`/element; `≈5 kΩ` off → `<3 Ω` on; `±40/50/60°` steering |
| MagLatch magnetic-latching RF MEMS (commercial) | `DC–6 GHz` | Yes (product) | **Yes** | IL `<0.5 dB`, isolation `≥40 dB`, actuation `<5 V`, zero hold power |

**The one that matters most for this repo is row 4.** Xiao *et al.* is printed (inkjet MoS₂
switches, screen-printed graphene), on paper with a metal-foil ground plane, works at microwave,
is measured, and costs nothing to hold its state. It is the existence proof that a printed
latching metasurface is not a fantasy. Its weaknesses are exactly the ones §4 is about: `300`
demonstrated cycles, and a retention figure that is **extrapolated**, not observed.

### 1.2 Routes that do *not* work, and why that is useful

- **VO₂ is not a latch.** The metal–insulator transition in VO₂ is *volatile* — it reverts when
  the drive is removed. The one measured mm-wave phase-transition RIS found in this pass uses VO₂
  and therefore still needs a standing bias (`20 V`, `17 mW`/element). Anyone reading "phase
  transition material" as "non-volatile" will get this wrong; the chalcogenides (GeTe, GST) latch,
  VO₂ does not.
- **Ferroelectric remanent polarisation was searched for and not found at RF.** No measured
  microwave metasurface using remanent (zero-bias) ferroelectric polarisation surfaced in this
  pass. BST reflectarrays — including the Karnati/Gong X-band device this repo already cites —
  are all *continuously biased* paraelectric tuning, not remanent-state latching. Whether a
  remanent-polarisation reflectarray cell has been published is **UNKNOWN and unsearched to
  exhaustion**; treat its absence here as "not found in one pass," not as "does not exist."
- **Magnetic/ferrite latching exists as components but was not found as a metasurface.**
  Latching ferrite phase shifters are decades-old waveguide technology, and magnetic-latching MEMS
  is commercial; neither surfaced as a *conformal printed metasurface* in this pass.

---

## 2. Self-writing — can the field write the pattern?

### 2.1 Optical writing is established, and here are the numbers

Rewritable optical discs are indeed a laser writing a retained phase pattern. The threshold
energies are small and well measured.

**GeTe** (Li *et al.*, *Materials* **18**(23):5466, 2025 — 150 nm film, 10 ns pulses at 532 nm):

> crystallization fluence window `8.5–15 mJ/cm²`; amorphization `25.44–41.28 mJ/cm²`;
> ablation above `41.28 mJ/cm²`.

**Ge₂Sb₂Te₅** (Sun *et al.*, *Sci. Rep.* **6**:28246, 2016 — 90 nm film, 248 nm):

> crystallization `≥36 mJ/cm²` with 20 ns pulses; `≥13 mJ/cm²` with 500 fs pulses.

*Plain reading: writing one bit on a disc takes about a hundredth of a millijoule per square
centimetre — a tiny amount of energy, but delivered in about ten billionths of a second, which
makes the spot momentarily very bright.*

**The intensity, which is the number that travels to the microwave question** (this program's own
arithmetic, `INFERRED` from the fetched fluences and pulse widths):

```
GST crystallisation, ns pulse:  36 mJ/cm² / 20 ns  = 1.8 MW/cm²  = 1.8×10¹⁰ W/m²
GeTe amorphisation, ns pulse:   38 mJ/cm² / 10 ns  = 3.8 MW/cm²  = 3.8×10¹⁰ W/m²
```

### 2.2 What field a microwave would need to do the same thing directly

**Route A — field-driven (ovonic) threshold switching.** Scoggin, Silva & Gokirmak
(arXiv:1906.09316, **full text ingested**) state:

> "The model can be tuned to capture switching fields from ~5 to 40 MV/m at room temperature…"

and, citing measured device literature, report switching fields from `8.1 MV/m` to `94 MV/m`
depending on material and thickness, with their own simulations landing at
`E_switch` from `5 to 42.5 MV/m`.

Convert an optimistic `10 MV/m` peak to a free-space plane wave (this program's own arithmetic,
`INFERRED`; `η₀ = 376.7 Ω`):

```
S = E_peak² / (2·η₀) = (1×10⁷ V/m)² / 753.4 = 1.33×10¹¹ W/m² = 1.33×10⁷ W/cm²
```

**Two things kill this:**

1. `10 MV/m` is above the breakdown field of air, quoted at `≈3.1 MV/m` for microwave-pulse
   atmospheric breakdown (search-synthesis confidence; the primary was not fetched, see §6).
   You cannot present that field to the surface through air — the air arcs first.
2. Even ignoring the air, `1.33×10¹¹ W/m²` is roughly **nine orders of magnitude** above the power
   density at which a rectifying cell already self-writes (§2.3), and `≈7` orders above the
   *laser* intensity that writes a disc.

*The obvious escape hatch, stated honestly.* A resonant cell concentrates field into its gap, and
inside a solid dielectric the breakdown limit is far higher than air's. With a generous `100×`
local field enhancement the required incident field falls to `≈100 kV/m`, i.e. `≈1.3×10⁷ W/m²`
(`≈1.3 kW/cm²`). That is below air breakdown and therefore not excluded — **but it is
high-power-microwave-weapon territory at close range**, not radar and certainly not
communications. For scale: a `1 kW` transmitter at `1 m` delivers `≈80 W/m²`. So even the
optimistic, enhancement-assisted direct route is `~10⁵` short of anything a normal illuminator
provides. **`INFERRED` — the `100×` enhancement factor is a stand-in, not a value taken from any
source.**

**Route B — thermal (the wave heats the cell until it crystallises).** This fails for a sharper
and more interesting reason, and the number comes from a measured source. Jeong *et al.* measured
amorphous GeTe at 10 GHz at `σ = 0.63×10⁻² S/m`. For a 100 nm film that is a sheet resistance of

```
R_s = 1/(σ·t) = 1/(0.63×10⁻² × 100×10⁻⁹) ≈ 1.6×10⁹ Ω/sq
```

A thin resistive sheet with `R_s ≫ η₀` absorbs roughly `η₀/R_s` of an incident wave:

```
A ≈ 376.7 / 1.6×10⁹ ≈ 2.4×10⁻⁷
```

*Plain reading: about two parts in ten million of the incident microwave power lands in the
amorphous film. The un-written state of the material is nearly invisible to the wave you wanted
to write with.* (This program's own arithmetic, `INFERRED`; the thin-sheet absorptance formula
assumes a non-resonant free-standing sheet, and a resonant cell with a ground plane would do
better — but it has to do better by a factor of millions.)

**A mechanism note worth flagging as a hypothesis, not a finding.** The same measured numbers say
the *crystalline* state is `3.2×10⁵ S/m`, giving `R_s ≈ 31 Ω/sq` — which is close to the
`≈377 Ω/sq`-family of values that make a good resistive absorber sheet, and is a strong absorber
in a grounded cell. So a field-written phase-change surface would be **thermally asymmetric**:
cells that have already crystallised absorb far more than cells that have not, so once a cell
flips it becomes the hot spot and preferentially keeps absorbing. That is a runaway/latch-up
stability question that any field-written PCM surface must answer. **No source was found that
addresses it. `HYPOTHESIS`, stated as such.**

### 2.3 Indirect self-writing at microwave is already demonstrated

Kiani, Tayarani, Momeni, Rajabalipanah & Abdolali, *"Self-biased Tri-state Power-Multiplexed
Digital Metasurface Operating at Microwave Frequencies"* (arXiv:1910.07353, **full text
ingested**). Verbatim:

> "Under high-power illuminations (e.g. 10 dBm), PIN-diodes function in the ON-state because the
> induced current exceeds the standard threshold; But, being exposed to low-power plane waves
> (e.g. −10 dBm), the current passing through the PIN-diode of nonlinear meta-atoms is far less
> than the standard threshold and the diodes are in OFF-state."

> "When a high-power plane wave impinges on the nonlinear particles, the PIN-diodes are in
> ON-state, although there is no any external biasing circuit. In fact, the I-shape meta-atoms are
> quite passive and adopt themselves with the power level of the input signals, making us call
> the metasurface as a self-biased architecture."

The mechanism is stated explicitly and is rectification, not field-driven switching: the PIN
diode's forward drop truncates the positive half-cycle at `0.75 V`, carriers accumulate in the
intrinsic layer faster than they leave, and the diode sits stably ON for as long as the
illumination lasts. Cell period `p = 11 mm`; substrate Rogers RT5880, `h = 1 mm`; diode Macom
MA4L401-134, `R_on = 1.2 Ω`, `C_off = 0.2–0.25 pF`; bands `6.7 GHz` (absorb) and `9.3–9.39 GHz`
(diffuse).

**Power density at the write threshold** (this program's own arithmetic, `INFERRED` — the paper
states `10 dBm` as an excitation level in a CST Floquet-port simulation and does not itself
convert it to an incident power density; reading it as per-cell incident power is an inference):

```
10 dBm = 10 mW over an 11 mm × 11 mm cell (1.21×10⁻⁴ m²)
S ≈ 82.6 W/m² ≈ 8.3 mW/cm²
E_rms = √(S·η₀) ≈ 176 V/m   (peak ≈ 249 V/m)
```

**Two critical caveats, both of which the idea has to survive:**

1. **This paper is simulation only.** Its own closing sentence is *"The numerical simulations
   verify the tri-state performance of the proposed nonlinear metasurface."* No fabricated,
   measured self-biased microwave metasurface was found in this pass.
2. **It is volatile.** The state is held only while the illumination is held; the surface reverts
   to its linear-mirror state when the high-power excitation stops. It is a *self-biasing*
   surface, not a *self-writing* one. **The missing piece is exactly one thing: replace the PIN
   diode with a latching element, so the rectified energy sets a state that survives.**

**The scale of the gap, stated as one ratio:**

```
direct field-driven route   1.33×10¹¹ W/m²
rectified self-bias route   8.3×10¹   W/m²
ratio                       ≈ 1.6×10⁹   (≈ 9 orders of magnitude)
```

---

## 3. The prize, quantified — what the control network actually costs

All numbers in this section are from Wang, Tang, Liang, Zhang, Dai, Li, Jin, Cheng & Cui,
*"Reconfigurable Intelligent Surface: Power Consumption Modeling and Practical Measurement
Validation"* (arXiv:2211.00323, **full text ingested**). These are *measured*, on five different
fabricated RISs.

| RIS | Elements | Freq. | Per-cell hold power | Static (controller + drivers) | Measured total |
|---|---|---|---|---|---|
| 1# PIN, 1-bit | `16×16 = 256` | `3.5 GHz` | `P_PIN = 12.56 mW` | control board `4.8 W`; 32 shift registers × `0.07 mW` = `2.24 mW` | — |
| 2# PIN, 1-bit, dual-pol | `60×60 = 3600` | `35 GHz` | `12.56 mW` | `P_static = 15.73 W` | **`103.2 W` all-ON**; `P_units ≈ 90 W` |
| 3# PIN, 1-bit | `32×16 = 512` | `2.6 GHz` | `11.99 mW` | `6.52 W` | `12.66 W` all-ON |
| 4# PIN, 2-bit | `8×8 = 64` | **`9.5 GHz`** | `1.25 mW` | — | — |
| 5# Varactor | `8×16 = 128` | `3.2 GHz` | **`≈ 0`** (reverse-biased) | `4.8 W` board + **`1720 mW` drivers** (4 × `430 mW` DAC+op-amp) | — |
| 6# RF switch | `8×8 = 64` | — | `3.3 V × 150 µA = 495 µW` | `240 mW` drive circuit | — |

Their own simplified engineering model:

> `P_RIS ≈ P_control_board + N × P_PIN`, with `P_control_board = 4.8 W` and `P_PIN = 10 mW`.

*Plain reading: a 3600-cell PIN-diode surface burns about 103 watts — a bright old-fashioned light
bulb — purely to sit still and hold a pattern it has already chosen. About 16 of those watts are
spent before a single cell is even turned on.*

**Three honest corrections to the idea's premise, which matter for how the pitch is made:**

1. **"N bias lines for N elements" is a strawman against good practice.** The measured PIN RIS
   does not run 256 wires; it runs `32` SN74LV595A 8-bit shift registers, serially loaded — one
   driver output per cell, but only a handful of control wires to the board. The real cost is not
   wire count, it is (a) a driver output per cell, (b) an RF-blocking bias network per cell, and
   (c) the standing power in the table above.
2. **Even a "zero-power" cell does not give you a zero-power surface.** The varactor RIS has
   essentially zero unit-cell power and still burns `4.8 W + 1.72 W ≈ 6.5 W` in board and drivers.
   A latch removes `P_units`, not `P_static`. To remove `P_static` you must also be able to power
   the controller down between writes — which is the actual systems argument for a latch, and is
   a different claim from "it saves 103 W."
3. **No verified number was found for bias-line insertion loss or bandwidth penalty.** Radial-stub
   RF/DC isolation is standard practice and was repeatedly described in search results, but no
   fetched primary source in this pass quantified the loss a bias network adds or the bandwidth it
   costs. **This is a real gap in the answer to question 3 and is not papered over.**

**What the latch is genuinely worth, stated at the size it actually is:** for the measured 3600-cell
35 GHz surface, a latching cell removes up to `≈90 W` of `P_units` and, *if* the controller can
also sleep between writes, a further `15.73 W` — i.e. the whole `103.2 W` collapses toward the
energy of the write pulses themselves. GeTe switch write pulses are `0.1–1.5 µs`; at that duty
cycle the average hold power of a rarely-repointed surface is essentially zero.

---

## 4. The load-bearing properties — retention, endurance, spread, contrast

This is where the honest answer is thinnest, and the thinness is the finding.

### 4.1 Loss / resistivity contrast at microwave — **good, and measured**

| Quantity | Value | Source | Status |
|---|---|---|---|
| GeTe σ, amorphous, **at 10 GHz** | `0.63×10⁻² S/m` | Sensors 2018 | measured |
| GeTe σ, crystalline, **at 10 GHz** | `3.2×10⁵ S/m` | Sensors 2018 | measured |
| GeTe crystalline resistivity (DC) | `3.1×10⁻⁴ Ω·cm` | APL 2014 | measured |
| `R_on` / `R_off` | `0.9 Ω` / `35.3 kΩ` | Micromachines 2024 benchmark | measured (survey) |
| IL / isolation | `<0.5 dB` / `>18 dB` to `20 GHz`; `0.1–0.24 dB` to `40 GHz` | Micromachines 2024; APL 2014 | measured |

**This assumption is not the one that kills the idea.** A conductivity ratio of `≈5×10⁷` between
states, measured at 10 GHz, is more contrast than a 1-bit cell needs. *Plain reading: in one state
the material is as good an insulator as window glass; in the other it conducts about as well as a
poor metal — and that difference was measured at X-band, not extrapolated from DC.*

### 4.2 Retention — **partly answered, and the RF-specific answer is missing**

- **From memory technology (not RF devices):** the industry criterion is `10 years at 85 °C` with
  `<1 ppb` array failures; retention falls very fast with temperature — `≈10 hours at 125 °C`,
  `≈10 seconds at 165 °C`, `≈10 µs at 225 °C`. Retention activation energies of `2.2–3.5 eV` are
  reported, with mushroom cells at `2.6 eV` implying `>300 years at 85 °C`.
  *(search-synthesis confidence; primary PCM-technology review not fetched.)*
- **From the printed metasurface:** Xiao *et al.* report on/off ratio retained "for over 10 years"
  — but that is **extrapolated from a shorter measurement**, not observed.
- **What is missing:** no fetched source reported retention *of an RF switch or an RF metasurface
  cell*, at a stated temperature, measured as RF insertion loss or reflection phase rather than as
  DC resistance. One early GeTe RF result quoted `10⁴ s` retention in search synthesis; that was
  not traced to a primary.

**Why this matters concretely for this repo:** a conformal surface on a vehicle skin or an aircraft
panel sits at whatever temperature that surface reaches. GeTe's crystallisation temperature is
`190–210 °C` and the Sensors 2018 absorber was crystallised at `250 °C` held for 30 minutes — but
partial crystallisation begins well below that, and the memory-technology numbers above say
retention collapses by orders of magnitude between 85 °C and 165 °C. **A written pattern surviving
a hot skin is a load-bearing assumption with no measured RF answer.**

### 4.3 Cycling endurance — **wide spread, and the spread is itself the warning**

Reported values found, spanning five orders of magnitude:

- `>10⁶` cycles (GeTe RF switch, best reported)
- `5000` cycles at 40 mK with "virtually identical performance"
- `2000` cycles with low-resistance state averaging `294 Ω`
- `>475` cycles at `9.3 ± 3.7 Ω`
- `100` cycles (early work)
- `300` DC cycles (the printed MoS₂ metasurface, Nat. Commun. 2024)
- **`3` cycles before visible damage** under repeated *optical* writing of GeTe at identical power
  — Li *et al.* 2025 report "ablation particles… formed after three cycles" and call this "a great
  challenge to the cycle durability of GeTe."

*Plain reading: reports range from a million rewrites down to three, depending entirely on how the
heat is delivered. Electrically-heated switches with a dedicated heater do best; anything that
dumps energy in through the surface itself does worst — which is precisely the regime a
field-written cell would live in.* That last row is the most important number in this section for
the self-writing idea specifically, and it points the wrong way.

### 4.4 Cell-to-cell switching-threshold variability — **nobody publishes it**

**This is the flat gap.** No fetched source reported a threshold distribution across the cells of
an array — no σ, no min/max, no yield figure. What exists is adjacent and weaker:

- A wafer-level GeTe sputtering study frames "compositional homogeneity and resistivity uniformity"
  as "crucial for ensuring the yield and reliability of RF switches" and tunes four deposition
  parameters to control it — an acknowledgement that the problem is real and unsolved, not a
  measurement of it. *(search-synthesis confidence; primary not fetched.)*
- The Micromachines 2024 benchmark review explicitly does **not** report device-to-device
  variability or wafer uniformity.
- Li *et al.* 2025 note Gaussian-beam edge effects but give "no specific uniformity metrics for
  threshold spread."

**Stated the way the charter requires:** *the assumption that thousands of printed cells will
switch at thresholds tight enough to write a coherent phase pattern is load-bearing, untested in
every source found, and — if it is wrong — turns a designed phase gradient into a partly random
one, which is the failure mode that destroys beam pointing rather than merely degrading gain.*
The cheapest way to find out is §6.

---

## 5. What this means for a candidate design in this program

Presented as a candidate, not a recommendation; scored nowhere, gated by nothing.

- **Label:** a **new arrangement** (rectifying self-bias cell + latching switch) containing **one
  new element** (the combined cell). **Not a new mechanism** — both halves are published.
- **Nearest buildable precedent in this repo's own process:** Xiao *et al.* 2024 — inkjet-printed
  switch, screen-printed conductor, paper substrate, foil ground plane, measured `0.3–12 GHz`,
  `<0.7 dB` insertion loss, zero static power. If the program wants a printed latching letter for
  the Element/Coding-Alphabet library, that paper is the closest thing to a recipe, and a printed
  memristive switch may be a better first target than a chalcogenide precisely because it needs
  `1.75 V`, not `250 °C`.
- **ADR-0027 still binds:** neither a chalcogenide cell nor a printed memristive cell enters the
  alphabet as a characterised letter until it has been printed and measured here. Everything above
  is `SIMULATED`-tier or other people's measurements, which is not this program's measurement.
- **The warning that is worth firing** (assumption / cost if wrong / cheapest check), per the
  charter's rule that a warning must be rare, specific and load-bearing:
  > **Assumed:** printed latching cells switch at close enough thresholds across an aperture to
  > realise a designed phase pattern. **Cost if wrong:** the written pattern is partly random;
  > beam pointing fails outright rather than degrading, and no amount of re-writing fixes it.
  > **Cheapest way to find out:** print one row of `N` nominally identical cells on the target
  > substrate and measure the switching threshold of each. This needs no array, no feed, and no
  > anechoic chamber.

---

## 6. What is still unknown, and the single fetch or measurement that resolves most

**Still unknown (each stated as a question, not a hedge):**

1. **Cell-to-cell switching-threshold spread for any printed or thin-film latching RF cell.**
   Nothing found. This is the assumption most likely to kill the idea and the one with the least
   published evidence.
2. **Retention of an *RF* state** — reflection phase or insertion loss, not DC resistance — at a
   stated elevated temperature, for a chalcogenide or printed memristive RF cell. The 10-year
   figures found are either from memory technology or extrapolated.
3. **Insertion loss and bandwidth cost of the bias network itself**, measured. Question 3's most
   quantitative sub-question is the one with no verified number in this pass.
4. **Whether a remanent-polarisation (zero-bias ferroelectric) microwave metasurface cell has ever
   been published.** Searched once, not found; absence here is weak evidence.
5. **Whether the thermal asymmetry flagged in §2.2 is a real instability.** The crystalline state
   absorbs microwaves vastly better than the amorphous one, so a field-written surface may be
   unstable in one direction. Nobody addresses this because nobody has tried to field-write a PCM
   surface at RF.
6. **Whether any fabricated, measured self-biased microwave metasurface exists.** The only one
   found is simulation.

**The single thing that would resolve the most, and it is a measurement, not a fetch:**

> **Print `N ≈ 32` nominally identical latching switch cells in one row on the intended flexible
> substrate, using the intended ink and cure, and measure the set/reset threshold of every one.**

This is cheap, needs no array, no feed, no chamber and no RF measurement at all — a DC probe
station or even a source-meter is enough — and it settles unknown 1, which is the load-bearing one.
If the spread is tight, the idea's main risk is retired and the next step is a small measured
array. If the spread is wide, the idea is dead in its printed form before any RF money is spent,
and the program has learned that from one afternoon's work. Following the charter's own
step-one logic (`CLAUDE.md`, "Filling the alphabet is step one"), it is also exactly the kind of
first print-and-measure the program already says is its fastest unblocking action.

**The single most valuable *fetch*, if a measurement is not available:** the full text of
Singh, Khaira, Repeta & Mansour, *"Phase-Change RF Devices for Future Communications: …
State-of-the-Art and Future Perspectives,"* *IEEE Microwave Magazine* (Feb 2024) — the only
source found that is scoped to exactly this question (PCM devices for reconfigurable RF
front-ends) and is likely to carry retention, endurance and variability figures in one place. It
was **not** fetched in this pass (paywalled; only a Semantic Scholar record and a ResearchGate
request page were reachable). Volume, issue and page numbers were **not verified** and are
deliberately not stated here.

---

## Sources

### Full text ingested into `knowledge/corpus/` in this pass

Converted from arXiv LaTeX source via this repo's `.claude/skills/arxiv-doc-builder`
(`convert_paper.py` → pandoc). Tarballs, PDFs and figures were kept in the scratchpad and are not
in the repo; only the converted Markdown body, with a provenance header, was added.

- Kiani, M., Tayarani, M., Momeni, A., Rajabalipanah, H. & Abdolali, A., *Self-biased Tri-state
  Power-Multiplexed Digital Metasurface Operating at Microwave Frequencies*,
  [arXiv:1910.07353](https://arxiv.org/abs/1910.07353) →
  `knowledge/corpus/arxiv_1910_07353_self_biased_power_multiplexed_metasurface.md`.
  **Simulation only** (CST; the paper says so in its own words). Journal of record not verified —
  the LaTeX uses an OSA template and the converted frontmatter carries no DOI; do not cite a
  journal, volume or page for this until one is verified.
- Scoggin, J., Silva, H. & Gokirmak, A., *Field Dependent Conductivity and Threshold Switching in
  Amorphous Chalcogenides — Modeling and Simulations of Ovonic Threshold Switches and Phase Change
  Memory Devices*, [arXiv:1906.09316](https://arxiv.org/abs/1906.09316) →
  `knowledge/corpus/arxiv_1906_09316_chalcogenide_threshold_switching_fields.md`.
  The arXiv record points to DOI `10.1063/5.0027671` (*J. Appl. Phys.* 128, 234503); the journal
  version was not fetched, so cite the preprint. **Modelling paper** — its `5–42.5 MV/m` is
  simulated; the `8.1–94 MV/m` it quotes is from its own reference [33], which was not chased.
- Wang, J., Tang, W., Liang, J. C., Zhang, L., Dai, J. Y., Li, X., Jin, S., Cheng, Q. & Cui, T. J.,
  *Reconfigurable Intelligent Surface: Power Consumption Modeling and Practical Measurement
  Validation*, [arXiv:2211.00323](https://arxiv.org/abs/2211.00323) →
  `knowledge/corpus/arxiv_2211_00323_ris_power_consumption_measurement.md`.
  **Measured**, five fabricated RISs. Every §3 number is from this ingested full text.

### Fetched full text or full publisher record (read in this pass, not ingested)

- Jeong, H., Park, J.-H., Moon, Y.-H., Baek, C.-W. & Lim, S., *Thermal Frequency Reconfigurable
  Electromagnetic Absorber Using Phase Change Material*, *Sensors* **18**(10):3506 (2018),
  DOI [10.3390/s18103506](https://doi.org/10.3390/s18103506) —
  [PMC6210757](https://pmc.ncbi.nlm.nih.gov/articles/PMC6210757/). **Measured, X-band.** Source of
  both 10 GHz conductivities and the `10.23 → 9.6 GHz` shift.
- Xiao, X., Peng, Z., Zhang, Z., Zhou, X., Liu, X., Liu, Y., Wang, J., Li, H., Novoselov, K. S.,
  Casiraghi, C. & Hu, Z., *Fully printed zero-static power MoS₂ switch coded reconfigurable
  graphene metasurface for RF/microwave electromagnetic wave manipulation and control*,
  *Nature Communications* **15**:10591 (2024),
  DOI [10.1038/s41467-024-54900-z](https://doi.org/10.1038/s41467-024-54900-z) —
  [PMC11618370](https://pmc.ncbi.nlm.nih.gov/articles/PMC11618370/). **Measured, printed, 6×6.**
- Gharbieh, S., Milbrandt, J., Reig, B., Mercier, D., Allain, M. & Clemente, A., *Design of a binary
  programmable transmitarray based on phase change material for beam steering applications in
  D-band*, *Scientific Reports* **14**:2966 (2024),
  DOI [10.1038/s41598-024-53150-9](https://doi.org/10.1038/s41598-024-53150-9) —
  [PMC11303715](https://pmc.ncbi.nlm.nih.gov/articles/PMC11303715/). **Simulation only**, by the
  authors' own statement.
- Li, Y., Ma, X., Chen, Q., Qian, S., Jiang, Y., Zheng, Y. & Fu, Y., *Phase Transition Behavior and
  Threshold Characteristics of GeTe Thin Films Under Single-Pulse Nanosecond Laser Irradiation*,
  *Materials* **18**(23):5466 (2025),
  DOI [10.3390/ma18235466](https://doi.org/10.3390/ma18235466) —
  [PMC12693245](https://pmc.ncbi.nlm.nih.gov/articles/PMC12693245/). **Measured.** Source of the
  GeTe write/erase fluence windows and the three-cycle optical damage finding.
- Sun, X., Ehrhardt, M., Lotnyk, A., Lorenz, P., Thelander, E., Gerlach, J. W., Smausz, T.,
  Decker, U. & Rauschenbach, B., *Crystallization of Ge₂Sb₂Te₅ thin films by nano- and femtosecond
  single laser pulse irradiation*, *Scientific Reports* **6**:28246 (2016),
  DOI [10.1038/srep28246](https://doi.org/10.1038/srep28246) —
  [PMC4904278](https://pmc.ncbi.nlm.nih.gov/articles/PMC4904278/). **Measured.** Source of the GST
  fluence thresholds.
- Qu, S., Gao, L., Wang, J., Chen, H. & Zhang, J., *A Review on Material Selection Benchmarking in
  GeTe-Based RF Phase-Change Switches for Each Layer*, *Micromachines* **15**(3):380 (2024),
  DOI [10.3390/mi15030380](https://doi.org/10.3390/mi15030380) —
  [PMC10972129](https://pmc.ncbi.nlm.nih.gov/articles/PMC10972129/). **Review of others' measured
  devices**, not itself a measurement. Explicitly reports no variability/uniformity data.
- Hojjati-Firoozabadi, A. & Mansour, R., *A Microfabricated PCM-Switched Reconfigurable Intelligent
  Surface for Wideband Millimeter-Wave Beam Steering*,
  [arXiv:2605.07311](https://arxiv.org/abs/2605.07311) (8 May 2026). **Measured, but volatile
  (VO₂).** HTML full text read; not ingested, because its finding here is a negative one.
- Chen *et al.*, *Chalcogenide phase-change material advances programmable terahertz metamaterials:
  a non-volatile perspective for reconfigurable intelligent surfaces*, *Nanophotonics* (2024),
  DOI [10.1515/nanoph-2023-0645](https://doi.org/10.1515/nanoph-2023-0645) —
  [PMC11501539](https://pmc.ncbi.nlm.nih.gov/articles/PMC11501539/). Read via full-text fetch;
  **terahertz, not microwave**, and it reports no retention or endurance numbers. Its
  `0.6366 mJ/cm²` switching-energy figure was **not traced to its own primary** and is therefore
  not used anywhere above.

### Abstract / record / search-synthesis only — explicitly weaker, and used only where labelled

- Wang, Y. & Rais-Zadeh, M. (attribution from search results; author list **not verified**),
  *Low-loss latching microwave switch using thermally pulsed non-volatile chalcogenide phase change
  materials*, *Applied Physics Letters* **105**(1):013501 (2014) —
  [publisher record](https://pubs.aip.org/aip/apl/article/105/1/013501/596284/Low-loss-latching-microwave-switch-using-thermally),
  **403 on direct fetch**. The `0.1–0.24 dB` over `0–40 GHz`, the `0.1–1.5 µs` pulse and the
  `3.1×10⁻⁴ Ω·cm` resistivity are search-synthesis restatements of this abstract, corroborated
  against the independently-fetched Micromachines 2024 review. **The full text was not read.**
- MagLatch magnetic-latching RF MEMS (Microlab / Arizona State; `DC–6 GHz`, `<0.5 dB`, `≥40 dB`,
  `<5 V`): **trade-press synthesis only** (EE Times, EDN, Microwave Journal). No peer-reviewed
  primary was fetched. A "0.2 dB at 10 GHz in the latched state with no bias" figure appeared in
  one search summary, could **not** be traced to any specific paper, and is therefore **not used**
  anywhere above.
- Microwave-pulse atmospheric breakdown at `≈3.1 MV/m`: search-synthesis, consistent with the
  textbook `≈3 MV/m` DC figure for air. Primary not fetched. §2.2 depends on this only for an
  order-of-magnitude argument.
- PCM retention figures (`10 years at 85 °C`, `10 h at 125 °C`, `10 s at 165 °C`, `10 µs at 225 °C`;
  activation energies `2.2–3.5 eV`): search-synthesis from phase-change-memory literature,
  consistently restated across independent results. Primary review not fetched. **These are memory
  numbers, not RF numbers** — §4.2 says so.
- GeTe RF switch endurance figures (`>10⁶`, `5000`, `2000`, `>475`, `100` cycles): search-synthesis
  across several ResearchGate/IEEE records, none fetched in full. The spread is reported as a
  spread precisely because no single primary was read.
- Wafer-level GeTe sputter uniformity study (IOP, `10.1088/1674-4926/24120033`): record-level only.
- Singh, Khaira, Repeta & Mansour, *IEEE Microwave Magazine* (Feb 2024): **record-level only;
  volume/issue/pages not verified.** Named in §6 as the highest-value unfetched source.

### Carried forward from this repo's own prior work, not re-verified here

- `docs/example4-5-beam-steering-scoring-recipe.md` (Example 5 / BST-tunable reflectarray as the
  volatile baseline this idea is proposed against, and the house evidence-labelling convention
  this document follows).
- `docs/seven-example-design-unknowns.md` §6.3, for "available bias supply and per-cell control
  wiring budget" already being a named per-family human input — which is the same quantity §3
  quantifies from measured data.
