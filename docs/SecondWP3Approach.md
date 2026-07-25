## Assessment of the statistical problem

The pipeline is testing an **adaptively selected maximum**, not a prespecified component pair. For burst (i), the operative statistic is approximately

[
M_i=\max_{1\le j\le m_i} T_{ij},
]

where (m_i) is the number of proposed windows and (T_{ij}) summarizes how convincingly proposal (j) passes the copy, achromaticity, and robustness tests.

The development analysis calibrated (T_{ij}) for one known window, while the production pipeline evaluates roughly eight proposals and retains the best. The blind-test deterioration—such as overlapping copies rising from 0% to 70%—is therefore consistent with adaptive selection rather than ordinary threshold miscalibration. 

Even under an unrealistic independence assumption, a 1% per-window false-positive probability becomes

[
1-(1-0.01)^8 \approx 7.7%
]

per burst. The real windows are correlated, heterogeneous, and generated from the data, so a simple Bonferroni factor of eight would be neither accurate nor especially efficient.

The three approaches below attack this in different ways.

---

# 1. End-to-end per-burst max-statistic calibration

### Basic idea

Replace the per-window null distribution with the null distribution of the **entire search result**:

[
M_i=\max_j T_{ij}.
]

Every null realization must go through:

1. window proposal,
2. delay search,
3. copy fitting,
4. achromaticity diagnostics,
5. robustness tests,
6. selection of the best surviving proposal.

This directly calibrates the quantity the pipeline actually reports.

### Constructing a scalar score

The current candidate decision is multidimensional: (\Delta\chi^2), NCC, reduced-(\chi^2), achromaticity, and robustness all matter. 

You do not necessarily need to replace these with a machine-learning classifier. A transparent scalar can be constructed as the weakest standardized margin:

[
T_{ij}=
\min_k
\left[
\frac{x_{ijk}-c_k}{s_k}
\right],
]

with signs reversed for criteria where smaller is better. Here:

* (x_{ijk}) is diagnostic (k),
* (c_k) is its frozen threshold,
* (s_k) is a prespecified scaling constant.

Then:

* (T_{ij}>0) means all gates pass;
* a larger value means the proposal clears its weakest gate by a larger margin;
* (M_i=\max_j T_{ij}) measures the strongest candidate in the burst.

This preserves the interpretation of the existing criterion while allowing ranked p-values.

### Empirical burst-level p-value

For an observed maximum (M_i), calculate

[
p_i=
\frac{1+\sum_{b=1}^{B} I(M_b^{(0)}\ge M_i)}
{B+1},
]

where each (M_b^{(0)}) comes from a complete null run.

The null ensemble should contain separately identified strata:

* real multi-component bursts;
* scintillation injections;
* differential-scattering injections;
* matched cross-event pairs;
* structure-preserving surrogates;
* instrumental and RFI controls.

Because no finite simulation library spans all plasma behavior, I would calculate a tail probability under each relevant null family and use the conservative value

[
p_i^{\mathrm{robust}}=\max_h p_{ih}.
]

Equivalently, set the threshold using the most adverse null family rather than pooling everything into an average null that could dilute scintillation.

### Conditional calibration

The maximum distribution will depend on more than the number of proposals. Useful conditioning variables include:

* proposal count (m_i);
* burst SNR;
* effective bandwidth;
* masked-channel fraction;
* temporal width;
* a prespecified complexity measure;
* repeater versus apparent non-repeater;
* minimum proposed delay.

You can estimate

[
P_0(M_i\ge m\mid Z_i)
]

using stratified empirical distributions, quantile regression, or a hierarchical generalized Pareto tail model.

Conditioning is important because otherwise difficult, high-SNR, or structurally complex bursts will dominate the extreme tail and force an unnecessarily severe threshold on clean bursts.

### Handling the limited hard-null sample

Only 96 multi-component bursts appear in the sealed test subset, and the same source can contribute multiple dependent bursts. 

I would use:

* source-cluster bootstrap confidence intervals;
* partial pooling across null subclasses;
* a generalized Pareto distribution only above a prespecified high threshold;
* conservative upper confidence bounds for false-positive probabilities;
* full-pipeline surrogates to improve resolution, while keeping real hard nulls as the validity benchmark.

Do not claim a (10^{-4}) tail probability merely because a fitted curve extrapolates there. Report how much of the tail is empirical and how much is model-based.

### Advantages

This is the cleanest correction because it changes neither the physical signal model nor the window proposer. It answers the exact statistical question: “How exceptional is the best candidate found after conducting the entire search?”

### Main limitation

It may substantially lower sensitivity once the true multiplicity penalty is paid. That would be an honest scientific result rather than a failure of the method.

**Recommendation:** This should be the first approach implemented. It is the correct baseline against which the other approaches should be compared.

---
