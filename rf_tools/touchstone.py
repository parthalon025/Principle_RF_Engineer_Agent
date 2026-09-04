from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import skrf as rf


def analyze_touchstone(path: str) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(path)

    network = rf.Network(str(p))
    # z0 (reference impedance) is complex in general (a lossy line's
    # characteristic impedance has a reactive part) -- a bare `complex`
    # isn't JSON-serializable, and this dict is returned as-is to callers
    # that do serialize it (ticket #19 writes it verbatim as an
    # `engineering_results.value` JSONB payload), so each entry is stored
    # as a JSON-safe [real, imag] pair rather than a Python complex.
    z0 = np.asarray(network.z0)
    result: dict[str, Any] = {
        "file": str(p.resolve()),
        "ports": int(network.nports),
        "frequency_start_hz": float(network.f[0]),
        "frequency_stop_hz": float(network.f[-1]),
        "points": int(len(network.f)),
        "z0": np.stack([z0.real, z0.imag], axis=-1).tolist(),
    }

    if network.nports >= 2:
        s11_db = 20 * np.log10(np.maximum(np.abs(network.s[:, 0, 0]), 1e-15))
        s21_db = 20 * np.log10(np.maximum(np.abs(network.s[:, 1, 0]), 1e-15))
        result["s11_min_db"] = float(np.min(s11_db))
        result["s21_max_db"] = float(np.max(s21_db))
        result["s11_min_frequency_hz"] = float(network.f[np.argmin(s11_db)])
        result["s21_max_frequency_hz"] = float(network.f[np.argmax(s21_db)])
    return result


def interpolate_touchstone(path: str, target_freqs_hz: Sequence[float]) -> rf.Network:
    """Interpolate a Touchstone network's S-parameters onto a new frequency grid.

    Loads the network at `path` and returns a new `skrf.Network` with its
    S-parameters interpolated onto `target_freqs_hz` (in Hz). Interpolation
    is done in polar coordinates (magnitude / unwrapped phase), which is
    exact for the common case of a matched, lossless network whose phase
    is linear in frequency, and is returned as an `skrf.Network` rather
    than summary statistics so downstream tools (cascading, comparison
    against another network) can operate on it directly.

    Every `target_freqs_hz` point must fall within the source network's
    original frequency range -- extrapolation is rejected with a
    `ValueError` rather than silently produced.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(path)

    network = rf.Network(str(p))

    targets = np.asarray(target_freqs_hz, dtype=float)
    if targets.size == 0:
        raise ValueError("target_freqs_hz must contain at least one frequency")

    f_min = float(network.f[0])
    f_max = float(network.f[-1])
    out_of_range = targets[(targets < f_min) | (targets > f_max)]
    if out_of_range.size:
        raise ValueError(
            "target_freqs_hz contains frequencies outside the source "
            f"network's range [{f_min:g}, {f_max:g}] Hz (extrapolation is "
            f"not supported): {sorted(out_of_range.tolist())}"
        )

    return network.interpolate(targets, coords="polar", f_kwargs={"unit": "hz"})


def _load_network(path: str) -> rf.Network:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(path)
    return rf.Network(str(p))


def _invert_fixture(fixture: rf.Network, path: str) -> rf.Network:
    try:
        return fixture.inv
    except np.linalg.LinAlgError as exc:
        raise ValueError(
            f"fixture network at {path!r} is singular (non-invertible) at "
            "one or more frequency points -- a physical fixture must pass "
            "signal through (nonzero S21); check for S21 == 0 or another "
            "non-physical fixture response"
        ) from exc


def deembed_touchstone(
    measured_path: str,
    fixture_path: str,
    output_fixture_path: str | None = None,
) -> rf.Network:
    """De-embed a test fixture's effect from a measured Touchstone network.

    Recovers the device-under-test's (DUT's) true response from a raw
    measurement that includes a test fixture in the signal path, by
    undoing the network cascade that produced the measurement.

    With a single fixture (e.g. present only on the input side):
        `measured = fixture ** dut`
    so de-embedding is the inverse cascade:
        `dut = fixture.inv ** measured`

    With `output_fixture_path` also given (a fixture on each side --
    pass the same path as `fixture_path` for a symmetric fixture used
    on both sides):
        `measured = fixture ** dut ** output_fixture`
        `dut = fixture.inv ** measured ** output_fixture.inv`

    Uses skrf's own `Network.inv` (ABCD-matrix inverse per frequency
    point) and `**` (network cascade) rather than re-deriving ABCD-matrix
    inversion by hand.

    Raises `ValueError` if a fixture network is singular (non-invertible)
    at any frequency point -- e.g. a fixture with zero transmission
    (S21 == 0), which is non-physical for a fixture meant to pass a
    signal through to the DUT -- instead of letting a cryptic linear
    algebra error or silent NaN/inf propagate.
    """
    measured = _load_network(measured_path)
    fixture = _load_network(fixture_path)

    dut = _invert_fixture(fixture, fixture_path) ** measured

    if output_fixture_path is not None:
        output_fixture = _load_network(output_fixture_path)
        dut = dut ** _invert_fixture(output_fixture, output_fixture_path)

    return dut


def cascade_touchstone(paths: list[str]) -> rf.Network:
    """Cascade an ordered chain of two-port Touchstone networks.

    Loads each network in `paths` (in order) and cascades them
    front-to-back with skrf's `**` operator, which multiplies each
    network's ABCD matrix in turn -- the standard way to predict the
    end-to-end response of a chain of components or stages (amplifiers,
    attenuators, lines, connectors, ...) from their individual
    measured/simulated networks:

        result = networks[0] ** networks[1] ** networks[2] ** ...

    Every network must be a two-port (this repo's whole Touchstone story
    is two-port so far, matching `analyze_touchstone`'s port-count
    field) -- a network with a different port count raises `ValueError`
    naming which entry in `paths` is at fault, rather than letting
    skrf's own port-count error point at an opaque matrix shape.

    Every network must also share the same reference impedance `z0`.
    skrf's `**` does not itself guard against cascading networks defined
    at different `z0` -- doing so without an explicit renormalization
    step would silently produce a physically wrong result -- so `z0` is
    compared (within a small floating-point tolerance) against the first
    network's before cascading, and a mismatch raises `ValueError` naming
    the offending network.
    """
    if not paths:
        raise ValueError("cascade_touchstone requires at least one network path")

    networks = [_load_network(path) for path in paths]

    for path, network in zip(paths, networks, strict=True):
        if network.nports != 2:
            raise ValueError(
                f"network at {path!r} has {network.nports} ports -- "
                "cascade_touchstone requires two-port networks"
            )

    ref_path, ref_network = paths[0], networks[0]
    ref_z0 = np.asarray(ref_network.z0[0])
    for path, network in zip(paths[1:], networks[1:], strict=True):
        z0 = np.asarray(network.z0[0])
        if not np.allclose(z0, ref_z0, atol=1e-6):
            raise ValueError(
                f"network at {path!r} has reference impedance z0="
                f"{z0.tolist()}, which does not match {ref_path!r}'s z0="
                f"{ref_z0.tolist()} -- cascading networks defined at "
                "different reference impedances without an explicit "
                "renormalization step would produce a physically wrong "
                "result"
            )

    result = networks[0]
    for network in networks[1:]:
        result = result**network
    return result


def compare_touchstone(path_a: str, path_b: str) -> dict[str, Any]:
    """Quantify how two Touchstone networks differ, per S-parameter.

    Useful for comparing a simulated design against a measured prototype,
    or one design revision against another -- anywhere the agent needs a
    number for "how close is this" rather than a bare pass/fail.

    The two networks may live on different frequency grids, so they are
    first brought onto a common grid by reusing `interpolate_touchstone`
    (rather than re-implementing interpolation here). The common grid is
    chosen as follows: take the overlapping frequency range of both
    networks (the highest of their two start frequencies to the lowest of
    their two stop frequencies), then use whichever network has *fewer*
    frequency points' own grid, restricted to that overlap. This avoids
    extrapolating beyond either network's real data (matching
    `interpolate_touchstone`'s own no-extrapolation contract) and avoids
    inventing extra resolution by up-sampling the sparser network onto the
    denser one's grid. Ties (equal point counts) fall back to `path_a`'s
    grid. Networks with no overlapping frequency range raise `ValueError`.

    For each S-parameter (`s11`, `s21`, ... -- `s{i+1}{j+1}` for an
    n-port), the returned dict holds:
      - `diff`: the per-frequency-point complex difference, `b - a`
        (network B's S-parameter minus network A's).
      - `magnitude_diff_db`: per-frequency-point difference in dB
        magnitude, `20*log10(|b|) - 20*log10(|a|)`.
      - `max_magnitude_diff_db`: the largest absolute dB magnitude
        difference across the common grid.
      - `rms_diff`: the RMS of `|diff|` across the common grid.
      - `max_abs_diff`: the largest `|diff|` across the common grid.

    Raises `ValueError` (naming both networks' port counts) if the two
    networks have different numbers of ports -- checked before any
    interpolation is attempted, since comparing across mismatched port
    counts is meaningless.
    """
    network_a = _load_network(path_a)
    network_b = _load_network(path_b)

    if network_a.nports != network_b.nports:
        raise ValueError(
            f"network at {path_a!r} has {network_a.nports} ports but network "
            f"at {path_b!r} has {network_b.nports} ports -- compare_touchstone "
            "requires both networks to have the same number of ports"
        )

    f_a, f_b = network_a.f, network_b.f
    overlap_min = max(float(f_a[0]), float(f_b[0]))
    overlap_max = min(float(f_a[-1]), float(f_b[-1]))
    if overlap_min > overlap_max:
        raise ValueError(
            f"networks at {path_a!r} ([{f_a[0]:g}, {f_a[-1]:g}] Hz) and "
            f"{path_b!r} ([{f_b[0]:g}, {f_b[-1]:g}] Hz) do not share an "
            "overlapping frequency range -- compare_touchstone cannot "
            "interpolate them onto a common grid"
        )

    if len(f_a) <= len(f_b):
        base_path, base_f = path_a, f_a
    else:
        base_path, base_f = path_b, f_b

    common_freqs = base_f[(base_f >= overlap_min) & (base_f <= overlap_max)]
    if common_freqs.size == 0:
        raise ValueError(
            f"no common frequency points found for {path_a!r} and {path_b!r} "
            f"within their overlapping range [{overlap_min:g}, {overlap_max:g}] Hz"
        )

    ntwk_a = interpolate_touchstone(path_a, common_freqs.tolist())
    ntwk_b = interpolate_touchstone(path_b, common_freqs.tolist())

    nports = network_a.nports
    result: dict[str, Any] = {
        "ports": int(nports),
        "common_frequencies_hz": common_freqs.tolist(),
        "common_grid_source": base_path,
    }

    for i in range(nports):
        for j in range(nports):
            s_a = ntwk_a.s[:, i, j]
            s_b = ntwk_b.s[:, i, j]
            diff = s_b - s_a
            mag_a_db = 20 * np.log10(np.maximum(np.abs(s_a), 1e-15))
            mag_b_db = 20 * np.log10(np.maximum(np.abs(s_b), 1e-15))
            magnitude_diff_db = mag_b_db - mag_a_db
            result[f"s{i + 1}{j + 1}"] = {
                "diff": diff,
                "magnitude_diff_db": magnitude_diff_db,
                "max_magnitude_diff_db": float(np.max(np.abs(magnitude_diff_db))),
                "rms_diff": float(np.sqrt(np.mean(np.abs(diff) ** 2))),
                "max_abs_diff": float(np.max(np.abs(diff))),
            }

    return result
