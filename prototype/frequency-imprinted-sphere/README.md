# Frequency-imprinted sphere prototype (THROWAWAY)

Answers one design question, raised in conversation and **not yet filed as an
issue**: does the chain *drive frequency → wavelength → resonant mode →
latched pattern* hang together well enough to be worth taking further?

The idea: a surface whose cells **latch their own configuration** and then hold
it with no sustained power or bias. Drive it at a chosen frequency, a resonant
pattern forms across it, cells where the field is strong switch state and
**stay** switched, and the pattern survives after the drive stops.

*In plain terms: today's tunable surfaces are like a screen — they only hold a
picture while powered. This would be like a printed page: written once, then
holding its shape with nothing attached to it.*

## Why this is framed electromagnetically

The idea arrived acoustically (cymatics — sand hopping into patterns on a
vibrating plate, but on a sphere, with the sand staying put). It was redirected
to the electromagnetic spectrum, which is both in scope for this repo and the
stronger version of the idea, for two reasons:

**The prize is concrete and already visible in this repo.** US12089385B2
Example 5 — the BST-tunable reflectarray this repo already models in
`designs/design_families.py` (`REFLECTION_PHASE`) — is *volatile*: every cell
needs a continuous bias voltage, so every cell needs a wire, a driver and a
share of a power budget. A latching surface needs none of that after writing.
For a thin conformal skin, which is what this program's charter is actually
about, that control network is a large part of what makes a reconfigurable
surface thick, fragile and expensive.

**The memory problem stops being speculative.** Mechanical bistability was the
weak link in the acoustic version. In EM there are materials that already do
this — chalcogenide phase-change materials (the GST family) flip between two
states with a heat pulse and stay flipped, and are already used in RF switches.
Note the contrast with near neighbours that do *not* work here: VO₂ relaxes when
it cools, and BST as Example 5 uses it needs sustained bias. Both are volatile;
neither latches.

## The fork that decides the novelty class — now settled

Research against primary sources has answered this
(**`docs/non-volatile-metasurface-prior-art.md`**). In the charter's three-way
vocabulary this is **not a new mechanism**. It is a **new arrangement** of two
demonstrated parts, plus **one new element** — the combined cell — that nobody
has built. That is a far cheaper claim, and a far cheaper thing to test.

The reason is that the wave cannot write the surface directly, and both routes
fail for measured reasons rather than engineering difficulty:

- **The field flipping the material directly: excluded by air.** Amorphous
  chalcogenide needs roughly 5–42.5 MV/m to threshold-switch. Air breaks down
  near 3 MV/m — *you would ionise the air in front of the surface before you
  switched a single cell.*
- **The wave heating the cell until it crystallises: excluded by transparency.**
  Amorphous GeTe measures 0.63×10⁻² S/m at 10 GHz; a 100 nm film absorbs about
  2×10⁻⁷ of an incident wave. *The state you need to write from is very nearly
  invisible to the very thing you wanted to write with.*
- **The wave rectified into a DC bias that does the writing: already
  demonstrated at microwave.** A self-biased PIN-diode metasurface flips its own
  coding state at about 10 dBm per cell — roughly 83 W/m², some **nine orders of
  magnitude** below the direct-field route.

*In plain terms: the wave can't kick the material hard enough, and can't warm it
either, but it can charge a tiny rectifier that does the switching for it. "The
wave writes the surface" survives only in that indirect form.*

## What already exists, in three tiers

- **Components: solved.** GeTe phase-change RF switches are latching and
  commercial-grade — 0.1–0.24 dB insertion loss over 0–40 GHz, >10⁶ cycles, zero
  hold power. Magnetic-latching RF MEMS ships at DC–6 GHz.
- **A whole small surface: demonstrated once.** Xiao et al., *Nature
  Communications* **15**:10591 (2024) — a fully printed, zero-static-power coded
  reconfigurable microwave metasurface, 6×6 switches, measured 0.3–12 GHz,
  <0.7 dB insertion loss, set/reset at +1.75 V / −1.1 V. Closest precedent to
  this repo's own printed, flexible, low-voltage build route — and notably not a
  chalcogenide but a printed Ag/MoS₂/Ag memristive switch.
- **A large, individually-addressed, non-volatile reflectarray: nobody has built
  one.** The nearest published design is simulation-only; the one measured
  mm-wave RIS using a phase-transition material is VO₂ and *volatile*, held on by
  a constant 20 V at ≈17 mW per element.

## Status of the code in this directory: still the acoustic model

**The running model has not yet been converted.** It computes elastic-wave
quantities in Hz and m/s, on a mechanical mass-in-mass lattice. Read the page as
a structural demonstration, not as an X-band prediction — nothing in it has been
retuned to electromagnetic units.

That transfer is real rather than hand-waved, because the algebra is the same
expression. The acoustic mass-in-mass effective mass and the lossless Lorentz
permittivity are the identical function:

| | acoustic (what the code runs) | electromagnetic (where it is going) |
|---|---|---|
| resonant effective parameter | `m_eff/m₁ = 1 + θ·ω₀²/(ω₀² − ω²)` | `ε_eff/ε₀ = 1 + F·ω₀²/(ω₀² − ω²)` |
| what goes negative above ω₀ | effective mass density | effective permittivity |
| consequence | stop band | stop band |
| wave speed | `v = √(K/m_eff)` | `v = c/√(ε_eff·μ)` |
| mode index on a sphere | `kR = √(ℓ(ℓ+1))` | same relation |
| mode character | scalar | **vector** (TE/TM multipoles) — differs in detail |
| what latches a cell | mechanical bistability | phase-change material |
| what writes it | mechanical force | field-induced heating, or a local pulse |

Converting it is a change of constants and labels, not of structure. A 60 mm
shell swept over roughly 2–14 GHz, with cells resonating near 8 GHz, lands the
mode order in the same ℓ ≈ 2–14 range the acoustic version already exercises —
squarely in this repo's own band. **That conversion has not been done**; saying
it is straightforward is not the same as having done it.

The last two rows are the ones that do *not* transfer for free: EM modes on a
sphere are vector fields, so the drawn pattern is a scalar stand-in for their
angular structure, and the latch mechanism is a different physical device
entirely.

**This is a throwaway prototype, not production code.** Nothing imports it and
no module in this repo reads it.

## What is really computed vs. what is asserted

Really computed, and correct for the acoustic case it currently models:

- **Mode shapes** from associated Legendre functions on the sphere (the standard
  recurrence), not a decorative texture. The pale curves are the real nodal set.
- **Dispersion** from the mass-in-mass expression above, whose negative region
  opens a genuine stop band. *In plain terms: over one band of frequencies the
  wave cannot travel through the material at all, so no pattern forms there
  however hard you drive it.*
- **Discrete resonances**: response is weighted by how near the drive lands to an
  exact mode, so most of the dial does little.
- **The homogenisation limit is shown, not hidden**: once the wavelength falls
  below two cell widths, the "smooth material with an effective parameter" story
  stops being true and the readout says so in red.

Asserted, illustrative, or assumed — each load-bearing:

- **Every constant is stated, not measured.** No part exists.
- **Drive direction is simplified** to selecting a single azimuthal order `m`; a
  real drive excites a weighted mix.
- **Losses are ignored entirely.** In the EM version this is the sharpest of the
  omissions: loss is what decides whether a resonance can concentrate enough
  energy to reach a switching threshold, and it is exactly what the self-writing
  question turns on.
- **Every cell is assumed to latch at the same threshold.** Manufacturing spread
  is the single most likely thing to destroy the pattern.
- **The latch itself is asserted, not modelled.** Switched cells perturb their
  neighbours — thermally in the EM case — and that coupling is not simulated, so
  the frozen pattern shown is the optimistic case.

## Citations, and what the research pass has already corrected

A directed research pass has now run on the acoustic framing. Its findings are
in **`docs/acoustic-mode-imprinting-prior-art.md`**, and three of them change
what this prototype can claim.

**A citation this prototype got wrong.** Liu et al., *Locally Resonant Sonic
Materials*, Science 289, 1734 (2000) has been fetched and read in full. Its
measured sub-wavelength band gap is solid — a lattice constant roughly 300×
smaller than the wavelength. But the phrase "negative effective mass density"
**does not appear in it**; the paper attributes the effect to negative *elastic
constants*, and Ping Sheng's own HKUST page says of that paper that "the effect
was wrongly attributed to negative elastic constant, but this has been corrected
in the subsequent publications." The correct source for negative effective mass
is Liu, Chan & Sheng, *Phys. Rev. B* **71**, 014103 (2005). This matters rather
than being pedantry: the mechanism here is a heavy core on a soft spring moving
*out of phase* with the drive, which is precisely what negative effective mass
density names.

**Prior art is partial, and the gap is not where I expected.** Latching a
pattern remotely from a single boundary drive, and having it persist, is
demonstrated (Watkins et al., arXiv:2508.20321). Selecting a pattern by
frequency and then making it permanent is demonstrated in acoustic holography —
but by *curing the surrounding medium*, not by the structure latching itself.
What no retrieved source shows is the specific claim here: that the thing
selecting the pattern is a **standing-wave mode** of the structure. In every
system found, the selector is the input amplitude at one boundary, a hand press
on the chosen cell, or a hologram shaping the field. That is a directed-search
negative, not proof of absence.

**The load-bearing assumption is worse than unverified.** Nobody publishes the
cell-to-cell switching-threshold distribution for a multistable lattice. The
largest demonstrated system is **three cells**; the proposal needs thousands.
Where spread is reported it is of geometry and stiffness (≈5% on truss
stiffness), not threshold — and thresholds are usually staggered *deliberately*
so cells snap in a known order, the opposite of what a shared threshold needs.
Separately, *pseudo-bistability* is a documented failure mode in which a
viscoelastic snapped-through structure slowly creeps back, and nobody has
quantified it for lattices. *In plain terms: the machinery has only been shown
working three cells at a time, the number that decides whether it scales has
never been published, and such cells are known to un-snap themselves eventually
with nobody reporting how long "eventually" is.*

**The EM claims have now been checked too**
(`docs/non-volatile-metasurface-prior-art.md`). Phase-change latching, VO₂
volatility and the commercial maturity of latching RF switches all held up
against measured sources. Two things that did not survive contact are recorded
above: direct field self-writing is excluded by air breakdown and by the
material's own transparency, and the novelty class drops from *new mechanism* to
*new arrangement plus one new element*.

**The prize is now a measured number rather than an assertion.** A 3600-element
PIN-diode RIS draws 103.2 W in total, of which **15.73 W is static** — about
12.56 mW per cell spent purely on holding state. That static share is what a
latching surface deletes outright. It is also the same quantity
`docs/seven-example-design-unknowns.md` §6.3 already lists as a per-family human
input ("available bias supply and per-cell control wiring budget"), so this
connects to an existing open question rather than a new one.

**The one assumption still unmeasured is the one most likely to kill it:**
nobody publishes cell-to-cell switching-threshold spread, in either the acoustic
or the RF literature. The cheapest way to find out is small — *print 32 cells in
a row and DC-probe every one of their thresholds.* No sphere, no array, no
field. If that distribution is tight the idea has a path; if it is wide, it does
not.

Chladni and Lamb remain named from memory.

## Run

Open `imprinted_sphere_prototype.html` in a browser. No build step, no
dependencies, no network calls (web fonts degrade to system fallbacks offline).

Findings are reported back in the conversation that produced this prototype,
not in this file — this directory intentionally carries no separate findings
write-up so there is exactly one place that can go stale.
