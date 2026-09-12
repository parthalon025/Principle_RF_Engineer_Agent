"""The Requirements document: a CDD-style artifact, one per Design (issue
#321; CONTEXT.md: Requirements document; docs/adr/0034, docs/adr/0030).

ADR-0034 settled that requirement intake produces a written, human-reviewable
document -- modelled on the DoD's JCIDS Capability Development Document, the
same real-world framework this project already draws Threshold/Objective
from -- that a human reads, pushes back on, and confirms *before* a
Requirement target or an Intended effect is extracted from it and *before*
the ARCHITECTURE decision may run. This module builds that document, its
review lifecycle (`DRAFT -> UNDER_REVIEW -> REFINED -> CONFIRMED`), and (issue
#323) the extraction that fires once a document reaches `CONFIRMED`:
`extract_requirement_fields` calls `designs.requirement_targets.attach_target`/
`attach_intent` for every requirement the document describes, and
`transition_requirements_document` triggers it automatically whenever a
transition's target status is `CONFIRMED`. Gating ARCHITECTURE on that same
status, and wiring these functions into `agent/main.py`/`mcp_server/server.py`,
remain separate, later tickets (issue #321's own scope note).

WHY A NEW MODULE, NOT `designs/lifecycle.py` OR `designs/requirement_targets.py`.
`designs/lifecycle.py` walks `DesignStatus` specifically -- a different,
already-fixed nine-value enum (docs/adr/0007) for a different row
(`designs.status`). A Requirements document is a distinct artifact with its
own four-value status, so its transition table gets its own small module
rather than overloading that one for a second, unrelated status type.
`designs/requirement_targets.py` is reused directly, not duplicated: a
document's per-requirement entries are validated as the exact
`propose_target`/`mark_unscoreable` shapes that module already defines
(`target_status` in `PROPOSED`/`UNSCOREABLE`) -- the same values ADR-0034
says get extracted later, once the document is `CONFIRMED`.

MODULE SHAPE. The same pure/I-O seam `designs/requirement_targets.py`
already establishes:

  - Pure, DB-free functions (`draft_requirements_document`,
    `revise_requirements_document`, the transition-checking functions, and
    (issue #323) `extract_requirement_fields`) -- exhaustively unit-tested
    in `tests/test_requirements_document.py` with no database needed.
    `extract_requirement_fields` reuses `designs.requirement_targets.
    attach_target`/`attach_intent` directly rather than duplicating their
    validation/tagging logic (issue #315's own implementation decision:
    the document module "does not duplicate the existing target-proposal
    logic -- it calls into it once the document is confirmed").
  - Thin I/O wrappers (`create_requirements_document`,
    `transition_requirements_document`, `read_requirements_document`) --
    read/write the new `requirements_documents` table directly with their
    own small amount of raw SQL, mirroring `designs/requirement_targets.py`'s
    self-contained connection-lifecycle discipline (open, validate, write,
    translate a domain exception into a structured `status`-tagged result,
    commit-or-rollback, always close) rather than `designs/db.py`'s
    caller-owns-the-connection convention -- this module has no caller that
    already holds one open, the same situation `requirement_targets.py`'s
    own docstring describes for itself. `designs.db.get_connection`/
    `designs.db.UnknownDesignError` are reused as-is (not modified).
    `transition_requirements_document` additionally reads and rewrites the
    design's own `designs.requirements` column -- the same table/column
    `designs.requirement_targets`'s own I/O wrappers touch -- whenever a
    transition's target status is `CONFIRMED`, via its own small SQL
    (`_fetch_requirements`/`_store_requirements` below), matching this
    module's stated "own small amount of raw SQL" discipline rather than
    importing `requirement_targets`'s private helpers of the same name.

EVERY REVISION IS KEPT, NEVER OVERWRITTEN. `requirements_documents`
(`db/schema.sql`) is append-only -- one row per revision, `UNIQUE(design_id,
revision_number)`, no `UPDATE` statement anywhere in this module -- the same
instinct CONTEXT.md gives for an ADR's own corrections: "kept, never
overwritten". A document's current status/narrative/requirement_targets are
simply its latest revision; `revisions` (oldest first) is the full history a
reviewer can read back.

DOCUMENT CONTENT: A NARRATIVE PLUS PER-REQUIREMENT TARGETS, COVERING EVERY
REQUIREMENT ROW. `narrative` is the single capability-description/
intended-effect prose for the whole design (CDD-style: one document bundles
every one of a design's Customer requirement rows, per ADR-0034's "one
document per Design, not one per Customer requirement"). `requirement_targets`
is a dict keyed by `requirement_id`, one entry per Customer requirement row
already recorded on the design (`designs.requirements`) -- validated for
exact coverage (no requirement left out, no stray id that doesn't exist) by
`_validate_requirement_targets` below, since a CDD that omits one of the
system's own KPPs is not the bundled document ADR-0034 describes.

EACH ENTRY MAY ALSO CARRY THE REQUIREMENT'S INTENDED EFFECT (issue #323).
`_validate_requirement_targets` only requires a `propose_target`/
`mark_unscoreable` shape and, like `designs.validation` everywhere else in
this package, tolerates extra keys -- so a per-requirement entry built via
`designs.requirement_targets.propose_intended_effect` and merged in under
an `intended_effect` key needs no validation change here.
`extract_requirement_fields` reads that key off each entry (when present)
and writes it to `requirements[requirement_id]["intended_effect"]` via
`attach_intent`, sibling to `target`/`attach_target` (ADR-0030's "another
key ... beside `requirement` and `target`"). A requirement whose entry
carries no `intended_effect` key is left without one -- ADR-0030's "having
none is a legal answer" (a bend radius, a mass budget or a cure ceiling
asks nothing of the wave).

NOT WIRED AS AN AGENT/MCP TOOL HERE. Issue #321's acceptance criteria stop
at "build the document and its lifecycle"; wiring `create_requirements_document`/
`transition_requirements_document` into `agent/main.py`/`mcp_server/server.py`
is left to whichever ticket actually needs an interviewing agent to call
them.
"""

from __future__ import annotations

import copy
from enum import StrEnum
from typing import Any

from psycopg.rows import dict_row
from psycopg.types.json import Json

from designs import db
from designs.requirement_targets import TargetStatus, attach_intent, attach_target

__all__ = [
    "LEGAL_TRANSITIONS",
    "TERMINAL_STATUSES",
    "DocumentStatus",
    "IllegalDocumentTransitionError",
    "InvalidRequirementsDocumentError",
    "check_transition",
    "coerce_status",
    "create_requirements_document",
    "draft_requirements_document",
    "extract_requirement_fields",
    "legal_transitions_from",
    "read_requirements_document",
    "revise_requirements_document",
    "transition_requirements_document",
]

_DOCUMENT_TARGET_STATUSES = frozenset({TargetStatus.PROPOSED.value, TargetStatus.UNSCOREABLE.value})


class DocumentStatus(StrEnum):
    """Lifecycle status of a Requirements document (CONTEXT.md: Requirements
    document; docs/adr/0034). Not `designs.models.DesignStatus` -- a
    document's review cycle and a design's engineering lifecycle are two
    different things tracked on two different rows.

    - `DRAFT`: the interviewing agent's first pass, from the grilling
      conversation.
    - `UNDER_REVIEW`: a human is reading it and may push back.
    - `REFINED`: the agent has revised it in response to that pushback.
    - `CONFIRMED`: the human has confirmed it reflects what the customer
      meant. Terminal -- see `TERMINAL_STATUSES`.
    """

    DRAFT = "DRAFT"
    UNDER_REVIEW = "UNDER_REVIEW"
    REFINED = "REFINED"
    CONFIRMED = "CONFIRMED"


_S = DocumentStatus

#: Which statuses may directly follow each status (ADR-0034: "DRAFT ->
#: UNDER_REVIEW -> REFINED -> CONFIRMED ... the cycle repeats until the
#: human confirms"). REFINED may return to UNDER_REVIEW -- that repeating
#: cycle -- or move on to CONFIRMED. Every `DocumentStatus` is a key, the
#: same discipline `designs.lifecycle.LEGAL_TRANSITIONS` applies, so a
#: status missing from the map raises `KeyError` at write time instead of
#: refusing the transition readably (`test_every_status_is_a_key_in_the_
#: transition_map` guards this).
LEGAL_TRANSITIONS: dict[DocumentStatus, frozenset[DocumentStatus]] = {
    _S.DRAFT: frozenset({_S.UNDER_REVIEW}),
    _S.UNDER_REVIEW: frozenset({_S.REFINED}),
    _S.REFINED: frozenset({_S.UNDER_REVIEW, _S.CONFIRMED}),
    _S.CONFIRMED: frozenset(),
}

#: Statuses nothing leaves. A confirmed document is what `attach_intent`
#: (ADR-0034, not yet implemented) will read from; nothing here reopens one.
TERMINAL_STATUSES: frozenset[DocumentStatus] = frozenset(
    status for status, targets in LEGAL_TRANSITIONS.items() if not targets
)


class IllegalDocumentTransitionError(ValueError):
    """Raised for a Requirements-document transition the lifecycle does not
    allow -- e.g. `DRAFT -> CONFIRMED` directly (issue #321 acceptance
    criteria's own worked example). Named and shaped exactly like
    `designs.lifecycle.IllegalStatusTransitionError`: a `ValueError`
    subclass naming both the offending statuses and what was legal instead,
    so a caller (human or agent) can act on the message without reading
    this module's source.
    """

    def __init__(self, current: DocumentStatus, target: DocumentStatus) -> None:
        allowed = sorted(s.value for s in LEGAL_TRANSITIONS[current])
        allowed_text = ", ".join(allowed) if allowed else "(none -- terminal)"
        super().__init__(
            f"illegal requirements-document transition {current.value!r} -> "
            f"{target.value!r}; legal next statuses from {current.value!r} "
            f"are: {allowed_text}"
        )
        self.current = current
        self.target = target


class InvalidRequirementsDocumentError(ValueError):
    """Raised by `draft_requirements_document`/`revise_requirements_document`
    when the content handed to them is wrong -- an empty narrative, a
    `requirement_targets` dict that isn't keyed by exactly this design's own
    requirement ids (missing one, or naming one that doesn't exist), or a
    per-requirement entry that isn't a `propose_target`/`mark_unscoreable`
    shape. Names exactly what's wrong, the same discipline
    `InvalidRequirementTargetError`/`InvalidRequirementsError` already
    apply elsewhere in this package.
    """


def coerce_status(status: DocumentStatus | str) -> DocumentStatus:
    """Accept a `DocumentStatus` or its string value, rejecting anything
    else. Callers reach this across an agent/MCP JSON tool boundary, where a
    status is a bare string -- an unknown value names itself in the error
    rather than raising a bare enum `ValueError`."""
    if isinstance(status, DocumentStatus):
        return status
    try:
        return DocumentStatus(status)
    except ValueError:
        legal = ", ".join(sorted(s.value for s in DocumentStatus))
        raise ValueError(
            f"unknown requirements-document status {status!r}; legal values are: {legal}"
        ) from None


def legal_transitions_from(status: DocumentStatus | str) -> frozenset[DocumentStatus]:
    """The statuses `status` may move to directly. Empty for `CONFIRMED`."""
    return LEGAL_TRANSITIONS[coerce_status(status)]


def check_transition(current: DocumentStatus | str, target: DocumentStatus | str) -> None:
    """Raise `IllegalDocumentTransitionError` unless `current -> target` is
    legal. A status may not transition to itself -- a no-op write is far
    more often a caller bug than an intent, matching
    `designs.lifecycle.check_transition`'s identical rule."""
    current_status = coerce_status(current)
    target_status = coerce_status(target)
    if target_status not in LEGAL_TRANSITIONS[current_status]:
        raise IllegalDocumentTransitionError(current_status, target_status)


def _validate_narrative(narrative: Any) -> str:
    if not isinstance(narrative, str) or not narrative.strip():
        raise InvalidRequirementsDocumentError(
            f"narrative must be a non-empty string, got {narrative!r}"
        )
    return narrative


def _validate_requirement_targets(requirement_targets: Any, requirement_ids: Any) -> dict[str, Any]:
    """Validate that `requirement_targets` is a dict covering exactly
    `requirement_ids` -- every Customer requirement row under this design
    has an entry, and no entry names a requirement_id that doesn't exist
    (issue #321 acceptance criteria: "per-requirement numeric targets for
    every Customer requirement row"). Each entry must itself be a
    `propose_target`/`mark_unscoreable` shape (`target_status` in
    `PROPOSED`/`UNSCOREABLE`) -- a document holds proposals pending
    confirmation, never an already-`CONFIRMED` individual target, since
    confirming *this document* is the trust signal at this stage, not
    confirming one requirement's number in isolation.
    """
    if not isinstance(requirement_targets, dict):
        raise InvalidRequirementsDocumentError(
            f"requirement_targets must be a dict keyed by requirement_id, "
            f"got {type(requirement_targets).__name__}"
        )

    known_ids = set(requirement_ids)
    given_ids = set(requirement_targets)
    missing = sorted(known_ids - given_ids)
    if missing:
        raise InvalidRequirementsDocumentError(
            f"requirement_targets is missing an entry for requirement_id(s): {missing} "
            "-- a Requirements document must bundle every Customer requirement row"
        )
    unknown = sorted(given_ids - known_ids)
    if unknown:
        raise InvalidRequirementsDocumentError(
            f"requirement_targets names requirement_id(s) not on this design: {unknown}"
        )

    for requirement_id, target in requirement_targets.items():
        valid_shape = (
            isinstance(target, dict) and target.get("target_status") in _DOCUMENT_TARGET_STATUSES
        )
        if not valid_shape:
            raise InvalidRequirementsDocumentError(
                f"requirement_targets[{requirement_id!r}] must be a propose_target/"
                f"mark_unscoreable shape (target_status in {sorted(_DOCUMENT_TARGET_STATUSES)}), "
                f"got {target!r}"
            )

    return copy.deepcopy(requirement_targets)


def _make_revision(
    revision_number: int,
    status: DocumentStatus,
    narrative: str,
    requirement_targets: dict[str, Any],
) -> dict[str, Any]:
    return {
        "revision_number": revision_number,
        "status": status.value,
        "narrative": narrative,
        "requirement_targets": requirement_targets,
    }


def draft_requirements_document(
    requirement_ids: Any,
    narrative: str,
    requirement_targets: dict[str, Any],
) -> dict[str, Any]:
    """Create revision 1 (status `DRAFT`) of a Requirements document (issue
    #321 acceptance criteria: "can be created for a Design, starting at
    status DRAFT"). `requirement_ids` is the design's own set of Customer
    requirement keys (`requirements.keys()` on the design's stored
    `requirements` dict) -- passed explicitly rather than fetched here, the
    same "pure functions take already-fetched data" discipline
    `designs.requirement_targets.attach_target` already follows.

    Raises `InvalidRequirementsDocumentError` naming exactly what's wrong:
    an empty `narrative`, or a `requirement_targets` dict that doesn't cover
    every id in `requirement_ids` exactly (see
    `_validate_requirement_targets`).

    Returns a document dict: `{"status": "DRAFT", "narrative": ...,
    "requirement_targets": {...}, "revisions": [<revision 1>]}` --
    `status`/`narrative`/`requirement_targets` at the top level always
    mirror the *latest* revision, so a caller reads "the document today"
    without reducing `revisions` itself; `revisions` (oldest first) is the
    full history (issue #321: "a caller can read back the full history of
    drafts, not just the current one").
    """
    resolved_narrative = _validate_narrative(narrative)
    resolved_targets = _validate_requirement_targets(requirement_targets, requirement_ids)

    revision = _make_revision(1, DocumentStatus.DRAFT, resolved_narrative, resolved_targets)
    return {
        "status": DocumentStatus.DRAFT.value,
        "narrative": resolved_narrative,
        "requirement_targets": copy.deepcopy(resolved_targets),
        "revisions": [revision],
    }


def revise_requirements_document(
    document: dict[str, Any],
    status: DocumentStatus | str,
    narrative: str,
    requirement_targets: dict[str, Any],
    requirement_ids: Any,
) -> dict[str, Any]:
    """Advance `document` to `status`, appending a new revision -- never
    mutating `document` or overwriting a prior revision (issue #321: "every
    revision is kept, never overwritten"). `status` must be legally
    reachable from `document`'s current status (`check_transition`) --
    `DRAFT -> CONFIRMED` directly raises `IllegalDocumentTransitionError`,
    the acceptance criteria's own worked example of a rejected transition.

    `narrative`/`requirement_targets`/`requirement_ids` are validated the
    same way `draft_requirements_document` validates them -- a revision
    that merely advances status without changing content still restates
    both explicitly (the caller passes the same values again), since every
    revision is a full snapshot, not a diff.

    Returns a new document dict in the same shape
    `draft_requirements_document` returns, with the new revision appended
    to `revisions`.
    """
    current_status = coerce_status(document["status"])
    target_status = coerce_status(status)
    check_transition(current_status, target_status)

    resolved_narrative = _validate_narrative(narrative)
    resolved_targets = _validate_requirement_targets(requirement_targets, requirement_ids)

    next_revision_number = document["revisions"][-1]["revision_number"] + 1
    revision = _make_revision(
        next_revision_number, target_status, resolved_narrative, resolved_targets
    )
    return {
        "status": target_status.value,
        "narrative": resolved_narrative,
        "requirement_targets": copy.deepcopy(resolved_targets),
        "revisions": [*document["revisions"], revision],
    }


def extract_requirement_fields(
    requirements: dict[str, Any],
    document: dict[str, Any],
) -> dict[str, Any]:
    """Attach the Requirement target and Intended effect described by a
    `CONFIRMED` `document` onto every Customer requirement row it covers
    (issue #323; ADR-0034's "Requirement target and Intended effect are
    extracted from the confirmed document, not elicited standalone").

    For each `document["requirement_targets"][requirement_id]` entry -- a
    `propose_target`/`mark_unscoreable` shape, optionally carrying an
    `intended_effect` key built by
    `designs.requirement_targets.propose_intended_effect` -- writes the
    target fields onto `requirements[requirement_id]["target"]` via
    `designs.requirement_targets.attach_target`, and, when present, the
    intended effect onto `requirements[requirement_id]["intended_effect"]`
    via `attach_intent`. A requirement whose entry carries no
    `intended_effect` key is left without one -- ADR-0030's "having none is
    a legal answer" (a bend radius, a mass budget or a cure ceiling asks
    nothing of the wave).

    Raises `InvalidRequirementsDocumentError` if `document["status"]` is
    not `CONFIRMED` -- extraction only ever happens from a confirmed
    document (ADR-0034); calling this on a `DRAFT`/`UNDER_REVIEW`/`REFINED`
    document names the mistake instead of quietly writing an unreviewed
    reading onto the design's own requirements.

    Provenance is untouched by this function -- every entry it copies over
    already carries `provenance="ASSUMED"` from `propose_target`/
    `mark_unscoreable`/`propose_intended_effect`, and nothing here upgrades
    it, regardless of how many review rounds produced this revision
    (docs/adr/0030, docs/adr/0034).

    Pure and DB-free, exactly like `attach_target`/`attach_intent`
    themselves (never mutates `requirements` or `document`);
    `transition_requirements_document` below is the only caller that also
    touches a database, calling this once a transition's target status is
    `CONFIRMED`.
    """
    status = coerce_status(document["status"])
    if status is not DocumentStatus.CONFIRMED:
        raise InvalidRequirementsDocumentError(
            "requirement fields can only be extracted from a CONFIRMED "
            f"Requirements document, got status {status.value!r}"
        )

    updated = requirements
    for requirement_id, entry in document["requirement_targets"].items():
        intended_effect = entry.get("intended_effect")
        target = {key: value for key, value in entry.items() if key != "intended_effect"}
        updated = attach_target(updated, requirement_id, target)
        if intended_effect is not None:
            updated = attach_intent(updated, requirement_id, intended_effect)
    return updated


# ---------------------------------------------------------------------------
# I/O layer: read/write the append-only `requirements_documents` table.
#
# Deliberately self-contained (own connection lifecycle), not added to
# designs/db.py or designs/service.py -- see this module's docstring
# ("MODULE SHAPE") for why, mirroring designs/requirement_targets.py.
# ---------------------------------------------------------------------------


def _fetch_requirements(conn: Any, design_id: int) -> dict[str, Any]:
    """Return `design_id`'s current `designs.requirements` JSONB payload --
    the same query `designs.requirement_targets`'s own `_fetch_requirements`
    makes, duplicated here (not imported) per this module's stated "own
    small amount of raw SQL" discipline (see MODULE SHAPE). Raises
    `designs.db.UnknownDesignError` (reused as-is) if no `designs` row
    matches."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT requirements FROM designs WHERE id = %s", (design_id,))
        row = cur.fetchone()
    if row is None:
        raise db.UnknownDesignError(design_id)
    return row["requirements"]


def _store_requirements(conn: Any, design_id: int, requirements: dict[str, Any]) -> None:
    """Overwrite `designs.requirements` for `design_id` with `requirements`
    and bump `updated_at` -- the same statement
    `designs.requirement_targets`'s own `_store_requirements` runs, called
    here (issue #323) only when `transition_requirements_document` has just
    confirmed a document and extracted its fields. Caller-owned transaction
    boundary: never commits itself."""
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE designs SET requirements = %s, updated_at = now() WHERE id = %s",
            (Json(requirements), design_id),
        )


def _fetch_requirement_ids(conn: Any, design_id: int) -> set[str]:
    """Return the set of Customer requirement ids already recorded on
    `design_id` (`designs.requirements`'s own keys). Raises
    `designs.db.UnknownDesignError` (reused as-is) if no `designs` row
    matches."""
    return set(_fetch_requirements(conn, design_id))


def _fetch_stored_document(conn: Any, design_id: int) -> dict[str, Any] | None:
    """Return `design_id`'s Requirements document (every revision, oldest
    first, folded into the same shape `draft_requirements_document`/
    `revise_requirements_document` return), or `None` if none has been
    created yet."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT revision_number, status, narrative, requirement_targets "
            "FROM requirements_documents WHERE design_id = %s ORDER BY revision_number",
            (design_id,),
        )
        rows = cur.fetchall()
    if not rows:
        return None

    revisions = [dict(row) for row in rows]
    latest = revisions[-1]
    return {
        "status": latest["status"],
        "narrative": latest["narrative"],
        "requirement_targets": latest["requirement_targets"],
        "revisions": revisions,
    }


def _insert_revision(conn: Any, design_id: int, revision: dict[str, Any]) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO requirements_documents
                (design_id, revision_number, status, narrative, requirement_targets)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                design_id,
                revision["revision_number"],
                revision["status"],
                revision["narrative"],
                Json(revision["requirement_targets"]),
            ),
        )


def create_requirements_document(
    design_id: int,
    narrative: str,
    requirement_targets: dict[str, Any],
) -> dict[str, Any]:
    """Create the Requirements document for a stored design -- the
    tool-facing entry point for `draft_requirements_document` (issue #321
    acceptance criteria: "a Requirements document can be created for a
    Design, starting at status DRAFT").

    Returns a structured `status`-tagged result: `"not_found"` (no such
    `design_id`), `"already_exists"` (this design already has a document --
    call `transition_requirements_document` to revise it instead, since
    creating a second one would fork the single-document-per-Design
    invariant ADR-0034 requires), `"invalid_document"` (bad shape --
    `draft_requirements_document`'s own error), or on success
    `{"status": "created", "design_id": ..., "document_status": "DRAFT",
    "narrative": ..., "requirement_targets": {...}}`. A write that fails for
    any other reason still raises, matching every other function in this
    package.
    """
    with db._write_transaction() as conn:
        try:
            requirement_ids = _fetch_requirement_ids(conn, design_id)
        except db.UnknownDesignError as exc:
            conn.rollback()
            return {"status": "not_found", "design_id": exc.design_id}

        if _fetch_stored_document(conn, design_id) is not None:
            conn.rollback()
            return {
                "status": "already_exists",
                "design_id": design_id,
                "message": (
                    f"design_id {design_id!r} already has a Requirements document -- "
                    "call transition_requirements_document to revise it"
                ),
            }

        try:
            document = draft_requirements_document(requirement_ids, narrative, requirement_targets)
        except InvalidRequirementsDocumentError as exc:
            conn.rollback()
            return {"status": "invalid_document", "message": str(exc)}

        _insert_revision(conn, design_id, document["revisions"][0])
        conn.commit()

    return {
        "status": "created",
        "design_id": design_id,
        "document_status": document["status"],
        "narrative": document["narrative"],
        "requirement_targets": document["requirement_targets"],
    }


def transition_requirements_document(
    design_id: int,
    status: str,
    narrative: str,
    requirement_targets: dict[str, Any],
) -> dict[str, Any]:
    """Advance `design_id`'s Requirements document to `status`, appending a
    new revision -- the tool-facing entry point for
    `revise_requirements_document` (issue #321 acceptance criteria: "moves
    through DRAFT -> UNDER_REVIEW -> REFINED -> CONFIRMED; an illegal
    transition ... is rejected").

    When the new revision's status is `CONFIRMED`, this also extracts the
    Requirement target and Intended effect for every requirement the
    document describes and writes them onto this design's own
    `requirements[requirement_id]` rows (issue #323; ADR-0034: "confirming
    a document should trigger extraction for every requirement it
    describes") -- via `extract_requirement_fields`, in the same
    transaction as the revision insert, so a caller never observes a
    document that reads `CONFIRMED` without the extraction having already
    happened.

    Returns a structured `status`-tagged result: `"not_found"` (no such
    `design_id`), `"no_document"` (this design has no Requirements document
    yet -- call `create_requirements_document` first), `"illegal_transition"`
    (not legally reachable from the document's current status --
    `legal_next` names what is), `"invalid_document"` (bad content shape),
    or on success `{"status": "transitioned", "design_id": ...,
    "document_status": ..., "narrative": ..., "requirement_targets": {...}}`.
    A write that fails for any other reason still raises.
    """
    with db._write_transaction() as conn:
        try:
            requirement_ids = _fetch_requirement_ids(conn, design_id)
        except db.UnknownDesignError as exc:
            conn.rollback()
            return {"status": "not_found", "design_id": exc.design_id}

        existing = _fetch_stored_document(conn, design_id)
        if existing is None:
            conn.rollback()
            return {
                "status": "no_document",
                "design_id": design_id,
                "message": (
                    f"design_id {design_id!r} has no Requirements document yet -- "
                    "call create_requirements_document first"
                ),
            }

        try:
            updated = revise_requirements_document(
                existing, status, narrative, requirement_targets, requirement_ids
            )
        except IllegalDocumentTransitionError as exc:
            conn.rollback()
            return {
                "status": "illegal_transition",
                "message": str(exc),
                "current_status": exc.current.value,
                "requested_status": exc.target.value,
                "legal_next": sorted(s.value for s in legal_transitions_from(exc.current)),
            }
        except InvalidRequirementsDocumentError as exc:
            conn.rollback()
            return {"status": "invalid_document", "message": str(exc)}

        _insert_revision(conn, design_id, updated["revisions"][-1])

        if updated["status"] == DocumentStatus.CONFIRMED.value:
            design_requirements = _fetch_requirements(conn, design_id)
            extracted = extract_requirement_fields(design_requirements, updated)
            _store_requirements(conn, design_id, extracted)

        conn.commit()

    return {
        "status": "transitioned",
        "design_id": design_id,
        "document_status": updated["status"],
        "narrative": updated["narrative"],
        "requirement_targets": updated["requirement_targets"],
    }


def read_requirements_document(design_id: int) -> dict[str, Any]:
    """Read back `design_id`'s Requirements document in full -- current
    status/narrative/requirement_targets plus every revision (issue #321
    acceptance criteria: "a caller can read back the full history of
    drafts, not just the current one").

    Returns `{"status": "not_found", "design_id": ...}` if this design has
    no Requirements document yet, else `{"status": "found", "design_id":
    ..., "document_status": ..., "narrative": ..., "requirement_targets":
    {...}, "revisions": [...]}` -- `revisions` oldest first, each entry
    carrying its own `revision_number`/`status`/`narrative`/
    `requirement_targets`.
    """
    conn = db.get_connection()
    try:
        document = _fetch_stored_document(conn, design_id)
    finally:
        conn.close()

    if document is None:
        return {"status": "not_found", "design_id": design_id}

    return {
        "status": "found",
        "design_id": design_id,
        "document_status": document["status"],
        "narrative": document["narrative"],
        "requirement_targets": document["requirement_targets"],
        "revisions": document["revisions"],
    }
