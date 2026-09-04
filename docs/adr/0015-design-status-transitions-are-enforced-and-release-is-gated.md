---
status: accepted
---

# `designs.status` transitions are enforced, and `RELEASED` has its own approval gate

ADR-0007 fixed the nine legal values of `designs.status` and deferred "how a
design moves between them" as future work. Issue #145 found that the deferral
had a sharper edge than it looked: `update_design_status` validated that a
status was one of the nine but constrained no *order*, so a brand-new `DRAFT`
design could be written straight to `RELEASED` in a single call — and
ADR-0007's own "RELEASED requires human approval" was enforced nowhere in the
code at all. The lifecycle existed as vocabulary and as an ADR, and as nothing
else.

We decided to keep the column and give it rules: an enforced transition graph
(`designs/lifecycle.py`) checked on the write path, and a dedicated
human-approval gate on the one transition into `RELEASED`
(`designs/release_approval.py`).

## Considered options

**Delete `designs.status` and let the design loop's step machine be the only
lifecycle.** This was the option issue #145 asked to settle first, on the
grounds that building transitions for a column that should not exist would be
the expensive mistake. Rejected because ADR-0010 makes the design loop
*opt-in and not the primary path*: a design tracked outside the loop would
then have no lifecycle at all, and `RELEASED` — which ADR-0007 and
`docs/OPERATIONS.md` both name as requiring human approval — would have
nowhere to live. The two notions are not redundant: the loop's step machine
tracks one iteration's progress, `designs.status` tracks the design's standing.

**Reuse `LoopStepApprovalReceipt` for the release gate.** Rejected because
`orchestration/approval.py`'s own design forbids it: an approval for one gate
must never satisfy another, since mixing receipt types lets one approval
silently pass an unrelated check. "May this loop advance past its
`MEASUREMENT` step" and "may this design be released for manufacture" are
different questions, asked of different people, at different moments. The
release gate therefore gets its own receipt class and its own signing key, and
each gate's `isinstance` check rejects the other's receipt outright. The cost
is a deliberately duplicated HMAC mechanism; the benefit is that the isolation
is structural rather than conventional.

**Enforce ordering advisorily, or only in the service layer.** Rejected: an
invariant checked somewhere other than the write path is an invariant that
holds until someone calls the writer directly.

## Three rules beyond `docs/OPERATIONS.md`'s linear reading

`OPERATIONS.md` states the happy path. Real work needs three additions, chosen
here rather than inherited:

- **`BLOCKED` is reachable from any in-progress stage.** Work stalls for
  reasons outside the design — a part goes end-of-life, a facility is
  unavailable.
- **Rework returns to `ANALYSIS`, not to wherever the design left off.**
  Nothing records where that was, and restating the stage is better than
  guessing it.
- **`RELEASED` is terminal.** A released design is not edited back into
  engineering; it gets a new `designs.revision`. This holds for every caller,
  including the design loop's flush.

## Relationship to ADR-0011 (flagged, not silently overridden)

ADR-0011 states that the design loop's persistence "never reaches `RELEASED`,
which stays exclusively `manufacturing_release`'s concern (not yet built)".
This ADR narrows that sentence in one respect and leaves it true in the other.

`advance_design_status` now exposes a transition whose destination *can* be
`RELEASED`, so `RELEASED` is no longer reachable only through a future
`manufacturing_release` tool. But no design can actually reach it: the gate
requires a signed receipt, and `request_design_release_approval` refuses to
issue one while no human-facing approval workflow exists — the same stance
`orchestration/approval.py` takes for the loop gate. `manufacturing_release`
remains unbuilt and remains in `tool_policy.yaml`'s `approval_required`
category. ADR-0011's substantive claim — that the loop's own flush never
writes `RELEASED` — is unchanged and now enforced rather than merely intended.

## Consequences

The design loop's iteration-boundary flush (ADR-0011) writes a status that
skips stages, because it walks them in memory and persists once. It therefore
passes `allow_nonsequential=True`, which relaxes the *ordering* check only. It
does not relax the release gate, does not permit entering `RELEASED` out of
order, and does not permit leaving a terminal status: ordering is bookkeeping,
releasing and terminality are not.

Nothing in this codebase can move a design to `RELEASED` today. That is the
intended state, not a gap to route around — and the first thing to build when
a real approval workflow arrives is the `approval_callback` that
`request_design_release_approval` already takes.
