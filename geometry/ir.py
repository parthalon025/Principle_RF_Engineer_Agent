"""A solver-independent geometry intermediate representation, and the one
rule that makes translating between solvers safe.

WHY THIS EXISTS. Six solver adapters in `simulation/` each take their own
geometry dict, and their FIELD NAMES already agree -- deliberately, by
convention: `simulation/palace.py`'s docstring says its `kappa_s_m` is
"the same field name and physical quantity simulation/openems.py's own
lossy materials entries already use", and the three volumetric adapters
cite each other by name when justifying a convention. What does NOT agree
is MEANING, and that is where translation goes wrong:

    openEMS  "conductors"                 -> idealized PEC
    Palace   "pec_patches"                -> idealized PEC, flat, any axis
    Palace   "materials" with kappa_s_m   -> REAL finite conductivity,
                                             z-normal only, thickness_m
                                             required
    MEEP     "conductors"                 -> PEC, or finite conductivity,
                                             or a sheet resistance

So the same word names an ideal lossless mirror in one adapter and a real
lossy film in another. A translator that maps field names would map a MEEP
conductor carrying `sheet_resistance_ohm_sq` onto a Palace `pec_patch` and
silently turn a designed absorber into a perfect reflector -- which is
EXACTLY the defect issue #230 already recorded once in this repo: "a sheet
modelled as ideal perfect metal, which reflects everything and absorbs
nothing however it was designed."

THE RULE THIS MODULE IS BUILT AROUND. `ConductorKind` is a REQUIRED,
explicitly-tagged field on every conductor. There is no default, and
"perfect" is a choice a caller has to make rather than what they get by
leaving a field out. An optional `conductivity_s_m` that a translator may
quietly ignore is the shape of the #230 defect; a required tag is not
ignorable, because a translator that does not handle a kind cannot compile
past its own match.

AND WHEN A TARGET CANNOT EXPRESS THE SOURCE: refuse. `UnrepresentableGeometry`
is raised, naming the field that cannot survive the crossing and what to do
instead. This is deliberately NOT ADR-0028's "warn, never block" -- that
rule governs withholding a CANDIDATE from a human reader, who can see the
warning and judge it. Nothing reads a warning here: a degraded geometry
goes straight into a solver and comes back as a confident `SIMULATED`
number that no human ever inspects. Emitting it would manufacture false
evidence, which is the one thing this project's provenance ladder exists to
prevent.

*In plain terms: every simulator describes the same object in its own
dialect, and some dialects have no word for "slightly lossy metal". Rather
than translate that as "metal" and quietly change the physics, this refuses
to translate at all and says which word was missing.*

SCOPE. This describes GEOMETRY, EXCITATION and BOUNDARIES -- what the
object is, how it is illuminated, and what surrounds it. It deliberately
does NOT describe meshing: grid density is a numerical choice per solver,
not a property of the object, and conflating the two is what makes a mesh
setting look like a design variable (see
prototype/mesh-convergence/README.md). Each translator applies its own
solver's meshing convention.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal

Axis = Literal["x", "y", "z"]
_AXES: tuple[Axis, ...] = ("x", "y", "z")
_AXIS_INDEX = {"x": 0, "y": 1, "z": 2}

#: Speed of light, m/s. Same constant every other module here uses.
C_M_S = 299_792_458.0


class UnrepresentableGeometry(Exception):
    """A model cannot cross into a target solver without changing physics.

    Carries the four things a caller needs to act, in the same shape
    `simulation/conservation_checks.py` uses for its soft warnings -- except
    that this one is raised rather than attached, for the reason in this
    module's docstring.
    """

    def __init__(self, *, solver: str, what: str, why: str, instead: str) -> None:
        self.solver = solver
        self.what = what
        self.why = why
        self.instead = instead
        super().__init__(f"{solver} cannot represent {what}: {why}. Instead: {instead}")


# ---------------------------------------------------------------------------
# Shapes
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Box:
    """An axis-aligned box, by two opposite corners, in metres.

    `equivalent_wire_radius_m` is the ONE field here that is not a fact
    about the box: it is a caller's stated thin-strip-to-wire equivalent
    radius, needed only when this box is to be posed to a wire-only solver
    (NEC). It is required rather than derived on purpose -- see
    `translate.to_nec2` and docs/adr/0052 for why this repo will not apply
    the common w/4 rule on the caller's behalf.
    """

    p1_m: tuple[float, float, float]
    p2_m: tuple[float, float, float]
    equivalent_wire_radius_m: float | None = None

    def __post_init__(self) -> None:
        for name, p in (("p1_m", self.p1_m), ("p2_m", self.p2_m)):
            if len(p) != 3 or not all(math.isfinite(v) for v in p):
                raise ValueError(f"Box.{name} must be three finite numbers, got {p!r}")
        if self.equivalent_wire_radius_m is not None and self.equivalent_wire_radius_m <= 0:
            raise ValueError("Box.equivalent_wire_radius_m must be > 0 when given")

    @property
    def extents_m(self) -> tuple[float, float, float]:
        return tuple(abs(b - a) for a, b in zip(self.p1_m, self.p2_m, strict=True))  # type: ignore[return-value]

    @property
    def degenerate_axes(self) -> tuple[Axis, ...]:
        """The axes along which this box has zero thickness -- i.e. the box
        is a flat face (one axis) or a line (two)."""
        return tuple(a for a in _AXES if self.extents_m[_AXIS_INDEX[a]] == 0.0)


@dataclass(frozen=True)
class Cylinder:
    """A circular cylinder about an axis-aligned centreline, in metres."""

    center_m: tuple[float, float, float]
    radius_m: float
    height_m: float
    axis: Axis = "z"

    def __post_init__(self) -> None:
        if self.radius_m <= 0 or self.height_m <= 0:
            raise ValueError("Cylinder radius_m and height_m must both be > 0")
        if self.axis not in _AXES:
            raise ValueError(f"Cylinder.axis must be one of {_AXES}, got {self.axis!r}")


@dataclass(frozen=True)
class Polygon:
    """A flat polygon lying in a plane normal to `normal_axis`, in metres."""

    points_m: tuple[tuple[float, float], ...]
    normal_axis: Axis = "z"
    elevation_m: float = 0.0

    def __post_init__(self) -> None:
        if len(self.points_m) < 3:
            raise ValueError("Polygon needs at least three points")
        if self.normal_axis not in _AXES:
            raise ValueError(f"Polygon.normal_axis must be one of {_AXES}")


Shape = Box | Cylinder | Polygon


# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------
class ConductorKind(StrEnum):
    """How a conductor conducts. REQUIRED on every conductor -- see this
    module's docstring for why this is a tag and not an optional field.

    PERFECT           -- an idealized lossless mirror (PEC). Right for a
                         ground plane; wrong for anything meant to absorb.
    BULK_CONDUCTIVITY -- a real material with a finite conductivity in S/m.
    SHEET_RESISTANCE  -- a printed film stated the way a print process
                         actually specifies it: ohms per square, plus the
                         cured thickness it was measured at.
    """

    PERFECT = "PERFECT"
    BULK_CONDUCTIVITY = "BULK_CONDUCTIVITY"
    SHEET_RESISTANCE = "SHEET_RESISTANCE"


@dataclass(frozen=True)
class Conductor:
    """A conducting region. `kind` is required and decides which of the
    other fields must be present."""

    shape: Shape
    kind: ConductorKind
    conductivity_s_m: float | None = None
    sheet_resistance_ohm_sq: float | None = None
    thickness_m: float | None = None
    name: str | None = None

    def __post_init__(self) -> None:
        if self.kind is ConductorKind.BULK_CONDUCTIVITY:
            if not self.conductivity_s_m or self.conductivity_s_m <= 0:
                raise ValueError("BULK_CONDUCTIVITY needs conductivity_s_m > 0")
        elif self.kind is ConductorKind.SHEET_RESISTANCE:
            if not self.sheet_resistance_ohm_sq or self.sheet_resistance_ohm_sq <= 0:
                raise ValueError("SHEET_RESISTANCE needs sheet_resistance_ohm_sq > 0")
            if not self.thickness_m or self.thickness_m <= 0:
                raise ValueError(
                    "SHEET_RESISTANCE needs thickness_m > 0 -- ohms-per-square is "
                    "meaningless without the cured thickness it was measured at"
                )
        elif self.kind is ConductorKind.PERFECT:
            if self.conductivity_s_m or self.sheet_resistance_ohm_sq:
                raise ValueError(
                    "PERFECT is an idealized lossless conductor and cannot also "
                    "carry a conductivity or a sheet resistance -- pick the kind "
                    "that describes what this actually is"
                )

    @property
    def is_lossy(self) -> bool:
        return self.kind is not ConductorKind.PERFECT

    def effective_conductivity_s_m(self) -> float:
        """Bulk conductivity in S/m, converting from sheet resistance when
        that is how the conductor was stated: sigma = 1 / (Rs * t). This is
        the same conversion `simulation/meep.py` already applies."""
        if self.kind is ConductorKind.BULK_CONDUCTIVITY:
            return float(self.conductivity_s_m)  # type: ignore[arg-type]
        if self.kind is ConductorKind.SHEET_RESISTANCE:
            return 1.0 / (float(self.sheet_resistance_ohm_sq) * float(self.thickness_m))  # type: ignore[arg-type]
        raise ValueError("a PERFECT conductor has no finite conductivity")


@dataclass(frozen=True)
class Dielectric:
    """A dielectric (optionally lossy) region."""

    shape: Shape
    epsilon_r: float = 1.0
    mu_r: float = 1.0
    loss_tangent: float = 0.0
    name: str | None = None

    def __post_init__(self) -> None:
        if self.epsilon_r <= 0 or self.mu_r <= 0:
            raise ValueError("Dielectric epsilon_r and mu_r must both be > 0")
        if self.loss_tangent < 0:
            raise ValueError("Dielectric loss_tangent must be >= 0")


# ---------------------------------------------------------------------------
# Excitation, boundaries, band
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PlaneWave:
    """An incident linearly-polarized plane wave -- how a passive surface
    (absorber, reflector, FSS) is illuminated."""

    theta_deg: float = 0.0
    phi_deg: float = 0.0
    polarization_deg: float = 0.0


@dataclass(frozen=True)
class LumpedPort:
    """A driven port -- how an antenna is fed."""

    center_m: tuple[float, float, float]
    size_m: tuple[float, float, float]
    direction: Axis
    impedance_ohm: float = 50.0


Excitation = PlaneWave | LumpedPort


class BoundaryKind(StrEnum):
    """What surrounds the model.

    OPEN          -- radiating into free space (absorbing/PML on all sides).
    PERIODIC_XY   -- one cell of an infinite planar array, repeating in x/y.
    GROUND_BACKED -- PERIODIC_XY with the far z face closed by a PEC ground.
    """

    OPEN = "OPEN"
    PERIODIC_XY = "PERIODIC_XY"
    GROUND_BACKED = "GROUND_BACKED"


@dataclass(frozen=True)
class Band:
    """The frequency band of interest, as a centre and a fractional width.

    A band, never a point -- the same discipline
    `designs/material_properties.py` and `designs/element_alphabet.py`
    already apply to every stored frequency.
    """

    center_hz: float
    fractional_bandwidth: float = 0.2

    def __post_init__(self) -> None:
        if self.center_hz <= 0:
            raise ValueError("Band.center_hz must be > 0")
        if not 0.0 <= self.fractional_bandwidth < 2.0:
            raise ValueError("Band.fractional_bandwidth must be in [0, 2)")

    @property
    def wavelength_m(self) -> float:
        """Free-space wavelength at the band centre."""
        return C_M_S / self.center_hz

    def shortest_wavelength_m(self, max_epsilon_r: float = 1.0) -> float:
        """The shortest wavelength anywhere in the band, in the densest
        material present -- the length every meshing and segmentation rule
        is actually measured against."""
        highest_hz = self.center_hz * (1.0 + self.fractional_bandwidth / 2.0)
        return C_M_S / (highest_hz * math.sqrt(max_epsilon_r))


# ---------------------------------------------------------------------------
# The model
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Model:
    """One electromagnetic problem, stated once, independent of any solver.

    `domain` is the bounding box the whole problem lives in. For a
    PERIODIC_XY or GROUND_BACKED model it is the unit cell itself.
    """

    domain: Box
    band: Band
    excitation: Excitation
    boundary: BoundaryKind = BoundaryKind.OPEN
    conductors: tuple[Conductor, ...] = field(default_factory=tuple)
    dielectrics: tuple[Dielectric, ...] = field(default_factory=tuple)
    name: str | None = None

    def __post_init__(self) -> None:
        if any(e <= 0 for e in self.domain.extents_m):
            raise ValueError("Model.domain must be a non-degenerate box")

    @property
    def max_epsilon_r(self) -> float:
        """The highest relative permittivity anywhere in the model -- what
        a mesher must size against, since the wavelength is shortest
        there."""
        return max((d.epsilon_r for d in self.dielectrics), default=1.0)

    @property
    def lossy_conductors(self) -> tuple[Conductor, ...]:
        return tuple(c for c in self.conductors if c.is_lossy)

    def shapes(self) -> tuple[Shape, ...]:
        return tuple(c.shape for c in self.conductors) + tuple(d.shape for d in self.dielectrics)
