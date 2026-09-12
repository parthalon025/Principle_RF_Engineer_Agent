"""Translate one solver-independent `geometry.ir.Model` into each adapter's
own geometry dict -- or refuse, naming what could not survive the crossing.

WHAT EACH TARGET CAN AND CANNOT TAKE. This table is the module in summary;
every "no" below is a raised `UnrepresentableGeometry`, never a silent
substitution.

    target    | shapes            | conductors     | boundaries    | excited by
    ----------|-------------------|----------------|---------------|-----------
    openEMS   | box, cyl, polygon | all three kinds| open/per/gnd  | PORT only
    MEEP      | box, cyl          | all three kinds| open/per/gnd  | plane wave
    Palace    | box only          | all three kinds| per/gnd ONLY  | plane wave
    gprMax    | box, cyl          | all three kinds| open only     | either
    Elmer     | box domain only   | none           | open only     | either
    NEC2++    | wire-like only    | PERFECT only   | open only     | either

THAT "PORT only" ROW IS A REAL GAP, and building this module is how it
surfaced: this repo's openEMS adapter requires at least one lumped port and
has no incident-plane-wave construction at all. So an illuminated passive
surface -- an absorber cell, an FSS, a reflectarray element, most of what
this programme is actually for -- cannot be run on openEMS here. It is not
a limitation of openEMS itself, which does have plane-wave sources; it is
what this adapter was built to do. Worth a ticket, not a workaround.

TWO KINDS OF CROSSING, and the difference is the whole point.

A CONVERSION preserves the physics and is done silently: a sheet resistance
of 188 ohm/sq on a 0.1 mm film IS a bulk conductivity of 53 S/m
(sigma = 1/(Rs*t)), so handing gprMax the bulk number loses nothing -- the
thickness it was measured at is still carried by the geometry itself.

A DEGRADATION changes the physics and is refused: there is no sheet
resistance, and no conductivity, that a NEC2 `GW` card can express, so a
lossy conductor cannot cross into NEC at all. Translating it as a bare wire
would produce a lossless antenna that radiates everything it was designed to
absorb -- issue #230's defect, rebuilt in a new place.

MESHING IS NOT TRANSLATED, it is applied. `geometry.ir` deliberately carries
no mesh, because grid density is a numerical choice per solver rather than a
property of the object (see prototype/mesh-convergence/README.md for why
mixing the two is actively harmful). Every function here takes
`cells_per_wavelength` and sizes the target's own mesh from the model's
shortest in-material wavelength. The default of 20 is the ordinary FDTD
rule of thumb and is NOT a convergence-verified value for any particular
model -- run a convergence sweep rather than trusting it.
"""

from __future__ import annotations

import math
from typing import Any

from geometry.ir import (
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


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
def _cell_size_m(model: Model, cells_per_wavelength: int) -> float:
    """The grid step that puts `cells_per_wavelength` cells across the
    shortest wavelength present anywhere in the model."""
    if cells_per_wavelength < 1:
        raise ValueError("cells_per_wavelength must be >= 1")
    return model.band.shortest_wavelength_m(model.max_epsilon_r) / cells_per_wavelength


def _box_dict(box: Box) -> dict[str, Any]:
    return {"shape": "box", "p1_m": list(box.p1_m), "p2_m": list(box.p2_m)}


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
        return _box_dict(shape)
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


def _dielectric_dict(d: Dielectric, *, solver: str, allow: tuple[type, ...]) -> dict[str, Any]:
    out = _shape_dict(d.shape, solver=solver, allow=allow)
    out.update({"epsilon_r": d.epsilon_r, "mue_r": d.mu_r, "loss_tangent": d.loss_tangent})
    if d.name:
        out["name"] = d.name
    return out


def _refuse_lossy(conductor: Conductor, *, solver: str, instead: str) -> None:
    if conductor.is_lossy:
        raise UnrepresentableGeometry(
            solver=solver,
            what=f"a {conductor.kind} conductor",
            why=(
                f"{solver} can only express an idealized lossless conductor, so this "
                "would cross as perfect metal and reflect everything it was designed "
                "to absorb (the defect recorded as issue #230)"
            ),
            instead=instead,
        )


# ---------------------------------------------------------------------------
# openEMS -- FDTD, the most expressive target here
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
    """
    if isinstance(model.excitation, PlaneWave):
        raise UnrepresentableGeometry(
            solver="openEMS",
            what="plane-wave illumination",
            why=(
                "this repo's openEMS adapter is lumped-port only -- it requires at "
                "least one port and has no incident-plane-wave construction, so an "
                "illuminated passive surface has no way to be excited at all"
            ),
            instead=(
                "use MEEP (whose adapter is built around exactly this) or Palace "
                "(Floquet ports) for an illuminated surface; openEMS here is for "
                "driven antennas"
            ),
        )
    allow = (Box, Cylinder, Polygon)
    step = _cell_size_m(model, cells_per_wavelength)

    conductors: list[dict[str, Any]] = []
    materials: list[dict[str, Any]] = [
        _dielectric_dict(d, solver="openEMS", allow=allow) for d in model.dielectrics
    ]
    for c in model.conductors:
        primitive = _shape_dict(c.shape, solver="openEMS", allow=allow)
        if c.kind is ConductorKind.PERFECT:
            conductors.append(primitive)
        else:
            # A CONVERSION, not a degradation: a finite conductivity is
            # exactly what openEMS's lossy-material kappa_s_m means.
            primitive["kappa_s_m"] = c.effective_conductivity_s_m()
            materials.append(primitive)

    geometry: dict[str, Any] = {
        "mesh": _mesh_lines(model, step),
        "frequency_hz": model.band.center_hz,
        "conductors": conductors,
        "materials": materials,
        "ports": _openems_ports(model),
    }
    if model.boundary in (BoundaryKind.PERIODIC_XY, BoundaryKind.GROUND_BACKED):
        geometry["periodic_axes"] = ["x", "y"]
    if model.boundary is BoundaryKind.GROUND_BACKED:
        geometry["conductors"] = [*conductors, _ground_plane_dict(model)]
    return geometry


def _mesh_lines(model: Model, step: float) -> dict[str, list[float]]:
    lines: dict[str, list[float]] = {}
    for axis, key in (("x", "x_lines_m"), ("y", "y_lines_m"), ("z", "z_lines_m")):
        i = _AXIS_INDEX[axis]
        lo = min(model.domain.p1_m[i], model.domain.p2_m[i])
        hi = max(model.domain.p1_m[i], model.domain.p2_m[i])
        count = max(2, int(math.ceil((hi - lo) / step)) + 1)
        lines[key] = [lo + (hi - lo) * n / (count - 1) for n in range(count)]
    return lines


def _ground_plane_dict(model: Model) -> dict[str, Any]:
    """The PEC termination a GROUND_BACKED model carries on its far z face."""
    x1, y1, _ = model.domain.p1_m
    x2, y2, _ = model.domain.p2_m
    z_hi = max(model.domain.p1_m[2], model.domain.p2_m[2])
    return {"shape": "box", "p1_m": [x1, y1, z_hi], "p2_m": [x2, y2, z_hi], "name": "ground"}


def _openems_ports(model: Model) -> list[dict[str, Any]]:
    p = model.excitation
    if not isinstance(p, LumpedPort):  # pragma: no cover -- guarded above
        return []
    half = tuple(s / 2.0 for s in p.size_m)
    return [
        {
            "name": "port1",
            "p1_m": [c - h for c, h in zip(p.center_m, half, strict=True)],
            "p2_m": [c + h for c, h in zip(p.center_m, half, strict=True)],
            "direction": p.direction,
            "resistance_ohms": p.impedance_ohm,
            "excite": True,
        }
    ]


# ---------------------------------------------------------------------------
# MEEP -- FDTD, no polygon primitive
# ---------------------------------------------------------------------------
def to_meep(
    model: Model,
    cells_per_wavelength: int = DEFAULT_CELLS_PER_WAVELENGTH,
) -> dict[str, Any]:
    """Render `model` as `simulation.meep.run_meep_simulation`'s geometry.

    MEEP's own primitive parser handles boxes and cylinders only (there is no
    polygon branch), so a polygon is refused rather than approximated by a
    bounding box -- an approximated element is a different element.
    """
    allow = (Box, Cylinder)
    if isinstance(model.excitation, LumpedPort):
        raise UnrepresentableGeometry(
            solver="MEEP",
            what="a driven lumped port",
            why=(
                "this repo's MEEP adapter drives a plane-wave reflectance/"
                "transmittance cross-check, not a fed antenna -- it has no lumped-port "
                "construction at all"
            ),
            instead="pose a driven antenna to openEMS or NEC2++, which do have ports",
        )

    domain = model.domain
    extents = domain.extents_m
    pml = (
        0.0
        if model.boundary in (BoundaryKind.PERIODIC_XY, BoundaryKind.GROUND_BACKED)
        else (model.band.wavelength_m / 2.0)
    )
    geometry: dict[str, Any] = {
        "cell_size_m": list(extents),
        "pml_thickness_m": pml,
        "mesh_cell_size_m": _cell_size_m(model, cells_per_wavelength),
        "materials": [_dielectric_dict(d, solver="MEEP", allow=allow) for d in model.dielectrics],
        "conductors": [_meep_conductor(c, allow) for c in model.conductors],
        "frequency_hz": model.band.center_hz,
    }
    if model.boundary in (BoundaryKind.PERIODIC_XY, BoundaryKind.GROUND_BACKED):
        geometry["periodic_axes"] = ["x", "y"]
    return geometry


def _meep_conductor(c: Conductor, allow: tuple[type, ...]) -> dict[str, Any]:
    out = _shape_dict(c.shape, solver="MEEP", allow=allow)
    if c.kind is ConductorKind.SHEET_RESISTANCE:
        # Passed through as-is: MEEP's adapter takes sheet resistance
        # natively and does its own sigma = 1/(Rs*t) conversion, so handing
        # it the derived bulk number instead would route around the
        # adapter's own tested path for no gain.
        out["sheet_resistance_ohm_sq"] = c.sheet_resistance_ohm_sq
        out["thickness_m"] = c.thickness_m
    elif c.kind is ConductorKind.BULK_CONDUCTIVITY:
        out["conductivity_s_m"] = c.conductivity_s_m
    if c.name:
        out["name"] = c.name
    return out


# ---------------------------------------------------------------------------
# Palace -- FEM, periodic unit cells only
# ---------------------------------------------------------------------------
def to_palace(
    model: Model,
    cells_per_wavelength: int = DEFAULT_CELLS_PER_WAVELENGTH,
) -> dict[str, Any]:
    """Render `model` as `simulation.palace.generate_palace_mesh`'s geometry.

    Palace is reached here through its Floquet-port unit-cell construction --
    the thing it is uniquely good at and the reason the adapter exists. That
    construction has no open-boundary form, so an OPEN model is refused
    rather than silently wrapped in periodicity it never asked for.
    """
    if model.boundary is BoundaryKind.OPEN:
        raise UnrepresentableGeometry(
            solver="Palace",
            what="an open-boundary (radiating) model",
            why=(
                "this repo's Palace adapter builds a periodic unit cell with Floquet "
                "ports on the z faces; it has no absorbing-boundary construction, so "
                "an open model would silently become one cell of an infinite array"
            ),
            instead="use openEMS or MEEP for a radiating model, or state the model as "
            "PERIODIC_XY if it really is one cell of an array",
        )

    lx, ly, lz = model.domain.extents_m
    materials: list[dict[str, Any]] = []
    pec_patches: list[dict[str, Any]] = []

    for d in model.dielectrics:
        box = _require_box(d.shape, solver="Palace", role="a dielectric region")
        entry: dict[str, Any] = {
            "p1_m": list(_shifted(box.p1_m, model)),
            "p2_m": list(_shifted(box.p2_m, model)),
            "epsilon_r": d.epsilon_r,
            "mue_r": d.mu_r,
            "loss_tan": d.loss_tangent,
        }
        if d.name:
            entry["name"] = d.name
        materials.append(entry)

    for c in model.conductors:
        box = _require_box(c.shape, solver="Palace", role=f"a {c.kind} conductor")
        p1, p2 = _shifted(box.p1_m, model), _shifted(box.p2_m, model)
        if c.kind is ConductorKind.PERFECT:
            if len(box.degenerate_axes) != 1:
                raise UnrepresentableGeometry(
                    solver="Palace",
                    what="a solid PEC conductor",
                    why=(
                        "Palace's pec_patches are flat interior boundary faces -- "
                        "exactly one axis must have zero thickness, and this shape has "
                        f"{len(box.degenerate_axes)}"
                    ),
                    instead="state the conductor as a flat patch (one zero-thickness "
                    "axis), which is what a printed metal layer is",
                )
            entry = {"p1_m": list(p1), "p2_m": list(p2)}
            if c.name:
                entry["name"] = c.name
            pec_patches.append(entry)
        else:
            # Palace's conductivity sheet is z-normal only, and requires the
            # thickness the conductivity was measured at.
            if box.degenerate_axes != ("z",):
                raise UnrepresentableGeometry(
                    solver="Palace",
                    what=f"a {c.kind} conductor lying in a non-z plane",
                    why=(
                        "the adapter's conductivity sheet must be flat in an x/y plane "
                        "(p1_m[2] == p2_m[2]); any other orientation is rejected rather "
                        "than silently reinterpreted"
                    ),
                    instead="reorient the model so the printed layer lies in an x/y "
                    "plane, which is how a printed layer on a substrate actually sits",
                )
            entry = {
                "p1_m": list(p1),
                "p2_m": list(p2),
                "kappa_s_m": c.effective_conductivity_s_m(),
                "thickness_m": c.thickness_m if c.thickness_m else _implied_thickness(c),
                "mue_r": 1.0,
            }
            if c.name:
                entry["name"] = c.name
            materials.append(entry)

    step = _cell_size_m(model, cells_per_wavelength)
    return {
        "unit_cell": {"lx_m": lx, "ly_m": ly, "lz_m": lz},
        "materials": materials,
        "pec_patches": pec_patches,
        "ground_backed": model.boundary is BoundaryKind.GROUND_BACKED,
        "mesh": {
            "nx": max(1, int(math.ceil(lx / step))),
            "ny": max(1, int(math.ceil(ly / step))),
            "nz": max(1, int(math.ceil(lz / step))),
        },
    }


def _implied_thickness(c: Conductor) -> float:
    """A BULK_CONDUCTIVITY conductor stated as a zero-thickness sheet has no
    thickness of its own; Palace requires one. Refuse rather than invent."""
    raise UnrepresentableGeometry(
        solver="Palace",
        what="a BULK_CONDUCTIVITY conductor with no thickness_m",
        why=(
            "Palace's conductivity sheet is a zero-thickness face and needs the real "
            "film thickness stated separately; there is nothing to derive it from"
        ),
        instead="state the conductor as SHEET_RESISTANCE with its cured thickness_m, "
        "which is how a print process specifies it anyway",
    )


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
    if model.boundary is not BoundaryKind.OPEN:
        raise UnrepresentableGeometry(
            solver="gprMax",
            what=f"a {model.boundary} model",
            why="this repo's gprMax adapter builds an open domain with a lossy "
            "half-space; it exposes no periodic boundary",
            instead="use Palace, openEMS or MEEP for a periodic unit cell",
        )
    allow = (Box, Cylinder)
    step = _cell_size_m(model, cells_per_wavelength)
    conductors: list[dict[str, Any]] = []
    materials: list[dict[str, Any]] = [
        _dielectric_dict(d, solver="gprMax", allow=allow) for d in model.dielectrics
    ]
    for c in model.conductors:
        primitive = _shape_dict(c.shape, solver="gprMax", allow=allow)
        if c.kind is ConductorKind.PERFECT:
            conductors.append(primitive)
        else:
            primitive["conductivity_s_m"] = c.effective_conductivity_s_m()
            primitive["epsilon_r"] = 1.0
            materials.append(primitive)

    return {
        "domain_m": list(model.domain.extents_m),
        "resolution_m": step,
        "frequency_hz": model.band.center_hz,
        "materials": materials,
        "conductors": conductors,
    }


# ---------------------------------------------------------------------------
# Elmer -- a single box domain, and nothing in it
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
    if model.boundary is not BoundaryKind.OPEN:
        raise UnrepresentableGeometry(
            solver="Elmer",
            what=f"a {model.boundary} model",
            why="the adapter exposes no periodic boundary construction",
            instead="use Palace for a periodic unit cell",
        )
    geometry: dict[str, Any] = {
        "domain": {"p1_m": list(model.domain.p1_m), "p2_m": list(model.domain.p2_m)},
        "mesh_max_size_m": _cell_size_m(model, cells_per_wavelength),
    }
    if isinstance(model.excitation, LumpedPort):
        p = model.excitation
        half = tuple(s / 2.0 for s in p.size_m)
        geometry["excitation"] = {
            "p1_m": [c - h for c, h in zip(p.center_m, half, strict=True)],
            "p2_m": [c + h for c, h in zip(p.center_m, half, strict=True)],
        }
    return geometry


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
    docs/adr/0052-volume-to-wire-is-a-modelling-decision.md. A method-of-moments
    wire code represents conductors as one-dimensional filaments with a radius;
    a volumetric model has no filaments in it. Deciding which filament stands in
    for a solid is an RF judgment, so this function makes only the judgments it
    can defend and refuses the rest:

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
    does not check (see docs/antenna-software-comparison.md section 2.1).
    """
    if model.dielectrics:
        raise UnrepresentableGeometry(
            solver="NEC2++",
            what=f"{len(model.dielectrics)} dielectric region(s)",
            why=(
                "a method-of-moments wire code has no volumetric dielectric -- this "
                "adapter emits GW wire cards and a GN ground card, nothing else"
            ),
            instead="use openEMS or MEEP, which model dielectric volumes directly",
        )
    if model.boundary is not BoundaryKind.OPEN:
        raise UnrepresentableGeometry(
            solver="NEC2++",
            what=f"a {model.boundary} model",
            why="NEC2 models a finite structure in free space or over ground; it has "
            "no periodic unit cell",
            instead="use Palace, openEMS or MEEP for a periodic unit cell",
        )

    lambda_m = model.band.shortest_wavelength_m(model.max_epsilon_r)
    max_segment_m = lambda_m / segments_per_wavelength

    wires: list[dict[str, Any]] = []
    for c in model.conductors:
        _refuse_lossy(
            c,
            solver="NEC2++",
            instead=(
                "model the loss with a NEC loading card (this adapter emits none), or "
                "run the lossy design on MEEP/openEMS/Palace, which take a sheet "
                "resistance directly"
            ),
        )
        wires.append(_wire_from(c, max_segment_m))

    if not wires:
        raise UnrepresentableGeometry(
            solver="NEC2++",
            what="a model with no conductors",
            why="a NEC deck is made of wires; there is nothing here to make one from",
            instead="add at least one PERFECT conductor shaped as a cylinder, or as a "
            "box carrying equivalent_wire_radius_m",
        )

    geometry: dict[str, Any] = {"wires": wires, "ground_condition": "free_space"}
    if isinstance(model.excitation, PlaneWave):
        geometry["excitation"] = {
            "type": "plane_wave",
            "theta_start_deg": model.excitation.theta_deg,
            "theta_count": 1,
            "phi_start_deg": model.excitation.phi_deg,
            "phi_count": 1,
            "eta_deg": model.excitation.polarization_deg,
        }
    else:
        geometry["excitation"] = {"type": "voltage", "voltage_real": 1.0, "voltage_imag": 0.0}
    return geometry


def _wire_from(c: Conductor, max_segment_m: float) -> dict[str, Any]:
    shape = c.shape
    if isinstance(shape, Cylinder):
        i = _AXIS_INDEX[shape.axis]
        p1 = list(shape.center_m)
        p2 = list(shape.center_m)
        p1[i] -= shape.height_m / 2.0
        p2[i] += shape.height_m / 2.0
        return _wire_dict(p1, p2, shape.radius_m, max_segment_m)

    if isinstance(shape, Box):
        if shape.equivalent_wire_radius_m is None:
            raise UnrepresentableGeometry(
                solver="NEC2++",
                what="a box conductor with no stated equivalent_wire_radius_m",
                why=(
                    "turning a flat strip into a filament needs an equivalent radius, "
                    "and this repo has not read a primary source for the common "
                    "r_eq = w/4 rule -- applying it unread would be inventing precision"
                ),
                instead=(
                    "state Box(equivalent_wire_radius_m=...) explicitly (w/4 is the "
                    "usual choice, and stating it makes it the caller's assumption "
                    "rather than a hidden one), or model the strip in openEMS/MEEP"
                ),
            )
        extents = shape.extents_m
        long_axis = max(range(3), key=lambda i: extents[i])
        if extents[long_axis] <= 0:
            raise UnrepresentableGeometry(
                solver="NEC2++",
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
        return _wire_dict(p1, p2, shape.equivalent_wire_radius_m, max_segment_m)

    raise UnrepresentableGeometry(
        solver="NEC2++",
        what=f"a {type(shape).__name__} conductor",
        why="a NEC wire runs between two endpoints; a polygon has no single centreline",
        instead="decompose the outline into cylinders or boxes, one wire each",
    )


def _wire_dict(
    p1: list[float], p2: list[float], radius_m: float, max_segment_m: float
) -> dict[str, Any]:
    length_m = math.dist(p1, p2)
    segments = max(1, int(math.ceil(length_m / max_segment_m)))
    # NEC's thin-wire kernel wants an odd segment count on a driven wire so a
    # feed lands on a true centre segment; rounding up costs one segment.
    if segments % 2 == 0:
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
