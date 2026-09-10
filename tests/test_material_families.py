"""Tests for designs/material_families.py (issue #404; ADR-0015;
CONTEXT.md: Material-property library, Family fallback bracket).

Mirrors tests/test_material_properties.py's own precedent: this registry is
pure and DB-free, so it is exercised directly here with no database needed.
"""

from __future__ import annotations

import warnings

import pytest

from designs.material_families import (
    UnknownMaterialFamilyError,
    UnknownMaterialNameWarning,
    get_material_family,
    is_known_material,
    is_known_material_family,
    known_material_family_names,
    known_material_names,
    register_material,
    warn_if_unknown_material,
)

# ---------------------------------------------------------------------------
# Material family -- closed vocabulary, mirrors designs/design_families.py
# ---------------------------------------------------------------------------


def test_known_material_family_names_includes_the_adr_named_examples():
    # ADR-0015's own worked example names exactly these two.
    names = known_material_family_names()
    assert "generic polymer" in names
    assert "generic conductor" in names


def test_get_material_family_returns_the_canonical_spelling_case_insensitively():
    assert get_material_family("Generic Polymer") == "generic polymer"
    assert get_material_family("GENERIC POLYMER") == "generic polymer"
    assert get_material_family("  generic polymer  ") == "generic polymer"


def test_get_material_family_rejects_an_unrecognized_family():
    with pytest.raises(UnknownMaterialFamilyError, match="generic plastic goo"):
        get_material_family("generic plastic goo")


def test_get_material_family_error_names_the_known_families():
    with pytest.raises(UnknownMaterialFamilyError, match="generic polymer"):
        get_material_family("nonexistent family")


def test_get_material_family_rejects_empty_string():
    with pytest.raises(UnknownMaterialFamilyError):
        get_material_family("   ")


def test_is_known_material_family_true_for_a_registered_name():
    assert is_known_material_family("generic polymer") is True
    assert is_known_material_family("Generic Conductor") is True


def test_is_known_material_family_false_for_an_unrecognized_name():
    assert is_known_material_family("unobtainium family") is False


# ---------------------------------------------------------------------------
# Material name -- open, growing registry: warns, never rejects
# ---------------------------------------------------------------------------


def test_known_material_names_includes_every_seeded_material():
    # Harvested from designs/material_properties.py's FR4_SEED_ENTRIES,
    # SUBSTRATE_SEED_ENTRIES, and DATASHEET_SEED_ENTRIES (this module's own
    # docstring records the exact grep/commit used).
    names = known_material_names()
    for expected in ("FR4", "Rogers RO4350B", "DuPont Kapton HN", "Isola Astra MT77"):
        assert expected in names


def test_is_known_material_is_case_insensitive():
    assert is_known_material("fr4") is True
    assert is_known_material("FR4") is True
    assert is_known_material("Fr4") is True


def test_is_known_material_false_for_an_unregistered_name():
    assert is_known_material("unobtainium foam mk9") is False


def test_is_known_material_false_for_non_string_input():
    assert is_known_material(None) is False


def test_register_material_adds_a_new_name_that_is_then_known():
    assert is_known_material("Novel Aerogel Substrate XR-1") is False
    register_material("Novel Aerogel Substrate XR-1")
    try:
        assert is_known_material("Novel Aerogel Substrate XR-1") is True
        assert is_known_material("novel aerogel substrate xr-1") is True
        assert "Novel Aerogel Substrate XR-1" in known_material_names()
    finally:
        # This registry is process-global module state; clean up after
        # ourselves so other tests' known_material_names() assertions stay
        # exact regardless of test order.
        from designs import material_families as _mf

        _mf._MATERIAL_REGISTRY.pop("novel aerogel substrate xr-1", None)


def test_register_material_rejects_an_empty_name():
    with pytest.raises(ValueError, match="material name"):
        register_material("   ")


def test_warn_if_unknown_material_warns_for_an_unregistered_name():
    with pytest.warns(UnknownMaterialNameWarning, match="Totally New Substrate Q7"):
        warn_if_unknown_material("Totally New Substrate Q7")


def test_warn_if_unknown_material_is_silent_for_a_known_name():
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        # Must not raise -- FR4 is already registered.
        warn_if_unknown_material("FR4")


def test_unknown_material_name_warning_is_a_user_warning():
    assert issubclass(UnknownMaterialNameWarning, UserWarning)
