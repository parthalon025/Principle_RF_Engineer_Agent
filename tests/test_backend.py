import pytest

from knowledge.backend import RestrictedBackendViolation, select_backend
from knowledge.models import Backend, Classification

_UNRESTRICTED = (Classification.PUBLIC, Classification.INTERNAL)
_RESTRICTED = (Classification.SENSITIVE, Classification.RESTRICTED)
_BOTH_DEFAULTS = (Backend.LOCAL, Backend.EXTERNAL)

# Table-driven over every (classification, requested, config_default)
# combination (ticket #9 acceptance criteria).
CASES = []

for classification in _UNRESTRICTED:
    for config_default in _BOTH_DEFAULTS:
        # Explicit request is honored regardless of config_default.
        CASES.append((classification, Backend.LOCAL, config_default, Backend.LOCAL, None))
        CASES.append((classification, Backend.EXTERNAL, config_default, Backend.EXTERNAL, None))
        # No request -> config_default picks.
        CASES.append((classification, None, config_default, config_default, None))

for classification in _RESTRICTED:
    for config_default in _BOTH_DEFAULTS:
        # LOCAL request or no request -> always LOCAL, config_default is
        # ignored (the floor is not configurable).
        CASES.append((classification, Backend.LOCAL, config_default, Backend.LOCAL, None))
        CASES.append((classification, None, config_default, Backend.LOCAL, None))
        # EXTERNAL request -> raises, regardless of config_default.
        CASES.append(
            (classification, Backend.EXTERNAL, config_default, None, RestrictedBackendViolation)
        )


def _case_id(case):
    classification, requested, config_default, expected, raises = case
    req = requested.value if requested is not None else "none"
    outcome = raises.__name__ if raises else expected.value
    return f"{classification.value}-req_{req}-default_{config_default.value}-{outcome}"


@pytest.mark.parametrize("case", CASES, ids=[_case_id(c) for c in CASES])
def test_select_backend_table(case):
    classification, requested, config_default, expected, raises = case
    if raises is not None:
        with pytest.raises(raises):
            select_backend(classification, requested, config_default)
    else:
        assert select_backend(classification, requested, config_default) == expected


def test_all_24_combinations_covered():
    # 4 classifications x 3 requested values (LOCAL/EXTERNAL/None) x 2
    # config_default values = 24.
    assert len(CASES) == 24


def test_restricted_violation_names_the_classification():
    with pytest.raises(RestrictedBackendViolation) as exc_info:
        select_backend(Classification.RESTRICTED, Backend.EXTERNAL, Backend.LOCAL)
    assert exc_info.value.classification is Classification.RESTRICTED
