# --- Patch antenna synthesis tests moved to tests/test_patch_synthesis.py ---
#
# wavelength, patch_effective_permittivity, patch_length_extension_m,
# patch_resonant_frequency_hz, fractional_bandwidth_from_q,
# quality_factor_from_fractional_bandwidth, curvature_length_correction_factor,
# curvature_shifted_resonant_frequency_hz, curvature_exceeds_validity_box, and
# aperture_gain (issue #522) now live in rf_tools/patch_synthesis.py, with
# their tests alongside in tests/test_patch_synthesis.py. Microstrip
# transmission-line synthesis (issue #286) lives in
# rf_tools/microstrip_line.py, with its tests in tests/test_microstrip_line.py.

# --- Metamaterial unit-cell effective medium (Maxwell-Garnett) tests moved
# to tests/test_metamaterial.py ---
#
# maxwell_garnett_effective_permeability (issue #523) now lives in
# rf_tools/metamaterial.py, with its tests alongside in
# tests/test_metamaterial.py.
