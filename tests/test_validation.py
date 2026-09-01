from knowledge.validation import ValidationResult, validate_field

# One (good, bad) pair per starter category (ticket #11 acceptance
# criteria), each exercising a field that has a defined physical bound for
# that category. `conversion_loss_db` is not in ADR-0003's literal bound
# list but is added here for the same reason `insertion_loss_db` is bounded
# -- a loss quantity cannot physically be negative -- so every category has
# at least one bounded field to test (see report for this assumption).
_CATEGORY_BOUND_CASES = {
    "amplifier": ("nf_db", 1.5, -1.5),
    "filter": ("insertion_loss_db", 0.5, -0.2),
    "mixer": ("conversion_loss_db", 6.0, -3.0),
    "attenuator": ("attenuation_db", 3.0, -1.0),
    "coupler_splitter": ("coupling_db", 10.0, -5.0),
    "circulator_isolator": ("isolation_db", 20.0, -5.0),
    "switch": ("switching_time_ns", 50.0, -10.0),
    "antenna": ("vswr", 1.5, 0.5),
    "connector_cable": ("vswr", 1.2, 0.9),
    "passive_component": ("tolerance_pct", 5.0, -1.0),
}


def test_validate_field_returns_a_result_not_an_exception():
    result = validate_field("nf_db", -3.0)
    assert isinstance(result, ValidationResult)


def test_known_good_and_known_bad_value_per_category():
    for category, (field, good, bad) in _CATEGORY_BOUND_CASES.items():
        good_result = validate_field(field, good)
        assert good_result.physically_valid, f"{category}.{field}={good} should be valid"
        assert good_result.error is None

        bad_result = validate_field(field, bad)
        assert not bad_result.physically_valid, f"{category}.{field}={bad} should be invalid"
        assert bad_result.error is not None
        assert field in bad_result.error


def test_power_rating_w_must_be_strictly_positive():
    assert validate_field("power_rating_w", 2.0).physically_valid
    assert not validate_field("power_rating_w", 0.0).physically_valid
    assert not validate_field("power_rating_w", -1.0).physically_valid


def test_q_factor_must_be_strictly_positive():
    assert validate_field("q_factor", 100.0).physically_valid
    assert not validate_field("q_factor", 0.0).physically_valid
    assert not validate_field("q_factor", -5.0).physically_valid


def test_field_with_no_bound_always_passes():
    # polarization is a string field with no physical-plausibility bound.
    assert validate_field("polarization", "vertical").physically_valid
    # gain_db has no defined bound either -- any numeric value passes.
    assert validate_field("gain_db", -999.0).physically_valid


def test_non_numeric_value_for_a_bounded_field_is_invalid():
    result = validate_field("nf_db", "not a number")
    assert not result.physically_valid
    assert result.error is not None
