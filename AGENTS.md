# Principle_RF_Engineer_Agent

## Communication

**Always explain in layman's terms.** This is an RF/microwave codebase and the
jargon is unavoidable in the work itself — but not in the explanation of it.
When a term, a piece of arithmetic, or a trade-off appears in a question,
recommendation, or summary, say plainly what it means and why it matters
before relying on it.

This is not a licence to be vague. Keep every number, unit and citation exactly
as precise as it was; add the plain-language reading alongside, don't replace
the precision with it. "Skin depth is 5.5 µm at 10 GHz, so the film needs
20–35 µm to behave like a conductor" becomes "radio waves only travel through
the top ~5.5 µm of the material, so anything thinner than about 20–35 µm leaks
instead of reflecting."

Applies to chat, issue bodies, resolution comments, and any document written
for a human to read.

## Agent skills

### Issue tracker

Issues live in this repo's GitHub Issues (`parthalon025/Principle_RF_Engineer_Agent`), using the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default label vocabulary: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout (`CONTEXT.md` + `docs/adr/` at repo root). See `docs/agents/domain.md`.
