# What actually sets the printed feature floor — three sources, three mechanisms

**Date:** 2026-09-05
**Ticket:** [#115](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/115) — bears on [#106](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/106), [#128](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/128); part of [#104](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/104).
**Question:** #115 asks what the feature floor constrains and how the loop enforces it. This asks the prior question — *what physically sets the floor at all*, and which published numbers may legitimately be carried onto a NOVA.

---

## Bottom line up front

**The floor is not a property of the nozzle. It is where nozzle fineness meets the machine's
maximum extrusion pressure, for a given ink.** That is the single most useful sentence here, and
it means "minimum feature size" cannot be a constant in the loop — it is a function of the ink.

**And the biggest trap in these three sources is that they describe three different dispensing
mechanisms.** Getting this wrong would import a constant across a mechanism boundary, which is
the failure this repo has already recorded twice.

| Source | Mechanism | Material | Transfers to NOVA? |
|---|---|---|---|
| EFD, *Auger Valve Dispensing* (SSL601b, ©2003) | **Auger valve** — rotating screw | Solder paste | **Mechanism: no.** Geometry rules: prior only |
| Voltera, *Introduction to DIW* | **Positive displacement** — motor-driven piston | Conductive ink | **Yes — this is the machine** |
| Lamnini et al., *Heliyon* 8 (2022) e10651 | **Pneumatic syringe** (psi/kPa) | Ceramic pastes | **Mechanism: partly.** Numbers: no |

Voltera's own blog states the distinction explicitly, contrasting time-pressure, auger valve and
positive displacement, and placing **V-One and NOVA in positive displacement** — *"a
positive-displacement, direct-ink-writing system"* using *"a motor-driven piston to extrude
material through the nozzle."*

**So the EFD document is not about this printer.** It is still worth reading, because its
tip-geometry rule is about tip bore and paste break-off rather than about what pushes the paste —
but it is a **prior to test on #106**, never a constraint to enforce.

---

## 1. The EFD tip rule, and the tension it creates

EFD's rule, verbatim:

> "When choosing a tip, the rule of thumb is you may not expect to produce a deposit with a
> diameter **less than 1½ times the tip ID**. It is technically possible to do so but is difficult."

Their published table is internally consistent with it to within 3%:

| Gage | Colour | Tip ID | Min. dot | Ratio |
|---|---|---|---|---|
| **30** | Lavender | 0.006″ = **152 µm** | 0.009″ = **229 µm** | 1.50 |
| **27** | Clear | 0.008″ = **203 µm** | 0.012″ = **305 µm** | 1.50 |
| 25 | Red | 0.010″ = 254 µm | 0.015″ = 381 µm | 1.50 |
| 23 | Orange | 0.013″ = 330 µm | 0.020″ = 508 µm | 1.54 |

**Those top two rows are the tips #106 already names** — "Nordson EFD 150 µm and 200 µm".

**The tension.** Voltera claims *"features down to 100 µm"* with the footnote *"[1] Dependent on
material and nozzle"*, and separately *"it is not uncommon for finer features to be produced."*
If EFD's 1.5× rule transferred, a 150 µm tip would floor at **229 µm** and a 200 µm tip at
**305 µm** — neither reaching 100 µm, and the second failing the patent's own 200 µm minimum
feature.

**Three ways that tension resolves, and we cannot yet say which:**

1. **A dot is not a line.** EFD's table is the minimum *static deposit* diameter. A line drawn by
   moving the substrate under a flowing bead is stretched by the motion and can be narrower than
   a static dot. This is the most likely explanation and it makes the 1.5× figure a bound on the
   wrong quantity.
2. **Different mechanism.** Positive displacement meters volume directly; an auger relies on
   screw-generated pressure against tip resistance. Break-off behaviour need not match.
3. **Different material.** Solder paste with alloy particles behaves unlike a filled conductive ink.

**What to do with it:** treat `1.5 × tip ID` as a **prior for dot diameter**, `ASSUMED` for line
width, and let #106 measure the real line width per tip. It is a reason to *expect* the achieved
line to exceed the nozzle bore, not a number to enforce.

---

## 2. The mechanism that actually sets the floor

From Lamnini et al., and this is the load-bearing insight:

> "…on the contrary, **fine nozzles required excessive syringe pressure beyond the machine
> capabilities** to enable paste extrusion."

And from the same review's printability-window discussion: a paste whose yield stress `σy` sits
**above the maximum extrusion pressure the system can apply cannot be extruded at all**; too low
a `σy` gives poor deposition control and nozzle dripping; a suitable `σy` with too low a storage
modulus `G′` extrudes but will not hold its shape.

**In plain terms.** *You can always fit a finer nozzle. What stops you is that pushing the same
ink through a smaller hole needs more pressure, and eventually more than the machine has. So the
finest line a machine can draw depends on what you are printing, not only on what tip is fitted —
and a thicker, stiffer ink hits that wall sooner.*

This is why Voltera's own "100 µm" carries "dependent on material and nozzle", and it is the
reason **#115 cannot enforce a single feature-floor constant**. The floor is per-ink.

---

## 3. The named mechanism for line-width scatter

Also from Lamnini et al. — this supplies the source the tolerance-band argument previously lacked:

> "…the size of the extrusion tip directly impacted on the range of syringe pressures which then
> had to be matched with the printing speed to prevent either **'under-pumping' or
> 'over-pumping'**, which were respectively described as the situations where the extruded struts
> are either **finer or wider than intended** upon deposition due to a mismatch between syringe
> pressure and travel speed."

So achieved line width is set by the **ratio of delivery rate to travel speed**, and any mismatch
shows up directly as width error. Two vendor-acknowledged contributors on the NOVA specifically,
both from Voltera's own blog listing positive displacement's drawbacks:

- *"Trapped air in your fluid which is compressible can alter your flow rate."*
- Conductive inks are **thixotropic** — viscosity drops under shear and **recovery takes time** —
  introducing *"variability in flow behavior."*

**Consequence for #106:** measuring line width thirty times and reporting the spread is not
belt-and-braces, it is measuring the quantity that actually varies. And the spread should be
reported **per tip and per ink**, because both enter the mechanism.

---

## 4. Numbers that exist but must not be carried over

Lamnini et al. give concrete settings. They are **ceramic robocasting** — aqueous concentrated
ceramic pastes, sintered afterward — and the numbers are recorded here only so nobody re-derives
them and mistakes them for guidance.

- Layer height and strut spacing determined empirically as **`d/1.15` and `d/1.2`** for a conical
  nozzle of `d` = 200 µm (so ≈ 174 µm and ≈ 167 µm) with hexagonal filament stacking.
- Reducing the orifice from **584 µm to 406 µm** gave *"significantly higher dimensional accuracy,
  lower staircasing effect"*.
- Worked settings: 47 vol% B₄C at **80 psi (550 kPa)**, 4 mm/s, 440 µm layer height on the 584 µm
  orifice; **30 psi (200 kPa)**, 4 mm/s, 260 µm on the 406 µm orifice.
- Their Table 4 rates **orifice diameter, printing speed and layer height all "crucial" (`+++`)
  for resolution**, particle size only `+`. The paper labels this table qualitative; it is a
  ranking, not data.

**None of these transfer.** Different material class, different mechanism, different objective
(self-supporting 3D lattices, not thin traces on film). What transfers is the **shape of the
relationship** — resolution is jointly set by orifice, speed and height, and rheology sets the
window all three live in.

EFD's two process figures are in the same category — auger-and-solder-paste priors, not NOVA
specifications:

- *"When tuned well, auger valves are capable of making sub-milligram size deposits with **less
  than 5% variability** from deposit to deposit."*
- *"A good starting point for **Z-height is ½ the tip ID**."* Directionally consistent with
  Voltera's *"both the nozzle and print height must be reduced to limit the amount of fluid that
  can be deposited"*, which gives no number.

---

## 5. What this changes for #115

**The ticket asks which limits reject a candidate and which merely score it. This says the
rejecting limit is not a constant.**

1. **Feature floor is a per-ink, per-tip measured quantity**, not a machine constant. A loop that
   hardcodes 100 µm is enforcing a figure the vendor itself qualifies twice.
2. **The binding number may be the gap, not the line.** Nothing in these three sources bounds
   line-to-line spacing, which for a resonant element is at least as load-bearing as trace width.
   Still unmeasured, still open.
3. **A candidate sitting exactly at the floor will not print reliably**, and now there is a named
   mechanism for why — pressure/speed mismatch plus thixotropic recovery — rather than an appeal
   to general caution. Whatever threshold #115 settles on wants margin, sized from #106's measured
   spread.
4. **#106's line-width task should record tip ID, ink, standoff, speed and pressure alongside each
   measurement.** Without those the number is not reusable, because every one of them is in the
   mechanism.
