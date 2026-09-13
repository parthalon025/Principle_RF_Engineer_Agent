# Computing static polarizability `γ` from aperture geometry

**Date:** 2026-09-13
**Ticket:** [#546](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/546); part of [#530](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/530). Context: [#482](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/482) (named the gap), [#547](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/547)/[PR #553](https://github.com/parthalon025/Principle_RF_Engineer_Agent/pull/553) (built the square-loop solve), [#552](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/552)/[PR #554](https://github.com/parthalon025/Principle_RF_Engineer_Agent/pull/554).
**Question:** What actually computes the static (DC) polarizability `γ` that `BANDPASS_FSS`'s physical bound needs — closed form, or a numerical electrostatic solve? Is there an open-source tool for it that fits this repo's dependency posture? And does the answer generalise across shapes, or must it be re-derived per shape family the way `physical_bound` itself must (ADR-0018)?

---

## Bottom line up front

**`γ` is one equation, not one-per-shape. Closed form exists only for the
ellipsoid family. Everything else — including a square — needs a numerical
electrostatic solve, and the method is the same numerical solve whatever the
shape. The open-source tool that does it off the shelf exists, computes
exactly the right quantity, and should not be adopted.**

| Sub-question | Answer |
|---|---|
| **Closed form, or numerical solve?** | **Closed form only for ellipsoids** (sphere, spheroid, circular and elliptic disks — §3.1, exact to machine precision). **A square plate has no closed form** — Mansfield et al., verbatim: *"the electrostatic properties of the square have been of interest, but also impossible to calculate exactly."* Everything else is one **numerical electrostatic solve** of a Laplace single-layer integral equation (§3.2). **Not** FDTD — not because FDTD is inaccurate but because there is no wave here to propagate. |
| **Is there an open-source tool?** | **Yes, one: `scuff-static`** (part of SCUFF-EM, GPL) — it takes `--ConstField` and returns `--PolFile`, handles open zero-thickness surfaces, and uses *the same* piecewise-constant-charge boundary-element method this repo already implements. **Recommendation: do not adopt it.** Its master branch last moved **2018-12-18** (confirmed twice, §4.1) and it carries an **open, un-replied-to bug report that `scuff-static` polarizability output differs by 7.8%–450% between two machines on identical inputs** (issue #247, opened 2024-09-30). Four other candidates fail on the wrong excitation, the wrong output, or the wrong geometry primitives. `bempp-cl` (MIT, maintained, pip-installable) is the right *library* if the in-house solver is ever replaced. |
| **Does it generalise across shapes?** | **Yes — and this is the opposite of ADR-0018's per-family finding.** Demonstrated, not asserted: the solver already in `rf_tools/aperture_polarizability.py`, with **nothing changed but the mesh**, reproduces the exact circular-disk value `16a³/3` to **0.14%** (§5.1) — a shape its own test file says its machinery "cannot represent." The physics, the kernel, the matrix and the output functional are shape-independent. What is per-shape is **meshing**, not derivation. |

**The one thing that would silently break, and nobody would catch it.** The
`γ` in `B ≤ γπΔ/(Aλ₀)` is the complementary PEC patch's in-plane electric
polarizability measured **along `k̂ × ê` — ninety degrees away from the
incident electric field**, not along it (§2.2, quoted from the source). For
`BANDPASS_FSS`'s square loop this is invisible, because a four-fold-symmetric
shape has the same polarizability in every in-plane direction. For a
horseshoe, a split ring, or any asymmetric letter the Element/Coding-Alphabet
library produces, picking the wrong one of the two in-plane directions
changes `γ` by a factor that is **not small** — §2.2 measures it at **8×** on
an elliptic disk of 4:1 aspect ratio and **36×** at 10:1, both exactly.
Nothing in the code checks this today,
and the bound would come back confident and wrong.

*In plain terms: the bound asks "how much electrical bulk does one cell's
worth of metal have when you sit it in a steady electric field?" For a square
the answer is the same whichever way you point the field, so the current code
gets away with never asking. For a lopsided shape it is not, and the right
direction to point is the surprising one — sideways to the radio wave's
electric field, not along it.*

---

## Symbols

| Symbol | Meaning | Units | Source of the definition |
|---|---|---|---|
| `γ` | Static (DC) polarizability entering the bound: the **electric** polarizability of a PEC patch shaped like the aperture's Babinet complement, resolved along `k̂ × ê`, **per unit cell of the periodic array** | m³ | Ludvig-Osipov et al. Eq. (5)–(6) |
| `γe`, `γm` | Electric / magnetic polarizability **tensors** of the complementary structure | m³ | Ludvig-Osipov et al., after Eq. (5) |
| `ê` | Unit vector along the incident electric field (in the screen plane) | — | Ludvig-Osipov et al. Eq. (5) |
| `k̂` | Propagation direction, `= ẑ`, normal to the screen | — | Ludvig-Osipov et al. Eq. (5) |
| `A` | Unit-cell area, `lx·ly` | m² | Ludvig-Osipov et al. Eq. (5) |
| `l` | Array period (square lattice, `lx = ly = l`) | m | Ludvig-Osipov et al. Fig. 2a |
| `B`, `Δ`, `λ₀` | Wavelength-domain fractional bandwidth; threshold factor `√(1−T₀²)/T₀`; passband centre wavelength | —, —, m | Ludvig-Osipov et al. Eqs. (8), (12) |
| `b`, `w` | Square loop's outer side and conducting strip width | m | `rf_tools/aperture_polarizability.py` |
| `a` | Disk radius, or patch outer size, depending on the source quoted | m | stated per use below |
| `σ` | Induced surface charge density on the conductor | C/m² (with `ε₀ = 1`) | §3.2 |
| `L_i` | Depolarization factor of an ellipsoid along axis `i`, `Σ L_i = 1` | — | §3.1 |

**Normalisation convention, stated once because it is the single easiest
place to lose a factor.** Throughout this document `γ` is in the **volume
convention**: `p = ε₀ γ E`, so a conducting sphere of radius `a` has
`γ = 4πa³ ≈ 12.566 a³`. This is the convention of Shahpari et al.'s Table 1
(sphere `12.56`), of Mansfield et al.'s Table IV (disk `5.333 = 16/3`), and
of `rf_tools/aperture_polarizability.py` (verified by running it, §5.1).
Kurennoy's 1996 convention is **one-sided** and is half of this — the
existing test file already handles that correction and this document does not
re-open it. `CALCULATED` (the convention identification is arithmetic on
three published anchors that agree).

---

## 1. What was read, and what was not

House rule (`CLAUDE.md`, "research is the referee"): a claim attributed to a
source must be something actually read and quotable.

| Source | Status |
|---|---|
| **Ludvig-Osipov et al. (2020)**, *IEEE TAP* 68(2):773–782, doi `10.1109/TAP.2019.2943430` | **READ IN FULL** — arXiv:1810.07669v3 author manuscript, text extracted from the PDF's own font-encoded text layer (not OCR). Sections II, V and the full reference list quoted below. Already read once for `docs/bandpass-fss-physical-bound-primary-source.md`; this pass re-read it for the polarizability-computation question specifically |
| **Sjöberg, D. (2008/2009)**, "Variational principles for the static electric and magnetic polarizability of anisotropic media with PEC inclusions," Lund TEAT-7175 / *J. Phys. A* **42**:335403 | **READ** — open technical-report PDF from `lup.lub.lu.se`. This is the source's own `[31]`, i.e. **the method Ludvig-Osipov et al. actually used**. Abstract, §5 (bounds) and §6 (numerical example) quoted |
| **Shahpari, M., Thiel, D. V. & Lewis, A. (2014)**, "Polarizability of 2D and 3D conducting objects using method of moments," arXiv:1402.3681 | **READ IN FULL** — open arXiv PDF. The only open-access, complete, reproducible recipe found for computing `γ` of an arbitrary conductor. Equations (1), (3)–(7), (11)–(15) and Table 1 quoted |
| **Mansfield, M. L., Douglas, J. F. & Garboczi, E. J. (2001)**, "Intrinsic viscosity and the electrical polarizability of arbitrarily shaped objects," *Phys. Rev. E* **64**:061401 | **READ IN FULL** — free NIST-hosted PDF (`tsapps.nist.gov`). Previously in this repo only as a single table value quoted second-hand in #547; now read first-hand, Table IV and §V-C transcribed |
| **SCUFF-EM documentation** (`scuff-static` application page, Geometries reference, TopLevel reference) | **READ** — quotes below taken from the rendered pages' own text, re-fetched and grepped rather than paraphrased |
| **SCUFF-EM repository state** | **READ** via two independent routes (GitHub commit listing; Software Heritage API snapshot `3cfaead…` → revision `9c6d0cb…`), which agree on `2018-12-18` |
| **ZENO 5.2.1 documentation** (NIST), `zeno.nist.gov` — Input, Validation, License pages | **READ** — input-primitive list read from the page's own HTML, not a summary |
| **bempp-cl** — PyPI metadata (version, licence, dependencies, release date) | **READ** from the PyPI JSON API directly |
| **Palace** `Electrostatic` problem type; **Elmer** `StatElecSolve` | **READ INDIRECTLY** — via documentation search results, not the primary docs pages (Palace's `config/problem` URL 404'd this pass, and `raw.githubusercontent.com` for its docs likewise). The claims drawn from them in §4.2 are **architectural**, not numerical, and are tagged accordingly |
| **De Meulenaere, F. & Van Bladel, J. (1983)**, "Computation of the magnetic polarizability of conducting disks and the electric polarizability of apertures," *IEEE TAP* 31(5), doi `10.1109/TAP.1983.1143122` | **STRANDED.** Unpaywall (queried 2026-09-13): `is_oa: false`, `oa_status: closed`, `has_repository_copy: false`, `oa_locations: []`. This is the canonical numerical treatment of exactly this quantity and would supply independent published values for non-square aperture shapes. → `RUNNING-LISTS.md` §1 |
| **Bethe, H. A. (1944)**, "Theory of diffraction by small holes," *Phys. Rev.* 66:163 | **NOT READ — and deliberately not relied on.** Bethe's theory is the *frequency-domain consequence* of these polarizabilities, not a way to compute them for a non-circular shape; nothing in §3–§5 needs it. Named here only so its absence is a decision, not an oversight |
| **Schiffer, M. M. & Szegő, G. (1948)**, "Virtual mass and polarization" — the source's `[34]`, the enclosing-object monotonicity result | **NOT READ this pass.** Already relied on (unread) by `rf_tools/aperture_polarizability.py`'s existing monotonicity test via the source's restatement of it; this document adds no new dependence on it |

---

## 2. What `γ` is, exactly

### 2.1 Per unit cell, of the complement, at DC

Ludvig-Osipov et al., §II, verbatim (their Eq. 5 and the sentences following
it; `ê` is the incident electric-field direction, `k̂ = ẑ` the propagation
direction):

> "`Tc(k) ∼ 1 + ikγ/(2A)` as `k → 0`, (5)
> where `γ = (ê · γe · ê + (k̂ × ê) · γm · (k̂ × ê))`, `k̂ = ẑ` is the wave
> propagation direction, `γe` and `γm` are the electric and the magnetic
> polarizability tensors of the complementary structure, respectively, and
> `A = lxly` is the area of the unit cell."

and then, verbatim:

> "Note that the polarizabilities used here are the polarizabilities for the
> complementary structure. Furthermore, for a planar PMC array and the
> electric field direction `ê` parallel to the array plane, the term
> `ê · γe · ê` vanishes, and thus we only need to calculate the magnetic
> polarizability. The magnetic polarizability of a PMC structure can be
> calculated as the electric polarizability of a PEC structure of the same
> shape, see e.g., [15], [16]."

Three facts follow, all `LITERATURE-SUPPORTED`:

1. **It is the complement's polarizability, not the aperture's.** Swap metal
   and hole; the patch you are left with is the object to solve.
2. **The chain collapses to one electrostatic problem.** Aperture → PMC
   complement → magnetic polarizability → electric polarizability of the
   *same-shaped PEC patch*. That last object is a flat piece of metal in a
   steady electric field, and nothing else.
3. **It is stated per unit cell of the array**, via `A` — not per isolated
   patch. Fig. 4's caption says its curves are for *"infinitely thin PEC
   periodic structures,"* so the paper's own plotted `γ/l³` already carries
   the array coupling. `rf_tools/aperture_polarizability.py` handles this
   with an explicit point-dipole lattice correction
   (`periodic_array_polarizability_correction_m3`), validated against that
   same Fig. 4; this document does not re-open it.

*In plain terms: you never solve for the hole. You solve for the piece of
metal shaped like the hole, sitting alone in a steady electric field, then add
back what its neighbours in the array do to it.*

### 2.2 The direction is `k̂ × ê` — sideways to the incident field

Read Eq. (5) again. The surviving term is `(k̂ × ê) · γm · (k̂ × ê)`. In the
plane of the screen, `k̂ × ê` is perpendicular to `ê`. So **the in-plane
direction along which `γ` is evaluated is rotated 90° from the incident
electric field.** The paper's own figure captions are consistent with this
mattering: Fig. 4 and Fig. 5 both say *"The external applied field for
polarizability calculation is directed vertically with respect to the unit
cells in the inset"* — the orientation is specified, because for their
horseshoe and split-ring cells it is not a free choice.

**Why this is load-bearing** (the charter's assumption / cost / cheapest-test
triad):

- **Assumed today:** that the patch's in-plane polarizability is isotropic,
  so direction need not be tracked. `rf_tools/aperture_polarizability.py`
  computes only `α_xx` (`_solve_alpha_xx`), and its test suite *asserts*
  in-plane isotropy as a property. For a square loop that assertion is
  correct — four-fold symmetry forces the in-plane tensor to be a multiple of
  the identity.
- **Costs if wrong:** the factor is not a rounding error. Evaluating the
  exact elliptic-disk polarizability (§3.1) at semi-axis ratio `b/a = 0.25`
  gives `2.271 a³` along the long axis and `0.274 a³` along the short one — a
  ratio of **8.3×**; at `b/a = 0.10` it is `1.548` against `0.0424`, a ratio
  of **36×**. `CALCULATED`. A horseshoe or split ring is nothing like that
  extreme, but it is nothing like isotropic either, and `γ` enters the bound
  linearly: a 2× error in `γ` is a 2× error in the permitted bandwidth,
  straight into a feasibility verdict.
- **Cheapest way to find out, per shape:** run the same solve twice, once per
  in-plane axis, and compare. Two solves instead of one, seconds of compute.
  There is no excuse for not doing it, and no way to detect the omission
  after the fact.

**This is a labelling and interface finding, not a defect in what exists.**
`square_loop_polarizability_m3` is correct for its shape. The finding is that
the function's *name and signature* carry no direction, so the first
asymmetric letter added to this module will inherit a silent assumption.
Provenance: `LITERATURE-SUPPORTED` (Eq. 5 and the figure captions) +
`CALCULATED` (the elliptic-disk ratios) + `INFERRED` (the judgement that the
current interface would not catch it).

---

## 3. Sub-question 1: closed form, or numerical solve?

### 3.1 Closed form exists, and only for ellipsoids

For a conducting ellipsoid with semi-axes `a₁, a₂, a₃` the polarizability
along each axis is exact:

```
    γ_i = V / L_i ,        V = (4π/3) a₁ a₂ a₃

    L_i = (a₁a₂a₃ / 2) ∫₀^∞  ds / [ (s + a_i²) · sqrt((s+a₁²)(s+a₂²)(s+a₃²)) ] ,   Σ_i L_i = 1
```

`L_i` is the standard depolarization factor; for a general ellipsoid it is an
elliptic integral, which is "closed form" in the sense that matters here —
one quadrature, machine precision, no mesh, no convergence study.

**Verified rather than quoted.** Evaluating the integral numerically:
`CALCULATED`

| Case | This quadrature | Independent value |
|---|---|---|
| Sphere, `γ/a³` | `12.566371` | `4π = 12.566371` (exact) |
| `Σ L_i`, sphere | `1.000000000` | `1` (exact, by construction) |
| Circular disk (`a₃ = c → 0`), `γ_xx/a³` | `5.333333` at `c/a = 10⁻⁴` and below | **`16/3 = 5.333333`** — Mansfield et al., verbatim: *"The polarizability component in the plane of the disc is known to be `(αe)xx = 16r³/3` [43], while the normal component is zero. Our estimate is `(αe)xx = [1.0000(3)](16r³/3)`."* |

The circular-disk row is the one that matters: it is a **zero-thickness flat
conductor** — the exact geometry class `BANDPASS_FSS` needs — reached as a
limit of the ellipsoid formula, and it lands on a published exact value that
an independent Monte-Carlo method confirms to 3 parts in 10⁴. That pins the
formula, the convention, and the `c → 0` limit all at once.

The elliptic disk (`a₁ = a`, `a₂ = b`, `a₃ → 0`) is therefore also exact:
`CALCULATED`

| `b/a` | `γ/a³` along the long axis | `γ/a³` along the short axis |
|---|---|---|
| 1.00 | 5.33333 | 5.33333 |
| 0.80 | 4.53291 | 3.24292 |
| 0.50 | 3.32282 | 1.16887 |
| 0.25 | 2.27138 | 0.27355 |
| 0.10 | 1.54756 | 0.04236 |

**And that is the end of the closed forms.** A square plate — the simplest
shape this programme actually prints — has none. Mansfield et al., verbatim:

> "Like the cube, the electrostatic properties of the square have been of
> interest, but also **impossible to calculate exactly**, with a number of
> calculations of increasing sophistication."

Their Table IV makes the same point in the table itself: for regular `n`-gons
with `n = 3…8` the "exact values" column reads `N.A.` in every row, and only
the `n = ∞` (circular disk) row carries one, `16/3 = 5.3333 (Ex)`. The square
(`n = 4`) entry is a *numerical* value, `(αe)xx/r³ = 2.943(1)`, with `r` the
centre-to-vertex distance. `LITERATURE-SUPPORTED`

Converting to the side length `b = r√2`: `γ/b³ = 2.943 / 2√2 = 1.04086 ±
0.00035`. `CALCULATED`. **Running `rf_tools/aperture_polarizability.py`'s own
solid-plate limit returns `1.03994`** — low by **0.088%**, inside the
converted uncertainty's neighbourhood and well inside any tolerance that
matters for a bound. `CALCULATED` (executed this pass).

> *Noted in passing, not fixed (out of this ticket's scope and another
> ticket's file):* `tests/test_aperture_polarizability.py`'s docstring records
> this conversion as `1.0405 ± 0.0004`. `2.943 / (2√2)` is `1.04086`, not
> `1.0405`. The discrepancy is 0.03%, the test's own tolerance straddles both,
> and the test asserts against the unconverted `2.943` constant rather than
> against the prose figure — so nothing is wrong in the code. It is a
> transcription slip in a comment, recorded here so the next reader of that
> docstring is not puzzled.

### 3.2 Everything else is one numerical electrostatic solve — the same one

Shahpari, Thiel & Lewis state the general position in their abstract,
verbatim:

> "**Polarizability is not available in closed form for most antenna shapes
> and no commercial electromagnetic packages have this facility.**"

and in their introduction, verbatim:

> "Popular commercial packages for antenna modelling, for example, Ansys
> Hfss, Feko, Awr, Ie3d, etc do not calculate the polarizability."

The solve is a **Laplace single-layer integral equation** for the induced
surface charge, and it is three lines. Their Eq. (1) and Eq. (3), verbatim in
substance:

```
    x_j + C_j  =  ∫_S  ρ_j(x') / (4π |x − x'|)  dS'          (1)   — find the charge that flattens the potential
    γ_ij       =  ∫_S  x_i ρ_j(x) dS                          (3)   — integrate charge × position for the dipole
```

with pulse (piecewise-constant) basis and testing functions on a triangular
mesh, `L_mn = (1/4π) ∫∫ 1/|x−x'|` for the matrix, an exact closed form for
the singular diagonal (their Eq. 7), and `C_j` a single extra unknown
enforcing total charge zero on a floating conductor, given by their Eq. (14):

```
    C_j = − Σ(L⁻¹u) / Σ(L⁻¹A) ,      u_m = x_jm A_m
```

about which they say, verbatim: *"As far as authors know, there is no
published literature which describes how to calculate `C_j` in general."*
(This matters in §5.2.)

**This is exactly — not approximately — the method already in
`rf_tools/aperture_polarizability.py`.** That module's docstring describes
"sub-domain collocation boundary-element method … cells of unknown uniform
charge density … solve for the charge density that makes the total potential
constant … integrate charge times position for the induced dipole moment."
Same equation, same basis, same output functional; rectangular cells with an
exact rectangle kernel instead of triangles with an exact triangle kernel.
`CALCULATED` (a reading of two sources side by side, not a new result).

**Why FDTD is the wrong tool, stated properly.** `physical_bounds.py`'s
docstring already says `simulation/meep.py` is "the wrong tool," and the
reason is stronger than "inefficient": at `k = 0` there is no wave. The
governing equations are `∇×E = 0`, `∇·D = 0` — Laplace, elliptic, solved in
one shot. A time-stepping Maxwell solver has nothing to time-step; you would
be driving a structure at a frequency low enough that the simulation domain
is a vanishing fraction of a wavelength, which is precisely the regime FDTD
is worst in. `INFERRED` from the physics, corroborated by the fact that every
source in §1 that computes `γ` uses an electrostatic method and none uses a
time-domain one.

### 3.3 How the primary source itself did it — and the error bar it bought

Ludvig-Osipov et al., §V, verbatim, the sentence that settles what the paper's
own route was:

> "**The evaluation of static polarizabilities was performed via a variational
> approach [31] in COMSOL Multiphysics electrostatic solver.**"

Their `[31]` is Sjöberg's variational-principles paper. Read first-hand, its
abstract, verbatim:

> "We derive four variational principles for the electric and magnetic
> polarizabilities for a structure consisting of anisotropic media with
> perfect electric conductor inclusions. From these principles we derive
> monotonicity results and upper and lower bounds on the electric and magnetic
> polarizabilities. **When computing the polarizabilities numerically, the
> bounds can be used as error bounds.**"

and §5, verbatim:

> "Using for instance the finite element method (FEM) for solving the field
> equations, we can compute each functional and consider the numerical
> potentials as trial fields. Each set of numerical potentials … can then be
> inserted in the inequalities (5.1) and (5.2), which **provides a strict
> error bound for the numerical computation of the polarizabilities**."

The inequalities themselves (his 5.1, for the electric case):

```
    −Ke(F, D₀)  ≤  ε₀ E₀ · γe E₀  ≤  Je(φ, E₀)
```

— two *complementary* functionals that bracket the true `γ` from below and
above, each computable from an approximate numerical potential. Refine the
mesh and the bracket tightens; the gap between them **is** the error bar, with
no extrapolation and no assumed convergence order.

**This is the one genuinely missing capability in what this repo has**, and it
is worth naming precisely. `square_loop_polarizability_m3`'s own docstring
says: *"No closed-form error bar exists for an arbitrary `w_m/b_m`."* Sjöberg
shows that is not a fact about the problem — it is a fact about the *method
chosen*. A complementary-variational pair gives a rigorous two-sided bound on
`γ`; the repo's collocation BEM gives a single number plus two empirical
sanity checks (a literature anchor at one shape, a two-resolution stability
test at another). `LITERATURE-SUPPORTED` (Sjöberg) + `INFERRED` (the judgement
that it applies to this repo's solver).

Sjöberg's own §6 worked example, verbatim, is also the cautionary note: *"The
calculations are made with the commercial software Comsol Multiphysics 3.4,"*
and his conclusion from it — *"With the simple procedure of only refining the
discretization, we conclude that we cannot expect more than about three digits
accuracy using this program."* **Three digits, from a commercial FEM package,
on a sphere.** The repo's BEM matches a published square-plate value to four
digits (§3.1). That is not a claim that this repo's solver is better than
COMSOL; it is a measurement of how much accuracy this problem actually needs
and how cheaply it is available.

---

## 4. Sub-question 2: is there an open-source tool, and does it fit?

### 4.1 `scuff-static` — the only direct hit, and a recommendation against it

`scuff-static` is part of SCUFF-EM. Its documentation, verbatim from the
TopLevel reference: *"An electrostatic solver. Available outputs include:
self- and mutual-capacitances of arbitrarily-shaped conductors; **DC
polarizabilities of conducting and dielectric bodies**; electrostatic
fields."*

Everything needed is there and in the right shape:

| Requirement | `scuff-static` |
|---|---|
| Uniform applied field as the excitation | `--ConstField Ex Ey Ez` — verbatim from the docs |
| Polarizability as a first-class output | `--PolFile MyPolFile.dat`: *"scuff-static will compute the DC polarizability of each object in your geometry and write the data to the specified file"* |
| Zero-thickness open surfaces (a flat patch is not a closed body) | Supported. Geometries reference, verbatim: *"Each surface is a mesh describing a closed **or open** 2D surface represented as a union of flat triangular panels."* |
| Method | The same one as this repo's. Verbatim: *"scuff-static expands surface electric charge densities on PEC and dielectric surfaces using ``pulse'' basis functions, which are constant on individual triangles and vanishing everywhere else."* |
| Mesh input | gmsh `.msh` — and gmsh is **already installed in this repo's Docker image** and already shelled out to by `simulation/elmer.py` |
| Licence | GPL — compatible with this repo's posture, which already treats GPLv3 binaries (openEMS, NEC2++, OpenParEM, gprMax) as the default path, invoked as subprocesses |
| Integration shape | CLI + mesh files — the same subprocess-adapter pattern as every existing `simulation/*.py` |

On paper it is an excellent fit. **Two facts say do not adopt it:**

1. **The code has not moved in almost eight years.** Master tip is commit
   `9c6d0cb7695463af803dee8d04cdae939740cdcc`, dated **2018-12-18**
   ("Merge pull request #183 from WenjieYao/appendenvfix"). Confirmed by two
   independent routes that agree: the GitHub commit listing, and the Software
   Heritage archive API (snapshot `3cfaead1de981afb974095014b6dff5d7211afab`,
   latest visit 2024-04-05, `refs/heads/master` → that revision).
   `LITERATURE-SUPPORTED` (read from the project's own repository, twice, via
   independent archives).
2. **There is an open, unanswered report of non-reproducible polarizability
   output from this exact tool.** SCUFF-EM issue #247, *"Inconsistent
   Polarizability Results on Different Machines Using `scuff-static`"*, opened
   **2024-09-30**: identical `.scuffgeo` and `.msh` inputs, identical
   installations, verified binary checksums, parallelisation disabled — and
   polarizability components differing between two machines from ~1% to
   ~450%, with the first component reported as `1.890611e+05` versus
   `2.037505e+05` (7.8%). **No maintainer reply; still open.**

*In plain terms: the one ready-made program that computes exactly the number
we need has been unmaintained since 2018, and somebody has publicly reported
that it gives different answers on different computers for the same input, and
nobody has answered them.*

For a programme whose charter states plainly that **nobody with RF expertise
reviews the output**, taking a load-bearing feasibility number from an
abandoned code with an open, un-triaged numerical-reproducibility defect is a
worse position than the ~430-line in-house solver that already exists,
reproduces two published values, and can be read end to end. Provenance of the
recommendation: `INFERRED` — a judgement, from `LITERATURE-SUPPORTED` facts
about the repository's state and issue tracker.

**Where `scuff-static` is still worth using:** as a one-off, out-of-band
cross-check on a single shape, run by a human, compared against the in-house
solver. Its triangular mesh handles curved and diagonal boundaries that the
rectangle kernel staircases (§5.1), so a disagreement would be informative —
and the reproducibility bug above is itself a reason to run it twice.

### 4.2 Every other candidate, and exactly where each fails

| Candidate | Licence / posture | Verdict |
|---|---|---|
| **ZENO 5.2.1** (NIST, `usnistgov/ZENO`) | NIST public-service terms: *"This software was developed by employees of the National Institute of Standards and Technology … Works created by NIST employees are not subject to U.S. copyright protection,"* free use/modify/redistribute. **More permissive than GPL** | **Computes the right quantity, cannot express the right geometry.** It lists *"capacitance, **electric polarizability tensor**, intrinsic conductivity, volume, …"* as outputs, by Walk-on-Spheres Monte Carlo — and it is the **descendant of the very code that produced this repo's square-plate validation anchor** (Mansfield et al. used "the Zeno algorithm"). But the distributed input format's only primitives are `SPHERE`, `CUBOID`, `CUBE`, `VOXELS` and `TRAJECTORY` (read directly off `zeno.nist.gov/Input.html`): **no triangle, no polygon, no zero-thickness plate.** Its own validation page lists eight cases, all solids or sphere-unions, and **no flat object at all** — so the flat-polygon path Mansfield et al. used in 2001 is not in today's public input language. A flat patch would have to be a thin cuboid with a thickness→0 extrapolation, which is exactly the slow limit. Monte Carlo also gives a statistical, not deterministic, answer — `CALCULATED` provenance for a `γ` that differs run to run needs its own argument |
| **`bempp-cl`** (`bempp/bempp-cl`) | **MIT.** v0.4.2, last release **2025-04-01**, `pip install bempp-cl`, dependencies `numpy, numba, meshio, scipy` — no OpenCL required, no system binary. The lightest dependency footprint of anything here | **The right answer if the in-house solver is ever replaced — but it is a library, not a tool.** It assembles the Laplace single-layer operator (`bempp_cl.api.operators.boundary.laplace.single_layer`) on a triangulated surface, including open screens, with proper singular quadrature. It does **not** compute polarizability: you still write the right-hand side (`φ = E₀·x` on the conductor), the charge-neutrality constraint, and the dipole-moment functional — §3.2's three lines. That is roughly thirty lines of glue, and what it buys over today's rectangle kernel is arbitrary triangulated boundaries at second order. **Recommended target if #546's machinery is ever generalised to curved letters** |
| **Palace** `Problem.Type = "Electrostatic"` (already wired: `simulation/palace.py`) | Apache-2.0, already on this repo's path | **Wrong excitation and wrong output.** It is terminal-driven: each `Terminal` boundary is held at unit voltage with others grounded, and it writes a Maxwell capacitance matrix (`terminal-C.csv`). A polarizability needs a **floating** conductor in a **uniform applied field**, which is neither a terminal nor a ground. Reachable in principle by post-processing a custom potential solve, not reachable by configuration. Note also `simulation/palace.py` emits only `"Driven"` today. `INFERRED` (read via documentation search, not the primary config reference — see §1) |
| **Elmer** `StatElecSolve` (already wired: `simulation/elmer.py`) | LGPL core / GPL modules, already on this repo's path; `simulation/elmer.py` already drives gmsh → ElmerGrid → ElmerSolver | **Closest of the already-wired solvers, still not it.** It solves the right PDE and even has an open-domain facility (`Electric Infinity BC = True`), but its packaged output is again a capacitance matrix from voltage-driven boundaries. Getting `γ` means writing a custom `.sif` with a non-standard excitation plus custom post-processing of the dipole moment — i.e. implementing §3.2 inside Elmer rather than in Python, with a FEM volume mesh instead of a BEM surface mesh. **This is, however, the natural host for Sjöberg's complementary variational bounds** (§3.3), which are FEM-shaped. `INFERRED`, same caveat as Palace |
| **FastCap / FasterCap** | FastCap: MIT-era academic terms; FasterCap: LGPL | **Capacitance only.** Same single-layer operator, no polarizability output and no uniform-field excitation. Strictly worse than `bempp-cl` for this purpose, because you cannot get at the matrix |
| **COMSOL Multiphysics** | **Commercial.** | **What the primary source used** (§3.3) **and therefore the most tempting answer.** It fails ADR-0012's posture test directly: that ADR's settled position is that "the free/OSS stack … becomes the complete, explicit default path end to end, with **no paid-tool step required** to reach it." Making `γ` — an input to a feasibility verdict the loop issues — depend on a licensed FEM package would put a paid tool back on the required path for a core output. (The ticket cites "ADR-0012/0013"; precisely, **ADR-0012** is the paid-EDA decision, and ADR-0013 is its measurement-side consequence, which is not implicated here.) |
| **openEMS / MEEP / gprMax** (all already wired) | GPL-family, already on the path | **Wrong physics**, §3.2. Time-domain Maxwell solvers at `k → 0`. |

**Conclusion on sub-question 2.** An open-source tool that computes this
exists (`scuff-static`) and should be used only as a manual cross-check, not
as a dependency. An open-source *library* that makes a better in-house solver
easy exists (`bempp-cl`, MIT, maintained, pip-installable). The solve itself
is small enough — §3.2 is three equations — that **writing it in this repo was
the right call, and keeping it is the right call.** That is what #547 already
did, with two published anchors, before this research pass existed; this
document is the justification it did not yet have.

---

## 5. Sub-question 3: does it generalise, or is it per-shape?

### 5.1 Decisive experiment: the existing machinery already does a different shape family

`tests/test_aperture_polarizability.py` states, in a comment, that the
production module's rectangle-kernel machinery *"cannot represent a curved
boundary"* — and for that reason its circular-annulus cross-check is built as
a **separate 1-D solver living only in the test file**.

That claim is too strong, and the difference matters for this ticket. The
rectangle-cell machinery can represent a curved boundary by staircasing it.
Reusing `rf_tools.aperture_polarizability`'s own internals
(`_graded_nodes_1d`, `_rect_potential_matrix`, `_solve_alpha_xx`) **unchanged**,
and changing **only the mesh** to a quarter-disk of radius `a` with each
column's height set to the exact circle: `CALCULATED` (executed this pass)

| Cells across radius | Cells in quarter | `γ/a³` | Error vs exact `16/3` |
|---|---|---|---|
| 20 | 256 | 5.30605 | −0.512% |
| 30 | 576 | 5.31740 | −0.299% |
| 40 | 1023 | 5.32208 | −0.211% |
| 56 | 1998 | 5.32576 | **−0.142%** |
| Richardson (`1/n`), from the last two | — | 5.33496 | +0.030% |

Monotone convergence from below (a staircase inscribes less conductor than the
true rim, so under-prediction is the *expected* direction, not a surprise),
landing on the published exact value to 0.03% after one extrapolation.
Observed convergence order, from successive error ratios: **1.33, 1.21, 1.18**
— i.e. roughly first order, against the second order the module documents for
the square. That gap is the whole cost of the staircase: **the boundary
representation, not the physics, sets the convergence rate.**

*In plain terms: the solver that was written for square loops already gets a
circle right to about one part in a thousand, with nothing changed but which
little rectangles you hand it. It is slower to converge on a curve than on a
straight edge, and that is the only penalty.*

### 5.2 What is shape-independent, and what is genuinely per-shape

| Component | Shape-independent? |
|---|---|
| The physics (`∇×E = 0`, `∇·D = 0`) | **Yes** — one PDE, every shape |
| The integral equation (§3.2, Eq. 1) and its kernel `1/(4π\|x−x'\|)` | **Yes** — the kernel knows nothing about the shape |
| The output functional `γ_ij = ∫ x_i ρ_j dS` | **Yes** |
| The units and normalisation convention | **Yes** |
| **The mesh, and the grading toward singular edges** | **No — this is the per-shape work.** Every edge of a flat conductor carries a `1/√distance` charge singularity; a mesh that does not grade into it converges badly |
| **The symmetry reduction** | **No, and this one is a trap.** `_solve_alpha_xx` solves one *quarter* and mirrors it with `sign_x=-1, sign_y=+1`. That is valid only for a shape with **both** in-plane mirror planes. A horseshoe has one; a general coding-alphabet letter has none |
| **Charge neutrality on a floating conductor** | **No.** The quarter-domain antisymmetry makes total charge zero *automatically* — the module's docstring says so explicitly. Drop the symmetry and you must add the constraint back: the `C_j` unknown of §3.2, Shahpari et al. Eq. (14) |
| **The direction `k̂ × ê`** | **No** — §2.2 |

So the minimal extension to an arbitrary planar letter is four concrete
things, none of them a re-derivation:

1. A mesh generator for the new outline (the only genuinely per-shape code),
   graded into every edge.
2. A full-domain path for shapes with less than four-fold symmetry — the
   existing `_rect_potential_matrix` already takes `sign_x`/`sign_y`, so a
   half-domain is already expressible; a no-symmetry shape needs the full
   mesh.
3. The floating-potential unknown `C_j` for that full-domain path, which
   Shahpari et al. Eq. (14) supplies in closed form — worth noting because
   those authors say in print that *"there is no published literature which
   describes how to calculate `C_j` in general,"* so this is the recipe, not
   one of several.
4. Both in-plane components, with the bound told which one to use.

Triangular cells (via `bempp-cl`, §4.2) would replace item 1 with a general
mesher and lift the convergence order back to second on curved boundaries. At
that point the per-shape work reduces to *an outline polygon* and nothing
else.

### 5.3 Why this is the opposite of ADR-0018, and that is not a contradiction

ADR-0018 made `physical_bound` a per-family function on a specific argument,
recorded in `rf_tools/physical_bounds.py`'s own docstring: the three bounds
"take different inputs …, return different quantities …, and rest on different
physics." All three tests fail for `γ`:

| ADR-0018's test | `physical_bound` | `γ` |
|---|---|---|
| Different inputs per family? | Yes — a thickness and a band; a reference simulation; a polarizability and an area | **No** — a planar region, every time |
| Different returned quantity? | Yes — metres; a dimensionless Q; m³ or a bandwidth | **No** — m³, every time |
| Different physics? | Yes — a causality integral; a stored-energy ratio; a Herglotz sum rule | **No** — Laplace's equation, every time |

So the registry seam that ADR-0018 put at the *family* level does not belong
at the shape level here. The right seam is **one shape-agnostic solver plus
per-shape mesh generators** — which is exactly what #547's own
Implementation Decisions already asked for ("The boundary-element solver
internals … stay internal to the module, not part of its public interface, so
a future shape can reuse the machinery") and what `rf_tools/aperture_polarizability.py`'s
docstring already delivers. **This document is evidence that decision was
right, not a proposal to change it.** `INFERRED` (a structural judgement, from
the three `LITERATURE-SUPPORTED`/`CALCULATED` rows above).

---

## 6. Every route tried

**Succeeded:**

| Route | Result |
|---|---|
| arXiv:1810.07669v3 PDF → `pymupdf` text layer | **The decisive sentence.** *"The evaluation of static polarizabilities was performed via a variational approach [31] in COMSOL Multiphysics electrostatic solver."* Plus Eq. (5)'s `k̂ × ê` direction and the Fig. 4/5 captions |
| Reference list of the same PDF | Identified `[31]` Sjöberg (the method), `[34]` Schiffer & Szegő (monotonicity), `[30]` Kleinman & Senior (the low-frequency asymptotics) |
| `lup.lub.lu.se` → TEAT-7175 PDF → `pymupdf` | Sjöberg's complementary variational bounds read first-hand, including the "three digits from COMSOL" remark |
| arXiv:1402.3681 PDF → `pymupdf` | Complete, open, reproducible MoM recipe for `γ` of an arbitrary conductor, including the `C_j` closed form and the "no commercial package does this" statement. **The single most useful open-access source found** |
| `tsapps.nist.gov` free PDF of Mansfield et al. (2001) | `16r³/3` confirmed as the published exact disk value; the square confirmed as having **no** exact value; Table IV transcribed |
| Running `rf_tools/aperture_polarizability.py` directly | Solid-plate `γ/b³ = 1.03994`, −0.088% against the converted Mansfield figure; convention confirmed |
| Reusing that module's internals on a quarter-**disk** mesh | **§5.1's decisive generalisation result**: exact `16/3` recovered to 0.142%, first-order convergence, Richardson to 0.030% |
| Numerical quadrature of the ellipsoid depolarization integral | Sphere `4π` and disk `16/3` both recovered exactly; elliptic-disk table and the 8.3×/36× anisotropy ratios of §2.2 |
| SCUFF-EM docs, re-fetched and grepped rather than summarised | `--ConstField`, `--PolFile`, open-surface support, and the "pulse basis functions on individual triangles" formulation, all verbatim |
| Software Heritage API (`/origin/.../visit/latest`, `/snapshot/`, `/revision/`) | **Independent confirmation** of SCUFF-EM's 2018-12-18 master tip when GitHub's API was unreachable — a route worth remembering |
| `zeno.nist.gov/Input.html`, read as raw HTML | ZENO's primitive list: `SPHERE`, `CUBOID`, `CUBE`, `VOXELS`, `TRAJECTORY` — **no flat primitive**. A negative result that a summary would have missed |
| PyPI JSON API for `bempp-cl` | MIT, v0.4.2, 2025-04-01, `numpy/numba/meshio/scipy` only |
| Crossref + Unpaywall on the Van Bladel 1983 paper | DOI pinned, and positively confirmed closed with no repository copy |

**Failed, and why:**

| Route | Outcome |
|---|---|
| `api.github.com` for SCUFF-EM repository metadata | **HTTP 403 from this session's agent proxy** — "GitHub access to this repository is not enabled for this session." Not a fact about SCUFF-EM. Software Heritage substituted cleanly; **reach for it first next time** rather than scraping GitHub HTML (which also returned nothing) |
| `awslabs.github.io/palace/stable/config/problem/` and `raw.githubusercontent.com/awslabs/palace/main/docs/src/guide/problem.md` | **Both HTTP 404** this pass. Palace's `Electrostatic` behaviour in §4.2 therefore rests on documentation *search results*, not the primary page — tagged `INFERRED`, and the claim drawn from it is architectural rather than numerical. Re-check against the primary docs before anyone builds on it |
| Elmer `StatElecSolve` primary documentation | Not reached directly either; same treatment and same caveat as Palace |
| **De Meulenaere & Van Bladel (1983)**, *IEEE TAP* 31(5) | **Closed access, no repository copy anywhere.** Unpaywall: `is_oa: false`, `has_repository_copy: false`, `oa_locations: []`. This is a claim about the world, not about fetching. → `RUNNING-LISTS.md` §1 |
| Generic web search for an elliptic-disk closed form | Returned scattering papers and elliptic-integral tables, never a clean citable polarizability expression. **Abandoned in favour of deriving it from the ellipsoid depolarization integral and anchoring the derivation on the published circular-disk value** — which is stronger evidence than a formula copied from a search snippet would have been |
| WebFetch's own summariser on the two research PDFs | **Returned wrong numbers** on the first attempt — it reported a conducting sphere's polarizability as `(3/2)πa³` and a disk's as `(8/3)πa³`, neither of which is in the paper. Both PDFs had to be downloaded and text-extracted locally. **Do not trust a small-model summary for a number that will be cited**; extract the text |

---

## 7. Provenance summary

| Claim | Provenance |
|---|---|
| `γ` is the complementary PEC patch's electric polarizability, per unit cell, at DC | `LITERATURE-SUPPORTED` — Ludvig-Osipov et al. Eq. (5)–(6), quoted verbatim |
| `γ` is evaluated along `k̂ × ê`, 90° from the incident E field | `LITERATURE-SUPPORTED` — Eq. (5), plus the Fig. 4/5 captions |
| The primary source computed `γ` with a variational approach in COMSOL | `LITERATURE-SUPPORTED` — verbatim, §V |
| Sjöberg's complementary functionals give a strict two-sided error bound on a numerical `γ` | `LITERATURE-SUPPORTED` — read first-hand, abstract and §5 quoted |
| Ellipsoid `γ_i = V/L_i`; sphere `4πa³`; circular disk `16a³/3`; normal component zero | `LITERATURE-SUPPORTED` (Mansfield et al. quote `16r³/3` and attribute it) + `CALCULATED` (quadrature reproduces `4π` and `16/3` to 7 digits) |
| Elliptic-disk table, and the 8.3× / 36× in-plane anisotropy ratios | `CALCULATED` — quadrature of the depolarization integral, anchored on the disk limit |
| A square plate has no closed form | `LITERATURE-SUPPORTED` — Mansfield et al. verbatim, plus the `N.A.` exact-value column of their Table IV |
| Mansfield Table IV `n=4`: `2.943(1)` at centre-to-vertex `r`; `= 1.04086 ± 0.00035` per side³ | `LITERATURE-SUPPORTED` (the table value) + `CALCULATED` (the `2√2` conversion) |
| `square_loop_polarizability_m3(1.0, 0.5) = 1.03994`, −0.088% against that | `CALCULATED` — executed this pass |
| The general method is a Laplace single-layer integral equation with pulse basis and a `C_j` neutrality unknown | `LITERATURE-SUPPORTED` — Shahpari et al. Eqs. (1), (3)–(7), (11)–(15), read in full |
| No commercial antenna package computes polarizability | `LITERATURE-SUPPORTED` — Shahpari et al., verbatim, abstract and §1. **Dated 2014**; treat as a statement about that era, not a verified 2026 survey |
| FDTD is the wrong tool because `k → 0` has no wave | `INFERRED` from the physics; corroborated by every source in §1 using an electrostatic method |
| `scuff-static` computes DC polarizability, takes `--ConstField`, supports open surfaces, uses pulse basis on triangles, GPL | `LITERATURE-SUPPORTED` — its own documentation, re-fetched and grepped verbatim |
| SCUFF-EM master tip is `9c6d0cb…`, 2018-12-18 | `LITERATURE-SUPPORTED` — the project's own repository, via two independent archives that agree |
| SCUFF-EM issue #247: `scuff-static` polarizability differs 7.8%–450% between machines; open, no maintainer reply, opened 2024-09-30 | `LITERATURE-SUPPORTED` — read from the issue itself |
| **Recommendation not to adopt `scuff-static` as a dependency** | `INFERRED` — a judgement built on the two rows above and `CLAUDE.md`'s "nobody with RF expertise reviews the output" |
| ZENO computes a polarizability tensor but its distributed input format has no flat/zero-thickness primitive; NIST public-service licence | `LITERATURE-SUPPORTED` — `zeno.nist.gov` Input, Validation and License pages, read as raw HTML |
| `bempp-cl`: MIT, v0.4.2, 2025-04-01, `numpy/numba/meshio/scipy`, Laplace single-layer on open screens | `LITERATURE-SUPPORTED` — PyPI JSON API and the project's own documentation |
| Palace `Electrostatic` and Elmer `StatElecSolve` are terminal/voltage-driven capacitance solvers, so the excitation is wrong | `INFERRED` — read via documentation search, **not** the primary docs pages (§1, §6) |
| COMSOL fails ADR-0012's posture test | `LITERATURE-SUPPORTED` — ADR-0012's own words, quoted |
| **The disk reproduction through the existing machinery**: `5.32576` at 1998 cells, −0.142%, order ≈1.2, Richardson +0.030% | `CALCULATED` — executed this pass, against a `LITERATURE-SUPPORTED` exact value |
| `γ` generalises across shapes; the per-shape work is meshing, symmetry reduction, the `C_j` unknown and the field direction | `CALCULATED` (the disk experiment) + `INFERRED` (the four-item extension list, read off the existing code) |
| `γ` fails all three of ADR-0018's per-family tests | `INFERRED` — a structural comparison against ADR-0018's own stated criteria |
| De Meulenaere & Van Bladel (1983) is closed with no repository copy | `LITERATURE-SUPPORTED` — Unpaywall, queried 2026-09-13 |

---

## 8. What this changes, and what it does not

**Nothing in this document requires a code change to be true, and it proposes
none.** `rf_tools/aperture_polarizability.py` already implements the right
method, for the one shape `BANDPASS_FSS` actually proposes, anchored on two
published values. What was missing was the *justification* — whether a
cheaper closed form existed (only for ellipsoids), whether an off-the-shelf
tool should have been used instead (one exists; it should not), and whether
the next shape needs a new derivation (it does not).

**Three things a future ticket should pick up, named precisely rather than
fixed here:**

1. **The `k̂ × ê` direction is not represented in the interface** (§2.2). The
   first asymmetric letter added to `rf_tools/aperture_polarizability.py`
   inherits a silent four-fold-symmetry assumption. Cheapest fix: return both
   in-plane components, or take the direction as an argument. This is a
   labelling gap, not a wrong number — today's square-loop result is correct.
2. **There is no rigorous error bar on `γ`, and Sjöberg shows there could be**
   (§3.3). The module's own docstring calls this a fact about the problem; it
   is a fact about the method. A complementary-variational pair brackets `γ`
   from both sides with no assumed convergence order. Elmer
   (`simulation/elmer.py`, already built) is the natural host.
3. **Curved and diagonal boundaries cost an order of convergence** with
   rectangular cells (§5.1: order ≈1.2 instead of ≈2). `bempp-cl` (MIT,
   maintained, `pip`-installable, §4.2) would fix that and reduce per-shape
   work to an outline polygon. Worth doing **when**, not before, a curved
   letter is actually wanted.

**For `RUNNING-LISTS.md` §1** (not edited by this document — another session
maintains that file):

> **De Meulenaere, F. & Van Bladel, J. (1983)**, "Computation of the magnetic
> polarizability of conducting disks and the electric polarizability of
> apertures," *IEEE Trans. Antennas Propag.* **31**(5), doi
> `10.1109/TAP.1983.1143122` — Closed access; **Unpaywall confirms
> `is_oa: false`, `has_repository_copy: false`, `oa_locations: []`** (queried
> 2026-09-13), i.e. no free copy exists rather than a fetch that failed. The
> canonical numerical treatment of exactly the quantity `BANDPASS_FSS`'s
> bound needs, and the most likely published source of independent `γ` values
> for **non-square** aperture shapes (circular loop, annulus, ellipse) to
> validate any future shape added to `rf_tools/aperture_polarizability.py`
> against. A library login closes it. Bears on #546, #547.

**Correction to the ticket's own cross-reference, recorded for the next
reader:** #546's body cites "ADR-0052" for the `bound`-kind infeasibility
verdict resolving #532. In the tree today that decision is
**ADR-0054**, *"An infeasibility verdict is advisory, never terminal, and
comes in two kinds: bound and exhaustion"*; ADR-0052 is *"Volume-to-wire is a
modelling decision, not a translation."* The ticket also attributes the
paid-EDA exclusion to "ADR-0012/0013"; it is **ADR-0012**.

**Closes:** #546, all three sub-questions.
(1) **A numerical electrostatic solve is required** for anything outside the
ellipsoid family — including a square — and that solve is a Laplace
single-layer integral equation, identical in form whatever the shape; closed
forms exist for the sphere, spheroid and circular/elliptic disk and are
tabulated in §3.1. (2) **One open-source tool computes it directly —
`scuff-static` — and this document recommends against depending on it**
(unmaintained since 2018-12-18; open, unanswered report of 7.8%–450%
machine-to-machine disagreement in that exact output), with four other
candidates failing on excitation, output or geometry primitives, and
`bempp-cl` named as the right library if the in-house solver is ever
replaced. (3) **It generalises** — demonstrated by reproducing the exact
circular-disk value to 0.14% through the existing machinery with nothing
changed but the mesh — and the per-shape work is meshing, symmetry reduction,
a charge-neutrality unknown and the field direction, **not** a re-derivation;
`γ` fails all three of ADR-0018's per-family tests, so unlike `physical_bound`
it is correctly one function, not one per family.

**Not closed, and not claimed:** whether any *specific* non-square letter's
`γ` is right. That needs a mesh for that letter and, for an asymmetric one,
the three additions in §5.2. And the PEC assumption behind `γ` is untouched
here — a printed conductor is not a perfect one, and
`docs/bandpass-fss-physical-bound-primary-source.md` §4.2 remains the honest
statement of that gap.
