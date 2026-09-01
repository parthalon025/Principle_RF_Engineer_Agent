from knowledge.component_schema import CATEGORY_FIELDS, fields_for
from knowledge.models import ComponentCategory

_EXPECTED_FIELDS: dict[ComponentCategory, set[str]] = {
    ComponentCategory.AMPLIFIER: {"gain_db", "nf_db", "p1db_dbm", "ip3_dbm", "freq_range_hz"},
    ComponentCategory.FILTER: {"passband_hz", "insertion_loss_db", "rejection_db"},
    ComponentCategory.MIXER: {"conversion_loss_db", "lo_drive_dbm", "ip3_dbm"},
    ComponentCategory.ATTENUATOR: {"attenuation_db", "power_rating_w"},
    ComponentCategory.COUPLER_SPLITTER: {"coupling_db", "isolation_db", "insertion_loss_db"},
    ComponentCategory.CIRCULATOR_ISOLATOR: {"isolation_db", "insertion_loss_db"},
    ComponentCategory.SWITCH: {"insertion_loss_db", "isolation_db", "switching_time_ns"},
    ComponentCategory.ANTENNA: {"gain_dbi", "freq_range_hz", "vswr", "polarization"},
    ComponentCategory.CONNECTOR_CABLE: {"freq_range_hz", "insertion_loss_db_per_m", "vswr"},
    ComponentCategory.PASSIVE_COMPONENT: {"value", "tolerance_pct", "q_factor", "srf_hz"},
}


def test_all_ten_starter_categories_have_a_schema():
    assert set(CATEGORY_FIELDS.keys()) == set(ComponentCategory)
    assert len(CATEGORY_FIELDS) == 10


def test_each_category_has_its_documented_field_set():
    for category, expected in _EXPECTED_FIELDS.items():
        assert set(fields_for(category).keys()) == expected


def test_every_field_has_a_unit_entry_even_if_empty_string():
    for category in ComponentCategory:
        for field, unit in fields_for(category).items():
            assert isinstance(unit, str), f"{category}.{field} unit must be a str"
