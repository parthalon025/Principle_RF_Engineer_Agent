"""Instrument adapter contract (issue #43) -- the measurement/ package's
counterpart to simulation/base.py's Simulator/SimulationResult/
SimulatorError, plus this ticket's own load-bearing piece: a hard,
structural human-approval gate that must be satisfied before ANY instrument
adapter is allowed to reach real SCPI/VISA traffic.

CRITICAL, NON-NEGOTIABLE PROJECT CONSTRAINT (per README.md's "Do not give
the agent unrestricted control of laboratory instruments or production
release", docs/BUILD_PLAN.md's Phase 10 text "Physical control remains
approval-required", and docs/SECURITY.md's "Human approval is required
before RF transmission, high-power output, calibration changes, or
controlled instrument configuration"): physical lab instruments are never
controlled autonomously. This is the same discipline as ticket #40's HFSS
workstation-confinement gate (simulation/hfss.py's
check_hfss_workstation_confinement) -- a hard gate, checked before any
potentially-dangerous action, requiring multiple independent signals, that
raises a clear error naming exactly what is missing -- generalized here to
cover every instrument adapter (VNA now; spectrum analyzer/signal
generator/power meter are a later ticket per docs/BUILD_PLAN.md's Phase 10
scope), which is why this gate lives in measurement/base.py rather than
measurement/vna.py: it is a shared contract, not a VNA-specific concern.

THE APPROVAL-GATE MECHANISM

The design goal (per this ticket's own guidance) is that it must be
STRUCTURALLY impossible to reach real instrument actuation without a
distinct, separate, auditable human-approval step -- not just a boolean
flag an LLM caller could set to True casually in the same call that
performs the measurement. Concretely:

  1. `request_physical_measurement_approval(job, approved_by,
     approval_callback)` is the ONLY way to obtain an `ApprovalReceipt`.
     It does nothing dangerous itself -- no SCPI, no VISA, no instrument
     I/O -- it only decides whether to grant a receipt.

  2. There is no human-approval UI/workflow wired up anywhere in this
     codebase yet. So by design, calling it with `approval_callback=None`
     (the default -- and the only way any of this project's current
     agent/MCP tool wiring can call it, since a Python callable cannot
     cross that JSON tool boundary) ALWAYS raises `InstrumentError`. This
     is intentional, not a bug to work around: it means the code path
     structurally cannot proceed to real instrument actuation in this
     build, full stop, even though the eventual human-facing
     implementation of `approval_callback` (a real confirmation UI/
     workflow) is a project for later. See
     tests/test_vna.py::test_request_physical_measurement_approval_raises_
     by_default_with_no_callback for the proof.

  3. A caller that DOES supply a real `approval_callback` (e.g. a test, or
     a future real approval workflow) gets back an `ApprovalReceipt` that
     is cryptographically bound to the EXACT measurement request it was
     granted for: its `token` is an HMAC-SHA256 signature (keyed by a
     random secret generated once per process at import time, never
     exposed) over a canonical fingerprint of the job's parameters plus
     who approved it and when. `Instrument.measure()` implementations call
     `check_physical_actuation_gate(job, ...)` before doing anything else;
     that function re-derives the same fingerprint from the job actually
     being executed and verifies the signature. Consequences:
       - A receipt minted for one measurement request cannot be replayed
         against a DIFFERENT request (different resource, frequency range,
         sweep points, ...) -- the fingerprint mismatch is caught and
         named explicitly.
       - A bare string/boolean an LLM caller invents in place of a real
         `ApprovalReceipt` fails outright (`isinstance` check) rather than
         being silently accepted.
       - The signing key lives only in this process's memory (never
         persisted, never logged, never returned to a caller) -- a
         receipt cannot be forged without having actually gone through
         `request_physical_measurement_approval` in this same process,
         and does not survive a process restart, so approvals cannot be
         cached/replayed across sessions.

  4. `check_physical_actuation_gate` additionally requires (mirroring
     check_hfss_workstation_confinement's multi-signal discipline):
       - `ALLOW_INSTRUMENT_CONTROL == "true"` in the environment -- the
         pre-existing `.env.example` flag docs/SECURITY.md already
         documents ("Default: ALLOW_INSTRUMENT_CONTROL=false. Human
         approval is required before RF transmission, high-power output,
         calibration changes, or controlled instrument configuration").
       - A configured VISA resource string (the caller/adapter is
         responsible for resolving this from job/env and passing it in;
         see measurement/vna.py).
       - The instrument-control library (pyvisa for the VNA adapter) being
         genuinely importable on this host -- the caller performs this
         *guarded* import itself (see measurement/vna.py's
         `_real_pyvisa_importable`) and passes the boolean result in, so
         this module never imports pyvisa itself.
     ALL of the above, plus a valid approval receipt, are required before
     `check_physical_actuation_gate` returns without raising. Missing
     checks are all named in one `InstrumentError`, same as
     check_hfss_workstation_confinement.

This sandboxed test/CI environment satisfies NONE of these signals by
default (ALLOW_INSTRUMENT_CONTROL is unset/false in .env, no VISA resource
is configured, pyvisa is not installed, and no approval callback exists) --
see tests/test_vna.py for the real, unmockable proof.
"""

import hashlib
import hmac
import json
import os
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

# Process-local signing key for approval receipts. Generated once, at
# import time, never persisted or exposed to any caller -- an
# ApprovalReceipt's token can only be produced (and only verifies) inside
# this same running process, via request_physical_measurement_approval()
# below. This is deliberate: it means an approval cannot be cached, leaked,
# or replayed across a process restart, and cannot be fabricated by
# anything that hasn't gone through the real approval function.
_APPROVAL_SIGNING_KEY = secrets.token_bytes(32)


@dataclass
class InstrumentResult:
    instrument: str
    status: str
    outputs: dict[str, Any]
    provenance: str = "MEASURED"


class InstrumentError(RuntimeError):
    pass


class Instrument:
    """Shared adapter contract for physical lab instruments -- the
    measurement/ package's analog of simulation/base.py's Simulator.
    `measure()` is the measurement-domain counterpart of Simulator.run():
    every real implementation MUST call check_physical_actuation_gate(...)
    before any SCPI/VISA traffic, exactly as every Simulator subclass's
    run() that touches licensed/dangerous infrastructure gates itself
    first (see simulation/hfss.py's HfssSimulator.run())."""

    name = "base"

    def measure(self, job: dict[str, Any]) -> InstrumentResult:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Approval receipts.
#
# An ApprovalReceipt is bound to a `fingerprint_fields` dict, NOT to a raw
# adapter `job` dict. The two are deliberately kept separate: `job` (an
# adapter's measure() input) commonly carries fields that are irrelevant to
# what a human is actually approving -- e.g. VnaAdapter's job also carries
# `calibration` (free-form caller metadata) and `touchstone_path` (where to
# write an output file), neither of which changes what gets physically sent
# to the instrument. `fingerprint_fields` is instead the small, explicit,
# adapter-defined subset of parameters that DOES determine what the
# instrument will be told to do (for VnaAdapter: resource, start_hz,
# stop_hz, points, sparams -- see measurement/vna.py's
# _vna_fingerprint_fields). Both request_physical_measurement_approval() and
# check_physical_actuation_gate() take this same explicit dict, computed the
# same way by the adapter on both the approval-request side and the
# measurement side, so the two calls fingerprint identically for the same
# physical request regardless of what unrelated metadata the job dict also
# happens to carry.
# ---------------------------------------------------------------------------


def _canonical_fingerprint(fields: dict[str, Any]) -> str:
    """A stable SHA-256 fingerprint of `fields`. Any change to a field that
    matters to the physical action being approved -- resource, frequency
    range, sweep points, S-parameters requested, power level, anything the
    adapter includes -- changes this fingerprint, which is exactly the
    property that stops a receipt granted for one request from being
    reused for a different one."""
    canonical = json.dumps(fields, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ApprovalReceipt:
    """Proof that a human approved ONE specific physical-measurement
    request. Only ever constructed by request_physical_measurement_approval
    below (or reconstructed field-for-field from one of its outputs, e.g.
    after crossing an MCP/agent JSON tool boundary and back -- the fields
    themselves, not object identity, are what
    check_physical_actuation_gate verifies)."""

    token: str
    job_fingerprint: str
    approved_by: str
    granted_at: float

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable form, for crossing the agent/MCP tool
        boundary (see measurement/vna.py's request_vna_measurement_approval
        tool) -- and for reconstructing an equivalent ApprovalReceipt on
        the other side via ApprovalReceipt(**that_dict)."""
        return {
            "token": self.token,
            "job_fingerprint": self.job_fingerprint,
            "approved_by": self.approved_by,
            "granted_at": self.granted_at,
        }


def request_physical_measurement_approval(
    fingerprint_fields: dict[str, Any],
    approved_by: str | None = None,
    approval_callback: Callable[[dict[str, Any]], bool] | None = None,
) -> ApprovalReceipt:
    """The ONLY way to obtain an ApprovalReceipt. Does nothing dangerous
    itself -- no SCPI, no VISA, no instrument I/O of any kind -- it is
    purely a decision-and-receipt step, deliberately kept separate from
    Instrument.measure() so that a distinct, auditable approval action must
    happen first.

    `fingerprint_fields` is the adapter-defined dict of parameters that
    determine what will physically happen (for the VNA adapter: resource,
    start_hz, stop_hz, points, sparams -- see measurement/vna.py's
    _vna_fingerprint_fields) -- the receipt is fingerprinted against it (see
    _canonical_fingerprint) so it can only approve that exact request. The
    adapter's measure() call must later reconstruct the SAME
    fingerprint_fields dict (same keys, same values) for
    check_physical_actuation_gate to accept the resulting receipt.

    `approval_callback`, if given, is called with `fingerprint_fields` and
    must return True/False for "a human approved this exact request" / "not
    approved".
    THIS CODEBASE DOES NOT YET WIRE UP A REAL HUMAN-FACING APPROVAL UI OR
    WORKFLOW -- that is a project for later. So `approval_callback`
    defaults to None, and when it is None this function ALWAYS raises
    InstrumentError rather than fabricating an approval. This is the
    load-bearing property of the whole gate: it is not merely "off by
    default", it is "there is currently no code path in this project that
    can produce a granted approval without a human-authored callback
    explicitly supplied at the call site" -- and neither agent/main.py's
    nor mcp_server/server.py's tool wiring supplies one (a bare Python
    callable cannot cross the JSON tool-call boundary those use), so a real
    agent invocation of the "request approval" tool always raises too. See
    this module's docstring, point 2.
    """
    if approval_callback is None:
        raise InstrumentError(
            "No human-approval mechanism is configured in this codebase yet. "
            "request_physical_measurement_approval() refuses to fabricate an "
            "approval on its own -- physical lab instruments are never "
            "controlled autonomously (README.md, docs/BUILD_PLAN.md Phase 10, "
            "docs/SECURITY.md). Pass an explicit approval_callback wired to a "
            "real human-facing approval workflow (e.g. a confirmation UI or "
            "review queue) once one exists; until then this function -- and "
            "therefore every Instrument.measure() call gated behind it -- "
            "structurally cannot proceed to real instrument actuation."
        )
    if not approved_by:
        raise InstrumentError(
            "approved_by (the identity of the approving human) is required "
            "for an auditable approval receipt"
        )

    approved = approval_callback(fingerprint_fields)
    if not approved:
        raise InstrumentError(
            f"Physical measurement request was not approved (approval_callback "
            f"returned a falsy result for approved_by={approved_by!r})"
        )

    fingerprint = _canonical_fingerprint(fingerprint_fields)
    granted_at = time.time()
    raw = f"{fingerprint}:{approved_by}:{granted_at!r}"
    token = hmac.new(_APPROVAL_SIGNING_KEY, raw.encode("utf-8"), hashlib.sha256).hexdigest()
    return ApprovalReceipt(
        token=token, job_fingerprint=fingerprint, approved_by=approved_by, granted_at=granted_at
    )


def _verify_approval_receipt(receipt: Any, fingerprint_fields: dict[str, Any]) -> list[str]:
    """Return a list of problems with `receipt` as an approval for
    `fingerprint_fields` (empty list == valid). Used by
    check_physical_actuation_gate below."""
    problems: list[str] = []

    if receipt is None:
        problems.append(
            "no approval was provided -- an ApprovalReceipt from "
            "request_physical_measurement_approval() is required"
        )
        return problems

    if not isinstance(receipt, ApprovalReceipt):
        problems.append(
            "the approval must be an ApprovalReceipt returned by "
            "request_physical_measurement_approval() (or reconstructed "
            f"field-for-field from its to_dict() output), not a bare "
            f"{type(receipt).__name__} -- a plain string/boolean token cannot "
            "be accepted"
        )
        return problems

    expected_fingerprint = _canonical_fingerprint(fingerprint_fields)
    if receipt.job_fingerprint != expected_fingerprint:
        problems.append(
            "the approval receipt's job_fingerprint does not match this "
            "measurement request's parameters -- it was granted for a "
            "different request (different resource/frequency range/sweep "
            "points/...); request approval again for this exact request"
        )

    raw = f"{receipt.job_fingerprint}:{receipt.approved_by}:{receipt.granted_at!r}"
    expected_token = hmac.new(
        _APPROVAL_SIGNING_KEY, raw.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected_token, receipt.token):
        problems.append(
            "the approval receipt's signature is invalid -- it was not issued "
            "by request_physical_measurement_approval() in this process (or "
            "the process that issued it has since restarted; approvals do not "
            "survive a restart, by design)"
        )

    return problems


def check_physical_actuation_gate(
    approval: Any,
    fingerprint_fields: dict[str, Any],
    resource: str | None,
    library_importable: bool,
    library_import_detail: str = "",
    library_name: str = "pyvisa",
    env: dict[str, str] | None = None,
) -> None:
    """Raise InstrumentError naming exactly what's missing unless ALL of
    the following hold. Called by every Instrument.measure() implementation
    that can physically actuate hardware, BEFORE doing anything else --
    exactly where simulation/hfss.py's HfssSimulator.run() calls
    check_hfss_workstation_confinement().

      1. ALLOW_INSTRUMENT_CONTROL == "true" in `env` (defaults to the real
         process environment; pass an explicit dict to test individual
         signal combinations without touching the real environment).
      2. `resource` (a VISA resource string) is a non-empty string -- the
         caller/adapter resolves this from job/env and passes it in, since
         where it lives is adapter-specific.
      3. `library_importable` is True -- the caller performs the actual
         guarded `import pyvisa` (or equivalent) itself and passes the
         result in, so this module never imports an instrument-control
         library itself; `library_import_detail`/`library_name` are used
         only to compose the error message.
      4. `approval` is a valid ApprovalReceipt for THIS exact
         `fingerprint_fields` (see _verify_approval_receipt) --
         signature-verified and fingerprint-matched, not merely present.

    Every failing check is named in the raised error at once, mirroring
    check_hfss_workstation_confinement's discipline: this cannot be fixed
    by satisfying one signal while others remain missing.
    """
    env = os.environ if env is None else env
    missing: list[str] = []

    allow_flag = str(env.get("ALLOW_INSTRUMENT_CONTROL", "")).strip().lower()
    if allow_flag != "true":
        missing.append(
            "ALLOW_INSTRUMENT_CONTROL must be 'true' "
            f"(got {env.get('ALLOW_INSTRUMENT_CONTROL', '<unset>')!r}) -- per "
            "docs/SECURITY.md, physical instrument control defaults off"
        )

    if not resource:
        missing.append(
            "no VISA resource string is configured for this instrument (pass "
            "job['resource'] or set the adapter's configured resource "
            "environment variable)"
        )

    if not library_importable:
        detail_suffix = f": {library_import_detail}" if library_import_detail else ""
        missing.append(
            f"{library_name} is not importable on this host "
            f"(import {library_name} failed{detail_suffix})"
        )

    missing.extend(_verify_approval_receipt(approval, fingerprint_fields))

    if missing:
        raise InstrumentError(
            "Physical instrument actuation refused: physical lab instruments "
            "are never controlled autonomously in this project (README.md's "
            "'Do not give the agent unrestricted control of laboratory "
            "instruments or production release', docs/BUILD_PLAN.md's Phase "
            "10 'Physical control remains approval-required', docs/"
            "SECURITY.md's 'Human approval is required before RF "
            "transmission, high-power output, calibration changes, or "
            "controlled instrument configuration'). This gate requires "
            "multiple independent signals, all of them, before any real "
            "SCPI/VISA traffic reaches the instrument. Missing/failed "
            "checks:\n" + "\n".join(f"  - {m}" for m in missing)
        )
