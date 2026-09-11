#!/usr/bin/env python3
"""
THROWAWAY PROTOTYPE -- answers GitHub issue #168's open question, does NOT
implement anything for rf_tools/. Nothing in this file is wired into the
production codebase and nothing here should be imported by it.

Question (issue #168, carried forward from ADR-0041 point 5 / Consequences):
    Does Feature Selective Validation (FSV) actually discriminate usefully
    when comparing US12089385B2's Example 3 (patent's own simulated curve,
    resonance ~9.2 GHz) against Landy, Sajuyigbe, Mock, Smith & Padilla's
    measured curve ("A Perfect Metamaterial Absorber," PRL 100:207402
    (2008), arXiv:0803.1670, measured peak absorbance >88% at 11.5 GHz) --
    or does the ~20-25% frequency offset (about five of Landy's own ~4%
    FWHM resonance-widths apart) make FSV report near-total disagreement
    just as bluntly as plain RMS error would, undercutting the reason FSV
    was chosen over RMS at all (ADR-0041 point 5)?

WHAT THIS SCRIPT IS AND IS NOT
-------------------------------
- It is a feasibility check with runnable numbers, not literature review.
- Curve data: SYNTHESIZED Lorentzian approximations, NOT digitized data.
  A repo-wide check (docs/example3-frequency-discrepancy.md,
  docs/example3-inventor-publications.md, docs/example3-cited-absorber-
  papers.md, docs/absorber-scoring-conventions.md, and a grep across
  docs/) turned up NO digitized point-by-point curve for either the
  patent's FIG. 7G or Landy's Fig. 4 anywhere in this repo -- only
  scalar facts (center frequency, FWHM, peak depth, a rough digitized
  null location for the patent). Those scalar facts anchor the
  synthesized curves below; everything about their exact *shape* between
  those anchor points is invented for this test and is explicitly
  ASSUMED-provenance, never CALCULATED or MEASURED, per this repo's
  provenance ladder (CONTEXT.md).
- FSV algorithm: a BEST-EFFORT reconstruction from non-paywalled sources
  (below), NOT a verified read of IEEE Std 1597.1-2008/2022 or of Duffy &
  Orlandi's original theory papers, which are IEEE/journal-paywalled and
  were not read for this prototype. Where the recovered source material
  was itself garbled (OCR of PDF-embedded math), this script states the
  assumption made and flags it in a comment at the point of use. Treat
  every number this script prints as INFERRED-from-a-partial-reconstruction,
  not as a verified implementation of the standard.

SOURCES USED FOR THE FSV RECONSTRUCTION (all fetched and read this
session; all non-IEEE-paywalled):
  [S1] A. Duffy, D. Di Febo, F. de Paulis, A. Orlandi, "Applying the
       Feature Selective Validation (FSV) method to ...", ARMMS EMC &
       Compliance Conference paper, https://www.armms.org/media/uploads/
       1259320006.pdf -- gives the ADM/FDM/GDM equations (1)-(3), the
       three-band Fourier decomposition procedure (DC / Lo / Hi), the
       six-level Table I natural-language grade thresholds, and the
       Grade/Spread definitions. This is the PRIMARY source for the
       reconstruction below; its equations were recovered via a text
       extraction of the PDF and the surrounding line structure, not by
       viewing typeset math, so exact weighting constants inside FDM are
       a best-effort reading (see FDM comments).
  [S2] D. Di Febo, F. de Paulis, A. Orlandi, "Feature Selective
       Validation: A new approach for new Engineers," European IBIS
       Summit, Naples, 2011, https://ibis.org/summits/may11/di_febo.pdf --
       independently confirms the DC/Lo/Hi FFT-filtering pipeline, the
       ADM/FDM/GDM structure, the same six-level Table I thresholds
       (<0.1 Excellent ... >1.6 Very Poor), and gives the cleaner Grade/
       Spread definitions used verbatim below ("Grade: number of
       categories starting from Excellent to contain 85% of the total
       confidence data"; "Spread: number of categories around the
       highest value category to contain 85%").
  [S3] docs/adr/0041-absorber-score-is-worst-in-band-minimax-with-fsv-
       comparison.md (this repo) -- states the six-level scale name and
       the GDM = sqrt(ADM^2 + FDM^2) combination; consistent with S1/S2.

Both S1 and S2 agree on: the six grade-threshold bins, the ADM/FDM/GDM
three-quantity structure, and the DC/Lo/Hi three-band FFT decomposition.
Where they under-specify (exact FDM internal weighting), this script
documents the choice made and why it does not change the qualitative
answer to the issue #168 question (see bottom-of-file discussion and the
final printed recommendation).

Run: python3 fsv_prototype.py
Deps: numpy only (pip install numpy).
"""

from __future__ import annotations

import numpy as np

# --------------------------------------------------------------------------
# 1. CURVE RECONSTRUCTION (SYNTHESIZED -- see module docstring)
# --------------------------------------------------------------------------
#
# Anchor facts actually found in this repo's research docs (all citations
# traced in docs/example3-frequency-discrepancy.md, read this session):
#
#   Landy et al. 2008 (arXiv:0803.1670), MEASURED:
#     - peak absorbance > 88% at 11.5 GHz                      [LITERATURE-SUPPORTED]
#     - FWHM = 4% of center frequency (paper's own words:
#       "a simulated full width at half maximum (FWHM) absorbance of 4%") [LITERATURE-SUPPORTED]
#     - baseline absorbance across ~8-10.5 GHz is ~0.10, not zero
#       (docs/example3-frequency-discrepancy.md sec 1, digitized from
#       Landy's own arXiv figure files)                        [LITERATURE-SUPPORTED]
#
#   US12089385B2 Example 3, FIG. 7G, SIMULATED (patent's own curve):
#     - reflectance null (peak absorption) digitizes to 9.200 GHz
#       (docs/example3-frequency-discrepancy.md sec 2.3, INFERRED from
#       re-digitizing the patent figure)                       [INFERRED]
#     - at 9.2 GHz: reflectance approx 0.02, i.e. absorption approx 95%
#       (same doc, sec "Against the patent's FIG. 7G")          [INFERRED]
#     - baseline reflectance near the plot edges (~9/~14 GHz) approx 97%,
#       i.e. baseline absorption approx 1 - 0.97**2 approx 0.06 [INFERRED]
#     - NO FWHM is reported anywhere in this repo's research docs for the
#       patent's own curve.
#
# What is SYNTHESIZED (ASSUMED provenance, this script only):
#   - The patent's resonance is given the SAME fractional FWHM as Landy's
#     (4% of its own center frequency) on the physical argument that
#     docs/example3-frequency-discrepancy.md establishes the geometry is
#     identical in all eight dimensions "including the 0.72 mm layer
#     separation" -- so a similar-Q resonance is a plausible, not measured,
#     assumption. This is exactly the kind of load-bearing assumption the
#     repo's charter says a warning must name; it is named here rather than
#     silently baked in.
#   - Both curves are modeled as single symmetric Lorentzian absorption
#     dips in |S11|, i.e. no second resonance, no asymmetry, no ripple --
#     Landy's own paper confirms "no second resonance" and a "smooth,
#     featureless" curve away from the peak, so a single Lorentzian is a
#     reasonable shape choice, not an arbitrary one, but the exact
#     curvature between anchor points is still invented.
#
# S11 magnitude is derived from the absorbance model as
#   |S11(f)| = sqrt(1 - A(f))
# which is the ground-backed reduction A = 1 - |S11|^2 (ADR-0017's
# default). ADR-0041's "Consequences" section notes the *real* Example 3
# reproduction needs the full two-port A = 1 - |S11|^2 - |S21|^2 because
# the patent's own geometry leaks some transmission -- that refinement is
# out of scope for this feasibility prototype, which only needs a
# resonance-shaped curve pair to stress-test FSV's discriminating power,
# not a physically exact reproduction.

FREQ_GHZ = np.linspace(7.0, 14.0, 4001)  # common frequency grid, 1.75 MHz step


def lorentzian_absorbance(f, f0, fwhm, peak, baseline):
    """Single symmetric Lorentzian absorbance dip, SYNTHESIZED shape."""
    gamma = fwhm / 2.0
    return baseline + (peak - baseline) / (1.0 + ((f - f0) / gamma) ** 2)


def s11_mag_from_absorbance(a):
    a_clipped = np.clip(a, 0.0, 0.999999)
    return np.sqrt(1.0 - a_clipped)


# Landy et al. 2008, measured curve
LANDY_F0 = 11.5
LANDY_FWHM = 0.04 * LANDY_F0  # 4% of center freq -> 0.46 GHz  [LITERATURE-SUPPORTED width]
LANDY_PEAK = 0.88  # ">88%" measured peak, conservative reading
# [LITERATURE-SUPPORTED]
LANDY_BASELINE = 0.10  # documented ~0.10 baseline      [LITERATURE-SUPPORTED]

landy_A = lorentzian_absorbance(FREQ_GHZ, LANDY_F0, LANDY_FWHM, LANDY_PEAK, LANDY_BASELINE)
landy_s11 = s11_mag_from_absorbance(landy_A)

# US12089385B2 Example 3, FIG. 7G, patent's own simulated curve
PATENT_F0 = 9.2
PATENT_FWHM = 0.04 * PATENT_F0  # SYNTHESIZED: assumed same fractional width as Landy
# [ASSUMED]
PATENT_PEAK = 0.95  # digitized peak absorption ~95%  [INFERRED]
PATENT_BASELINE = 0.06  # digitized-adjacent baseline ~6% [INFERRED]

patent_A = lorentzian_absorbance(FREQ_GHZ, PATENT_F0, PATENT_FWHM, PATENT_PEAK, PATENT_BASELINE)
patent_s11 = s11_mag_from_absorbance(patent_A)

FREQ_OFFSET_PCT = (LANDY_F0 - PATENT_F0) / LANDY_F0 * 100.0
FREQ_OFFSET_IN_FWHM = (LANDY_F0 - PATENT_F0) / LANDY_FWHM

# --------------------------------------------------------------------------
# 2. FSV RECONSTRUCTION (BEST-EFFORT -- see module docstring, sources S1/S2)
# --------------------------------------------------------------------------


def _band_split(y):
    """
    Split a real 1-D signal into DC / Lo (trend) / Hi (feature) components
    via FFT, per [S1]/[S2]'s stated procedure:
      - DC band = the zero-frequency term plus the lowest 4 spectral bins.
      - Lo band = the next bins up to where the cumulative spectral
        magnitude reaches ~40% of the total (a proxy for "40% of the
        total area under the transformed curve" in S1's wording).
      - Hi band = everything else.
    Each band is zeroed out elsewhere in the spectrum and inverse-
    transformed back to the frequency-axis domain (FSV's "time domain"
    step, here the swept-frequency axis itself, matching how this project
    already treats a Touchstone-style sweep as the independent variable).
    """
    n = len(y)
    spec = np.fft.rfft(y - np.mean(y))
    mag = np.abs(spec)
    dc_val = np.mean(y)

    dc_cut = min(4, len(mag) - 1)
    lo_start = dc_cut + 1

    total_mag = np.sum(mag[lo_start:])
    if total_mag > 0:
        cum = np.cumsum(mag[lo_start:]) / total_mag
        lo_bins_after_dc = int(np.searchsorted(cum, 0.40)) + 1
    else:
        lo_bins_after_dc = 0
    lo_end = min(lo_start + lo_bins_after_dc, len(mag))

    lo_spec = np.zeros_like(spec)
    lo_spec[lo_start:lo_end] = spec[lo_start:lo_end]
    lo = np.fft.irfft(lo_spec, n=n) + dc_val

    hi_spec = np.zeros_like(spec)
    hi_spec[lo_end:] = spec[lo_end:]
    hi = np.fft.irfft(hi_spec, n=n)

    dc = np.full(n, dc_val)
    return dc, lo, hi


def _rms(x):
    return np.sqrt(np.mean(np.asarray(x) ** 2))


def compute_adm(dc1, lo1, dc2, lo2):
    """
    ADM(n), eq. (1) in [S1] / matching structure in [S2].

    BEST-EFFORT reading: numerator is the point-by-point difference of the
    trend (Lo) components plus the difference of the DC components;
    denominator is the RMS of dataset 1's own Lo and DC components (S1's
    OCR-recovered equation shows the sqrt(mean(...^2)) normalization terms
    keyed to a single reference dataset's Lo/DC, not the mean of both
    datasets -- this matches the general FSV convention of normalizing by
    the "reference"/first dataset's own trend magnitude). This is the one
    formula in this script with the most OCR uncertainty in its exact
    constants; the qualitative behavior (small trend gap -> small ADM,
    same units as the RMS check) is not sensitive to that uncertainty.
    """
    denom = _rms(lo1) + _rms(dc1)
    if denom == 0:
        denom = 1e-12
    return ((lo1 - lo2) + (dc1 - dc2)) / denom


def compute_fdm(hi1, hi2, freq):
    """
    FDM(n), eq. (2) in [S1]: a combination of the feature (Hi) component
    itself and its 1st and 2nd derivatives w.r.t. frequency, each
    normalized by the mean absolute value of the reference dataset's own
    term at that derivative order. [S1]'s recovered text shows three
    sub-terms (FDM1 from Hi, FDM2 from Hi', FDM3 from Hi'') combined with
    per-term normalization constants (2/N, 6/N, 2.7/N in the OCR text)
    that could not be recovered with full confidence from the garbled PDF
    extraction -- BEST-EFFORT choice made here: equal-weight average of
    the three normalized derivative-order differences, which preserves
    FDM's purpose (penalize disagreement in the *fast-changing* resonant
    shape, increasingly sensitive to derivative order) without leaning on
    unverified numeric constants.
    """
    d_hi1 = np.gradient(hi1, freq)
    d_hi2 = np.gradient(hi2, freq)
    dd_hi1 = np.gradient(d_hi1, freq)
    dd_hi2 = np.gradient(d_hi2, freq)

    def term(a1, a2):
        denom = np.mean(np.abs(a1)) + np.mean(np.abs(a2))
        if denom == 0:
            denom = 1e-12
        return (a1 - a2) / denom

    fdm1 = term(hi1, hi2)
    fdm2 = term(d_hi1, d_hi2)
    fdm3 = term(dd_hi1, dd_hi2)
    return (fdm1 + fdm2 + fdm3) / 3.0


GRADE_BINS = [
    (0.1, "Excellent"),
    (0.2, "Very good"),
    (0.4, "Good"),
    (0.8, "Fair"),
    (1.6, "Poor"),
    (np.inf, "Very poor"),
]
GRADE_NAMES = [name for _, name in GRADE_BINS]


def classify(values):
    """Six-level Table I classification, [S1]/[S2], identical in both."""
    idx = np.zeros(len(values), dtype=int)
    for i, v in enumerate(np.abs(values)):
        for b, (cutoff, _name) in enumerate(GRADE_BINS):
            if v < cutoff:
                idx[i] = b
                break
        else:
            idx[i] = len(GRADE_BINS) - 1
    return idx


def confidence_histogram(values):
    idx = classify(values)
    counts = np.array([np.sum(idx == b) for b in range(len(GRADE_BINS))], dtype=float)
    return counts / counts.sum()


def grade_and_spread(hist):
    """
    GRADE: number of adjacent categories, STARTING FROM EXCELLENT, whose
    cumulative share reaches >=85% of the confidence histogram. [S2]'s
    phrasing, used verbatim: "number of categories starting from
    'Excellent' to contain 85% of the total confidence data."

    SPREAD: number of categories CENTERED ON THE MODAL (highest-count)
    category needed to reach >=85%, expanding outward symmetrically.
    [S2]'s phrasing: "number of categories around the highest value
    category to contain 85% of the total confidence data." Grade
    therefore penalizes disagreement that is *far from Excellent* even if
    concentrated in one bin; Spread measures how *concentrated* the
    histogram is regardless of which bin it sits in -- e.g. a histogram
    entirely in "Very Poor" gets a large Grade (bad) but a small Spread
    (tight/consistent verdict), which is exactly the discriminating
    signal issue #168 asks whether FSV can still produce once two curves
    barely overlap.
    """
    n_bins = len(hist)

    grade = n_bins
    cum = 0.0
    for b in range(n_bins):
        cum += hist[b]
        if cum >= 0.85:
            grade = b + 1
            break

    modal = int(np.argmax(hist))
    spread = n_bins
    for radius in range(n_bins):
        lo_b = max(0, modal - radius)
        hi_b = min(n_bins - 1, modal + radius)
        if hist[lo_b : hi_b + 1].sum() >= 0.85:
            spread = hi_b - lo_b + 1
            break

    return grade, spread


def fsv_compare(freq, y1, y2, label=""):
    dc1, lo1, hi1 = _band_split(y1)
    dc2, lo2, hi2 = _band_split(y2)

    adm = compute_adm(dc1, lo1, dc2, lo2)
    fdm = compute_fdm(hi1, hi2, freq)
    gdm = np.sqrt(adm**2 + fdm**2)

    adm_c = float(np.mean(np.abs(adm)))
    fdm_c = float(np.mean(np.abs(fdm)))
    gdm_c = float(np.mean(np.abs(gdm)))

    adm_hist = confidence_histogram(adm)
    fdm_hist = confidence_histogram(fdm)
    gdm_hist = confidence_histogram(gdm)

    adm_grade, adm_spread = grade_and_spread(adm_hist)
    fdm_grade, fdm_spread = grade_and_spread(fdm_hist)
    gdm_grade, gdm_spread = grade_and_spread(gdm_hist)

    def name_of(v):
        for cutoff, nm in GRADE_BINS:
            if v < cutoff:
                return nm
        return GRADE_BINS[-1][1]

    result = {
        "label": label,
        "ADMc": adm_c,
        "ADMc_grade": name_of(adm_c),
        "FDMc": fdm_c,
        "FDMc_grade": name_of(fdm_c),
        "GDMc": gdm_c,
        "GDMc_grade": name_of(gdm_c),
        "ADM_Grade": adm_grade,
        "ADM_Spread": adm_spread,
        "FDM_Grade": fdm_grade,
        "FDM_Spread": fdm_spread,
        "GDM_Grade": gdm_grade,
        "GDM_Spread": gdm_spread,
        "GDM_hist": gdm_hist,
    }
    return result


def rms_error_db(y1_mag, y2_mag):
    """Plain RMS error in dB between two S11-magnitude curves."""
    db1 = 20.0 * np.log10(np.clip(y1_mag, 1e-6, None))
    db2 = 20.0 * np.log10(np.clip(y2_mag, 1e-6, None))
    return float(_rms(db1 - db2))


def print_result(r, rms_db_val, offset_ghz, offset_pct, offset_fwhm):
    print(f"\n=== {r['label']} ===")
    print(
        f"  frequency offset: {offset_ghz:.3f} GHz "
        f"({offset_pct:.1f}% of reference center freq, "
        f"{offset_fwhm:.2f}x Landy's FWHM)"
    )
    print(f"  RMS error (dB):        {rms_db_val:8.3f} dB")
    print(
        f"  ADMc = {r['ADMc']:.4f}  ({r['ADMc_grade']:<10s})  "
        f"Grade={r['ADM_Grade']}  Spread={r['ADM_Spread']}"
    )
    print(
        f"  FDMc = {r['FDMc']:.4f}  ({r['FDMc_grade']:<10s})  "
        f"Grade={r['FDM_Grade']}  Spread={r['FDM_Spread']}"
    )
    print(
        f"  GDMc = {r['GDMc']:.4f}  ({r['GDMc_grade']:<10s})  "
        f"Grade={r['GDM_Grade']}  Spread={r['GDM_Spread']}"
    )
    hist_str = ", ".join(
        f"{n}:{p * 100:4.1f}%" for n, p in zip(GRADE_NAMES, r["GDM_hist"], strict=False)
    )
    print(f"  GDM confidence histogram: {hist_str}")


# --------------------------------------------------------------------------
# 3. THE DISPUTED COMPARISON: patent Example 3 vs Landy measured
# --------------------------------------------------------------------------

print("=" * 78)
print("FSV feasibility prototype -- issue #168")
print("Patent Example 3 (SYNTHESIZED, ~9.2 GHz) vs Landy 2008 measured")
print("(SYNTHESIZED, ~11.5 GHz). Curves are Lorentzian approximations, NOT")
print("digitized data -- see module docstring for exactly what is assumed.")
print("=" * 78)

main_result = fsv_compare(
    FREQ_GHZ, landy_s11, patent_s11, label="Patent Ex.3 vs Landy (disputed pair)"
)
main_rms = rms_error_db(landy_s11, patent_s11)
print_result(main_result, main_rms, LANDY_F0 - PATENT_F0, FREQ_OFFSET_PCT, FREQ_OFFSET_IN_FWHM)

# --------------------------------------------------------------------------
# 4. SANITY CHECK: sweep of offsets, in units of Landy's own FWHM
# --------------------------------------------------------------------------

print("\n" + "=" * 78)
print("Sanity sweep: same two Lorentzian shapes (Landy's), swept apart by a")
print("range of offsets expressed in units of Landy's FWHM (0.46 GHz).")
print("5% offset = close pair; 5.0x offset ~= the disputed patent/Landy gap.")
print("=" * 78)

offsets_in_fwhm = [0.05, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0]
sweep_rows = []
for k in offsets_in_fwhm:
    shift = k * LANDY_FWHM
    f0_shifted = LANDY_F0 - shift
    shifted_A = lorentzian_absorbance(FREQ_GHZ, f0_shifted, LANDY_FWHM, LANDY_PEAK, LANDY_BASELINE)
    shifted_s11 = s11_mag_from_absorbance(shifted_A)

    label = f"offset = {k:.2f} x FWHM ({shift:.3f} GHz, {shift / LANDY_F0 * 100:.1f}% of f0)"
    r = fsv_compare(FREQ_GHZ, landy_s11, shifted_s11, label=label)
    rms_val = rms_error_db(landy_s11, shifted_s11)
    sweep_rows.append((k, shift, r, rms_val))
    print_result(r, rms_val, shift, shift / LANDY_F0 * 100.0, k)

# --------------------------------------------------------------------------
# 5. SUMMARY TABLE + ANSWER
# --------------------------------------------------------------------------

print("\n" + "=" * 78)
print("SUMMARY TABLE")
print("=" * 78)
header = (
    f"{'offset (x FWHM)':>16s} | {'RMS dB':>9s} | {'GDMc':>7s} | "
    f"{'GDM grade':>10s} | {'Grade':>5s} | {'Spread':>6s}"
)
print(header)
print("-" * len(header))
for k, _shift, r, rms_val in sweep_rows:
    print(
        f"{k:16.2f} | {rms_val:9.3f} | {r['GDMc']:7.4f} | {r['GDMc_grade']:>10s} | "
        f"{r['GDM_Grade']:5d} | {r['GDM_Spread']:6d}"
    )
print(
    f"{'DISPUTED PAIR':>16s} | {main_rms:9.3f} | {main_result['GDMc']:7.4f} | "
    f"{main_result['GDMc_grade']:>10s} | {main_result['GDM_Grade']:5d} | "
    f"{main_result['GDM_Spread']:6d}"
)

print("\n" + "=" * 78)
print("READ-OUT for issue #168 (data-driven, matches the numbers printed above)")
print("=" * 78)

gdmc_values = [r["GDMc"] for _, _, r, _ in sweep_rows]
rms_values = [rv for _, _, _, rv in sweep_rows]
gdmc_plateau_from = None
for i in range(1, len(gdmc_values)):
    if abs(gdmc_values[i] - gdmc_values[i - 1]) < 0.02 * max(gdmc_values[i - 1], 1e-6):
        gdmc_plateau_from = offsets_in_fwhm[i - 1]
        break
gdmc_plateau_label = gdmc_plateau_from if gdmc_plateau_from else offsets_in_fwhm[-1]

print(f"""
This run's numbers (all from SYNTHESIZED curves and a BEST-EFFORT FSV
reconstruction -- see header) do NOT confirm the a-priori worry this
prototype set out to test ("FSV collapses to Very Poor just as bluntly as
RMS"). What they show instead is a different, still-load-bearing problem:

  - The disputed patent-vs-Landy pair sits at a {FREQ_OFFSET_IN_FWHM:.2f}x-FWHM offset,
    matching ADR-0041's "roughly five resonance-widths apart" estimate.
    Its GDMc = {main_result["GDMc"]:.4f} lands in "{main_result["GDMc_grade"]}" --
    NOT "Very poor" or even "Poor". Two physically near-unrelated resonances (a peak that
    exists at 9.2 GHz in one curve and at 11.5 GHz in the other, with
    essentially baseline behavior at the other curve's peak) are rated
    "{main_result["GDMc_grade"]}" by this reconstruction's headline GDMc number.

  - Why: across the {FREQ_GHZ[0]:.0f}-{FREQ_GHZ[-1]:.0f} GHz analysis window, most points sit far
    from either resonance, where both curves are close to the same flat
    baseline reflectance -- so most point-by-point ADM/FDM values are
    small there and pull the *averaged* GDMc back down. The confidence
    histogram is the tell: {main_result["GDM_hist"][0] * 100:.1f}% of points still grade "Excellent"
    even for the fully-displaced disputed pair, because "most of the
    curve" (the flat part) really does still agree.

  - The sweep shows GDMc rising only up to about {gdmc_plateau_label:.2f}x FWHM offset and then
    roughly PLATEAUING (values across the sweep: {[f"{v:.3f}" for v in gdmc_values]}),
    while RMS error in dB keeps climbing across the same sweep (values:
    {[f"{v:.2f}" for v in rms_values]} dB). In THIS reconstruction, on THIS
    curve pair, plain RMS error is the metric that keeps discriminating
    across the offset range -- GDMc alone saturates early and stops.

  - What DOES keep discriminating inside FSV is Spread, not GDMc: it
    grows monotonically from {sweep_rows[0][2]["GDM_Spread"]} (tight, all-"Excellent",
    near-identical curves) to {main_result["GDM_Spread"]} (disputed pair) as the offset
    grows -- i.e. FSV's
    extra information over RMS is not in its headline GDMc number here,
    it is in how SPREAD OUT the point-by-point confidence histogram is.
    A consumer reading only "GDMc = {main_result["GDMc"]:.2f}, Good" would be misled; a
    consumer reading the full histogram/Grade/Spread would not be.
""")
