import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

from .base import SimulationResult, Simulator, SimulatorError


class GprmaxSimulator(Simulator):
    name = "gprMax"

    def __init__(self, python_executable: str | None = None):
        self.python_executable = python_executable or os.getenv("GPRMAX_PYTHON", sys.executable)

    def run(self, job: dict) -> SimulationResult:
        input_file = Path(job["input_file"]).resolve()
        workdir = Path(job.get("workdir", input_file.parent)).resolve()
        if not input_file.exists():
            raise SimulatorError(f"Input file not found: {input_file}")

        # gprMax has no standalone console-script executable at all -- its own
        # setup.py defines no console_scripts entry_points (see module
        # docstring citation) -- so unlike Nec2ppSimulator/OpenemsSimulator
        # (which shell out to a single named binary), this adapter always
        # shells out through *some* Python interpreter running gprMax as a
        # module: "python -m gprMax <input_file> [options]", gprMax's own
        # documented CLI contract. `-n` (repeat-run count) is deliberately
        # never passed -- it defaults to gprMax's own default of 1, matching
        # this adapter's single-run S-parameter/impedance scope, not a
        # B-scan sweep (see module docstring SCOPE).
        extra_args = job.get("extra_args", [])
        timeout_s = int(job.get("timeout_s", 3600))
        try:
            completed = subprocess.run(
                [self.python_executable, "-m", "gprMax", str(input_file), *extra_args],
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise SimulatorError(f"gprMax timed out after {timeout_s}s: {exc}") from exc
        if completed.returncode != 0:
            raise SimulatorError(
                f"gprMax failed ({completed.returncode}): {completed.stderr[-4000:]}"
            )

        # gprMax's structured results live entirely in the HDF5 .out file it
        # writes next to the input file (see module docstring citation for
        # the exact naming convention) -- unlike NEC2++'s stdout, gprMax's
        # console text is just a tqdm progress bar plus timing/banner lines,
        # nothing this module's parser reads, so (like openEMS's adapter)
        # it is kept only tail-truncated, for diagnostics.
        return SimulationResult(
            simulator=self.name,
            status="COMPLETED",
            workdir=workdir,
            outputs={"stdout": completed.stdout[-8000:]},
        )


# ---------------------------------------------------------------------------
# gprMax .in deck generation, execution, and .out (HDF5) result parsing
# (issue #63: ground-coupled / lossy-half-space EM simulation).
#
# WHAT THIS ADAPTER IS FOR: NEC2++ (simulation/nec2pp.py) only offers three
# ground models -- free space, an idealized perfect ground plane, or a
# single-parameter Sommerfeld/Norton finite-ground approximation (its own
# #GN card, see nec2pp.py's module docstring). None of those represent a
# real lossy, possibly-layered dielectric half-space (soil, concrete, a
# vehicle hull, human tissue) that a near-ground, ground-coupled, or
# embedded antenna actually couples into. gprMax is a full 3-D FDTD solver
# whose entire reason for existing is modelling exactly that kind of lossy
# half-space (it is Ground Penetrating Radar simulation software), so this
# adapter gives the agent a real volumetric-lossy-medium option that
# NEC2++ cannot provide and that openEMS's own adapter (simulation/
# openems.py) does not currently expose either (its `materials` primitives
# model finite dielectric/conductor bodies, not an explicit ground
# half-space workflow).
#
# SOURCES CONSULTED (primary; all fetched directly from the upstream
# gprMax/gprMax GitHub repository and its docs.gprmax.com-published Sphinx
# sources during implementation of this pass -- per-fact citations below):
#   - Installation method and invocation ("python -m gprMax path_to/
#     name_of_input_file"), and that gprMax has no console-script
#     executable: README.rst and setup.py,
#     github.com/gprMax/gprMax/blob/master/{README.rst,setup.py} (`master`
#     branch, fetched directly).
#   - CLI/Python-API entry point -- `api(inputfile, n=1, task=None,
#     restart=None, mpi=False, mpi_no_spawn=False, mpicomm=None, gpu=None,
#     benchmark=False, geometry_only=False, geometry_fixed=False,
#     write_processed=False, opt_taguchi=False)` ("If installed as a module
#     this is the entry point.") and the `main()` argparse flag set (-n,
#     -task, -restart, -mpi, --mpi-no-spawn, -gpu, -benchmark,
#     --geometry-only, --geometry-fixed, --write-processed,
#     --opt-taguchi): gprMax/gprMax.py, github.com/gprMax/gprMax/blob/
#     master/gprMax/gprMax.py.
#   - Input-file (.in) command syntax used by generate_gprmax_input() below
#     -- #domain, #dx_dy_dz, #time_window (float seconds OR integer
#     iterations), #material (epsr, conductivity S/m, mu_r, magnetic loss
#     Ohm/m, identifier), #box/#cylinder/#edge/#plate (corner/axis points
#     in metres, material identifier, #box's optional trailing y/n
#     dielectric-smoothing flag), #waveform (type, amplitude, centre
#     frequency Hz, identifier -- gaussian/gaussiandot/.../ricker/sine/
#     contsine types), #hertzian_dipole / #voltage_source /
#     #transmission_line (polarisation, x/y/z metres, [resistance for the
#     latter two], waveform identifier, optional start-delay/removal-time
#     seconds), #rx (x/y/z metres, optional identifier, optional
#     space-separated field-component list from Ex/Ey/Ez/Hx/Hy/Hz/Ix/Iy/
#     Iz), #pml_cells (one count for all sides, or six individually),
#     #num_threads, #title, #soil_peplinski (sand/clay fraction, bulk
#     density, sand-particle density, water-fraction range, identifier --
#     see SCOPE below for why this adapter does not use it): docs/source/
#     input.rst, github.com/gprMax/gprMax/blob/master/docs/source/
#     input.rst.
#   - #add_dispersion_debye / #add_dispersion_lorentz / #add_dispersion_drude
#     (issue #277) -- each attaches frequency-dependent behaviour to an
#     ALREADY-declared #material of the same identifier (never a
#     replacement for #material, a separate command layered on top), with
#     the #material's own epsilon_r field re-purposed as the
#     relative-permittivity-at-infinite-frequency for that pole set. Exact
#     syntax, verified by fetching docs/source/input.rst directly (same
#     URL as above) rather than reproduced from docs/tools/gprmax.md's own
#     research pass (which explicitly declined to guess this):
#       #add_dispersion_debye:   i1 f1 f2 f3 f4 ... str1
#         i1 = pole count; each pole is a (delta_epsilon_r, tau_s) pair,
#         delta_epsilon_r = zero-frequency epsilon_r minus the #material's
#         epsilon_r (i.e. epsilon_r at infinite frequency), tau_s = pole
#         relaxation time in seconds; str1 = material identifier.
#       #add_dispersion_lorentz: i1 f1 f2 f3 f4 f5 f6 ... str1
#         each pole is a (delta_epsilon_r, omega_hz, delta_hz) triplet,
#         omega_hz = pole frequency (Hz), delta_hz = damping coefficient
#         (Hz).
#       #add_dispersion_drude:   i1 f1 f2 f3 f4 ... str1
#         each pole is an (omega_hz, gamma_hz) pair, omega_hz = pole
#         frequency (Hz), gamma_hz = inverse relaxation time (Hz).
#     Worked example reproduced verbatim from that same page ("#material: 4.9
#     0 1 0 my_water" / "#add_dispersion_debye: 1 75.2 9.231e-12 my_water"
#     for a single-pole Debye water model, epsilon_r_infinity=4.9,
#     delta_epsilon_r=80.1-4.9=75.2, tau=9.231e-12s) is reproduced as a
#     regression test in tests/test_gprmax.py.
#   - Built-in reserved material identifiers "pec" (perfect electric
#     conductor) and "free_space" (air, never declared via #material) --
#     same input.rst.
#   - #transmission_line's characteristic-resistance bound ("any value
#     greater than zero and less than the impedance of free space (376.73
#     Ohms)"), enforced in generate_gprmax_input() below: same input.rst.
#   - Object-construction ordering -- later #box/#cylinder/#edge/#plate
#     commands overwrite earlier ones' material at any overlapping cell
#     ("layered canvas" -- gprMax's own FAQ wording), which is why
#     generate_gprmax_input() below always emits the half-space ground
#     material before the caller's own materials/conductors, so the
#     antenna's own geometry correctly overrides the ground fill where
#     they overlap: docs/source/faqs.rst, github.com/gprMax/gprMax/blob/
#     master/docs/source/faqs.rst.
#   - Output file naming ("gprMax produces an output file that has the
#     same name as the input file but with .out appended" -- i.e.
#     "model.in" -> "model.in.out", not extension-replacement) and the
#     HDF5 structure read by parse_gprmax_output() below -- root attributes
#     `dt`/`Iterations`/`nx_ny_nz`/`dx_dy_dz`/etc, per-receiver groups
#     `/rxs/rxN/` (attributes Name/Position; datasets Ex/Ey/Ez/Hx/Hy/Hz/
#     Ix/Iy/Iz, one per requested #rx field component), and per-
#     transmission-line groups `/tls/tlN/` (attributes Position/
#     Resistance/dl; datasets Vinc/Iinc/Vtotal/Itotal) -- both numbered by
#     declaration order, N starting at 1: docs/source/output.rst,
#     github.com/gprMax/gprMax/blob/master/docs/source/output.rst.
#   - S-parameter (S11) and input-impedance extraction formula --
#     Vref = Vtotal - Vinc; s11 = fft(Vref) / fft(Vinc); zin =
#     (fft(Vtotal) * delaycorrection) / fft(Itotal) with
#     delaycorrection = exp(1j*2*pi*freqs*(dt/2)) (the half-timestep
#     correction for the FDTD Yee grid's V/I staggering) -- this is
#     gprMax's OWN official post-processing tool for exactly this
#     #transmission_line-fed antenna use case, not an independently
#     invented formula: tools/plot_antenna_params.py, github.com/gprMax/
#     gprMax/blob/master/tools/plot_antenna_params.py. This module's
#     _compute_s_and_z_from_tl() below reproduces that same ratio (via
#     numpy.fft.rfft/rfftfreq rather than gprMax's own full
#     fft/fftfreq, for the same "only ever used as a ratio, so the
#     unscaled-transform convention cancels" reasoning already established
#     in simulation/openems.py's own S-parameter extraction -- see that
#     module's docstring for the fuller version of this argument).
#   - Antenna-feed worked example (a centre-fed dipole, Z_in=73 Ohm
#     #transmission_line, 1GHz Gaussian waveform, 60ns time window "to
#     give ... a reasonable resolution (17MHz) for calculating antenna
#     parameters that involve taking a FFT") that this module's `port`
#     shape and #transmission_line usage is modelled on: docs/source/
#     examples_antennas.rst, github.com/gprMax/gprMax/blob/master/docs/
#     source/examples_antennas.rst.
#   - Commercial-antenna-proxy confirmation for gprMax's bundled antenna
#     library -- `antenna_like_GSSI_1500(x, y, z, resolution=0.001,
#     rotate90=False)` / `antenna_like_GSSI_400(...)`, "Inserts a
#     description of an antenna similar to the GSSI 1.5GHz antenna" /
#     "...GSSI 400MHz antenna", modelling GSSI (Geophysical Survey Systems,
#     Inc.) commercial GPR antenna housings (170x108x45mm / 300x300x178mm
#     external dimensions) -- and separately licensed under Creative
#     Commons Attribution-ShareAlike 4.0 International, NOT gprMax's own
#     GPLv3+ core license: user_libs/antennas/GSSI.py, github.com/gprMax/
#     gprMax/blob/master/user_libs/antennas/GSSI.py (MALA.py is the
#     equivalent for the MALA GeoScience 1.2GHz antenna, referenced by the
#     same docs/source/examples_antennas.rst page but not independently
#     re-fetched in this pass).
#   - License -- "gprMax is currently released under the GNU General
#     Public License v3 or higher" (README), setup.py's own classifier
#     "License :: OSI Approved :: GNU General Public License v3 or later
#     (GPLv3+)", and the LICENSE file itself ("GNU GENERAL PUBLIC LICENSE,
#     Version 3, 29 June 2007"): all three fetched directly from
#     github.com/gprMax/gprMax's `master` branch.
#
# CORRECTION TO THIS ADAPTER'S OWN TICKET (issue #63 states gprMax is
# "pip-installable" -- VERIFIED FALSE, not guessed around): a direct query
# to PyPI's JSON API for both casings (https://pypi.org/pypi/gprMax/json
# and https://pypi.org/pypi/gprmax/json) returns HTTP 404 for both -- there
# is no "gprMax" (or "gprmax") package on PyPI. setup.py's own
# install_requires (colorama, Cython, h5py, matplotlib, numpy, psutil,
# scipy, terminaltables, tqdm) confirms the "pure Python/Cython" half of
# the ticket's premise, but gprMax's own documented installation path is
# conda (`conda env create -f conda_env.yml`) plus a C compiler with OpenMP
# support, then `python setup.py build && python setup.py install` (i.e. a
# local Cython-extension compile step) -- README.rst, same citation as
# above. Per this repo's own CLAUDE.md convention ("a tool that's a manual
# binary/source install ... gets documented in README.md's existing
# 'Optional' tools list instead ... do not invent a new pyproject extra for
# a manual-install-only tool", matching how NEC2++/openEMS are already
# handled there), gprMax is therefore documented in README.md's Optional
# list, NOT added as a new `pyproject.toml` `[project.optional-dependencies]`
# extra -- there is no pip-installable "gprMax" package such an extra could
# even name. `h5py` (needed by parse_gprmax_output() below to read gprMax's
# own native .out format) IS separately pip-installable, is free/open
# source with no special hardware or license requirement (unlike pyaedt),
# and this module's own tests construct synthetic .out files with
# it -- so, unlike pyaedt, it is added as an ordinary hard
# dependency in pyproject.toml, not an optional extra (see that file's own
# comment on this decision).
#
# ADAPTATION WORK (issue #63's own acceptance criterion -- this is
# deliberately NOT a drop-in wrapper around gprMax's GPR-survey-oriented
# defaults):
#   1. gprMax's bundled antenna library (user_libs/antennas/{GSSI,MALA}.py,
#      cited above) is NEVER imported or used by this adapter. Those
#      functions insert a fixed, pre-built geometry calibrated to
#      reproduce ONE specific commercial GPR antenna housing's measured
#      response (a GSSI 1.5GHz/400MHz or MALA 1.2GHz shielded antenna,
#      complete with that unit's absorber/shielding/PCB layout) -- they
#      are not stand-ins for an arbitrary antenna design, and they carry
#      their own separate CC-BY-SA-4.0 license. This repo's whole design
#      pipeline (rf_tools/, the NEC2++/openEMS adapters' own `wires`/
#      `materials`/`conductors` primitives) is about simulating the
#      CALLER's own antenna geometry -- so generate_gprmax_input() below
#      instead builds the caller's geometry directly from the same box/
#      cylinder/edge/plate primitive vocabulary simulation/openems.py's
#      `materials`/`conductors` already use, fed by gprMax's generic,
#      antenna-agnostic #transmission_line source (the same excitation
#      primitive gprMax's OWN antenna examples use to drive their antenna
#      models, cited above) -- i.e. this adapter reuses gprMax's generic
#      FDTD excitation/measurement machinery while deliberately not
#      reusing its specific commercial-hardware antenna geometry.
#   2. A `half_space` job field (see generate_gprmax_input()'s docstring)
#      builds an explicit lossy dielectric ground fill (#material +
#      full-footprint #box, cited above) representing the near-ground/
#      embedded host surface this issue is about -- something neither
#      NEC2++'s ground models nor openEMS's adapter currently exposes
#      (see "WHAT THIS ADAPTER IS FOR" above). #soil_peplinski (a
#      statistically randomized soil-mixing model) is documented but
#      deliberately NOT implemented in this pass: gprMax's own docs say it
#      "is designed to be used in conjunction with the #fractal_box
#      command" (cited above) -- composing those two commands correctly
#      was not independently verified against a real gprMax input file in
#      this pass, so rather than guess at that composition, `half_space`
#      only supports an explicit, caller-supplied epsilon_r/
#      conductivity_s_m/mu_r/magnetic_loss_ohm_m (a physically real but
#      spatially uniform lossy half-space), an honest scope limit, not a
#      fabricated shortcut.
#   3. Result parsing (parse_gprmax_output() below) returns S-parameters
#      and input impedance in the same structured, provenance-tagged
#      shape (`s_parameters`: computed/method/frequency_hz/values/note,
#      optionally `touchstone_file`) simulation/openems.py's own
#      computed=True S-parameter path already returns -- so
#      rf_tools/correlation.py's existing "touchstone_file"/"file"
#      lookup (see openems.py's own top-level `touchstone_file` surfacing
#      for why) works unchanged for a gprMax result too, rather than
#      inventing a third, gprMax-specific result shape.
#
# SCOPE OF THIS IMPLEMENTATION (explicitly narrower than gprMax's full
# feature set, an implementation decision, not quoted from issue #63):
#   - Exactly one #transmission_line excitation port per run (this
#     adapter's primary use case -- a single antenna-under-test's S11 and
#     input impedance -- matching simulation/openems.py's own single-
#     active-port primary case). #hertzian_dipole/#voltage_source/multi-
#     port S-parameter extraction are not exposed.
#   - #soil_peplinski/#fractal_box randomized-soil modelling: not
#     implemented (see point 2 above) -- `half_space` is a uniform lossy
#     dielectric only.
#   - B-scans (`-n` > 1, #src_steps/#rx_steps) and GPU/MPI execution: not
#     exposed -- this adapter always runs a single model on CPU, matching
#     its single-antenna-under-test scope.
#   - Receiver (#rx) field data is returned as raw time-domain arrays
#     (parse_gprmax_output()'s `receivers` key) -- no near-field-to-far-
#     field transform or gain/pattern extraction is performed (gprMax has
#     no such tool at all, unlike openEMS's separate nf2ff utility that
#     simulation/openems.py's own module docstring already flags as
#     out-of-scope for the same reason). `far_field` is therefore always
#     `{"computed": False, ...}`, structurally parallel to nec2pp.py's
#     `pattern`/`gain_dbi` and openems.py's `far_field` keys.
#
# HONEST CAVEAT: gprMax is NOT installed in this environment, and (per the
# "CORRECTION" section above) genuinely CANNOT be installed via a simple
# pip/uv command here at all -- it requires a conda environment plus a C
# compiler with OpenMP support to compile its Cython extensions, none of
# which this environment provides. Deck generation and result parsing
# below are built to the letter of the documented/verified .in command
# syntax and .out HDF5 structure cited above, and exercised in tests only
# against (a) a small fake "python -m gprMax" script (mirroring nec2pp.py's/
# openems.py's own fake-executable pattern) and (b) synthetic .out HDF5
# files hand-built with h5py to match the documented schema -- NOT against
# a real gprMax run's actual output. Treat any result as unverified
# end-to-end until it has been run against the real tool at least once.
# ---------------------------------------------------------------------------

# gprMax's own documented bound on #transmission_line's characteristic
# resistance (see module docstring citation): strictly between 0 and the
# impedance of free space.
_TL_MAX_RESISTANCE_OHMS = 376.73

# Minimum |Vinc(f)|, as a fraction of that spectrum's own peak magnitude,
# for a frequency point to be reported -- same "exclude the excitation
# pulse's own low-energy tail, don't divide by FFT noise" reasoning as
# simulation/openems.py's _S_PARAM_MIN_RELATIVE_MAGNITUDE (see that
# module's docstring for the fuller argument); kept as this module's own
# constant rather than imported, matching how nec2pp.py/openems.py each
# stay self-contained.
_MIN_RELATIVE_MAGNITUDE = 1e-3

_RX_FIELD_COMPONENTS = ("Ex", "Ey", "Ez", "Hx", "Hy", "Hz", "Ix", "Iy", "Iz")


def _fmt_num(value: float) -> str:
    """Format a float as a compact free-format gprMax decimal field."""
    return f"{float(value):.6g}"


def _fmt_int(value: int) -> str:
    return str(int(value))


def _primitive_command(
    shape: str,
    p1_m: Any,
    p2_m: Any,
    material: str,
    radius_m: float | None = None,
) -> str:
    """Render one #box/#cylinder/#edge/#plate primitive command (see module
    docstring citation for each command's field order)."""
    x1, y1, z1 = (float(v) for v in p1_m)
    x2, y2, z2 = (float(v) for v in p2_m)
    coords = [x1, y1, z1, x2, y2, z2]
    if shape == "box":
        return "#box: " + " ".join(_fmt_num(v) for v in coords) + f" {material}"
    if shape == "cylinder":
        if radius_m is None:
            raise ValueError("cylinder primitive requires 'radius_m'")
        return "#cylinder: " + " ".join(_fmt_num(v) for v in [*coords, radius_m]) + f" {material}"
    if shape == "plate":
        return "#plate: " + " ".join(_fmt_num(v) for v in coords) + f" {material}"
    if shape == "edge":
        return "#edge: " + " ".join(_fmt_num(v) for v in coords) + f" {material}"
    raise ValueError(f"shape must be 'box', 'cylinder', 'plate', or 'edge', got {shape!r}")


# Per-model required fields for one dispersion "pole" dict, in the exact
# order gprMax's #add_dispersion_<model> command expects them (issue #277;
# see module docstring citation for the verbatim docs/source/input.rst
# syntax this was verified against directly):
#   #add_dispersion_debye:   i1 f1 f2 f3 f4 ... str1
#     (pairs: delta_epsilon_r, tau_s)
#   #add_dispersion_lorentz: i1 f1 f2 f3 f4 f5 f6 ... str1
#     (triplets: delta_epsilon_r, omega_hz, delta_hz)
#   #add_dispersion_drude:   i1 f1 f2 f3 f4 ... str1
#     (pairs: omega_hz, gamma_hz)
_DISPERSION_POLE_FIELDS: dict[str, tuple[str, ...]] = {
    "debye": ("delta_epsilon_r", "tau_s"),
    "lorentz": ("delta_epsilon_r", "omega_hz", "delta_hz"),
    "drude": ("omega_hz", "gamma_hz"),
}


def _require_dispersion_fields(dispersion: dict[str, Any], context: str) -> None:
    """Validate a `dispersion` block carries both `model` and `poles` before
    `_dispersion_command()` is called on it (issue #277). Shared by both of
    `generate_gprmax_input()`'s call sites -- `geometry['half_space']
    ['dispersion']` and each `materials[idx]['dispersion']` -- so the two
    checks (previously written out near-verbatim at each site) can't drift
    apart. `context` names the offending field in the caller's own error
    message, e.g. "geometry['half_space']['dispersion']" or
    "materials[2]['dispersion']"."""
    missing = [f for f in ("model", "poles") if f not in dispersion]
    if missing:
        raise ValueError(f"{context} missing required field(s): {missing}")


def _dispersion_command(model: str, params: dict[str, Any], material_name: str) -> str:
    """Render one #add_dispersion_debye/_lorentz/_drude command attaching
    frequency-dependent behaviour to an already-declared #material of the
    same identifier (issue #277). `params["poles"]` is a list of one dict
    per pole, each carrying that model's fields (see
    `_DISPERSION_POLE_FIELDS` above); the emitted `i1` pole count is always
    `len(params["poles"])`, never a caller-supplied number, so there is no
    way for a declared count to disagree with the poles actually rendered.
    Command syntax and per-model parameter order verified directly against
    gprMax's own docs/source/input.rst -- see this module's header comment
    citation."""
    pole_fields = _DISPERSION_POLE_FIELDS.get(model)
    if pole_fields is None:
        raise ValueError(
            f"dispersion['model'] must be 'debye', 'lorentz', or 'drude', got {model!r}"
        )
    poles = params.get("poles")
    if not poles:
        raise ValueError(
            f"dispersion['poles'] is required and must be a non-empty list (material "
            f"{material_name!r}, model {model!r})"
        )
    values: list[float] = []
    for idx, pole in enumerate(poles):
        missing = [f for f in pole_fields if f not in pole]
        if missing:
            raise ValueError(
                f"dispersion['poles'][{idx}] missing required field(s) {missing} for "
                f"model {model!r} (material {material_name!r})"
            )
        values.extend(pole[f] for f in pole_fields)
    return f"#add_dispersion_{model}: " + " ".join(
        [_fmt_int(len(poles)), *(_fmt_num(v) for v in values), material_name]
    )


def generate_gprmax_input(
    geometry: dict[str, Any],
    fdtd: dict[str, Any] | None = None,
    comment: str = "Generated by run_gprmax_simulation",
) -> str:
    """Generate a gprMax .in input file from structured geometry/materials/
    port/receivers input, for a single ground-coupled or lossy-half-space
    antenna FDTD run.

    `geometry` shape:
        {
          "domain_m": [x, y, z],           # required, model size in metres
          "resolution_m": float | [dx, dy, dz],   # required, metres
          "frequency_hz": float,           # optional default for
              port["center_frequency_hz"] below (same convention as
              simulation/openems.py's geometry["frequency_hz"])
          "half_space": {                  # optional lossy ground fill --
              "z_m": float,                    # required, ground-interface
                  height; the ground fills z_min_m..z_m across the full
                  x/y domain footprint
              "epsilon_r": float,          # required
              "conductivity_s_m": float,   # required
              "mu_r": float = 1.0,
              "magnetic_loss_ohm_m": float = 0.0,
              "z_min_m": float = 0.0,
              "name": str = "ground",
              "dispersion": {              # optional (issue #277) --
                  "model": "debye"|"lorentz"|"drude",   # required
                  "poles": [               # required, non-empty; one dict
                      {...},               # per pole, fields depend on
                      ...                  # `model` (see below)
                  ],
              },
          },
          "materials": [                   # dielectric/lossy bodies (the
              {                             # antenna's own substrate, a
                "name": str,                # radome, etc.), optional
                "shape": "box"|"cylinder"|"plate"|"edge",
                "p1_m", "p2_m": [x, y, z],
                "radius_m": float,          # cylinder only
                "epsilon_r": float, "conductivity_s_m": float,
                "mu_r": float = 1.0, "magnetic_loss_ohm_m": float = 0.0,
                "dispersion": {...},        # optional, same shape as
                                             # half_space["dispersion"] above
              }, ...
          ],
          "conductors": [                  # PEC bodies (patch, ground
              {"shape": ..., "p1_m", "p2_m", "radius_m" (cylinder only)},
              ...                          # plane, dipole arms), optional
          ],
          "port": {                        # required -- single
              "polarization": "x" | "y" | "z",
              "position_m": [x, y, z],
              "resistance_ohms": float = 50.0,   # must be in (0, 376.73),
                  see module docstring citation
              "waveform_type": str = "gaussian",
              "amplitude": float = 1.0,
              "center_frequency_hz": float,   # falls back to
                  geometry["frequency_hz"] if omitted; one of the two is
                  required
          },
          "receivers": [                   # optional field probes
              {"name": str, "position_m": [x, y, z],
               "components": str},         # optional space-separated
                                            # subset of Ex/Ey/Ez/Hx/Hy/Hz/
                                            # Ix/Iy/Iz; omit for gprMax's
                                            # own default (all of them)
              ...
          ],
        }

    `dispersion["poles"]` entry shape, by `model` (issue #277; field names
    and per-model ordering verified directly against gprMax's own
    docs/source/input.rst -- see this module's header comment citation for
    the full "#add_dispersion_debye/_lorentz/_drude" syntax this renders):
        "debye":   {"delta_epsilon_r": float, "tau_s": float}
            delta_epsilon_r = (zero-frequency relative permittivity) minus
            (relative permittivity at infinite frequency, i.e. the
            epsilon_r already given in this material's own #material
            line); tau_s = pole relaxation time in seconds.
        "lorentz": {"delta_epsilon_r": float, "omega_hz": float, "delta_hz": float}
            delta_epsilon_r as above; omega_hz = pole frequency in Hertz;
            delta_hz = damping coefficient in Hertz.
        "drude":   {"omega_hz": float, "gamma_hz": float}
            omega_hz = pole frequency in Hertz; gamma_hz = inverse pole
            relaxation time in Hertz.
    Multiple poles are supported (a list of more than one dict) -- the
    emitted command's own pole count (`i1`) is always `len(poles)`, never a
    separately caller-supplied number. Each model's temporal/frequency
    values must exceed the model's own FDTD time step per gprMax's own
    documented constraint (not validated here -- gprMax itself will reject
    a violating deck at run time).

    `fdtd` shape: exactly one of `time_window_s` (float seconds) or
    `time_window_iterations` (int) is required (see module docstring for
    why this adapter does not guess a default); `pml_cells` (int, or a
    6-int list for x0/y0/z0/xmax/ymax/zmax individually) and `num_threads`
    (int) are optional.

    Geometry is in metres; command formats are verified against gprMax's
    own primary documentation -- see this module's header comment for the
    full citation list.
    """
    domain = geometry.get("domain_m")
    if not domain or len(domain) != 3:
        raise ValueError("geometry['domain_m'] must be a 3-element [x, y, z] list, in metres")

    resolution = geometry.get("resolution_m")
    if resolution is None:
        raise ValueError("geometry['resolution_m'] is required (a float, or [dx, dy, dz])")
    if isinstance(resolution, (int, float)):
        dx = dy = dz = float(resolution)
    else:
        if len(resolution) != 3:
            raise ValueError(
                "geometry['resolution_m'] must be a float or a 3-element [dx, dy, dz] list"
            )
        dx, dy, dz = (float(v) for v in resolution)

    fdtd = fdtd or {}
    time_window_s = fdtd.get("time_window_s")
    time_window_iterations = fdtd.get("time_window_iterations")
    if (time_window_s is None) == (time_window_iterations is None):
        raise ValueError(
            "fdtd must supply exactly one of 'time_window_s' or "
            "'time_window_iterations' -- gprMax's own #time_window command "
            "(see module docstring citation) takes either a duration in "
            "seconds or an iteration count, never both or neither, and "
            "this adapter deliberately does not guess a default given how "
            "widely the right answer varies between a small antenna "
            "problem and a GPR survey-scale one."
        )

    lines: list[str] = [f"#title: {comment}"]
    lines.append("#domain: " + " ".join(_fmt_num(v) for v in domain))
    lines.append("#dx_dy_dz: " + " ".join(_fmt_num(v) for v in (dx, dy, dz)))
    lines.append(
        f"#time_window: {_fmt_num(time_window_s)}"
        if time_window_s is not None
        else f"#time_window: {_fmt_int(time_window_iterations)}"
    )

    pml_cells = fdtd.get("pml_cells")
    if pml_cells is not None:
        if isinstance(pml_cells, int):
            lines.append(f"#pml_cells: {_fmt_int(pml_cells)}")
        else:
            lines.append("#pml_cells: " + " ".join(_fmt_int(v) for v in pml_cells))
    num_threads = fdtd.get("num_threads")
    if num_threads is not None:
        lines.append(f"#num_threads: {_fmt_int(num_threads)}")

    # --- lossy ground-coupled half-space (this issue's whole point -- see
    # module docstring "WHAT THIS ADAPTER IS FOR"). Emitted before the
    # caller's own materials/conductors below so the "layered canvas"
    # object-construction ordering (see module docstring citation) lets
    # those correctly override the ground fill wherever they overlap it.
    half_space = geometry.get("half_space")
    if half_space is not None:
        required = ("z_m", "epsilon_r", "conductivity_s_m")
        missing = [f for f in required if f not in half_space]
        if missing:
            raise ValueError(f"geometry['half_space'] missing required field(s): {missing}")
        hs_name = half_space.get("name", "ground")
        lines.append(
            "#material: "
            + " ".join(
                [
                    _fmt_num(half_space["epsilon_r"]),
                    _fmt_num(half_space["conductivity_s_m"]),
                    _fmt_num(half_space.get("mu_r", 1.0)),
                    _fmt_num(half_space.get("magnetic_loss_ohm_m", 0.0)),
                    hs_name,
                ]
            )
        )
        dispersion = half_space.get("dispersion")
        if dispersion is not None:
            _require_dispersion_fields(dispersion, "geometry['half_space']['dispersion']")
            lines.append(_dispersion_command(dispersion["model"], dispersion, hs_name))
        lines.append(
            _primitive_command(
                "box",
                [0.0, 0.0, half_space.get("z_min_m", 0.0)],
                [domain[0], domain[1], half_space["z_m"]],
                hs_name,
            )
        )

    # --- additional dielectric/lossy materials (antenna substrate, radome,
    # etc.) -- never "pec": that identifier is reserved for the caller's
    # conductors below (see module docstring citation).
    for idx, mat in enumerate(geometry.get("materials", [])):
        required = ("shape", "p1_m", "p2_m", "epsilon_r", "conductivity_s_m")
        missing = [f for f in required if f not in mat]
        if missing:
            raise ValueError(f"materials[{idx}] missing required field(s): {missing}")
        name = mat.get("name", f"material_{idx + 1}")
        lines.append(
            "#material: "
            + " ".join(
                [
                    _fmt_num(mat["epsilon_r"]),
                    _fmt_num(mat["conductivity_s_m"]),
                    _fmt_num(mat.get("mu_r", 1.0)),
                    _fmt_num(mat.get("magnetic_loss_ohm_m", 0.0)),
                    name,
                ]
            )
        )
        dispersion = mat.get("dispersion")
        if dispersion is not None:
            _require_dispersion_fields(dispersion, f"materials[{idx}]['dispersion']")
            lines.append(_dispersion_command(dispersion["model"], dispersion, name))
        lines.append(
            _primitive_command(mat["shape"], mat["p1_m"], mat["p2_m"], name, mat.get("radius_m"))
        )

    # --- PEC conductors (patch/ground-plane/dipole elements, etc.) -- "pec"
    # is gprMax's own builtin perfect-electric-conductor identifier, never
    # declared via #material (see module docstring citation).
    for idx, cond in enumerate(geometry.get("conductors", [])):
        required = ("shape", "p1_m", "p2_m")
        missing = [f for f in required if f not in cond]
        if missing:
            raise ValueError(f"conductors[{idx}] missing required field(s): {missing}")
        lines.append(
            _primitive_command(
                cond["shape"], cond["p1_m"], cond["p2_m"], "pec", cond.get("radius_m")
            )
        )

    # --- excitation port: a single #transmission_line, gprMax's own
    # generic (antenna-model-agnostic) source for exactly this "measure an
    # antenna's own S11/input impedance" use case -- see module docstring
    # "ADAPTATION WORK" point 1 for why this adapter uses this instead of
    # gprMax's bundled commercial-antenna library.
    port = geometry.get("port")
    if not port:
        raise ValueError("geometry['port'] is required (a single #transmission_line excitation)")
    missing = [f for f in ("polarization", "position_m") if f not in port]
    if missing:
        raise ValueError(f"geometry['port'] missing required field(s): {missing}")
    polarization = port["polarization"]
    if polarization not in ("x", "y", "z"):
        raise ValueError(
            f"geometry['port']['polarization'] must be 'x', 'y', or 'z', got {polarization!r}"
        )
    resistance = float(port.get("resistance_ohms", 50.0))
    if not (0.0 < resistance < _TL_MAX_RESISTANCE_OHMS):
        raise ValueError(
            "geometry['port']['resistance_ohms'] must be strictly between 0 and "
            f"{_TL_MAX_RESISTANCE_OHMS} (the impedance of free space) -- gprMax's own "
            f"documented #transmission_line bound (see module docstring citation), got "
            f"{resistance}"
        )
    center_frequency_hz = port.get("center_frequency_hz", geometry.get("frequency_hz"))
    if center_frequency_hz is None:
        raise ValueError(
            "geometry['port']['center_frequency_hz'] (or geometry['frequency_hz']) is "
            "required -- it sets the #waveform Gaussian pulse's centre frequency."
        )
    waveform_id = "gprmax_adapter_src"
    lines.append(
        "#waveform: "
        + " ".join(
            [
                port.get("waveform_type", "gaussian"),
                _fmt_num(port.get("amplitude", 1.0)),
                _fmt_num(center_frequency_hz),
                waveform_id,
            ]
        )
    )
    px, py, pz = (float(v) for v in port["position_m"])
    lines.append(
        "#transmission_line: "
        + " ".join(
            [
                polarization,
                _fmt_num(px),
                _fmt_num(py),
                _fmt_num(pz),
                _fmt_num(resistance),
                waveform_id,
            ]
        )
    )

    # --- receivers (optional field probes) ---
    for idx, rx in enumerate(geometry.get("receivers", []), start=1):
        if "position_m" not in rx:
            raise ValueError(f"receivers[{idx - 1}] missing required field 'position_m'")
        rx_name = rx.get("name", f"rx{idx}")
        rx_x, rx_y, rx_z = (float(v) for v in rx["position_m"])
        line = f"#rx: {_fmt_num(rx_x)} {_fmt_num(rx_y)} {_fmt_num(rx_z)} {rx_name}"
        components = rx.get("components")
        if components:
            line += f" {components}"
        lines.append(line)

    return "\n".join(lines) + "\n"


def _read_receivers(h5file: Any, receivers: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Read each declared receiver's time-domain field-component datasets
    from `/rxs/rxN/` (N = 1-based declaration order, per this module's
    header comment citation). Silently skips a receiver whose group is
    absent (e.g. the run genuinely didn't produce it) rather than raising
    -- this is diagnostic time-domain data, not a required result."""
    out: dict[str, Any] = {}
    for idx, rx in enumerate(receivers or [], start=1):
        group_path = f"rxs/rx{idx}"
        if group_path not in h5file:
            continue
        group = h5file[group_path]
        fields = {
            comp: np.asarray(group[comp][()], dtype=float).tolist()
            for comp in _RX_FIELD_COMPONENTS
            if comp in group
        }
        out[rx.get("name", f"rx{idx}")] = {
            "position_m": rx.get("position_m"),
            "fields": fields,
        }
    return out


def _compute_s_and_z_from_tl(
    vinc: np.ndarray,
    vtotal: np.ndarray,
    itotal: np.ndarray,
    dt: float,
    port: dict[str, Any],
    touchstone_dir: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Compute S11(f) and Zin(f) from one #transmission_line's Vinc/Vtotal/
    Itotal time-domain dumps, per gprMax's own tools/plot_antenna_params.py
    formula (see module docstring citation): Vref = Vtotal - Vinc,
    S11 = FFT(Vref)/FFT(Vinc), Zin = FFT(Vtotal)*delaycorrection/FFT(Itotal).
    Returns (s_parameters, impedance), both carrying computed=False with an
    explanatory note (never a guess) when the incident-wave spectrum is
    unusable."""
    freqs = np.fft.rfftfreq(len(vinc), d=dt)
    vinc_fd = np.fft.rfft(vinc)
    vtotal_fd = np.fft.rfft(vtotal)
    itotal_fd = np.fft.rfft(itotal)
    vref_fd = vtotal_fd - vinc_fd

    peak = float(np.max(np.abs(vinc_fd))) if len(vinc_fd) else 0.0
    if peak <= 0.0:
        note = (
            "the transmission line's incident-wave spectrum (Vinc) is identically "
            "zero -- nothing to normalize S11/Zin against (check the excitation "
            "actually ran)."
        )
        return {"computed": False, "note": note}, {"computed": False, "note": note}

    mask = (np.abs(vinc_fd) >= _MIN_RELATIVE_MAGNITUDE * peak) & (np.abs(itotal_fd) > 0.0)
    if not np.any(mask):
        note = (
            "no frequency point met the "
            f"{_MIN_RELATIVE_MAGNITUDE:g}x-of-peak incident-wave magnitude threshold "
            "used to exclude FFT noise outside the excitation pulse's bandwidth (or "
            "every masked point had a zero total-current spectrum) -- nothing usable "
            "to report."
        )
        return {"computed": False, "note": note}, {"computed": False, "note": note}

    f_masked = freqs[mask]
    s11 = vref_fd[mask] / vinc_fd[mask]
    delaycorrection = np.exp(1j * 2 * np.pi * f_masked * (dt / 2.0))
    zin = (vtotal_fd[mask] * delaycorrection) / itotal_fd[mask]

    s_parameters: dict[str, Any] = {
        "computed": True,
        "method": (
            "FFT (numpy.fft.rfft) of the #transmission_line port's Vinc/Vtotal "
            "time-domain dumps; Vref=Vtotal-Vinc, S11=FFT(Vref)/FFT(Vinc), per "
            "gprMax's own tools/plot_antenna_params.py -- see simulation/gprmax.py's "
            "module docstring for the full citation."
        ),
        "port": port.get("name", "port1"),
        "resistance_ohms": float(port.get("resistance_ohms", 50.0)),
        "frequency_hz": f_masked.tolist(),
        "values": {"S11": [[complex(v).real, complex(v).imag] for v in s11]},
        "note": "values['S11'] holds [real, imag] pairs per frequency_hz point.",
    }
    impedance: dict[str, Any] = {
        "computed": True,
        "method": (
            "Zin(f) = FFT(Vtotal)*delaycorrection / FFT(Itotal), delaycorrection = "
            "exp(1j*2*pi*f*dt/2) -- gprMax's own half-timestep Yee-grid V/I-staggering "
            "correction, per tools/plot_antenna_params.py (see module docstring "
            "citation)."
        ),
        "frequency_hz": f_masked.tolist(),
        "resistance_ohms": [complex(v).real for v in zin],
        "reactance_ohms": [complex(v).imag for v in zin],
        "note": (
            "resistance_ohms/reactance_ohms are broadband arrays (one value per "
            "frequency_hz point), unlike NEC2++'s single-frequency impedance."
        ),
    }

    if len(s11) and touchstone_dir is not None:
        try:
            import skrf as rf

            s = np.array([complex(re, im) for re, im in s_parameters["values"]["S11"]]).reshape(
                -1, 1, 1
            )
            network = rf.Network(
                frequency=rf.Frequency.from_f(f_masked / 1e9, unit="ghz"),
                s=s,
                z0=float(port.get("resistance_ohms", 50.0)),
            )
            touchstone_path = touchstone_dir / "gprmax_s_parameters.s1p"
            network.write_touchstone(str(touchstone_path))
            s_parameters["touchstone_file"] = str(touchstone_path)
        except Exception:
            # Touchstone export is a convenience for rf_tools/correlation.py
            # integration (matching simulation/openems.py's own
            # computed=True pattern), not the acceptance criterion itself --
            # a failure here (e.g. skrf unavailable) must not hide the
            # already-computed S-parameter values above.
            pass

    return s_parameters, impedance


def parse_gprmax_output(
    output_file: str | Path,
    port: dict[str, Any],
    receivers: list[dict[str, Any]] | None = None,
    tl_index: int = 1,
) -> dict[str, Any]:
    """Parse a gprMax .out HDF5 results file (see module docstring citation
    for the exact naming convention and internal structure) into real
    S-parameter/impedance results (FFT-computed from the excited
    #transmission_line's own Vinc/Vtotal/Itotal dumps) plus any declared
    receivers' raw time-domain field data.

    Returns computed=False (with an explanatory note, never a guess) when
    the output file or the expected `/tls/tl{tl_index}/` group is absent --
    both real, honestly-reported gaps (e.g. the run genuinely didn't
    execute, or --geometry-only was passed), not silently worked around.
    """
    output_path = Path(output_file)
    if not output_path.exists():
        note = f"gprMax output file not found: {output_path}"
        return {
            "s_parameters": {"computed": False, "note": note},
            "impedance": {"computed": False, "note": note},
            "receivers": {},
        }

    import h5py

    with h5py.File(output_path, "r") as f:
        tl_group_path = f"tls/tl{tl_index}"
        if tl_group_path not in f:
            note = (
                f"'/{tl_group_path}/' group missing from {output_path} -- was a "
                "#transmission_line port actually declared and excited this run?"
            )
            return {
                "s_parameters": {"computed": False, "note": note},
                "impedance": {"computed": False, "note": note},
                "receivers": _read_receivers(f, receivers),
            }

        dt = float(f.attrs["dt"])
        tl_group = f[tl_group_path]
        vinc = np.asarray(tl_group["Vinc"][()], dtype=float)
        vtotal = np.asarray(tl_group["Vtotal"][()], dtype=float)
        itotal = np.asarray(tl_group["Itotal"][()], dtype=float)
        receivers_out = _read_receivers(f, receivers)

    s_parameters, impedance = _compute_s_and_z_from_tl(
        vinc, vtotal, itotal, dt, port, touchstone_dir=output_path.parent
    )

    return {"s_parameters": s_parameters, "impedance": impedance, "receivers": receivers_out}


def run_gprmax_simulation(
    geometry: dict[str, Any],
    fdtd: dict[str, Any] | None = None,
    timeout_s: int = 3600,
    executable: str | None = None,
    workdir: str | None = None,
) -> dict[str, Any]:
    """Generate a gprMax .in file from structured geometry/materials/port/
    receivers (optionally including a lossy ground-coupled half-space --
    see generate_gprmax_input()'s docstring for the full shape), run it via
    GprmaxSimulator ("python -m gprMax", see module docstring), and parse
    S-parameter/impedance results plus any receiver field data tagged with
    SIMULATED provenance.

    `executable` names the PYTHON interpreter to run "-m gprMax" through
    (defaults to the GPRMAX_PYTHON env var, else sys.executable) -- NOT a
    "gprmax" binary, since gprMax has none (see module docstring).

    See this module's header comment for the format-verification citations
    and the honest caveat: deck generation and result parsing are built to
    the documented/verified gprMax .in/.out formats, not to a real gprMax
    run in this environment (gprMax genuinely cannot be installed here at
    all -- no pip package exists, and it needs a conda + C-compiler build,
    see the "CORRECTION" section of this module's header comment).
    """
    work_dir = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="gprmax_"))
    work_dir.mkdir(parents=True, exist_ok=True)
    input_file = work_dir / "model.in"
    fdtd = fdtd or {}
    input_file.write_text(generate_gprmax_input(geometry, fdtd))

    simulator = GprmaxSimulator(python_executable=executable)
    result = simulator.run(
        {"input_file": str(input_file), "workdir": str(work_dir), "timeout_s": timeout_s}
    )

    # gprMax's own documented output-filename convention (see module
    # docstring citation): the input filename with ".out" appended, not an
    # extension swap -- "model.in" -> "model.in.out".
    output_file = work_dir / (input_file.name + ".out")
    parsed = parse_gprmax_output(
        output_file, port=geometry["port"], receivers=geometry.get("receivers")
    )

    output: dict[str, Any] = {
        "provenance": "SIMULATED",
        "s_parameters": parsed["s_parameters"],
        "impedance": parsed["impedance"],
        "receivers": parsed["receivers"],
        "far_field": {
            "computed": False,
            "note": (
                "gprMax has no near-field-to-far-field transform tool at all (unlike "
                "openEMS's separate nf2ff utility) -- see simulation/gprmax.py's module "
                "docstring 'SCOPE OF THIS IMPLEMENTATION'."
            ),
        },
        "simulator": result.simulator,
        "status": result.status,
        "workdir": str(result.workdir),
        "input_file": str(input_file),
        "output_file": str(output_file),
    }
    touchstone_file = parsed["s_parameters"].get("touchstone_file")
    if touchstone_file:
        # Surfaced at top level (not just nested under s_parameters) so it
        # integrates with rf_tools.correlation.correlate_simulation_
        # measurement's own "touchstone_file"/"file" lookup, the same way
        # simulation/openems.py's computed=True result already does.
        output["touchstone_file"] = touchstone_file
    return output
