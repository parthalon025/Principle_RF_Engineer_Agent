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

## The fork that decides what kind of novelty this is

In the charter's own three-way vocabulary:

- **The incident field writes the pattern itself** → a genuinely **new
  mechanism**. Established at optical frequencies (a rewritable optical disc is
  literally a beam writing a retained phase pattern into a chalcogenide film),
  but the field strength needed to heat a cell past its switching threshold gets
  much harder to reach as frequency falls.
- **Cells written electrically, then holding with no power** → a **new
  arrangement** of known parts. Less novel, more likely to survive a bench.

Which one this is has not been established. A research pass against primary
sources is running specifically to settle it.

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

**Still unverified:** Chladni and Lamb remain named from memory, and the EM
claims above — GST non-volatility, VO₂ and BST volatility, optical writing of
phase-change films, and the cost of a bias network — are stated from background
knowledge. A second research pass is running on those.

## Run

Open `imprinted_sphere_prototype.html` in a browser. No build step, no
dependencies, no network calls (web fonts degrade to system fallbacks offline).

Findings are reported back in the conversation that produced this prototype,
not in this file — this directory intentionally carries no separate findings
write-up so there is exactly one place that can go stale.
