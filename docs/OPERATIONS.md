# Operating procedure

Before each task:
1. Identify project/design.
2. Load current revision.
3. Load requirements.
4. Check newer measurements.
5. Check known failure reports.
6. Record simulator/model versions.
7. Create isolated work directory.

During engineering:
1. Record assumptions.
2. Use deterministic tools.
3. Save outputs.
4. Record provenance.
5. Never overwrite prior revisions.
6. Keep simulation input/output together.
7. Keep measurements immutable.
8. Record calibration metadata.

Before review:
- requirements
- assumptions
- component limits
- thermal limits
- stability
- tolerance
- simulation convergence
- measurement correlation
- verification matrix
- unresolved risks

States:
DRAFT → ANALYSIS → SIMULATION → OPTIMIZATION → VERIFICATION →
CONDITIONAL-PASS/PASS/FAIL/BLOCKED → RELEASED

RELEASED requires human approval. No agent/MCP tool can grant it: a human with local
access to the machine running the live session runs `uv run python -m
orchestration.approval_cli submit-release / list-release / show-release /
approve-release / refuse-release` (see README.md's "How it works" section). Without
that, a design simply stays short of RELEASED.
