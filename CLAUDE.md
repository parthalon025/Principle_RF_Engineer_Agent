# Principle_RF_Engineer_Agent

## What this program is for

**This section is a charter, not a status report.** It says what the program
is for and how it must behave. It is deliberately ahead of the code in
places. Never cite it as evidence that something is built — for that, read
`README.md`, open the file, or check GitHub Issues.

### The problem, physically

Metal reflects radio waves upside down. Most external surfaces — a vehicle, an
aircraft, a wall — are primarily conducting, and such a surface is *"reflective
with 180-degree phase shift and zero transmission"* (US12089385B2, [0003]).
Lay an antenna flat against it and the returning wave comes back inverted, so
*"a planar or conformal antenna situated slightly above such surface will have
its signal cancelled on axis"* ([0058]). The classical fix is to hold the
antenna a quarter-wavelength clear, so the round trip adds another half
wavelength and the cancellation becomes reinforcement — but then the standoff
is part of the design, and the part is no longer thin.

A surface engineered to reflect with **0° phase shift instead** — a magnetic
mirror — *"produces the same full reflection with 0° phase shift, with doubling
the signal strength"*, flat against the antenna ([0058]).

*In plain terms: metal makes an antenna lying on it deaf. A surface like this
makes it loud instead, while staying thin enough to bend around whatever it is
stuck to.*

That is one behaviour among several — absorbing, transmitting, steering,
scattering — but it is the clearest statement of the general problem: **a host
surface imposes whatever electromagnetic behaviour its material happens to
have, and the job is to replace that with the behaviour the requirement asks
for, in something thin and flexible enough to conform.** Every design this
program proposes is an answer to that, and the trade-off is nearly always the
same one — the behaviour you want versus the thickness, bandwidth and
manufacturability you can afford.

### The purpose

Take a stated problem or end state for an antenna and return **several
scored, buildable candidate designs, each traceable to research**.

The program exists because the people who need those answers — the systems
engineer and the CEO — are not RF engineers and have no RF engineer to ask.
So it is not a calculator that answers the question typed at it. It hands
back **options with their trade-offs**, because the reader is making a
decision, not checking a number.

The work ends in a manufactured part. Design-for-manufacture is the
destination: printer, ink, substrate and cure are first-class inputs, not an
afterthought. That destination is not reached today; naming it here is how
it stays the destination.

### Who checks the answer

**Nobody with RF expertise reviews the output.** ADR-0009 settled that a
second LLM under a different system prompt is not independent review, and
there is no RF engineer downstream. Three consequences:

- **The judgment is the model's; the code only checks form.** Nothing here
  parses a requirement, invents a target, or proposes a geometry.
  `designs/requirement_targets.py` validates that a number is finite and its
  unit non-empty; `orchestration/solver.py` scores candidates the model
  wrote. The provenance labels, approval receipts and 82 tools are a filing
  system around a model's opinion. *In plain terms: the machinery checks the
  paperwork, not the physics.*
- **Research is the referee.** Every stated result traces to literature, a
  patent, a partner's work, or a calculation. Where none exists, the program
  says so rather than inventing one. Re-deriving a published, measured
  result without being shown it first is how the method earns trust.
- **Measurement is the destination and is not available yet.** Everything
  produced here is capped at `SIMULATED` until there is bench access.

### Warn, never block

The program does not withhold a candidate to protect the reader from it. It
hands the candidate over and says what is uncertain.

**One hard stop survives**: nothing that spends real material, machine time
or money happens without a human saying yes — no print, no order, no
release. A permanent principle, not a limit of the current build.

A warning is only useful if it is rare and specific. Each must carry **what
is assumed**, **what it costs if that is wrong**, and **the cheapest way to
find out** — and must fire only when the assumption is **load-bearing**, so
that changing it would change the decision. Warning on everything and
warning on nothing are the same outcome.

### What may be proposed

**The search space is unbounded; the alphabet is not.** The program may
propose anything physics allows, drawing shapes from patents, papers and
partner work — including designs needing an ink not in stock or a machine
not owned. Present equipment and inventory shape the *ranking* and the
*warnings*, never the *search*.

What they do bound is what may be **claimed**. A letter enters the
Element/Coding-Alphabet library only by being printed and measured
(ADR-0027); nothing here loosens that. A candidate built from printed
letters and one built from a shape nobody has made are both returned, and
each says which it is.

**No method is privileged.** Symbol placement, continuous dimensions, pixel
bitmaps, ML inverse design — the method is chosen per requirement and the
choice recorded with its reason.

Three kinds of novelty are permitted, and each is labelled:

- a **new arrangement** of letters already printed and measured;
- a **new element** — a shape nobody has made, a hypothesis until it comes
  off a printer and onto a bench;
- a **new mechanism** — a different physical route to the same behaviour.

The last two arrive as hypotheses with a test attached. That is a labelling
rule, not a gate: nothing is withheld.

### Filling the alphabet is step one

The composition this program promises needs characterised letters, and there
are none. Printing and measuring the first ones is not a prerequisite to get
out of the way — it is the program's first job, and the fastest thing a
decision-maker can unblock.

### How it iterates

A language model drives the loop, following the method a trained engineer
uses:

1. **Read the requirement and state what it demands** — threshold and
   objective — saying plainly where the reading is a guess.
2. **Search precedent before inventing.** Reuse a characterised element
   before proposing a new one.
3. **State the mechanism and the prediction before evaluating** (ADR-0022):
   why this should work, and what number is expected.
4. **Evaluate cheap before expensive.** Closed form, then fast solver, then
   full wave. Kill weak candidates early.
5. **Compare prediction against result and say which broke** — the model or
   the design. This is what separates iterating from retrying.
6. **When stuck, name the missing measurement.** Do not guess harder.

The program closes its own research gaps where it can, and names them
precisely where it cannot.

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

### Model selection

Match Claude model tier (Haiku/Sonnet/Opus/Fable) to the task rather than a blanket default. See `docs/agents/model-selection.md`.

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
