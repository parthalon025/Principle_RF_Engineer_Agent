import pytest

from designs.validation import (
    InvalidRequirementsError,
    extract_component_refs,
    validate_requirements,
)

# --- validate_requirements ---------------------------------------------

_VALID_REQUIREMENTS_CASES = {
    "single requirement": {"REQ-1": {"requirement": "Gain >= 20 dB over band."}},
    "multiple requirements": {
        "REQ-1": {"requirement": "Gain >= 20 dB over band."},
        "REQ-2": {"requirement": "NF <= 2 dB at 2.4 GHz."},
    },
    "extra fields on a requirement are fine": {
        "REQ-1": {"requirement": "Gain >= 20 dB.", "priority": "must-have"},
    },
    "empty dict is a valid (if pointless) requirements set": {},
}


@pytest.mark.parametrize(
    "requirements", _VALID_REQUIREMENTS_CASES.values(), ids=_VALID_REQUIREMENTS_CASES.keys()
)
def test_validate_requirements_accepts_well_formed_shapes(requirements):
    validate_requirements(requirements)  # must not raise


_INVALID_REQUIREMENTS_CASES = {
    "not a dict at all (list)": ["Gain >= 20 dB."],
    "not a dict at all (string)": "Gain >= 20 dB.",
    "not a dict at all (None)": None,
    "requirement value is not a dict": {"REQ-1": "Gain >= 20 dB."},
    "requirement value missing 'requirement' key": {"REQ-1": {"priority": "must-have"}},
    "requirement value has non-string 'requirement'": {"REQ-1": {"requirement": 123}},
    "requirement value has empty 'requirement'": {"REQ-1": {"requirement": ""}},
}


@pytest.mark.parametrize(
    "requirements", _INVALID_REQUIREMENTS_CASES.values(), ids=_INVALID_REQUIREMENTS_CASES.keys()
)
def test_validate_requirements_rejects_wrong_shapes(requirements):
    with pytest.raises(InvalidRequirementsError):
        validate_requirements(requirements)


# --- extract_component_refs ---------------------------------------------

_COMPONENT_REF_CASES = {
    "no references": ({"lna": {"notes": "TBD"}}, []),
    "empty architecture": ({}, []),
    "one reference": ({"lna": {"component_id": 12}}, [12]),
    "many references across blocks": (
        {"lna": {"component_id": 12}, "mixer": {"component_id": 34}},
        [12, 34],
    ),
    "reference nested inside a list": (
        {"stages": [{"component_id": 1}, {"component_id": 2}]},
        [1, 2],
    ),
    "repeated reference is not deduplicated": (
        {"lna": {"component_id": 5}, "driver": {"component_id": 5}},
        [5, 5],
    ),
}


@pytest.mark.parametrize(
    "architecture,expected", _COMPONENT_REF_CASES.values(), ids=_COMPONENT_REF_CASES.keys()
)
def test_extract_component_refs(architecture, expected):
    assert sorted(extract_component_refs(architecture)) == sorted(expected)
