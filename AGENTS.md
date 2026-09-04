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

## Planning docs are not a status source

`docs/BUILD_PLAN.md` and `docs/ROADMAP.md` describe an *intended* build order.
The repo has grown well past both. Read them as a plan someone wrote once, not
as a record of what is in the tree today.

So: don't conclude something is unbuilt because `docs/ROADMAP.md` files it under
a future milestone (its `0.6`/`0.7` labels are targets, not status), and don't
conclude it is built because a planning doc names it. Both inferences have been
wrong here. **Check the code.**

This matters because it has bitten repeatedly: three consecutive revisions of a
now-removed "what's still open" section in `CONTEXT.md` shipped stale, each one
written by trusting a doc or a commit message instead of opening the file it
described. That section is gone for exactly this reason — implementation status
belongs in `README.md` and in GitHub Issues, where it can be closed, not in a
prose list that silently rots.
