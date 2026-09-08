"""Drive the COMMITTED adapter against a real Meep, on a case with exact R and T.

    MEEP_PYTHON=/opt/conda/envs/mp/bin/python3 uv run python -m \
        verification.meep_adapter_transmittance_check

WHY THIS EXISTS, and how it differs from its neighbour.
`verification/meep_absorber_validation.py` deliberately builds `mp.Simulation`
objects itself and re-derives the unit conversions, so that the validation does
not assume the thing it validates. The cost of that choice is stated in its own
caveat: the ADAPTER's deck emission, its subprocess handoff and its result
parsing are then not what those numbers check.

This closes that gap from the other side. It calls `run_meep_simulation` -- the
real public entry point, through the real `MEEP_PYTHON` subprocess path -- and
checks the numbers that come back against an answer derived on paper. The two
scripts are complementary and neither replaces the other: one validates the
physics without the adapter, this validates the adapter's own path.

WHY A LOSSY SLAB RATHER THAN AN ABSORBER. Transmittance is the quantity #240
added, and a normalisation mistake in it (the wrong baseline plane, a monitor
area folded in twice) shows up as a FIXED MULTIPLICATIVE OFFSET -- a T that is
uniformly 2x or 0.5x the truth. Catching that needs a case whose transmission
is substantial and exactly known. A uniform slab of finite conductivity is
that case: it has closed-form R and T from a one-line ABCD chain, it transmits
most of the power, and unlike a thin resistive sheet its answer does not depend
on how many grid cells land across it -- so a disagreement here is the
adapter's fault, not the mesh's.

*In plain terms: a partly-see-through slab. We can work out on paper exactly
how much bounces back and how much comes out the far side, so if the adapter
reports anything else, the adapter is wrong.*

Deliberately a script, not a pytest test: it needs a solver CI does not have.
`tests/test_meep.py` covers the mechanics against a fake; this covers whether
the real path tells the truth.
"""

from __future__ import annotations

import cmath
import math

from simulation.meep import run_meep_simulation

C_M_S = 299_792_458.0
EPS0_F_M = 8.8541878128e-12
ETA0_OHM = 376.730313412

A_M = 1e-3  # Meep's characteristic length: 1 mm
RESOLUTION = 60  # pixels per a
F0_HZ = 10e9
SLAB_THICKNESS_M = 3e-3
SLAB_SIGMA_S_M = 0.5

SZ_M = 60e-3
DPML_M = 10e-3
SRC_Z_M = -SZ_M / 2 + DPML_M + 2e-3
REFL_Z_M = -SZ_M / 2 + DPML_M + 6e-3
TRAN_Z_M = SZ_M / 2 - DPML_M - 6e-3

TOLERANCE = 0.01


def exact_slab_r_t(
    frequency_hz: float, thickness_m: float, sigma_s_m: float
) -> tuple[float, float]:
    """Closed-form power reflectance and transmittance of a conductive slab
    with free space on both sides.

    A conducting slab's permittivity is complex: `eps = 1 - j*sigma/(w*eps0)`.
    The slab is one transmission-line section, so its ABCD matrix is the
    standard `[[cosh, Z*sinh], [sinh/Z, cosh]]`, and S-parameters follow from
    it with free space as both port impedances. No approximation is involved,
    which is the point -- any disagreement is the adapter's.
    """
    omega = 2 * math.pi * frequency_hz
    eps_c = 1.0 - 1j * sigma_s_m / (omega * EPS0_F_M)
    n = cmath.sqrt(eps_c)
    gamma = 1j * (omega / C_M_S) * n
    z_slab = ETA0_OHM / n
    cosh, sinh = cmath.cosh(gamma * thickness_m), cmath.sinh(gamma * thickness_m)
    a, b, c, d = cosh, z_slab * sinh, sinh / z_slab, cosh
    den = a * ETA0_OHM + b + c * ETA0_OHM**2 + d * ETA0_OHM
    s11 = (a * ETA0_OHM + b - c * ETA0_OHM**2 - d * ETA0_OHM) / den
    s21 = 2 * ETA0_OHM / den
    return abs(s11) ** 2, abs(s21) ** 2


def _geometry() -> dict:
    """The slab is declared as a CONDUCTOR, not a material, deliberately: the
    adapter's reference run omits conductors and keeps materials, so putting
    the structure under test in `conductors` is what makes the baseline an
    empty cell. A lossy slab listed under `materials` would be present in both
    runs and there would be nothing to subtract."""
    return {
        "cell_size_m": [0.0, 0.0, SZ_M],
        "pml_thickness_m": DPML_M,
        "mesh_cell_size_m": A_M / RESOLUTION,
        "conductors": [
            {
                "shape": "box",
                # Transverse extent far larger than the (zero-width, 1-D) cell,
                # so the slab spans it completely.
                "p1_m": [-1.0, -1.0, -SLAB_THICKNESS_M / 2],
                "p2_m": [1.0, 1.0, SLAB_THICKNESS_M / 2],
                "conductivity_s_m": SLAB_SIGMA_S_M,
            }
        ],
        "port": {
            "center_m": [0.0, 0.0, SRC_Z_M],
            "size_m": [0.0, 0.0, 0.0],
            "direction": "z",
            "component": "Ex",
            "frequency_hz": F0_HZ,
            "fractional_bandwidth": 0.2,
        },
        "reflection_monitor_center_m": [0.0, 0.0, REFL_Z_M],
        "reference_monitor_center_m": [0.0, 0.0, TRAN_Z_M],
        "transmission_monitor_center_m": [0.0, 0.0, TRAN_Z_M],
    }


def main() -> int:
    exact_r, exact_t = exact_slab_r_t(F0_HZ, SLAB_THICKNESS_M, SLAB_SIGMA_S_M)

    result = run_meep_simulation(geometry=_geometry(), characteristic_length_m=A_M, nfreq=1)
    s_parameters = result.get("s_parameters") or {}
    reflectance = s_parameters.get("reflectance")
    transmittance_block = s_parameters.get("transmittance") or {}

    if not reflectance or not transmittance_block.get("computed"):
        print(
            "The adapter returned no usable spectrum. reflectance="
            f"{reflectance!r}, transmittance={transmittance_block!r}. If Meep is "
            "not importable, run this under an interpreter that has it -- this "
            "repo's Dockerfile puts it at /opt/conda/envs/mp/bin/python3 and "
            "MEEP_PYTHON points the adapter at it."
        )
        return 2

    got_r = abs(float(reflectance[0]))
    got_t = abs(float(transmittance_block["transmittance"][0]))

    print("\n=== conductive slab through run_meep_simulation (real Meep) ===")
    print(f"  {'':<10}{'R':>10}{'T':>10}{'A = 1-R-T':>12}")
    print(f"  {'exact':<10}{exact_r:>10.4f}{exact_t:>10.4f}{1 - exact_r - exact_t:>12.4f}")
    print(f"  {'adapter':<10}{got_r:>10.4f}{got_t:>10.4f}{1 - got_r - got_t:>12.4f}")
    print(f"  {'delta':<10}{got_r - exact_r:>+10.4f}{got_t - exact_t:>+10.4f}")

    failures = sum(
        1
        for got, expected in ((got_r, exact_r), (got_t, exact_t))
        if abs(got - expected) > TOLERANCE
    )
    print(
        f"\n{'PASSED' if failures == 0 else f'{failures} QUANTITY(S) FAILED'} "
        f"(tolerance +/-{TOLERANCE})"
    )
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
