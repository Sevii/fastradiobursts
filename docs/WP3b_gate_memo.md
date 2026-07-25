# WP3b Gate Memo — Blind Round 2 (`wp3-blind-v2` / `wp2-frozen-v2`)

**Date:** 2026-07-25. **Status:** complete (round 2). **Verdict: GATE FAIL.**
**Recommendation: withhold Authorization C; WP4 remains blocked (§8.1).** The final authorization is the
PI's; this is a recommendation.

**Pool 1 is now burned. No sealed pool remains.** Per §8.1 / §11, a second failure means **redesign at
the methodology level, not another draw.**

---

## 1. Verdict

| gate | result |
|---|---|
| **G1** efficiency agreement | **PASS** — obs 0.200 vs pred 0.228 (\|Δ\|=0.028 ≤ 0.07), cell coverage 1.00, signed bias −0.016 |
| **G2** false positives | **FAIL** — one class, `real_null`, at **0.0111 vs target 0.010** |

**PASS = G1(all) AND G2(all hard classes). G2 failed. The gate failed.**

## 2. The full result

Hidden mixture: 600 items from test pool 1 (359 sources / 362 bursts), seed sealed, labels committed
19:16:39Z, scores 19:59:16Z, both git-committed before the next step ran. Guardrails verified: labels
untampered, `labels_ts < scores_ts`, freeze held at `a24f285e569e211e`.

| class | n | target | **round 2** | 95% CI hi | round 1 (v1) | validation dry run |
|---|---:|---:|---:|---:|---:|---:|
| **real_null** | 180 | ≤ 0.010 | **0.0111 ✗** | 0.040 | 0.003 | 0.0024 |
| real_null_multicomponent | 17 | report-only | 0.000 | 0.184 | — | 0.000 |
| adverse: drift | 40 | ≤ 0.025 | 0.000 ✓ | 0.088 | — | 0.000 |
| adverse: differential_dm | 40 | ≤ 0.025 | 0.000 ✓ | 0.088 | — | 0.002 |
| adverse: chromatic_echo | 40 | ≤ 0.025 | 0.000 ✓ | 0.088 | — | 0.001 |
| adverse: rfi_remnant | 40 | ≤ 0.025 | 0.000 ✓ | 0.088 | — | 0.001 |
| adverse: **overlapping** | 40 | ≤ 0.025 | **0.000 ✓** | 0.088 | **0.60** | 0.007 |
| adverse: **differential_scattering** | 40 | ≤ 0.100 | **0.000 ✓** | 0.088 | **0.25** | 0.010 |
| adverse: **scintillation** | 40 | ≤ 0.100 | **0.075 ✓** | 0.199 | **0.70** | 0.039 |
| efficiency, μ ≥ 0.5 | 35 | — | 0.486 | — | — | 0.446 |
| efficiency, all μ | 140 | — | 0.200 | — | — | 0.300 |

## 3. What actually failed

**Two real bursts out of 180.** At n=180 a ≤0.010 target permits at most one (1/180 = 0.0056; 2/180 =
0.0111). Two were flagged:

| item | host | multi? | M | p_robust | worst family | n_proposals | peak S/N |
|---|---|---|---:|---:|---|---:|---:|
| ITEM00318 | FRB20181218A | no | 1.157 | 0.0085 | adverse_overlapping | 1 | 14.3 |
| ITEM00469 | FRB20200506E | no | 1.491 | 0.0085 | adverse_differential_dm | 2 | 7.9 |

Both are single-component real bursts with very few proposals, both cleared α = 0.05 by a wide margin
(p ≈ 0.0085). ITEM00469's `M = 1.4914` is exactly the statistic's saturation ceiling — the value taken
when per-band magnification spread is identically zero, the degenerate corner identified during
calibration (`docs/WP3b_dry_run_findings.md` §3).

## 4. Honest statistical context — which does NOT change the verdict

The observation is **consistent** with the pre-registered expectation. At the validated rate of 0.0024,
the expected count in 180 is 0.43, and **P(X ≥ 2) ≈ 7%**. The 95% interval on 2/180 is [0.003, 0.040],
which contains the validated 0.0024.

So this is not evidence that the analysis misbehaves. It is a gate boundary crossed by one event, on a
rule we committed to in advance. **We do not get to relitigate the rule after seeing the number** — that
is precisely what the preregistration exists to prevent. The verdict is FAIL.

**A methodological miss, recorded plainly.** Before scoring, the ≤0.01 deterministic target was relaxed
to 0.025 *because* a sub-resolution target tests sampling noise rather than the analysis (addendum §3,
decision 3). That power analysis was run for the five deterministic classes and for scintillation — and
**not** for `real_null`. The guard that was added,
`test_every_gated_target_is_expressible_at_its_sample_size`, only requires `target ≥ 1/n`, which 0.01 at
n=180 satisfies; it guarantees one event is survivable, not two. Had the same P(fail | analysis correct)
calculation been run on `real_null`, it would have shown ~7% and the target would have been argued
before the draw rather than after. That omission is on the analysis team, and it is why the memo reports
a failed gate rather than a passed one.

## 5. What round 2 nevertheless establishes

The round-1 failure mode is **fixed, out-of-sample, on a genuinely untouched source-disjoint pool**:

| imitator | round 1 (v1, blind) | **round 2 (v2, blind)** |
|---|---:|---:|
| scintillation | 0.70 | **0.075** |
| overlapping | 0.60 | **0.000** |
| differential scattering | 0.25 | **0.000** |

G1 passed: recovery agrees with the v2 prediction (0.200 vs 0.228), with full cell coverage and
negligible bias. Efficiency at μ ≥ 0.5 is 0.486 [n=35], consistent with the 0.446 measured on validation.
The within-burst multiple-comparison correction generalises.

These are measurements, not authorizations. They stand as an **observable-space characterisation** of the
revised pipeline regardless of the gate outcome.

## 6. §8.1 stop condition — TRIGGERED, and now terminal for the draw-again route

> *"Do not run the catalog-wide search if WP3 fails the hidden-injection gate."*

WP4 is blocked. Both pools are spent: pool 0 (round 1) and pool 1 (round 2). §8.1 / §11 are explicit that
after K failures the response is **redesign at the methodology level, not another draw** — the catalog is
finite and further partitions would not be independent.

**Not legitimate from here:** re-targeting `real_null` and re-scoring pool 1; drawing a "pool 2" from
already-used sources; or reporting round 2 as a pass with a footnote. Each would convert a
pre-registered test into a post-hoc one.

**Available to the PI:**
1. **Report the measurement without the authorization.** §5's numbers are a legitimate, fully-auditable
   characterisation of detectable lensing-like echoes and their false-positive behaviour — an
   observable-space rate/upper-limit result, which the proposal already identifies (§2, obstacles §1) as
   the claim this data can support.
2. **Methodology redesign**, then a gate on genuinely new data (a future CHIME/FRB catalog release), not
   on a re-partition of this one.
3. **Escalate the target-construction defect** in §4 as a documented process finding for whatever gate
   design follows.

## 7. Provenance

Analysis `wp2-frozen-v2` (`a24f285e569e211e`), harness `wp3-blind-v2` (`27c378c153546ecd`), calibration
`070b1900b4ce0579…` (75 cells, 26,962 dev null realizations), α = 0.05. Preregistration signed
2026-07-25 and committed before the draw (`6a5d215`); scores committed before unblinding (`929b292`).
Pool 1 verified untouched pre-draw: 0 of round 1's 640 hosts, 0 source overlap with pool 0, partition
reproducing round 1's exactly. Quarantine held (23 TNS); the named candidates were **not** evaluated.
Round data on popos `~/frb_catalog2_prep/wp3b/round2/`; audit trail `docs/wp3b_artifacts/`.
