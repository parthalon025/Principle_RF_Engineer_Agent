# Principle_RF_Engineer_Agent

## What this is

An agent intended to act as a principal-level RF (radio-frequency) engineer:
reviewing designs, running RF engineering calculations, and answering
questions the way a senior RF engineer would. As of this writing the repo
contains only process scaffolding (issue tracker, triage labels, domain-doc
conventions installed via the Matt Pocock Claude Code skills) — no RF
domain code, no agent/skill definitions, and no concrete feature has been
built yet.

## Status: scope undefined

The repository name and this doc are the only signal for what the agent
should actually do. Before real implementation work starts, the following
need a decision from a human maintainer:

- **Surface**: is this a standalone Claude Code subagent/skill definition,
  an MCP server exposing RF tools, a CLI, or a library other tools import?
- **Core capabilities**: e.g. link-budget calculations, noise figure,
  VSWR/return loss, impedance matching, antenna gain, filter/matching
  network synthesis, S-parameter analysis, schematic/design review.
- **Inputs**: what does a user hand the agent — datasheets, S2P/Touchstone
  files, schematics, plain-text specs?
- **Correctness bar**: RF engineering calculations have real-world
  consequences (spectrum compliance, hardware damage from mismatch, etc.),
  so accuracy/verification requirements should be explicit before code is
  written against unverified assumptions.

Tracked in issue-tracker as a `needs-info` item — see the issue linked from
the PR that introduced this file. Until scope is decided, treat any RF
domain claim made here as provisional and confirm it before relying on it.

## Vocabulary

No domain terms have been resolved yet. This section is intentionally
empty; `/domain-modeling` should populate it once real terms and decisions
exist (see `docs/agents/domain.md`).
