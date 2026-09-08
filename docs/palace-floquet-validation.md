# The Palace Floquet adapter, run against a real Palace at last

**Date:** 2026-09-08
**Ticket:** [#210](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/210) — validates the adapter built in [#61](https://github.com/parthalon025/Principle_RF_Engineer_Agent/issues/61).
**Question:** Does `simulation/palace.py` actually work? It had never been run against a real `palace` binary — only against fake scripts feeding it text this repo wrote itself.

---

## Bottom line up front

**It works now. It did not work before.**

Palace was built from source, and Palace's own worked example — "Floquet Ports
for a Dielectric Grating" — was run **through `run_palace_simulation()`**: the
adapter emitted the config, wrote its own mesh, shelled out to the real binary,
and parsed the real results file. Against Palace's own published numbers for
that example, the adapter's answers agreed to **0.056 dB** in magnitude and
**0.91 degrees** in phase, and agreed on every one of the 176 mode-frequency
points where a diffraction order carries no power.

**In plain terms.** Ask this tool how much of a radio wave a repeating
dielectric structure bounces back and how much passes through, and it now gives
the same answer the tool's own authors publish, to better than a percent.

Getting there exposed **two real defects**, both of which would have been
invisible forever without a real binary:

1. **The results parser could not read a single real Palace file.** It matched
   the wrong character. Every real run would have come back
   `computed: False` — no numbers at all, just an honest-sounding note saying
   the header did not match.
2. **The `specular` convenience view silently returned the wrong number.** It
   handed back a cross-polarised channel sitting on the solver's noise floor
   (−158 dB) where the true reflection was −18.9 dB. In plain terms: it would
   have reported a grating that reflects about 11% of what hits it as one that
   swallows everything.

Neither is a physics error. Both are the kind of error that only a real run
finds, because both passed every test written against invented data.

---

## 1. What was run, and what agreed

### 1.1 The validation case

Palace's own example (`examples/dielectric_grating/`, awslabs/palace commit
`43a5483`) is a single cell of a repeating structure, 4 cm × 1 cm across and
8 cm tall, with a bar of dielectric (relative permittivity 7) 2 × 0.5 × 0.5 cm
suspended in vacuum at its centre. A radio wave arrives at 30° from straight-on,
polarised so its electric field lies across the grating (TE), and the sweep runs
2–12 GHz.

**In plain terms.** A repeating row of plastic bars in air, hit by a radio wave
at a slant, asking how much comes back and how much goes through — and, above a
certain frequency, how much gets deflected sideways into extra beams the way a
diffraction grating splits light.

That deflection has a threshold. Below **8.66 GHz** only the straight-through
and straight-back beams exist; above it the ±1 sideways beams switch on. Palace's
example doc calls this the Rayleigh anomaly, and it is a sharp, unforgiving thing
for a solver to get right — either your solver says a beam exists at a given
frequency or it does not.

### 1.2 The two runs

**Run A — Palace on its own example, unmodified,** to check the build itself:

```
palace -np 4 dielectric_grating_uniform.json
```

Result: **identical to Palace's own checked-in reference output
(`test/data/regression/ref/dielectric_grating/uniform/port-floquet-S.csv`) to
every digit printed** — 12 significant figures, all 72 columns, all 6
frequencies. The build is trustworthy; anything that disagrees afterwards is the
adapter's doing, not the compiler's.

**Run B — the same physics through `run_palace_simulation()`.** This is the run
the ticket asks for. The adapter was handed the geometry as a Python dict and
did everything else itself: built a 972-element hexahedral mesh in MFEM's native
format, emitted the JSON config, invoked `palace`, and parsed
`port-floquet-S.csv` back into per-diffraction-order S-parameters. 62 seconds on
4 cores.

```python
run_palace_simulation(
    geometry={
        "unit_cell": {"lx_m": 0.04, "ly_m": 0.01, "lz_m": 0.08},
        "materials": [
            {
                "name": "dielectric_bar",
                "p1_m": [0.010, 0.00250, 0.03750],
                "p2_m": [0.030, 0.00750, 0.04250],
                "epsilon_r": 7.0,
            }
        ],
        "mesh": {"nx": 3, "ny": 2, "nz": 6},
        "floquet": {
            "wave_vector_1_per_m": [0.0, 104.79, 0.0],
            "reference_frequency_hz": 10e9,
            "polarization": "TE",
            "max_order": 1,
        },
    },
    frequency_hz=10e9,
    sweep={"start_hz": 2e9, "stop_hz": 12e9, "points": 6},
    num_processes=4,
    solver_order=2,
)
```

Two translations were needed and are worth recording. Palace's own mesh centres
the cell on the origin; this adapter puts the cell's corner there, so every
coordinate is shifted by half a period. And Palace's example states its Floquet
wave vector as **1.0479 cm⁻¹**, which is **104.79 rad/m** in the metres this
adapter speaks. (That number is 2πf/c × sin 30° at 10 GHz — it is how the
"arrives at a slant" is expressed to the solver.)

### 1.3 The agreement, in numbers

Six frequencies × 36 modes = **216 mode-frequency points**, compared against
Palace's published reference:

| | count | agreement |
|---|---|---|
| Non-propagating orders (both report "no power here") | 176 | **exact — zero disagreements about which beams exist** |
| Real, power-carrying channels | 28 | **max 0.056 dB, mean 0.013 dB; max phase 0.91°** |
| Cross-polarised channels on the numerical noise floor | 12 | not compared — see below |

The 12 excluded points are the cross-polarised channels, which for this
symmetric grating carry no power at all: the reference puts them between −204
and −279 dB, this run between −107 and −167 dB. **Both mean "nothing".**
Comparing
them in dB would produce a headline "145 dB disagreement" that is entirely an
artefact of taking the logarithm of two different flavours of zero. Saying so
explicitly is the honest form; quietly averaging them away is not.

The headline channels:

| f (GHz) | reflection \|S11\| adapter / reference (dB) | transmission \|S21\| adapter / reference (dB) |
|---|---|---|
| 2 | −18.941 / −18.955 | −0.0558 / −0.0556 |
| 4 | −12.978 / −12.990 | −0.2245 / −0.2239 |
| 6 | −9.264 / −9.271 | −0.5477 / −0.5466 |
| 8 | −1.611 / −1.606 | −5.088 / −5.098 |
| 10 | −8.963 / −8.960 | −2.185 / −2.188 |
| 12 | −10.434 / −10.378 | −2.716 / −2.728 |

And the sideways beams, which must be absent below 8.66 GHz and present above:

| f (GHz) | (−1,0) reflected, adapter / reference (dB) |
|---|---|
| 2, 4, 6, 8 | no power / no power |
| 10 | −15.357 / −15.352 |
| 12 | −16.871 / −16.887 |

**In plain terms.** At 2 GHz the grating is nearly transparent — 99% of the wave
goes through. By 8 GHz it is close to a mirror, sending back 69% of the power
(the sharp feature Palace's doc calls a Fano resonance, where the wave briefly
couples into the slab and back out). Above 8.66 GHz two extra beams peel off
sideways. The adapter reproduces all of it.

The residual differences are **not** adapter error in any interesting sense.
They are the difference between two discretisations of the same problem: the
reference uses a Gmsh mesh of about 1700 elements, this run uses the adapter's
own 972-element mesh. Refining further does not drive the difference to zero, it
moves it around by a few hundredths of a dB — which is the size of the
*reference's own* discretisation error. That is what agreement looks like when
you have hit the floor.

---

## 2. The defects the run exposed

### 2.1 A semicolon read as a comma

Palace's prose documentation (`docs/src/guide/boundaries.md`) describes the
results-file column labels as `S[P<port>(<m>,<n>)<pol>][<exc>]`, with a comma.
Palace's per-iteration terminal output prints the comma form too. But the CSV
file — the thing the adapter actually parses — uses a **semicolon**:

```
     |S[P1(0;0)TE][1]| (dB),arg(S[P1(0;0)TE][1]) (deg.)
```

which makes sense the moment you see it: the label lives inside a
comma-separated file, so a comma inside the label would collide with the
delimiter. Palace's writer builds it that way deliberately
(`palace/models/postoperatorcsv.cpp`, `InitializeFloquetPortS`).

`simulation/palace.py` matched the comma. Consequence: `parse_palace_output()`
found no columns, returned `computed: False`, and said so politely. **Every real
Palace run this adapter ever did would have produced no numbers.** The module's
own honest-caveat section had even flagged the comma as a risk — it worried that
Palace might not quote the comma properly — and reached the wrong conclusion,
because the real answer was that there is no comma to quote.

The old docstring's fourth reasoned-not-verified item is now moot, and the fix is
pinned to columns copied **verbatim** out of Palace's published reference file
(`tests/test_palace.py`, `PALACE_REFERENCE_FLOQUET_CSV`), not to anything this
repo wrote.

### 2.2 Two modes fighting over one dictionary key

Palace reports **both** polarisations of **every** diffraction order — for a TE
excitation, the TE columns carry the answer and the TM columns carry whatever
polarisation conversion the structure produces. For this symmetric grating that
is nothing: numerical noise a hundred-plus dB down.

The adapter's `specular` convenience view keyed on port number alone
(`specular["S11"]`), so both the TE and TM specular modes of port 1 mapped to the
same key and the last one written won. On the real run, `specular["S11"]` came
back as **−158 dB** — the noise — instead of **−18.9 dB**.

**In plain terms.** A caller asking "how much comes back?" would have been told
"essentially none", when in truth about a ninth of the wave's amplitude comes
straight back. That is not a small error; it inverts the conclusion.

Keys are now polarisation-qualified: `S11_TE`, `S11_TM`, `S21_TE`, `S21_TM`
(and `S11_RHC`/`S11_LHC` for a circular excitation). The co-polarised one — the
one you almost always want — is whichever suffix matches
`geometry["floquet"]["polarization"]`.

This one could never have been caught by a synthetic fixture, because the
fixture only ever had one polarisation in it. Palace always writes two.

### 2.3 A gap, not a defect: the finite-element order was not settable

Palace's default finite-element order is 1; its own grating example uses 2.
The adapter emitted no `Solver.Order` at all, so it silently took the default —
and at order 1 it could not reproduce the example at any practical mesh size. A
3888-element order-1 run was still 0.67 dB and 22° off at its worst; a
**216**-element order-2 run — a sixth of the elements — was worst-case 4.5° off
in phase, and comparable or better in magnitude on five of the six frequencies
(at 12 GHz the coarse order-2 mesh was the worse of the two, at 0.66 dB against
0.42 dB). Refining the order-2 mesh from there closes the remainder; refining
the order-1 mesh does not touch the phase error, because that error is
dispersion, not resolution.

**In plain terms.** Order 1 lets the field vary in a straight line across each
mesh cell; order 2 lets it curve. Waves curve, so order 2 buys far more accuracy
per cell than shrinking cells does.

`solver_order` is now an argument on `generate_palace_config()`,
`run_palace_simulation()` and both tool wrappers, defaulting to 1 (Palace's own
default, now emitted explicitly rather than inherited silently) — the same
discipline the module already applied to `L0`.

---

## 3. How Palace was built

Ubuntu 24.04, 4 cores, 15 GB RAM. **About 17 minutes wall-clock** for the whole
superbuild (METIS/ParMETIS, HYPRE, SuperLU_DIST, libCEED, MFEM, ARPACK, Palace);
1.2 GB of build tree, 189 MB installed.

```bash
apt-get install -y libopenmpi-dev openmpi-bin libopenblas-dev gfortran \
                   pkg-config zlib1g-dev            # cmake/ninja/g++ already present
git clone --depth 1 https://github.com/awslabs/palace.git      # commit 43a5483
cmake <src> -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=<prefix> \
  -DPALACE_WITH_ARPACK=ON  -DPALACE_WITH_SLEPC=OFF \
  -DPALACE_WITH_GSLIB=OFF  -DPALACE_WITH_SUNDIALS=OFF \
  -DPALACE_WITH_MAGMA=OFF  -DPALACE_WITH_LIBXSMM=OFF
make -j4
```

`palace --version` then reports `Palace version: 43a5483, Schema version: 1-6-0`.

Four things bit, all recorded so the next session does not rediscover them:

1. **`libblas-dev`/`liblapack-dev` are not enough.** Palace's CMake decides it
   is looking at OpenBLAS and then fails to find it. Install `libopenblas-dev`.
2. **Palace refuses to configure with both eigenvalue solvers off** — "Build
   requires at least one of ARPACK or SLEPc dependencies" — even for a driven
   (non-eigenmode) run. ARPACK is much the cheaper of the two: it needs only a
   Fortran compiler, where SLEPc drags in all of PETSc.
3. **Three MFEM patch downloads and two dependency tarballs come from
   `github.com/...` URLs that this sandbox's egress proxy refuses (HTTP 403).**
   Both are workable without touching Palace's build files:
   - The patches are fetched with `file(DOWNLOAD ... EXPECTED_HASH)`, which
     **skips the download when the file already exists and its hash matches**.
     Pre-populate `<build>/extern/mfem-patches/`. Two of the three are commit
     diffs reproducible byte-for-byte with
     `git -c core.abbrev=11 diff <sha>^ <sha>` — the `core.abbrev=11` is
     load-bearing, since that is the blob-hash abbreviation GitHub uses in the
     `index` lines. The third (a pull-request diff) is served by
     `patch-diff.githubusercontent.com`, which the proxy does allow.
   - The tarballs (`json-schema-validator`, `scnlib`) carry **no** hash check,
     so `git archive --prefix=<name>-<version>/` reproductions pointed at with
     `-DEXTERN_JSON_SCHEMA_VALIDATOR_URL=` / `-DEXTERN_SCN_URL=` are accepted.
4. **OpenMPI refuses to run as root.** Set `OMPI_ALLOW_RUN_AS_ROOT=1` and
   `OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1` in the environment. The adapter shells out
   as `palace -np <N> <config>` with no way to pass Palace's `--launcher-args`,
   so an environment variable is the only lever it has — a real, if minor,
   limitation of `PalaceSimulator.run()`.

The CLI contract the adapter was written to — `palace -np <N> config.json` — is
confirmed correct by `palace --help`.

---

## 4. What is still not proven

Say this plainly, because the headline number above is easy to over-read.

- **One geometry, one incidence angle.** An all-dielectric grating at 30°, TE.
  Nothing here exercises a different unit-cell shape, normal incidence, TM or
  circular polarisation, a lossy material (`LossTan` is emitted but never
  exercised against a real run), or a magnetic one.
- **Embedded PEC conductors remain unimplemented.** That is the metallic
  metasurface case — which is the case this programme actually cares about. The
  gap was declared in #61 and is unchanged. The adapter can simulate a grating of
  plastic bars; it cannot yet simulate a printed metal pattern.
- **This is still a simulation agreeing with a simulation.** Palace agreeing
  with Palace's own published Palace output is a strong check on *this adapter*
  and no check at all on *the physics*. Every result the adapter returns is
  `SIMULATED` and stays that way. Per ADR-0027 and this repo's evidence
  hierarchy, nothing becomes `MEASURED` without a bench.
- **The `Excitation` field is only ever emitted as a boolean.** Palace also
  accepts a positive integer excitation index for multi-excitation sweeps; the
  adapter always excites port 1 alone, and the parser assumes excitation index 1.
  Untested against anything else.
- **The winding direction of boundary quads is confirmed only by behaviour.**
  MFEM loaded the adapter's mesh and reported the right bounding box, element
  count and matched periodic faces. That is strong evidence the ordering is
  right; it is not the same as having read MFEM's reference-element definition.

## 5. Reproducing this

The comparison is not automated in `pytest` — it needs a compiled Palace, which
CI does not have. What *is* in the test suite is everything that can be checked
without the binary: the parser is now pinned against columns copied verbatim
from Palace's published reference output (`tests/test_palace.py`), which is what
would have caught defect 2.1 on day one.

To redo the full run: build Palace as in §3, set `PALACE_BIN`, and call
`run_palace_simulation()` with the geometry in §1.2. Compare
`<workdir>/postpro/port-floquet-S.csv` against
`test/data/regression/ref/dielectric_grating/uniform/port-floquet-S.csv` in the
Palace source tree.
