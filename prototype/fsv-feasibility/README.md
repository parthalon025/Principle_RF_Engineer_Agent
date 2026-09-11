# FSV feasibility prototype (THROWAWAY)

Answers the open question on GitHub issue #168, carried forward from
`docs/adr/0041-absorber-score-is-worst-in-band-minimax-with-fsv-comparison.md`
point 5 / "Consequences": does Feature Selective Validation (FSV) actually
discriminate usefully when comparing US12089385B2's Example 3 (patent's own
simulated curve, ~9.2 GHz) against Landy et al. 2008's measured curve
(~11.5 GHz), given the two curves are roughly five of Landy's own ~4%-FWHM
resonance-widths apart — or does FSV just report near-total disagreement as
bluntly as plain RMS error would, the same way plain RMS would?

**This is a throwaway prototype, not production code.** It is not wired
into `rf_tools/`, is not imported by anything else in this repo, and should
not be treated as an implementation of FSV for issue #168 — only as a
feasibility check with runnable numbers. See the top-of-file docstring in
`fsv_prototype.py` for exactly what is synthesized data vs. real, and what
is a best-effort reconstruction of the FSV algorithm vs. a verified read of
the IEEE standard (which is paywalled and was not read here).

Run:

```
pip install numpy
python3 fsv_prototype.py
```

No other dependencies. Findings are reported back in the conversation that
produced this prototype, not in this file — this directory intentionally
carries no separate findings write-up so there is exactly one place (the
script's own comments and its printed output) that can go stale.
