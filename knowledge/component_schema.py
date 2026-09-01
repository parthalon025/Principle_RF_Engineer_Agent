"""Per-category component specification schema (CONTEXT.md: Category).

Ticket #11's starter taxonomy: ten `ComponentCategory` values, each mapped
to the specification field names and units it's expected to carry. Pure
data, no I/O -- `knowledge/extract.py` uses this to decide which fields of
a raw extraction to keep and store; `knowledge/validation.py` uses field
names (not this schema directly) to look up physical-plausibility bounds.

An empty-string unit means the field is either dimensionless (a ratio like
`vswr` or `q_factor`) or has no single fixed unit across components
(`value`, `polarization`).
"""

from __future__ import annotations

from knowledge.models import ComponentCategory

CATEGORY_FIELDS: dict[ComponentCategory, dict[str, str]] = {
    ComponentCategory.AMPLIFIER: {
        "gain_db": "dB",
        "nf_db": "dB",
        "p1db_dbm": "dBm",
        "ip3_dbm": "dBm",
        "freq_range_hz": "Hz",
    },
    ComponentCategory.FILTER: {
        "passband_hz": "Hz",
        "insertion_loss_db": "dB",
        "rejection_db": "dB",
    },
    ComponentCategory.MIXER: {
        "conversion_loss_db": "dB",
        "lo_drive_dbm": "dBm",
        "ip3_dbm": "dBm",
    },
    ComponentCategory.ATTENUATOR: {
        "attenuation_db": "dB",
        "power_rating_w": "W",
    },
    ComponentCategory.COUPLER_SPLITTER: {
        "coupling_db": "dB",
        "isolation_db": "dB",
        "insertion_loss_db": "dB",
    },
    ComponentCategory.CIRCULATOR_ISOLATOR: {
        "isolation_db": "dB",
        "insertion_loss_db": "dB",
    },
    ComponentCategory.SWITCH: {
        "insertion_loss_db": "dB",
        "isolation_db": "dB",
        "switching_time_ns": "ns",
    },
    ComponentCategory.ANTENNA: {
        "gain_dbi": "dBi",
        "freq_range_hz": "Hz",
        "vswr": "",
        "polarization": "",
    },
    ComponentCategory.CONNECTOR_CABLE: {
        "freq_range_hz": "Hz",
        "insertion_loss_db_per_m": "dB/m",
        "vswr": "",
    },
    ComponentCategory.PASSIVE_COMPONENT: {
        "value": "",
        "tolerance_pct": "%",
        "q_factor": "",
        "srf_hz": "Hz",
    },
}


def fields_for(category: ComponentCategory) -> dict[str, str]:
    """Return the {field_name: unit} schema for a category."""
    return CATEGORY_FIELDS[category]
