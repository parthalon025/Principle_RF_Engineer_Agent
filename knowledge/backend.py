"""Pure backend-selection logic (ADR-0004).

`select_backend` is the floor: it decides which `Backend` a document's
chunks may be embedded through, given the document's classification, an
optional explicit request, and the configured default. No I/O, no network,
no environment reads -- everything it needs is passed in, so it's trivially
unit-testable and is the single place the SENSITIVE/RESTRICTED floor is
enforced.

This module only decides; it never calls a backend. `knowledge/embedding.py`
holds the two structurally separate I/O adapters, and `knowledge/index.py`
routes SENSITIVE/RESTRICTED documents to the local adapter only, with no
code path from there to the external one (ADR-0004: "no shared fallback
path") -- that structural separation lives in the caller, not here.
"""

from __future__ import annotations

from knowledge.models import Backend, Classification

_RESTRICTED = {Classification.SENSITIVE, Classification.RESTRICTED}


class RestrictedBackendViolation(Exception):
    """Raised when a SENSITIVE/RESTRICTED document requests the EXTERNAL
    backend. There is no fallback from this -- the caller must not catch
    this and retry against the external API."""

    def __init__(self, classification: Classification):
        self.classification = classification
        super().__init__(
            f"{classification.value} documents may not use the EXTERNAL backend "
            "(ADR-0004): self-hosted is the only permitted backend for this "
            "classification, with no fallback."
        )


def select_backend(
    classification: Classification,
    requested: Backend | None,
    config_default: Backend,
) -> Backend:
    """Return the backend a document's chunks should be embedded through.

    - SENSITIVE/RESTRICTED: `requested == EXTERNAL` raises
      `RestrictedBackendViolation`. Otherwise (LOCAL or no request) always
      returns LOCAL -- `config_default` is ignored, because the floor for
      this classification is not configurable.
    - PUBLIC/INTERNAL: an explicit `requested` is honored as-is; with no
      request, `config_default` picks.
    """
    if classification in _RESTRICTED:
        if requested is Backend.EXTERNAL:
            raise RestrictedBackendViolation(classification)
        return Backend.LOCAL

    return requested if requested is not None else config_default
