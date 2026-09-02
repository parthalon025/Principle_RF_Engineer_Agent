"""Regression guard for the measurement/ adapter pyvisa-import-helper
dedup (code-review finding): `_real_pyvisa_importable` and
`_import_pyvisa_module` used to be byte-for-byte duplicated across
measurement/vna.py, measurement/spectrum_analyzer.py, measurement/
signal_generator.py, and measurement/power_meter.py. They now live once in
measurement/base.py and every adapter module imports the same function
objects from there. This test fails if any adapter module regresses back
to defining its own local copy."""

import measurement.base as base
import measurement.power_meter as power_meter
import measurement.signal_generator as signal_generator
import measurement.spectrum_analyzer as spectrum_analyzer
import measurement.vna as vna


def test_all_adapters_share_the_same_pyvisa_helper_functions_from_base():
    for module in (vna, spectrum_analyzer, signal_generator, power_meter):
        assert module._real_pyvisa_importable is base._real_pyvisa_importable
        assert module._import_pyvisa_module is base._import_pyvisa_module
