# WP1 Reproducibility Matrix

Status: EXACT / APPROX / NOT / N-A (out of scope) / SUBJECTIVE (non-algorithmic).
Literal = authors' code on Tier A; Clean-room = independent blind impl on our Tier B.

| statistic | reported_value | literal_status | cleanroom_status | robust | cause |
|---|---|---|---|---|---|
| processed count | 340 | EXACT | EXACT | nan |  |
| candidate count [G_3] | 11 | EXACT | NOT | nan | spike-detection algorithm/threshold under-determined (W1.4 factorial: ALGORITHM-dominated; W1.5: count 22->3 across spike kSigma in [2,4]) |
| candidate count [SG_20] | 16 | EXACT | N-A | nan |  |
| candidate count [SG_100] | 12 | EXACT | N-A | nan |  |
| funnel 11->9 (morphology reassessment) | 9 | SUBJECTIVE | SUBJECTIVE | nan | authors' 11->9 step is a manual morphology reassessment; no algorithm to reproduce |
| final candidates (->2) | 2 | SUBJECTIVE | NOT | nan | spike-detection algorithm/threshold under-determined (W1.4 factorial: ALGORITHM-dominated; W1.5: count 22->3 across spike kSigma in [2,4]) |
| candidate membership [G_3] | 11 FRBs | EXACT | NOT | nan | spike-detection algorithm/threshold under-determined (W1.4 factorial: ALGORITHM-dominated; W1.5: count 22->3 across spike kSigma in [2,4]) |
| FRB20190131D: detected | True | EXACT | EXACT | 1.0 |  |
| FRB20190131D: delay dt (ms) | 8.82 | EXACT | EXACT | 1.0 |  |
| FRB20190131D: has_drift | False | EXACT | EXACT | 1.0 |  |
| FRB20190131D: magnification mu / R_f | R_f=0.35/0.55 | N-A | APPROX | 1.0 | convention/episode difference: authors' R_f<1 (weaker image) vs clean-room mag_ratio>1 |
| FRB20211115A: detected | True | EXACT | NOT | 0.882 | FRB20211115A: no ACF spike on Tier B at any threshold (W1.4 MIXED = algorithm + preprocessing suppression; absent under authors' own SG_100) |
| FRB20211115A: delay dt (ms) | 6.86 | EXACT | NOT | 0.882 | FRB20211115A: no ACF spike on Tier B at any threshold (W1.4 MIXED = algorithm + preprocessing suppression; absent under authors' own SG_100) |
| FRB20211115A: has_drift | False | EXACT | NOT | 0.882 | FRB20211115A: no ACF spike on Tier B at any threshold (W1.4 MIXED = algorithm + preprocessing suppression; absent under authors' own SG_100) |
| FRB20211115A: magnification mu / R_f | R_f=0.37/0.38 | N-A | NOT | 0.882 | FRB20211115A: no ACF spike on Tier B at any threshold (W1.4 MIXED = algorithm + preprocessing suppression; absent under authors' own SG_100) |
| spike delays of 11 G_3 candidates | 11 FRBs | EXACT | NOT | nan | spike-detection algorithm/threshold under-determined (W1.4 factorial: ALGORITHM-dominated; W1.5: count 22->3 across spike kSigma in [2,4]) |
| redshifted lens mass | reported in paper | N-A | N-A | nan |  |
| source redshift z_s | reported in paper | N-A | N-A | nan |  |
| f_PBH | reported in paper | N-A | N-A | nan |  |

## Summary
- rows: 19
- literal: EXACT=12, N-A=5, SUBJECTIVE=2
- cleanroom: APPROX=1, EXACT=4, N-A=5, NOT=8, SUBJECTIVE=1