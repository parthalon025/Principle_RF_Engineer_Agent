"""Translate one solver-independent `geometry.ir.Model` into each adapter's
own geometry dict -- or refuse, naming what could not survive the crossing.

*In plain terms: every simulator describes the same object in its own dialect.
This turns one description into each of theirs. Where a dialect has no word
for something -- "slightly lossy metal", "a wave arriving at an angle" -- this
stops rather than picking the nearest word and quietly changing the physics.*

WHAT EACH TARGET CAN AND CANNOT TAKE. Every "no" below is a raised
`UnrepresentableGeometry`, never a silent substitution. These columns are
facts about THIS REPO'S ADAPTERS, not about the solvers upstream: openEMS
itself has periodic boundaries and plane-wave sources; `simulation/openems.py`
implements neither.

    target    | shapes            | conductors     | boundaries   | excited by
    ----------|-------------------|----------------|--------------|-----------
    openEMS   | box, cyl, polygon | all three kinds| OPEN only    | port only
    MEEP      | box, cyl          | all three kinds| all three    | plane wave
    Palace    | box only          | all three kinds| periodic/gnd | plane wave
    gprMax    | box, cyl          | all three kinds| OPEN only    | port only
    Elmer     | bare domain only  | none           | OPEN only    | port only
    OpenParEM | bare domain only  | none           | OPEN only    | port only
    NEC2      | wire-like only    | PERFECT only   | OPEN only    | either

TWO REAL GAPS THAT BUILDING THIS SURFACED, both now ticketed:

  - `simulation/openems.py` has NO boundary-condition handling at all (no
    periodic, no explicit PML) and NO plane-wave source -- it requires a
    lumped port. So an illuminated passive surface (absorber cell, FSS,
    reflectarray element) cannot run on openEMS here, and openEMS cannot be
    MEEP's FDTD cross-check partner for that entire class of problem. #538.
  - `simulation/gprmax.py`'s port is a driven `#transmission_line`
    excitation, so it too cannot be illuminated.

TWO KINDS OF CROSSING, and the difference is the whole point.

A CONVERSION preserves the physics and is done silently: a sheet resistance
of 188 ohm/sq on a 0.1 mm film IS a bulk conductivity of 53 S/m
(sigma = 1/(Rs*t)), so handing gprMax the bulk number loses nothing -- the
thickness it was measured at is still carried by the geometry itself.
Likewise an incidence angle IS a transverse wave vector (k = k0 sin(theta)),
which is exactly what Palace's Floquet port takes.

A DEGRADATION changes the physics and is refused: there is no sheet
resistance, and no conductivity, that a NEC2 `GW` card can express, so a
lossy conductor cannot cross into NEC at all. Translating it as a bare wire
would produce a lossless antenna that radiates everything it was designed to
absorb -- issue #230's defect, rebuilt in a new place.

MESHING IS NOT TRANSLATED, it is applied. `geometry.ir` deliberately carries
no mesh, because grid density is a numerical choice per solver rather than a
property of the object (see prototype/mesh-convergence/README.md and #540 for
why mixing the two is actively harmful). Every function here takes
`cells_per_wavelength` and sizes the target's own mesh from the model's
shortest in-material wavelength. The default of 20 is the ordinary FDTD rule
of thumb and is NOT a convergence-verified value for any particular model.
"""

from __future__ import annotations

import math
from typing import Any

from geometry.ir import (
    C_M_S,
    BoundaryKind,
    Box,
    Conductor,
    ConductorKind,
    Cylinder,
    Dielectric,
    LumpedPort,
    Model,
    PlaneWave,
    Polygon,
    UnrepresentableGeometry,
)

_AXIS_INDEX = {"x": 0, "y": 1, "z": 2}

#: Cells per shortest in-material wavelength, the ordinary FDTD rule of
#: thumb. Not convergence-verified for any particular model.
DEFAULT_CELLS_PER_WAVELENGTH = 20

#: Segments per wavelength for a NEC wire. NEC's own long-standing guidance
#: is that a driven wire wants segments no longer than about a tenth of a
#: wavelength; shorter is safer and costs only runtime.
DEFAULT_SEGMENTS_PER_WAVELENGTH = 10

# Plane placements for a MEEP illumination run, as fractions of the free-space
# wavelength inward from the absorbing layer's inner edge. These mirror the
# proportions of the committed reference case in
# verification/simulator_reference_cases.py (70 mm cell, 10 mm PML, source
# 2 mm inside, monitors 6 mm inside, at 10 GHz where lambda is 30 mm).
_SOURCE_INSET = 1.0 / 15.0
_MONITOR_INSET = 1.0 / 5.0
_STANDOFF = 0.5


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
def _cell_size_m(model: Model, cells_per_wavelength: int) -> float:
    """The grid step that puts `cells_per_wavelength` cells across the
    shortest wavelength present anywhere in the model."""
    if cells_per_wavelength < 1:
        raise ValueError("cells_per_wavelength must be >= 1")
    return model.band.shortest_wavelength_m(model.max_epsilon_r) / cells_per_wavelength


def _corner_box(
    center_m: tuple[float, float, float], size_m: tuple[float, float, float]
) -> tuple[list[float], list[float]]:
    """A centre-and-size box as the two-corner form every adapter here uses."""
    half = tuple(s / 2.0 for s in size_m)
    return (
        [c - h for c, h in zip(center_m, half, strict=True)],
        [c + h for c, h in zip(center_m, half, strict=True)],
    )


def _shape_dict(shape: Any, *, solver: str, allow: tuple[type, ...]) -> dict[str, Any]:
    """Render a shape into the box/cylinder/polygon primitive-dict vocabulary
    the volumetric adapters share, refusing a kind the target has no form for."""
    if not isinstance(shape, allow):
        raise UnrepresentableGeometry(
            solver=solver,
            what=f"a {type(shape).__name__} shape",
            why=f"{solver} accepts only {', '.join(t.__name__ for t in allow)}",
            instead=(
                "restate the region using a shape the target supports, or run this "
                "model on a solver that has one"
            ),
        )
    if isinstance(shape, Box):
        return {"shape": "box", "p1_m": list(shape.p1_m), "p2_m": list(shape.p2_m)}
    if isinstance(shape, Cylinder):
        return {
            "shape": "cylinder",
            "center_m": list(shape.center_m),
            "radius_m": shape.radius_m,
            "height_m": shape.height_m,
            "axis": shape.axis,
        }
    return {
        "shape": "polygon",
        "points_m": [list(p) for p in shape.points_m],
        "normal_axis": shape.normal_axis,
        "elevation_m": shape.elevation_m,
    }


def _tagged(out: dict[str, Any], region: Conductor | Dielectric) -> dict[str, Any]:
    """Carry the optional name and geometry-layer role through unchanged."""
    if region.name:
        out["name"] = region.name
    if region.role is not None:
        out["role"] = str(region.role)
    return out


def _dielectric_dict(d: Dielectric, *, solver: str, allow: tuple[type, ...]) -> dict[str, Any]:
    out = _shape_dict(d.shape, solver=solver, allow=allow)
    out.update({"epsilon_r": d.epsilon_r, "mue_r": d.mu_r, "loss_tangent": d.loss_tangent})
    return _tagged(out, d)


def _require_open(model: Model, *, solver: str, instead: str) -> None:
    if model.boundary is not BoundaryKind.OPEN:
        raise UnrepresentableGeometry(
            solver=solver,
            what=f"a {model.boundary} model",
            why=f"this repo's {solver} adapter implements no periodic-boundary construction",
            instead=instead,
        )


def _require_port(model: Model, *, solver: str, instead: str) -> LumpedPort:
    if not isinstance(model.excitation, LumpedPort):
        raise UnrepresentableGeometry(
            solver=solver,
            what="plane-wave illumination",
            why=(
                f"this repo's {solver} adapter is driven-source only -- it requires a "
                "port and has no incident-plane-wave construction, so an illuminated "
                "passive surface has no way to be excited at all"
            ),
            instead=instead,
        )
    return model.excitation


def _require_normal_incidence(wave: PlaneWave, *, solver: str) -> None:
    if wave.theta_deg or wave.phi_deg:
        raise UnrepresentableGeometry(
            solver=solver,
            what=f"illumination at theta={wave.theta_deg} deg, phi={wave.phi_deg} deg",
            why=(
                f"this repo's {solver} adapter builds a single plane source with no "
                "Bloch phase across it, so it can only illuminate at normal incidence; "
                "an oblique wave would silently become a normal one"
            ),
            instead=(
                "use Palace, whose Floquet port takes a transverse wave vector and so "
                "expresses incidence angle exactly"
            ),
        )


# ---------------------------------------------------------------------------
# openEMS -- FDTD, driven antennas in free space
# ---------------------------------------------------------------------------
def to_openems(
    model: Model,
    cells_per_wavelength: int = DEFAULT_CELLS_PER_WAVELENGTH,
) -> dict[str, Any]:
    """Render `model` as `simulation.openems.run_openems_simulation`'s geometry.

    openEMS splits conducting regions two ways, and the split is exactly this
    module's `ConductorKind`: an idealized PEC belongs in `conductors`, while
    anything with real loss belongs in `materials` carrying `kappa_s_m`. That
    is the adapter's own convention, not an invention here.

    Refuses anything but an OPEN, port-driven model, because that is all the
    adapter implements -- see #538 and this module's docstring.
    """
    port = _require_port(
        model,
        solver="openEMS",
        instead=(
            "use MEEP (built around exactly this) or Palace (Floquet ports) for an "
            "illuminated surface; openEMS here is for driven antennas"
        ),
    )
    _require_open(
        model,
        solver="openEMS",
        instead="use Palace for a periodic unit cell, or MEEP, which does set a k_point",
    )

    allow = (Box, Cylinder, Polygon)
    conductors: list[dict[str, Any]] = []
    materials: list[dict[str, Any]] = [
        _dielectric_dict(d, solver="openEMS", allow=allow) for d in model.dielectrics
    ]
    for c in model.conductors:
        primitive = _tagged(_shape_dict(c.shape, solver="openEMS", allow=allow), c)
        if c.kind is ConductorKind.PERFECT:
            conductors.append(primitive)
        else:
            # A CONVERSION, not a degradation: a finite conductivity is
            # exactly what openEMS's lossy-material kappa_s_m means.
            primitive["kappa_s_m"] = c.effective_conductivity_s_m()
            materials.append(primitive)

    p1, p2 = _corner_box(port.center_m, port.size_m)
    return {
        "mesh": _mesh_lines(model, _cell_size_m(model, cells_per_wavelength)),
        "frequency_hz": model.band.center_hz,
        "conductors": conductors,
        "materials": materials,
        "ports": [
            {
                "name": "port1",
                "p1_m": p1,
                "p2_m": p2,
                "direction": port.direction,
                "resistance_ohms": port.impedance_ohm,
                "excite": True,
            }
        ],
    }


def _mesh_lines(model: Model, step: float) -> dict[str, list[float]]:
    lines: dict[str, list[float]] = {}
    for axis, key in (("x", "x_lines_m"), ("y", "y_lines_m"), ("z", "z_lines_m")):
        i = _AXIS_INDEX[axis]
        lo = min(model.domain.p1_m[i], model.domain.p2_m[i])
        hi = max(model.domain.p1_m[i], model.domain.p2_m[i])
        count = max(2, int(math.ceil((hi - lo) / step)) + 1)
        lines[key] = [lo + (hi - lo) * n / (count - 1) for n in range(count)]
    return lines


# ---------------------------------------------------------------------------
# MEEP -- FDTD, illuminated surfaces
# ---------------------------------------------------------------------------
def to_meep(
    model: Model,
    cells_per_wavelength: int = DEFAULT_CELLS_PER_WAVELENGTH,
) -> dict[str, Any]:
    """Render `model` as `simulation.meep.run_meep_simulation`'s geometry.

    THE CELL IS NOT THE DOMAIN. A MEEP illumination run needs room along the
    propagation axis that the object itself does not occupy: an absorbing
    layer at each end, a source plane inside that, and monitor planes between
    the source and the structure and beyond it. So the emitted `cell_size_m`
    is the model's domain EXTENDED along z, and every coordinate is shifted
    into MEEP's origin-centred cell frame. The plane placements mirror the
    proportions of the committed reference case in
    `verification/simulator_reference_cases.py`.

    MEEP's own primitive parser handles boxes and cylinders only (there is no
    polygon branch), so a polygon is refused rather than approximated by a
    bounding box -- an approximated element is a different element.
    """
    if isinstance(model.excitation, LumpedPort):
        raise UnrepresentableGeometry(
            solver="MEEP",
            what="a driven lumped port",
            why=(
                "this repo's MEEP adapter drives a plane-wave reflectance/transmittance "
                "cross-check, not a fed antenna -- it has no lumped-port construction"
            ),
            instead="pose a driven antenna to openEMS or NEC2++, which do have ports",
        )
    _require_normal_incidence(model.excitation, solver="MEEP")

    allow = (Box, Cylinder)
    lambda_m = model.band.wavelength_m
    pml = _STANDOFF * lambda_m
    standoff = _STANDOFF * lambda_m

    lo = [min(a, b) for a, b in zip(model.domain.p1_m, model.domain.p2_m, strict=True)]
    hi = [max(a, b) for a, b in zip(model.domain.p1_m, model.domain.p2_m, strict=True)]
    sx, sy, _ = model.domain.extents_m
    cell_z = (hi[2] - lo[2]) + 2.0 * (pml + standoff)
    # Shift so the domain's own centre sits at the origin of MEEP's cell.
    shift = [-(a + b) / 2.0 for a, b in zip(lo, hi, strict=True)]

    conductors = [_meep_conductor(c, allow, shift) for c in model.conductors]
    if model.boundary is BoundaryKind.GROUND_BACKED:
        # openEMS and Palace each close the far z face; MEEP must too, or a
        # metal-backed absorber crosses as a free-standing sheet.
        conductors.append(_meep_ground_plane(sx, sy, hi[2] + shift[2]))

    z_inner = cell_z / 2.0 - pml
    geometry: dict[str, Any] = {
        "cell_size_m": [sx, sy, cell_z],
        "pml_thickness_m": pml,
        "mesh_cell_size_m": _cell_size_m(model, cells_per_wavelength),
        "materials": [
            _tagged(_shape_dict(d.shape, solver="MEEP", allow=allow) | _eps(d), d)
            for d in model.dielectrics
        ],
        "conductors": conductors,
        "frequency_hz": model.band.center_hz,
        "port": {
            "center_m": [0.0, 0.0, -z_inner + _SOURCE_INSET * lambda_m],
            "size_m": [0.0, 0.0, 0.0],
            "direction": "z",
            "component": "Ex",
            "frequency_hz": model.band.center_hz,
            "fractional_bandwidth": model.band.fractional_bandwidth or 0.2,
        },
        "reflection_monitor_center_m": [0.0, 0.0, -z_inner + _MONITOR_INSET * lambda_m],
        "reference_monitor_center_m": [0.0, 0.0, -z_inner + _MONITOR_INSET * lambda_m],
    }
    if model.boundary in (BoundaryKind.PERIODIC_XY, BoundaryKind.GROUND_BACKED):
        geometry["periodic_axes"] = ["x", "y"]
    if model.boundary is not BoundaryKind.GROUND_BACKED:
        # A ground-backed surface passes nothing through by construction, and
        # the adapter's own docstring says to leave the monitor out there.
        geometry["transmission_monitor_center_m"] = [
            0.0,
            0.0,
            z_inner - _MONITOR_INSET * lambda_m,
        ]
    return geometry


def _eps(d: Dielectric) -> dict[str, Any]:
    return {"epsilon_r": d.epsilon_r, "mue_r": d.mu_r, "loss_tangent": d.loss_tangent}


def _meep_ground_plane(sx: float, sy: float, z: float) -> dict[str, Any]:
    half_x = sx / 2.0 if sx else 1.0
    half_y = sy / 2.0 if sy else 1.0
    return {
        "shape": "box",
        "p1_m": [-half_x, -half_y, z],
        "p2_m": [half_x, half_y, z],
        "name": "ground",
        "role": "REFLECTOR",
    }


def _meep_conductor(c: Conductor, allow: tuple[type, ...], shift: list[float]) -> dict[str, Any]:
    out = _shifted_shape(_shape_dict(c.shape, solver="MEEP", allow=allow), shift)
    if c.kind is ConductorKind.SHEET_RESISTANCE:
        # Passed through as-is: MEEP's adapter takes sheet resistance natively
        # and does its own sigma = 1/(Rs*t), so handing it the derived bulk
        # number would route around the adapter's own tested path for no gain.
        out["sheet_resistance_ohm_sq"] = c.sheet_resistance_ohm_sq
        out["thickness_m"] = c.thickness_m
    elif c.kind is ConductorKind.BULK_CONDUCTIVITY:
        out["conductivity_s_m"] = c.conductivity_s_m
    return _tagged(out, c)


def _shifted_shape(primitive: dict[str, Any], shift: list[float]) -> dict[str, Any]:
    for key in ("p1_m", "p2_m", "center_m"):
        if key in primitive:
            primitive[key] = [v + s for v, s in zip(primitive[key], shift, strict=True)]
    return primitive


# ---------------------------------------------------------------------------
# Palace -- FEM, periodic unit cells, oblique incidence
# ---------------------------------------------------------------------------
def to_palace(
    model: Model,
    cells_per_wavelength: int = DEFAULT_CELLS_PER_WAVELENGTH,
) -> dict[str, Any]:
    """Render `model` as `simulation.palace.generate_palace_mesh`'s geometry.

    Palace is reached here through its Floquet-port unit-cell construction --
    the thing it is uniquely good at and the reason the adapter exists. That
    construction has no open-boundary form, so an OPEN model is refused rather
    than silently wrapped in periodicity it never asked for.

    Incidence angle is CONVERTED, not refused: a Floquet port takes a
    transverse wave vector, and an angle is exactly that
    (kx = k0 sin(theta) cos(phi), ky = k0 sin(theta) sin(phi)).
    """
    if model.boundary is BoundaryKind.OPEN:
        raise UnrepresentableGeometry(
            solver="Palace",
            what="an open-boundary (radiating) model",
            why=(
                "this repo's Palace adapter builds a periodic unit cell with Floquet "
                "ports on the z faces; it has no absorbing-boundary construction, so an "
                "open model would silently become one cell of an infinite array"
            ),
            instead=(
                "use openEMS or MEEP for a radiating model, or state the model as "
                "PERIODIC_XY if it really is one cell of an array"
            ),
        )
    if isinstance(model.excitation, LumpedPort):
        raise UnrepresentableGeometry(
            solver="Palace",
            what="a driven lumped port",
            why="the adapter excites a unit cell through its Floquet ports, not a feed",
            instead="pose a driven antenna to openEMS or NEC2++",
        )

    lx, ly, lz = model.domain.extents_m
    materials: list[dict[str, Any]] = []
    pec_patches: list[dict[str, Any]] = []

    for d in model.dielectrics:
        box = _require_box(d.shape, solver="Palace", role="a dielectric region")
        materials.append(
            _tagged(
                {
                    "p1_m": list(_shifted(box.p1_m, model)),
                    "p2_m": list(_shifted(box.p2_m, model)),
                    "epsilon_r": d.epsilon_r,
                    "mue_r": d.mu_r,
                    "loss_tan": d.loss_tangent,
                },
                d,
            )
        )

    for c in model.conductors:
        box = _require_box(c.shape, solver="Palace", role=f"a {c.kind} conductor")
        p1, p2 = list(_shifted(box.p1_m, model)), list(_shifted(box.p2_m, model))
        if c.kind is ConductorKind.PERFECT:
            if len(box.degenerate_axes) != 1:
                raise UnrepresentableGeometry(
                    solver="Palace",
                    what="a solid PEC conductor",
                    why=(
                        "Palace's pec_patches are flat interior boundary faces -- exactly "
                        "one axis must have zero thickness, and this shape has "
                        f"{len(box.degenerate_axes)}"
                    ),
                    instead=(
                        "state the conductor as a flat patch (one zero-thickness axis), "
                        "which is what a printed metal layer is"
                    ),
                )
            pec_patches.append(_tagged({"p1_m": p1, "p2_m": p2}, c))
        else:
            if box.degenerate_axes != ("z",):
                raise UnrepresentableGeometry(
                    solver="Palace",
                    what=f"a {c.kind} conductor lying in a non-z plane",
                    why=(
                        "the adapter's conductivity sheet must be flat in an x/y plane "
                        "(p1_m[2] == p2_m[2]); any other orientation is rejected rather "
                        "than silently reinterpreted"
                    ),
                    instead=(
                        "reorient the model so the printed layer lies in an x/y plane, "
                        "which is how a printed layer on a substrate actually sits"
                    ),
                )
            if c.thickness_m is None:
                raise UnrepresentableGeometry(
                    solver="Palace",
                    what=f"a {c.kind} conductor with no thickness_m",
                    why=(
                        "Palace's conductivity sheet is a zero-thickness face and needs "
                        "the real film thickness stated separately; there is nothing here "
                        "to derive it from"
                    ),
                    instead=(
                        "state the conductor as SHEET_RESISTANCE with its cured "
                        "thickness_m, which is how a print process specifies it anyway"
                    ),
                )
            materials.append(
                _tagged(
                    {
                        "p1_m": p1,
                        "p2_m": p2,
                        "kappa_s_m": c.effective_conductivity_s_m(),
                        "thickness_m": c.thickness_m,
                        "mue_r": 1.0,
                    },
                    c,
                )
            )

    step = _cell_size_m(model, cells_per_wavelength)
    return {
        "unit_cell": {"lx_m": lx, "ly_m": ly, "lz_m": lz},
        "materials": materials,
        "pec_patches": pec_patches,
        "ground_backed": model.boundary is BoundaryKind.GROUND_BACKED,
        "floquet": _floquet(model),
        "mesh": {
            "nx": max(1, int(math.ceil(lx / step))),
            "ny": max(1, int(math.ceil(ly / step))),
            "nz": max(1, int(math.ceil(lz / step))),
        },
    }


def _floquet(model: Model) -> dict[str, Any]:
    """Incidence angle as the transverse wave vector a Floquet port takes."""
    wave = model.excitation
    assert isinstance(wave, PlaneWave)  # guarded by the caller
    k0 = 2.0 * math.pi * model.band.center_hz / C_M_S
    theta = math.radians(wave.theta_deg)
    phi = math.radians(wave.phi_deg)
    kt = k0 * math.sin(theta)
    if wave.polarization_deg % 180.0 == 0.0:
        polarization = "TE"
    elif wave.polarization_deg % 180.0 == 90.0:
        polarization = "TM"
    else:
        raise UnrepresentableGeometry(
            solver="Palace",
            what=f"a polarization angle of {wave.polarization_deg} deg",
            why=(
                "the adapter's Floquet port takes a closed vocabulary (TE/TM/RHC/LHC), "
                "not an arbitrary angle, so this would be rounded to whichever is nearest"
            ),
            instead="state a polarization of 0 deg (TE) or 90 deg (TM)",
        )
    return {
        "wave_vector_1_per_m": [kt * math.cos(phi), kt * math.sin(phi), 0.0],
        "reference_frequency_hz": model.band.center_hz,
        "polarization": polarization,
    }


def _shifted(p: tuple[float, float, float], model: Model) -> tuple[float, float, float]:
    """Palace's unit cell is anchored at the origin (0..lx, 0..ly, 0..lz), so
    every coordinate is expressed relative to the domain's low corner."""
    lo = tuple(min(a, b) for a, b in zip(model.domain.p1_m, model.domain.p2_m, strict=True))
    return tuple(v - o for v, o in zip(p, lo, strict=True))  # type: ignore[return-value]


def _require_box(shape: Any, *, solver: str, role: str) -> Box:
    if not isinstance(shape, Box):
        raise UnrepresentableGeometry(
            solver=solver,
            what=f"{role} shaped as a {type(shape).__name__}",
            why=f"{solver}'s geometry is expressed entirely as axis-aligned p1_m/p2_m boxes",
            instead="restate the region as a box, or run this model on openEMS/MEEP",
        )
    return shape


# ---------------------------------------------------------------------------
# gprMax -- FDTD with a lossy half-space
# ---------------------------------------------------------------------------
def to_gprmax(
    model: Model,
    cells_per_wavelength: int = DEFAULT_CELLS_PER_WAVELENGTH,
) -> dict[str, Any]:
    """Render `model` as `simulation.gprmax`'s geometry.

    gprMax states every lossy material as a bulk conductivity, so a sheet
    resistance is CONVERTED (sigma = 1/(Rs*t)) rather than refused: the
    thickness it was measured at is still carried by the region's own
    geometry, so nothing about the physics is lost.
    """
    port = _require_port(
        model,
        solver="gprMax",
        instead="use MEEP or Palace for an illuminated surface",
    )
    _require_open(model, solver="gprMax", instead="use Palace for a periodic unit cell")

    allow = (Box, Cylinder)
    conductors: list[dict[str, Any]] = []
    materials: list[dict[str, Any]] = [
        _dielectric_dict(d, solver="gprMax", allow=allow) for d in model.dielectrics
    ]
    for c in model.conductors:
        primitive = _tagged(_shape_dict(c.shape, solver="gprMax", allow=allow), c)
        if c.kind is ConductorKind.PERFECT:
            conductors.append(primitive)
        else:
            primitive["conductivity_s_m"] = c.effective_conductivity_s_m()
            primitive["epsilon_r"] = 1.0
            materials.append(primitive)

    return {
        "domain_m": list(model.domain.extents_m),
        "resolution_m": _cell_size_m(model, cells_per_wavelength),
        "frequency_hz": model.band.center_hz,
        "materials": materials,
        "conductors": conductors,
        "port": {
            "polarization": port.direction,
            "position_m": list(port.center_m),
            "resistance_ohms": port.impedance_ohm,
            "center_frequency_hz": model.band.center_hz,
        },
    }


# ---------------------------------------------------------------------------
# Elmer and OpenParEM -- a single bulk box domain, and nothing in it
# ---------------------------------------------------------------------------
def to_elmer(
    model: Model,
    cells_per_wavelength: int = DEFAULT_CELLS_PER_WAVELENGTH,
) -> dict[str, Any]:
    """Render `model` as `simulation.elmer.generate_gmsh_geo_script`'s geometry.

    That generator builds ONE bulk box plus an optional excitation box. It has
    no materials list and no conductor list at all, so a model carrying either
    is refused -- translating it would produce an empty box wearing the name of
    a real design.
    """
    if model.conductors or model.dielectrics:
        raise UnrepresentableGeometry(
            solver="Elmer",
            what=(
                f"{len(model.conductors)} conductor(s) and "
                f"{len(model.dielectrics)} dielectric region(s)"
            ),
            why=(
                "this repo's Elmer adapter meshes a single homogeneous bulk box with an "
                "optional excitation volume; it has no way to place embedded regions, so "
                "every one of them would simply vanish"
            ),
            instead=(
                "use openEMS, MEEP or Palace for a structured model; Elmer's value here "
                "is a multiphysics cross-check on a bulk domain"
            ),
        )
    _require_open(model, solver="Elmer", instead="use Palace for a periodic unit cell")

    geometry: dict[str, Any] = {
        "domain": {"p1_m": list(model.domain.p1_m), "p2_m": list(model.domain.p2_m)},
        "mesh_max_size_m": _cell_size_m(model, cells_per_wavelength),
    }
    if isinstance(model.excitation, LumpedPort):
        p1, p2 = _corner_box(model.excitation.center_m, model.excitation.size_m)
        geometry["excitation"] = {"p1_m": p1, "p2_m": p2}
    return geometry


def to_openparem(
    model: Model,
    cells_per_wavelength: int = DEFAULT_CELLS_PER_WAVELENGTH,
) -> dict[str, Any]:
    """Render `model` as `simulation.openparem`'s geometry.

    OpenParEM3D takes either a pre-meshed Gmsh file or a `geometry` dict that
    it meshes by REUSING `simulation.elmer.generate_gmsh_geo_script` -- the
    same generator, so the same dict shape and the same limits apply. This is
    a thin alias rather than a second implementation, so the two cannot drift.
    """
    return to_elmer(model, cells_per_wavelength)


# ---------------------------------------------------------------------------
# NEC2++ -- wires, and only wires
# ---------------------------------------------------------------------------
def to_nec2(
    model: Model,
    segments_per_wavelength: int = DEFAULT_SEGMENTS_PER_WAVELENGTH,
) -> dict[str, Any]:
    """Render `model` as `simulation.nec2pp.generate_nec2_deck`'s geometry.

    THIS IS A MODELLING DECISION, NOT A TRANSLATION, and it is the one tier of
    this module that is not a lossless restatement -- see
    docs/adr/0052-volume-to-wire-is-a-modelling-decision-not-a-translation.md.
    A method-of-moments wire code represents conductors as one-dimensional
    filaments with a radius; a volumetric model has no filaments in it.
    Deciding which filament stands in for a solid is an RF judgment, so this
    function makes only the judgments it can defend and refuses the rest:

      - A `Cylinder` becomes a wire along its own centreline, with the
        cylinder's own radius. This is not an equivalence at all -- a thin
        cylindrical conductor IS what a NEC wire models -- so it is exact.
      - A `Box` becomes a wire ONLY if the caller has stated
        `equivalent_wire_radius_m` on it. The widely-used thin-strip rule is
        r_eq = w/4, but that is not applied on the caller's behalf here: it has
        not been read from a primary source in this repo, and silently applying
        an unverified equivalence is how a confident wrong number gets made.
      - Anything else -- a solid box, a polygon, a dielectric, a lossy
        conductor -- is refused.

    SEGMENTATION IS COMPUTED, NOT ACCEPTED. Every wire is segmented to at least
    `segments_per_wavelength` per wavelength, so a deck this function produces
    cannot violate the segmentation rule that `simulation/nec2pp.py` itself
    does not check (see #539).
    """
    if model.dielectrics:
        raise UnrepresentableGeometry(
            solver="NEC2",
            what=f"{len(model.dielectrics)} dielectric region(s)",
            why=(
                "a method-of-moments wire code has no volumetric dielectric -- this "
                "adapter emits GW wire cards and a GN ground card, nothing else"
            ),
            instead="use openEMS or MEEP, which model dielectric volumes directly",
        )
    _require_open(
        model,
        solver="NEC2",
        instead="use Palace, openEMS or MEEP for a periodic unit cell",
    )

    driven = isinstance(model.excitation, LumpedPort)
    lambda_m = model.band.shortest_wavelength_m(model.max_epsilon_r)
    max_segment_m = lambda_m / segments_per_wavelength

    wires: list[dict[str, Any]] = []
    for c in model.conductors:
        if c.is_lossy:
            raise UnrepresentableGeometry(
                solver="NEC2",
                what=f"a {c.kind} conductor",
                why=(
                    "NEC2 can only express an idealized lossless conductor, so this would "
                    "cross as perfect metal and reflect everything it was designed to "
                    "absorb (the defect recorded as issue #230)"
                ),
                instead=(
                    "model the loss with a NEC loading card (this adapter emits none), or "
                    "run the lossy design on MEEP/openEMS/Palace, which take a sheet "
                    "resistance directly"
                ),
            )
        wires.append(_wire_from(c, max_segment_m, driven=driven))

    if not wires:
        raise UnrepresentableGeometry(
            solver="NEC2",
            what="a model with no conductors",
            why="a NEC deck is made of wires; there is nothing here to make one from",
            instead=(
                "add at least one PERFECT conductor shaped as a cylinder, or as a box "
                "carrying equivalent_wire_radius_m"
            ),
        )

    geometry: dict[str, Any] = {"wires": wires, "ground_condition": "free_space"}
    if driven:
        geometry["excitation"] = {"type": "voltage", "voltage_real": 1.0, "voltage_imag": 0.0}
    else:
        wave = model.excitation
        assert isinstance(wave, PlaneWave)
        geometry["excitation"] = {
            "type": "plane_wave",
            "theta_start_deg": wave.theta_deg,
            "theta_count": 1,
            "phi_start_deg": wave.phi_deg,
            "phi_count": 1,
            "eta_deg": wave.polarization_deg,
        }
    return geometry


def _wire_from(c: Conductor, max_segment_m: float, *, driven: bool) -> dict[str, Any]:
    shape = c.shape
    if isinstance(shape, Cylinder):
        i = _AXIS_INDEX[shape.axis]
        p1, p2 = list(shape.center_m), list(shape.center_m)
        p1[i] -= shape.height_m / 2.0
        p2[i] += shape.height_m / 2.0
        return _wire_dict(p1, p2, shape.radius_m, max_segment_m, driven=driven)

    if isinstance(shape, Box):
        if shape.equivalent_wire_radius_m is None:
            raise UnrepresentableGeometry(
                solver="NEC2",
                what="a box conductor with no stated equivalent_wire_radius_m",
                why=(
                    "turning a flat strip into a filament needs an equivalent radius, and "
                    "this repo has not read a primary source for the common r_eq = w/4 "
                    "rule -- applying it unread would be inventing precision"
                ),
                instead=(
                    "state Box(equivalent_wire_radius_m=...) explicitly (w/4 is the usual "
                    "choice, and stating it makes it the caller's assumption rather than a "
                    "hidden one), or model the strip in openEMS/MEEP"
                ),
            )
        extents = shape.extents_m
        long_axis = max(range(3), key=lambda i: extents[i])
        if extents[long_axis] <= 0:
            raise UnrepresentableGeometry(
                solver="NEC2",
                what="a degenerate box conductor",
                why="it has no long axis to run a wire along",
                instead="give the conductor a non-zero length",
            )
        lo = [min(a, b) for a, b in zip(shape.p1_m, shape.p2_m, strict=True)]
        hi = [max(a, b) for a, b in zip(shape.p1_m, shape.p2_m, strict=True)]
        mid = [(a + b) / 2.0 for a, b in zip(lo, hi, strict=True)]
        p1, p2 = list(mid), list(mid)
        p1[long_axis] = lo[long_axis]
        p2[long_axis] = hi[long_axis]
        return _wire_dict(p1, p2, shape.equivalent_wire_radius_m, max_segment_m, driven=driven)

    raise UnrepresentableGeometry(
        solver="NEC2",
        what=f"a {type(shape).__name__} conductor",
        why="a NEC wire runs between two endpoints; a polygon has no single centreline",
        instead="decompose the outline into cylinders or boxes, one wire each",
    )


def _wire_dict(
    p1: list[float],
    p2: list[float],
    radius_m: float,
    max_segment_m: float,
    *,
    driven: bool,
) -> dict[str, Any]:
    length_m = math.dist(p1, p2)
    segments = max(1, int(math.ceil(length_m / max_segment_m)))
    # Only a DRIVEN wire needs an odd count, so the adapter's own midpoint
    # feed-segment default lands on a true centre. Forcing it on an
    # illuminated structure would be an unasked-for modelling choice.
    if driven and segments % 2 == 0:
        segments += 1
    return {
        "segments": segments,
        "x1_m": p1[0],
        "y1_m": p1[1],
        "z1_m": p1[2],
        "x2_m": p2[0],
        "y2_m": p2[1],
        "z2_m": p2[2],
        "radius_m": radius_m,
    }
