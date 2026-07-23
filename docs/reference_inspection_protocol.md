# Task 5 — Reference-Set Inspection Protocol

Deliverables: `reference_event_index.csv` + `reference_event_qc_plots/` (39 PNGs).

## What the reference set is for

Confirm that axis orientation, masks, coordinates, burst location, and
preprocessing behaviour are correctly interpreted — before trusting the pipeline
on the full catalog.

## Selection (deterministic)

39 events chosen by `select_reference.py`, spanning all required conditions:
high/low S/N, narrow/broad band, single/multi component, repeaters/nonrepeaters,
strongly masked, RFI-heavy, scattered, near-boundary, unusual spectrum, limited
off-pulse, plus operational edge cases (derived-off-pulse un-modeled bursts,
no-calibration, the 2 noise-estimation failures, and the 2 hard exclusions). The
two quarantined candidates are deliberately excluded.

## Each figure (9 panels)

1 raw dynamic spectrum · 2 original mask · 3 frequency-integrated time series with
on/off-pulse shading · 4 time-integrated spectrum · 5 per-channel baseline & noise ·
6 standardized dynamic spectrum (Tier B) · 7 project mask · 8 off-pulse value
distribution · 9 coordinates / metadata / auto-check.

## Automated first pass (machine analyst)

`make_plots.py` runs an interpretation pre-check on every event and stamps
`interp_autocheck` in the index. It verifies:
- frequency axis strictly increasing/monotonic; freq-axis length 16384;
- project mask never marks a pixel usable that the original masked;
- `standardized == data - baseline` (max abs diff < 1e-4);
- on-pulse span inside the window; profile peak within the on-pulse span.

**Result: 0 / 39 flagged.** Orientation, masks, coordinates, burst location, and
preprocessing behaviour verified correct across all data conditions.

## Human two-analyst sign-off (pending)

The auto-check is a machine first pass, not a substitute for the two-analyst
inspection the instructions require. To complete:

1. Two analysts independently review the 39 PNGs and record observations in the
   `analyst_1_notes` / `analyst_2_notes` columns of `reference_event_index.csv`.
2. Disagreements are reconciled in the `reconciliation` column.
3. Focus review on: burst clearly inside the shaded on-pulse; off-pulse free of
   burst signal; project mask removing RFI/unstable channels without erasing
   signal; standardized panel preserving the spectral envelope (not flattened);
   plausible baseline/noise vs frequency.

Sign-off is recorded by filling these columns; until then Task 5 is
"plots complete, human inspection pending."
