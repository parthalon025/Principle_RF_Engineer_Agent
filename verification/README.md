# Verification

Every serious design needs a verification matrix.

Minimum fields:

| Field | Description |
|---|---|
| requirement_id | Stable requirement identifier |
| requirement | Human-readable requirement |
| method | analysis / simulation / measurement / inspection / test |
| expected | threshold or expected behavior |
| actual | measured/calculated result |
| status | PASS / CONDITIONAL PASS / FAIL / NOT VERIFIED / BLOCKED |
| evidence | file/report/measurement reference |
| notes | limitations |

A release recommendation must not be PASS if a critical requirement is NOT VERIFIED.
