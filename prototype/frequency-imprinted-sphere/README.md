# Frequency-imprinted sphere prototype (THROWAWAY)

Answers one design question, raised in conversation and **not yet filed as an
issue**: does the chain *drive frequency → wavelength → spherical mode →
latched pattern* hang together well enough to be worth taking further?

The idea under test is acoustic, not electromagnetic: a spherical shell of
graded mechanical resonators, driven at a chosen frequency so that a
standing-wave mode forms, with bistable ("click-to-stay") cells latching that
mode shape so it survives after the drive stops. *In plain terms: cymatics —
sand hopping into patterns on a vibrating plate — except on a sphere, and with
the sand staying put once the sound is switched off.*

**Scope is undecided.** This repo is an electromagnetic metasurface program;
this prototype is not. Whether the idea belongs here at all, belongs here only
as an analogy, or belongs in a sibling repo is exactly the open question, and
it is settled by a `/grill-with-docs` pass, not by this directory. Nothing here
should be read as a decision that it is in scope.

**This is a throwaway prototype, not production code.** It is not wired into
anything, nothing imports it, and no module in this repo reads it.

## What is really computed vs. what is asserted

Really computed, and correct as far as it goes:

- **Mode shapes** are evaluated from associated Legendre functions on the
  sphere (the standard recurrence), not drawn as a decorative texture. The pale
  curves are the real nodal set of the mode — *the places the shell is not
  moving, where sand would collect.*
- **Dispersion** is the textbook mass-in-mass locally-resonant result:
  `m_eff/m₁ = 1 + θ·ω₀²/(ω₀² − ω²)`, which goes negative just above the
  resonators' own frequency and opens a stop band. *In plain terms: over one
  band of frequencies the wave cannot travel through the material at all, so no
  pattern can form there however hard you drive it.*
- **Discrete resonances**: response is weighted by how near the drive lands to
  an exact mode, so most of the dial does little. A real shell only rings at
  particular frequencies.
- **The homogenisation limit is shown, not hidden**: once the wavelength falls
  below two cell widths the "smooth material with an effective speed" story
  stops being true, and the readout says so in red rather than quietly
  continuing to draw.

Asserted, illustrative, or assumed — each one load-bearing:

- **Every constant is stated, not measured**: 120 mm shell, 120 m/s baseline
  wave speed, 1200 Hz cell resonance, 0.6 mass ratio, 12 mm pitch. Chosen to be
  plausible and to give a legible range. No part exists.
- **Drive direction is simplified** to selecting a single azimuthal order `m`
  (pole → m=0, oblique → m≈ℓ/2, equator → m=ℓ). A real shaker excites a
  weighted mix, which would smear the picture.
- **Losses are ignored entirely.** Damping is what decides whether the drive can
  ever reach the latch threshold; if it cannot, the whole idea fails and this
  prototype would not show it.
- **Every cell is assumed to latch at the same threshold.** Manufacturing spread
  is the single most likely thing to destroy the pattern in practice.
- **The latch itself is asserted, not modelled.** Cells that snap push on their
  neighbours; this prototype does not simulate that coupling, so the frozen
  pattern it draws is the live one thresholded, which is the optimistic case.

## Citations

Sources named on the rendered page — Chladni (1787), Lamb (1882), and Liu et
al., *Locally Resonant Sonic Materials*, Science 289, 1734 (2000) — were
**named from memory and not fetched**. Treat them as leads to verify, not as
evidence already checked. A research pass against primary sources is what
should replace this paragraph.

## Run

Open `imprinted_sphere_prototype.html` in a browser. No build step, no
dependencies, no network calls (web fonts degrade to system fallbacks offline).

Findings are reported back in the conversation that produced this prototype,
not in this file — this directory intentionally carries no separate findings
write-up so there is exactly one place that can go stale.
