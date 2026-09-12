"""The translator's output must be accepted by each adapter's OWN deck/config
generator -- not merely by a test's idea of what that generator wants.

That is the point of most of this file: every "accepts" test below calls the
real `generate_*` function from `simulation/`, so a drift in either the
translator or the adapter breaks it. No solver binary is needed, because deck
generation is pure string/dict work -- which is exactly why this can run in CI
while the solvers themselves cannot.
"""

import math

import pytest

from geometry.ir import (
    Band,
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
from geometry.translate import to_elmer, to_gprmax, to_meep, to_nec2, to_openems, to_palace

# A printed resistive film in a periodic unit cell -- the free-standing
# matched sheet from verification/simulator_reference_cases.py, restated in
# the IR. Rs = eta0/2 on a 0.1 mm film.
MATCHED_RS = 376.730313412 / 2


def lossy_unit_cell() -> Model:
    return Model(
        domain=Box((0.0, 0.0, 0.0), (1e-3, 1e-3, 5e-3)),
        band=Band(10e9),
        excitation=PlaneWave(),
        boundary=BoundaryKind.PERIODIC_XY,
        conductors=(
            Conductor(
                name="film",
                shape=Box((0.0, 0.0, 2e-3), (1e-3, 1e-3, 2e-3)),
                kind=ConductorKind.SHEET_RESISTANCE,
                sheet_resistance_ohm_sq=MATCHED_RS,
                thickness_m=0.1e-3,
            ),
        ),
    )


def dipole() -> Model:
    """A half-wave dipole at 300 MHz -- the canonical NEC case."""
    half_len = 0.5 * (299_792_458.0 / 300e6) / 2
    return Model(
        domain=Box((-0.01, -0.01, -half_len * 1.2), (0.01, 0.01, half_len * 1.2)),
        band=Band(300e6, fractional_bandwidth=0.0),
        excitation=LumpedPort(center_m=(0, 0, 0), size_m=(0, 0, 1e-3), direction="z"),
        conductors=(
            Conductor(
                shape=Cylinder(center_m=(0, 0, 0), radius_m=1e-3, height_m=2 * half_len, axis="z"),
                kind=ConductorKind.PERFECT,
            ),
        ),
    )


# ---------------------------------------------------------------------------
# The #230 guard: a lossy film must never cross as perfect metal.
# ---------------------------------------------------------------------------
def driven_lossy_patch() -> Model:
    """The same lossy film, but fed by a port instead of illuminated -- the
    only way openEMS can be reached at all (see to_openems's refusal)."""
    cell = lossy_unit_cell()
    return Model(
        domain=cell.domain,
        band=cell.band,
        excitation=LumpedPort(center_m=(5e-4, 5e-4, 1e-3), size_m=(0, 0, 2e-4), direction="z"),
        boundary=BoundaryKind.OPEN,
        conductors=cell.conductors,
    )


def test_lossy_film_reaches_openems_as_a_lossy_material_not_a_pec_conductor():
    geometry = to_openems(driven_lossy_patch())
    assert geometry["conductors"] == [], "a lossy film must not land in the PEC list"
    (material,) = [m for m in geometry["materials"] if "kappa_s_m" in m]
    assert material["kappa_s_m"] == pytest.approx(1.0 / (MATCHED_RS * 0.1e-3))


def test_lossy_film_reaches_meep_carrying_its_own_sheet_resistance():
    geometry = to_meep(lossy_unit_cell())
    (conductor,) = geometry["conductors"]
    assert conductor["sheet_resistance_ohm_sq"] == pytest.approx(MATCHED_RS)
    assert conductor["thickness_m"] == pytest.approx(0.1e-3)


def test_lossy_film_reaches_palace_as_a_conductivity_sheet_not_a_pec_patch():
    geometry = to_palace(lossy_unit_cell())
    assert geometry["pec_patches"] == [], "a lossy film must not land in pec_patches"
    (sheet,) = [m for m in geometry["materials"] if "kappa_s_m" in m]
    assert sheet["kappa_s_m"] == pytest.approx(1.0 / (MATCHED_RS * 0.1e-3))
    assert sheet["thickness_m"] == pytest.approx(0.1e-3)


def test_lossy_film_is_REFUSED_by_nec2_rather_than_becoming_a_bare_wire():
    """The defect this whole module exists to prevent. NEC has no loss on a
    GW card, so a designed absorber would become a lossless radiator."""
    model = Model(
        domain=Box((-0.1, -0.1, -0.1), (0.1, 0.1, 0.1)),
        band=Band(10e9),
        excitation=PlaneWave(),
        conductors=(
            Conductor(
                shape=Cylinder(center_m=(0, 0, 0), radius_m=1e-4, height_m=0.01),
                kind=ConductorKind.SHEET_RESISTANCE,
                sheet_resistance_ohm_sq=MATCHED_RS,
                thickness_m=0.1e-3,
            ),
        ),
    )
    with pytest.raises(UnrepresentableGeometry) as excinfo:
        to_nec2(model)
    assert excinfo.value.solver == "NEC2++"
    assert "#230" in excinfo.value.why


def test_a_perfect_conductor_cannot_also_claim_a_conductivity():
    """PERFECT is a claim about being lossless; carrying a conductivity too
    is the ambiguity that lets a translator pick whichever it prefers."""
    with pytest.raises(ValueError, match="cannot also"):
        Conductor(
            shape=Box((0, 0, 0), (1e-3, 1e-3, 0)),
            kind=ConductorKind.PERFECT,
            conductivity_s_m=5.8e7,
        )


# ---------------------------------------------------------------------------
# Each adapter's own generator accepts what we hand it.
# ---------------------------------------------------------------------------
def test_openems_adapter_accepts_the_translated_geometry():
    from simulation.openems import generate_openems_xml

    xml = generate_openems_xml(to_openems(driven_lossy_patch()), {})
    assert "<openEMS>" in xml or "openEMS" in xml


def test_palace_adapter_accepts_the_translated_geometry():
    from simulation.palace import generate_palace_mesh

    result = generate_palace_mesh(to_palace(lossy_unit_cell()))
    assert result["num_elements"] > 0


def test_nec2_adapter_accepts_the_translated_dipole():
    from simulation.nec2pp import generate_nec2_deck

    deck = generate_nec2_deck(to_nec2(dipole()), 300e6)
    assert deck.startswith("CM ")
    assert "GW " in deck
    assert "EX " in deck


def test_elmer_adapter_accepts_a_bare_bulk_domain():
    from simulation.elmer import generate_gmsh_geo_script

    model = Model(
        domain=Box((0, 0, 0), (0.02, 0.02, 0.02)),
        band=Band(10e9),
        excitation=PlaneWave(),
    )
    geo = generate_gmsh_geo_script(to_elmer(model))
    assert "Box(1)" in geo


# ---------------------------------------------------------------------------
# Segmentation is computed, so a deck cannot violate the rule the adapter
# itself never checks.
# ---------------------------------------------------------------------------
def test_every_nec_wire_is_segmented_to_at_least_ten_per_wavelength():
    geometry = to_nec2(dipole())
    lambda_m = 299_792_458.0 / 300e6
    for wire in geometry["wires"]:
        length = math.dist(
            (wire["x1_m"], wire["y1_m"], wire["z1_m"]),
            (wire["x2_m"], wire["y2_m"], wire["z2_m"]),
        )
        assert length / wire["segments"] <= lambda_m / 10 + 1e-12


def test_a_driven_wire_gets_an_odd_segment_count_so_a_feed_lands_on_centre():
    for wire in to_nec2(dipole())["wires"]:
        assert wire["segments"] % 2 == 1


def test_mesh_is_sized_against_the_densest_material_not_free_space():
    """A wavelength is shorter inside a dielectric, so the grid must be finer
    there -- sizing against free space would under-resolve the substrate."""
    bare = Model(domain=Box((0, 0, 0), (1e-3, 1e-3, 1e-3)), band=Band(10e9), excitation=PlaneWave())
    loaded = Model(
        domain=Box((0, 0, 0), (1e-3, 1e-3, 1e-3)),
        band=Band(10e9),
        excitation=PlaneWave(),
        dielectrics=(Dielectric(shape=Box((0, 0, 0), (1e-3, 1e-3, 1e-3)), epsilon_r=10.2),),
    )
    assert to_meep(loaded)["mesh_cell_size_m"] < to_meep(bare)["mesh_cell_size_m"]


# ---------------------------------------------------------------------------
# Refusals: each target says no to what it genuinely cannot hold.
# ---------------------------------------------------------------------------
def test_meep_refuses_a_polygon_rather_than_approximating_it():
    model = Model(
        domain=Box((0, 0, 0), (1e-3, 1e-3, 1e-3)),
        band=Band(10e9),
        excitation=PlaneWave(),
        conductors=(
            Conductor(
                shape=Polygon(points_m=((0, 0), (1e-3, 0), (1e-3, 1e-3))),
                kind=ConductorKind.PERFECT,
            ),
        ),
    )
    with pytest.raises(UnrepresentableGeometry, match="Polygon"):
        to_meep(model)
    # openEMS does have a polygon primitive, so the same outline crosses there
    # once the model is driven by a port rather than illuminated.
    driven = Model(
        domain=model.domain,
        band=model.band,
        excitation=LumpedPort(center_m=(5e-4, 5e-4, 5e-4), size_m=(0, 0, 1e-4), direction="z"),
        conductors=model.conductors,
    )
    assert to_openems(driven)["conductors"][0]["shape"] == "polygon"


def test_openems_refuses_plane_wave_illumination_because_it_has_no_such_excitation():
    """A real capability gap, surfaced by building the translator: this
    repo's openEMS adapter is lumped-port only, so an illuminated passive
    surface -- an absorber cell, an FSS -- cannot run on it at all."""
    with pytest.raises(UnrepresentableGeometry, match="plane-wave"):
        to_openems(lossy_unit_cell())


def test_palace_refuses_an_open_boundary_rather_than_silently_making_it_periodic():
    model = Model(
        domain=Box((0, 0, 0), (1e-3, 1e-3, 1e-3)),
        band=Band(10e9),
        excitation=PlaneWave(),
        boundary=BoundaryKind.OPEN,
    )
    with pytest.raises(UnrepresentableGeometry, match="open-boundary"):
        to_palace(model)


def test_elmer_refuses_a_model_whose_contents_it_would_silently_drop():
    with pytest.raises(UnrepresentableGeometry, match="vanish"):
        to_elmer(lossy_unit_cell())


def test_nec2_refuses_a_box_with_no_stated_equivalent_wire_radius():
    model = Model(
        domain=Box((-0.5, -0.01, -0.01), (0.5, 0.01, 0.01)),
        band=Band(300e6),
        excitation=LumpedPort(center_m=(0, 0, 0), size_m=(0, 0, 1e-3), direction="z"),
        conductors=(
            Conductor(
                shape=Box((-0.25, -1e-3, 0), (0.25, 1e-3, 0)),
                kind=ConductorKind.PERFECT,
            ),
        ),
    )
    with pytest.raises(UnrepresentableGeometry, match="equivalent_wire_radius_m"):
        to_nec2(model)


def test_nec2_accepts_the_same_box_once_the_caller_states_the_radius():
    model = Model(
        domain=Box((-0.5, -0.01, -0.01), (0.5, 0.01, 0.01)),
        band=Band(300e6),
        excitation=LumpedPort(center_m=(0, 0, 0), size_m=(0, 0, 1e-3), direction="z"),
        conductors=(
            Conductor(
                shape=Box((-0.25, -1e-3, 0), (0.25, 1e-3, 0), equivalent_wire_radius_m=5e-4),
                kind=ConductorKind.PERFECT,
            ),
        ),
    )
    (wire,) = to_nec2(model)["wires"]
    assert wire["radius_m"] == pytest.approx(5e-4)
    assert wire["x1_m"] == pytest.approx(-0.25)
    assert wire["x2_m"] == pytest.approx(0.25)


def test_gprmax_converts_a_sheet_resistance_because_that_preserves_the_physics():
    """Not every crossing is a refusal. gprMax states loss as a bulk
    conductivity, and sigma = 1/(Rs*t) is exact -- so this one goes through."""
    model = Model(
        domain=Box((0, 0, 0), (0.05, 0.05, 0.05)),
        band=Band(10e9),
        excitation=PlaneWave(),
        conductors=(
            Conductor(
                shape=Box((0.01, 0.01, 0.02), (0.04, 0.04, 0.0201)),
                kind=ConductorKind.SHEET_RESISTANCE,
                sheet_resistance_ohm_sq=MATCHED_RS,
                thickness_m=0.1e-3,
            ),
        ),
    )
    geometry = to_gprmax(model)
    assert geometry["conductors"] == []
    (material,) = geometry["materials"]
    assert material["conductivity_s_m"] == pytest.approx(1.0 / (MATCHED_RS * 0.1e-3))
