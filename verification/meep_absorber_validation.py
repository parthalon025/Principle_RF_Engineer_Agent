"""Execute the two absorber reference cases against a real Meep install.

    MEEP_PYTHON=/opt/conda/envs/mp/bin/python3 uv run python -m \
        verification.meep_absorber_validation

or, more simply, run it directly with an interpreter that has Meep:

    /opt/conda/envs/mp/bin/python3 -m verification.meep_absorber_validation

WHY THIS EXISTS. An adapter's own unit tests use hand-built fakes: they
confirm the adapter writes the right input and parses the output it is
handed. That is a claim about talking to the solver, not about whether the
solver told us the truth -- and only the second justifies the `SIMULATED`
provenance tag. `verification/simulator_reference_cases.py` names the
problems whose answers are published; this runs two of them.

NOT the first real-solver run in this repo. #210 drove simulation/palace.py
against a real compiled binary (docs/palace-floquet-validation.md) and found
two genuine defects. The two efforts checked DIFFERENT halves and neither has
done both: #210 validated the adapter path and says plainly it is "no check
at all on the physics"; this validates the physics and does NOT exercise the
adapter, because the runs below build mp.Simulation objects directly rather
than calling run_meep_simulation(), deliberately, so the validation does not
assume the thing it validates.

THE TWO CASES, and why these two:

  * A free-standing resistive sheet has an EXACT answer -- peak absorptance
    0.5, at Rs = eta0/2 = 188.365 ohm/sq. Not an approximation, a closed-form
    maximum, so any disagreement is the model's fault. It also fails loudly
    (returning 0) against the defect #230 recorded, where conductors were
    modelled as lossless perfect metal and could not dissipate anything.
  * A Salisbury screen is the canonical ground-backed absorber, and
    `rf_tools/absorber.py` models the same stack by a completely different
    method (an equivalent circuit, no grid, no time stepping). Agreement
    between two unrelated methods is worth far more than either alone.

This is deliberately a script, not a pytest test: it needs a solver CI does
not have, and takes minutes rather than milliseconds. `tests/test_meep.py`
covers the mechanics; this covers the physics.
"""

from __future__ import annotations

import math

from rf_tools.absorber import absorptivity
from verification.simulator_reference_cases import REFERENCE_CASES

C_M_S = 299_792_458.0
EPS0_F_M = 8.8541878128e-12
ETA0_OHM = 376.730313412

A_M = 1e-3  # Meep's characteristic length: 1 mm
RESOLUTION = 60  # pixels per a; 1-D runs are cheap, so do not skimp
SHEET_THICKNESS_M = 0.1e-3
F0_HZ = 10e9
SPACER_M = C_M_S / F0_HZ / 4  # quarter wave in air


def _sigma_d(sigma_s_m: float) -> float:
    """SI conductivity -> Meep's dimensionless D_conductivity. Same
    conversion `simulation.meep.sigma_d_from_conductivity` performs; spelled
    out here so this validation does not assume the thing it is validating."""
    return sigma_s_m * A_M / (C_M_S * EPS0_F_M)


def _analytic_free_sheet(rs_ohm_sq: float) -> float:
    """Exact absorptance of a shunt resistive sheet in free space."""
    z = rs_ohm_sq * ETA0_OHM / (rs_ohm_sq + ETA0_OHM)
    gamma = (z - ETA0_OHM) / (z + ETA0_OHM)
    return 1 - gamma**2 - (1 + gamma) ** 2


def _reflectance_1d(mp, freqs_hz: list[float], build_structure, ground_backed: bool):
    """Meep's own documented reflectance recipe: an empty reference run for
    the incident spectrum and the reflection plane's DFT fields, then the
    structure run with those fields subtracted so what is left is reflection
    only."""
    fcen = sum(freqs_hz) / len(freqs_hz) * A_M / C_M_S
    span = (max(freqs_hz) - min(freqs_hz)) * A_M / C_M_S
    fwidth = max(span * 1.4, fcen * 0.2)

    sz, dpml = 70.0, 10.0
    src_z, refl_z = -sz / 2 + dpml + 2, -sz / 2 + dpml + 6
    sources = [
        mp.Source(
            mp.GaussianSource(fcen, fwidth=fwidth),
            component=mp.Ex,
            center=mp.Vector3(0, 0, src_z),
        )
    ]

    def build(geometry):
        return mp.Simulation(
            cell_size=mp.Vector3(0, 0, sz),
            boundary_layers=[mp.PML(dpml, direction=mp.Z)],
            geometry=geometry,
            sources=sources,
            resolution=RESOLUTION,
            dimensions=1,
        )

    stop = mp.stop_when_fields_decayed(50, mp.Ex, mp.Vector3(0, 0, refl_z), 1e-9)

    sim = build([])
    refl = sim.add_flux(fcen, span, len(freqs_hz), mp.FluxRegion(center=mp.Vector3(0, 0, refl_z)))
    tran_z = sz / 2 - dpml - 4
    tran = (
        None
        if ground_backed
        else sim.add_flux(fcen, span, len(freqs_hz), mp.FluxRegion(center=mp.Vector3(0, 0, tran_z)))
    )
    sim.run(until_after_sources=stop)
    incident = mp.get_fluxes(refl)
    incident_forward = mp.get_fluxes(tran) if tran is not None else None
    saved = sim.get_flux_data(refl)

    sim = build(build_structure(mp))
    refl = sim.add_flux(fcen, span, len(freqs_hz), mp.FluxRegion(center=mp.Vector3(0, 0, refl_z)))
    tran = (
        None
        if ground_backed
        else sim.add_flux(fcen, span, len(freqs_hz), mp.FluxRegion(center=mp.Vector3(0, 0, tran_z)))
    )
    sim.load_minus_flux_data(refl, saved)
    sim.run(until_after_sources=stop)
    reflected = [-f for f in mp.get_fluxes(refl)]
    transmitted = mp.get_fluxes(tran) if tran is not None else None

    r = [rr / ii for rr, ii in zip(reflected, incident, strict=True)]
    if ground_backed:
        return r, [0.0] * len(r)
    t = [tt / ii for tt, ii in zip(transmitted, incident_forward, strict=True)]
    return r, t


def run_free_standing_sheet(mp) -> dict[str, float]:
    rs = ETA0_OHM / 2
    sigma = 1.0 / (rs * SHEET_THICKNESS_M)

    def structure(mp_mod):
        return [
            mp_mod.Block(
                size=mp_mod.Vector3(mp_mod.inf, mp_mod.inf, SHEET_THICKNESS_M / A_M),
                center=mp_mod.Vector3(0, 0, 0),
                material=mp_mod.Medium(epsilon=1.0, D_conductivity=_sigma_d(sigma)),
            )
        ]

    r, t = _reflectance_1d(mp, [F0_HZ], structure, ground_backed=False)
    return {"absorptance": 1 - r[0] - t[0], "exact": _analytic_free_sheet(rs)}


def run_salisbury_screen(mp, freqs_hz: list[float]) -> list[dict[str, float]]:
    sigma = 1.0 / (ETA0_OHM * SHEET_THICKNESS_M)
    ground_z = 70.0 / 2 - 10.0 - 6
    sheet_z = ground_z - SPACER_M / A_M

    def structure(mp_mod):
        return [
            mp_mod.Block(
                size=mp_mod.Vector3(mp_mod.inf, mp_mod.inf, 4),
                center=mp_mod.Vector3(0, 0, ground_z + 2),
                material=mp_mod.metal,
            ),
            mp_mod.Block(
                size=mp_mod.Vector3(mp_mod.inf, mp_mod.inf, SHEET_THICKNESS_M / A_M),
                center=mp_mod.Vector3(0, 0, sheet_z),
                material=mp_mod.Medium(epsilon=1.0, D_conductivity=_sigma_d(sigma)),
            ),
        ]

    r, _ = _reflectance_1d(mp, freqs_hz, structure, ground_backed=True)
    rows = []
    for f, rr in zip(freqs_hz, r, strict=True):
        rows.append(
            {
                "frequency_hz": f,
                "meep": 1 - rr,
                "closed_form": absorptivity(
                    frequency_hz=f,
                    eps_r=1.0,
                    tan_delta=0.0,
                    thickness_m=SPACER_M,
                    period_m=3e-3,
                    gap_m=None,  # continuous sheet
                    sheet_resistance_ohm_sq=ETA0_OHM,
                    squares=1.0,
                ),
            }
        )
    return rows


def main() -> int:
    try:
        import meep as mp
    except ImportError:
        print(
            "meep is not importable by this interpreter. Run this under one that "
            "has it, e.g. MEEP_PYTHON, which this repo's Dockerfile sets to "
            "/opt/conda/envs/mp/bin/python3."
        )
        return 2

    failures = 0

    sheet = run_free_standing_sheet(mp)
    case = REFERENCE_CASES["free-standing-resistive-sheet-10ghz"]
    expected = case.expected[0]
    ok = expected.matches(sheet["absorptance"])
    failures += 0 if ok else 1
    print("\n=== free-standing resistive sheet (exact answer 0.5) ===")
    print(
        f"  meep {sheet['absorptance']:.4f} | exact {sheet['exact']:.4f} | "
        f"{'PASS' if ok else 'FAIL'} (tolerance +/-{expected.tolerance})"
    )

    freqs = [6e9 + i * 1e9 for i in range(9)]
    rows = run_salisbury_screen(mp, freqs)
    print("\n=== Salisbury screen: Meep vs rf_tools/absorber.py ===")
    print(f"  {'f (GHz)':>8} {'meep':>8} {'closed':>8} {'diff':>8}")
    worst = 0.0
    for row in rows:
        diff = row["meep"] - row["closed_form"]
        worst = max(worst, abs(diff))
        print(
            f"  {row['frequency_hz'] / 1e9:>8.1f} {row['meep']:>8.4f} "
            f"{row['closed_form']:>8.4f} {diff:>+8.4f}"
        )
    peak = max(rows, key=lambda r: r["meep"])
    case = REFERENCE_CASES["salisbury-screen-10ghz"]
    expected = case.expected[0]
    ok = expected.matches(peak["meep"]) and math.isclose(peak["frequency_hz"], F0_HZ)
    failures += 0 if ok else 1
    print(
        f"\n  peak {peak['meep']:.4f} at {peak['frequency_hz'] / 1e9:.1f} GHz | "
        f"worst two-method disagreement {worst:.4f} | {'PASS' if ok else 'FAIL'}"
    )

    print(f"\n{'ALL CASES PASSED' if failures == 0 else f'{failures} CASE(S) FAILED'}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
