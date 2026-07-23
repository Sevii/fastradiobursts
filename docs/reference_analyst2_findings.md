# Reference Set — Analyst-2 Review (AI) & Reconciliation

**Reviewer:** Claude (AI), acting as the second, independent reviewer of the WP0
reference set. **This is an AI review, not a human sign-off** — recorded honestly
so the audit trail is truthful. If the preregistration requires two *human*
analysts, treat this as a machine pre-review and have a colleague be the formal
second analyst.

**Analyst 1:** the user (notes in `reference_event_index.csv`, `analyst_1_notes`).

## Methodology (honest scope)

- **14 of 39 figures directly visually inspected** by AI-analyst-2, chosen to cover
  every data-condition category **and** all four events Analyst 1 flagged most
  strongly: FRB20190724A, FRB20190925B, FRB20191222A, FRB20200115A, FRB20200116B,
  FRB20200119E, FRB20200427A, FRB20200723B, FRB20200922B, FRB20201014B,
  FRB20201125B, FRB20210216A, FRB20211031A, FRB20221116F.
- The remaining 25 were assessed from the **per-event automated interpretation
  check** (which ran on all 39 and verifies freq-axis orientation, project-mask ⊆
  original, `standardized == data − baseline`, and burst-peak-inside-on-pulse —
  0/39 flagged), plus per-event metrics and the characterized class pattern. These
  are marked `[auto+metrics]` in the CSV, not `[viewed]`.

## Reconciliation with Analyst 1

Most of Analyst 1's notes describe **appearance/data-quality** ("faint", "blotch",
"scattered", "box"), not interpretation errors. On the interpretation question the
two reviewers **agree**: axis orientation, masks, coordinates, burst location, and
standardization are correctly handled across the set. Several of Analyst 1's
"looks weird" flags resolve to expected behaviour:

- **"tight lines"** (FRB20191222A) = masked RFI channels — expected.
- **"cut in half"** (FRB20200723B) = on-pulse correctly covering a long scattering
  tail — expected.
- **"box instead of peak"** (FRB20200427A) = on-pulse shading width (region+guard)
  around a real compact burst — expected.
- **"blotch"** (multi-component events) = real drifting sub-bursts — correct.

## Substantive findings (from the genuine review)

**F1 — Eligibility bandwidth overstated for heavily flag-masked events.**
E007 usable-bandwidth uses the *channel* mask `good_freq`, but some events are
heavily *pixel*-masked (`flag`): FRB20201125B (96%), FRB20211031A (85%),
FRB20211202A (82%) report "usable BW" 340–370 MHz yet have real data only in a
~25–75 MHz sliver. The **project mask captures this** (Tier B `n_usable`/masked-frac
are correct), but the eligibility *status* let them through as provisional on an
overstated bandwidth. **Recommend** adding a pixel-`flag`-based usable-fraction
criterion to eligibility. Agrees with A1's "not sure enough data" instinct.

**F2 — Derived off-pulse unreliable for wide-window, no-clear-burst un-modeled events.**
The `derived_profile` fallback (87 un-modeled bursts) works when a burst is present
(FRB20200115A) but picks noise when the wide 814-bin window has no clear burst,
and off-pulse is then contaminated (FRB20190724A diagonal streak; FRB20200119E
RFI-dominated). **Recommend** flagging derived-off-pulse wide-window/no-peak events
for extra WP1 scrutiny or exclusion. Agrees with A1's "trash"/"weird flat".

**F3 — E006/E014 remove some real high-S/N bursts whose components fill the window.**
FRB20201014B (7-component repeater, S/N 117) excluded on E006 (14 off-pulse bins);
FRB20210216A (real burst, 4× downsampled) → E014 because too few windowed off-pulse
samples. Both are correct under the frozen rules, but the bursts are real.
**Recommend** WP1 consider estimating noise from the Tier A full-timeseries
`statistics` group when windowed off-pulse is insufficient. Agrees with A1's
"might be useful".

**F4 — No interpretation errors found.** Orientation, mask subsetting, coordinates,
burst location, and `standardized == data − baseline` verified correct on every
inspected event and by the automated check on all 39. The reference set confirms
the pipeline interpretation is correct — the WP0 gate item 11 intent is met at the
interpretation level.

## Verdict

Interpretation is correct across the set (gate-item-11 intent satisfied). Findings
F1–F3 are **eligibility/preprocessing-policy refinements for WP1**, not Tier A/B
correctness bugs, and none require reprocessing to fix. The formal exit-gate item
11 remains **PENDING a human two-analyst sign-off**; this AI review + Analyst 1's
notes are the inputs to that decision.
