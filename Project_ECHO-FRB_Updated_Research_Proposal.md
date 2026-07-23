**PROJECT ECHO-FRB | RESEARCH PROPOSAL | VERSION 2.0** 

**PROJECT ECHO-FRB** 

**A Preregistered Search for Resolved Gravitationally Lensed Fast Radio Bursts in CHIME/FRB Catalog 2** 

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ 

**Updated Research Project Proposal** 

**Version** 2.0 

**Date** July 22, 2026 

**Project stage** Reproducibility and methods development **Primary data** Public CHIME/FRB Catalog 2 dynamic spectra 

**Compute assumption** Existing 16-core Linux workstation, 64 GB RAM, 16 GB GPU  VRAM 

**Additional compute budget** Up to approximately $1,000, released only after decision gates *Draft for technical review and staged authorization*

Project ECHO-FRB \- July 22, 2026 \- Page 1   
**PROJECT ECHO-FRB | RESEARCH PROPOSAL | VERSION 2.0** 

**Executive Summary** 

Project ECHO-FRB will conduct a preregistered, injection-calibrated search for resolved two-image gravitational lensing  signatures in the public CHIME/FRB Catalog 2 intensity data. The target signal is not merely a burst with two peaks. It is a second time-frequency component that is statistically consistent with a delayed and scalar-magnified copy of the first component under a  restricted point-mass lens model. The analysis will ask whether any observed component pair is more copy-like than can be  explained by the empirical population of intrinsically complex FRBs, chromatic plasma propagation, instrumental artifacts,  correlated noise, or the catalog-wide look-elsewhere effect. 

The project begins with a strict reproduction audit of the two recently reported candidates, FRB 20190131D and FRB 20211115A.  It will reproduce the published workflow as literally as possible, then perform an independent clean-room reproduction. The  named candidates will be quarantined while the new pipeline is designed. A lightweight first-stage scan will be applied to every  eligible Catalog 2 spectrum rather than only to events already labeled as multi-component. Detailed inference will be reserved for a small candidate set. 

The primary statistic will be a masked, noise-weighted two-dimensional copy-consistency score in the time-frequency plane. Its  false-positive distribution will be calibrated primarily from real complex bursts, matched cross-event component pairs, structure preserving resamples, and physically motivated adverse simulations. Point-lens echoes will be injected into real observations to  

measure recovery efficiency as a function of delay, magnification ratio, signal-to-noise ratio, width, scattering, bandwidth, and data quality. Thresholds and robustness tests will be frozen before the named candidates or the full catalog are evaluated. 

The primary population result will be an observable-space rate or upper limit for detectable lensing-like echoes in Catalog 2\.  Conversion to compact-object or primordial-black-hole abundance will be treated as a separate, conditional inference requiring  explicit assumptions about source distances, lens distributions, magnification bias, and CHIME selection effects. A catalog  candidate will not be described as a discovery without independent higher-time-resolution corroboration and instrument-specific  validation. 

**Authorization recommendation** 

Authorize Phase 0 and Phase 1 on the existing workstation. Purchase storage only after the archive footprint is measured.  Release cloud or additional compute funds only after the pipeline reproduces the published candidates and passes a hidden injection validation at a predetermined false-positive rate. 

**Contents** 

1\. Scientific context and rationale 

2\. Research question, scope, and hypotheses 

3\. Data resources and study population 

4\. Research objectives 

5\. Experimental design and analysis pipeline 

6\. Statistical framework 

7\. Candidate evidence standard 

8\. Work packages and decision gates 

9\. Compute, storage, and software plan 

10\. Team, governance, and reproducibility 

11\. Risks and mitigation 

12\. Timeline, deliverables, and success criteria 

13\. Expected scientific impact 

References 

Appendix A. Preregistration checklist 

Appendix B. Minimum candidate audit record

Project ECHO-FRB \- July 22, 2026 \- Page 2   
**PROJECT ECHO-FRB | RESEARCH PROPOSAL | VERSION 2.0** 

**1\. Scientific Context and Rationale** 

Fast radio bursts (FRBs) are brief, bright extragalactic radio transients with rich temporal and spectral structure. CHIME/FRB  Catalog 2 contains 4,539 bursts from 3,641 sources and supplies total-intensity dynamic spectra from 400 to 800 MHz at 0.983 ms  time resolution, together with morphology, localization, exposure, and signal measurements \[1\]. The uniform reprocessing and  public data products make the catalog unusually suitable for a large, auditable search for rare propagation signatures. 

A compact gravitational lens can produce two unresolved angular images of the same FRB that arrive at different times. At the  telescope, a sufficiently large lensing delay appears as two burst components. In the ideal geometric-optics limit, the components  should preserve the same intrinsic time-frequency morphology, apart from a relative magnification, a constant delay, and  observational noise \[3\]. This produces a more restrictive prediction than generic multi-component emission. 

A 2026 preprint reported two possible microlensing signatures in Catalog 2, FRB 20190131D and FRB 20211115A, and  interpreted their delays and flux ratios as possible intermediate-mass black-hole lenses \[2\]. The same paper emphasized that  intrinsic burst structure and propagation effects remain plausible alternatives. This creates a timely reproduction target, but it also  raises the methodological question that motivates ECHO-FRB: how often do naturally complex bursts imitate delayed copies after  realistic preprocessing and a catalog-wide search? 

The project is designed so that a null result remains scientifically useful. A calibrated search can reject candidate interpretations,  demonstrate the limitations of autocorrelation-based screening, measure the frequency of highly copy-like intrinsic structures, and  place upper limits on detectable echo rates. The work therefore does not depend on confirming either reported candidate. 

**1.1 Scientific novelty** 

 A catalog-wide first-stage search that does not require a pre-existing multi-peak morphology label.  A two-dimensional time-frequency copy test rather than a frequency-integrated autocorrelation trigger as the primary  evidence. 

 An empirical null population built from real complex FRBs and matched component pairs. 

 A preregistered blind protocol with hidden injections, frozen thresholds, and source-aware global trials corrections.  A strict separation between an observable echo-rate result and model-dependent compact-object abundance inference. 

**Central methodological principle** 

The project will not ask whether a burst looks unusual. It will test whether one component is an achromatic delayed copy of  another under a restricted physical model, and whether the observed degree of agreement is absent from a realistically  calibrated null population. 

**2\. Research Question, Scope, and Hypotheses** 

**2.1 Primary research question** 

Among all usable CHIME/FRB Catalog 2 intensity observations, are there events containing a resolved second component that is  statistically consistent with a delayed, scalar-magnified copy of the first component at a similarity level not produced by intrinsic  FRB morphology, plasma propagation, instrumental artifacts, correlated noise, or the catalog-wide look-elsewhere effect? 

**2.2 Strict lensing hypothesis** 

For a resolved two-image event, the observed intensity can be approximated by: 

*D(t, nu) \= S(t, nu) \+ mu S(t \- Delta t, nu) \+ N(t, nu)* 

where S is the intrinsic burst intensity, Delta t is the image delay, mu is the relative magnification of the delayed image, and N  includes measurement noise and residual contamination. The discovery model will impose one delay across the observing band  and one scalar magnification ratio after baseline and bandpass treatment. It will not allow arbitrary frequency-dependent warping. 

For an isolated point-mass lens, the observables can later be mapped to a redshifted lens-mass scale through the standard point-lens time-delay relation. Detection efficiency will initially be mapped directly in observable space, Delta t and mu, rather than  assuming a cosmological lens population during candidate selection.

Project ECHO-FRB \- July 22, 2026 \- Page 3   
**PROJECT ECHO-FRB | RESEARCH PROPOSAL | VERSION 2.0** 

**2.3 Competing hypotheses** 

| Hypothesis  | Predicted behavior  | Role in analysis |
| :---- | :---- | :---- |
| H-L: strict gravitational lens  | One achromatic delay; one relative   magnification; shared detailed time-frequency  morphology. | Primary discovery model. |
| H-LP: lens plus differential propagation  | Constant gravitational delay with tightly  constrained chromatic magnification, differential DM, or differential scattering. | Prespecified robustness extension; not the  primary discovery model. |
| H-I: independent intrinsic components  | Separate widths, spectra, drifts, and temporal  substructure; components may be correlated but  are not copies. | Main astrophysical null. |
| H-P: plasma propagation  | Chromatic delays, caustic magnification, spectral fringes, or path-dependent propagation  distortions. | Adverse propagation null; no single model is  treated as exhaustive. |
| H-N: instrumental or analysis artifact  | Noise, RFI, masking edges, background error,  dedispersion mismatch, interpolation, or fitting  artifacts. | Instrumental null and quality-control category. |

**2.4 Claims the project can and cannot support** 

From public Catalog 2 intensity data, the project can establish reproducibility, catalog-global statistical significance under stated  nulls, an efficiency map for resolved echoes, and an observable-space echo rate or upper limit. It may identify targets that justify  collaboration access to higher-resolution data. 

Catalog data alone cannot prove that a lens is primordial, that it constitutes dark matter, or that a specific foreground object is  absent. The approximate Catalog 2 localization is generally insufficient for decisive foreground association work, and the lens  mass remains conditional on source distance, lens position, and lens model. Any compact-object abundance constraint will be  labeled model-dependent. 

**3\. Data Resources and Study Population** 

**3.1 Primary dataset** 

The primary dataset is the public CHIME/FRB Catalog 2 release \[1\]. The first operational task will be to create an immutable  manifest of every downloaded file, checksum, data shape, time and frequency coordinate, mask, usable off-pulse interval, and  catalog association. Archive size, compression ratio, and preprocessing throughput will be measured before storage or compute  purchases are made. 

**3.2 Named candidate holdout** 

FRB 20190131D and FRB 20211115A will be used only during the literal reproduction audit and then quarantined. Their new pipeline scores will remain hidden until the analysis protocol and thresholds are frozen. Intermediate events identified by the  published search should also be recorded so that the project can test whether the new statistic changes the ranking rather than  merely comparing two selected examples. 

**3.3 Higher-resolution supporting data** 

The public Catalog 1 baseband release contains 140 events with substantially improved time resolution, coherent dedispersion,  sub-arcminute localization, and polarization information \[4\]. The project will determine whether any relevant candidate has public  baseband coverage. If a Catalog 2 candidate survives the frozen search, the team will seek CHIME/FRB collaboration review and  determine whether nonpublic baseband or polarization products exist. 

**3.4 Eligibility criteria** 

 A readable dynamic spectrum with validated time and frequency coordinates. 

 A usable off-pulse interval sufficient to estimate channel-dependent noise and residual covariance.  Enough unmasked bandwidth and time coverage to test at least one prespecified delay. 

 No unrecoverable saturation, truncation, or data corruption in the candidate region. 

 Every exclusion must be machine-readable and assigned a single primary reason code.

Project ECHO-FRB \- July 22, 2026 \- Page 4   
**PROJECT ECHO-FRB | RESEARCH PROPOSAL | VERSION 2.0** 

The main search will include every spectrum meeting these requirements, regardless of catalog morphology label. Repeater status,  source identity, and morphology will be retained for stratification and source-aware null calibration. 

**4\. Research Objectives** 

**Objective 1 \- Reproduce the reported candidates.** Reproduce the published pipeline and reported candidate statistics, then  perform an independent clean-room implementation. Determine which results depend on masking, smoothing, background  estimation, component windows, or frequency subdivision. 

**Objective 2 \- Develop an auditable two-dimensional copy statistic.** Measure delayed-copy consistency directly in the dynamic  spectrum, with explicit noise, masks, interpolation, and nuisance parameters. Use machine learning only for proposal acceleration,  never as the final evidence score. 

**Objective 3 \- Construct a realistic empirical null population.** Measure how often real complex FRB morphology, propagation  effects, noise, and analysis artifacts produce copy-like pairs. Preserve source-level dependence and separate repeaters from  apparent nonrepeaters where needed. 

**Objective 4 \- Measure detection efficiency by injection.** Inject delayed copies into real observations and map recovery over  delay, magnification, S/N, width, scattering, bandwidth, overlap, and data quality. Use adaptive injection allocation where the  efficiency surface changes rapidly. 

**Objective 5 \- Conduct a blinded catalog-wide search.** Freeze preprocessing, thresholds, and global-significance calculations  before evaluating the named candidates and the full catalog. 

**Objective 6 \- Produce candidate evidence or calibrated limits.** Publish candidate rankings and robustness diagnostics, or an  observable-space upper limit. Derive compact-object abundance constraints only after the selection model passes a separate  validation gate. 

**5\. Experimental Design and Analysis Pipeline** 

**5.1 Phase 0: literal and independent reproduction** 

1\. Inventory the public data products, published code, parameter choices, and candidate tables associated with the 2026  microlensing claim \[2\]. 

2\. Run the authors' available workflow, or reproduce it as literally as possible, using documented software versions and file  hashes. 

3\. Implement a clean-room version from the paper's stated equations and thresholds. 

4\. Reproduce the candidate-selection path, not only the final two events. Record all intermediate candidates and every filter that  removes them. 

5\. Perform a controlled sensitivity analysis over RFI masks, smoothing, rebinning, time windows, background regions, and  frequency-band definitions. 

The output will be a reproducibility matrix showing whether each reported statistic is reproduced exactly, approximately, or not at  all. Any discrepancy will be traced to data version, preprocessing, software, numerical tolerance, or undocumented choice before  the project proceeds. 

**5.2 Standardized preprocessing** 

 Validate array orientation, units, cadence, channel frequencies, and metadata against a small manually inspected reference set.  Retain original masks and create a separate project mask; never overwrite the archived product.  Estimate per-channel baseline and noise from off-pulse regions using robust statistics. Preserve the true spectral envelope  rather than normalizing every channel to identical burst amplitude. 

 Use catalog dedispersion as the baseline. Permit only a prespecified small DM perturbation as a robustness diagnostic, not as a candidate-specific tuning parameter. 

 Record every smoothing, interpolation, and rebinning operation. The primary analysis will use one frozen representation;  alternative resolutions will be diagnostic tests. 

 Estimate correlated noise where material. Candidate residuals will be tested for structure rather than judged only by a scalar  correlation coefficient. 

**5.3 Tier 1: catalog-wide candidate generation** 

A lightweight scan will operate on every eligible spectrum. It will identify possible component windows or delayed-energy  matches without requiring the catalog to label the burst as multi-peaked. Candidate generation may use simple segmentation,  matched filtering, or a fast proposal network, but its threshold will be deliberately permissive and calibrated on null data. The  purpose is computational triage, not evidence.

Project ECHO-FRB \- July 22, 2026 \- Page 5   
**PROJECT ECHO-FRB | RESEARCH PROPOSAL | VERSION 2.0** 

The initial delay domain will be selected after the archive audit. The lower boundary must exceed the effective temporal resolution enough to distinguish two components; the upper boundary is limited by the saved time window and the availability of clean off pulse data. Overlapping-image searches may be developed as a later extension, but the primary project concerns resolved echoes. 

**5.4 Tier 2: masked two-dimensional copy test** 

For proposed component windows A and B, the primary score will minimize a noise-weighted residual over a common valid pixel  set V: 

*chi2\_copy \= min\_(Delta t, a) Sum\_V \[B(t,nu) \- a A(t-Delta t,nu)\]^2 / \[sigma\_B^2(t,nu) \+ a^2 sigma\_A^2(t,nu)\]* 

Here a is the relative magnification and Delta t may be evaluated with prespecified fractional-bin interpolation. The final test  statistic will be defined before unblinding and may combine reduced residual, normalized cross-correlation, and posterior  predictive diagnostics. Complexity penalties will be explicit whenever extra nuisance parameters are introduced. 

**5.5 Mandatory robustness diagnostics** 

| Diagnostic  | Required test |
| :---- | :---- |
| Achromatic delay  | Estimate delay independently in broad frequency regions and with a  smooth delay-versus-frequency model. A candidate must be consistent  with one delay within calibrated uncertainty. |
| Magnification stability  | Estimate the component ratio by frequency region. Strong unexplained  variation is evidence against the strict lens model. |
| Fine-structure ordering  | Test whether identifiable peaks, gaps, and substructure repeat in the same  sequence. |
| Residual structure  | Inspect and quantify residual autocorrelation, drift, spectral bands, and  channel-edge effects after the best copy fit. |
| Resolution stability  | Repeat prespecified analyses under limited rebinning and smoothing  changes. A candidate that exists only at one arbitrary representation is  downgraded. |
| Leave-band-out stability  | Refit after excluding each broad frequency region. No single narrow band  may control the result. |
| Window stability  | Perturb component boundaries within a prespecified range. Candidate  status must not depend on a hand-selected window. |
| DM and scattering consistency  | Test for differential DM or scattering. Equality is not strong positive  evidence, but a significant difference can reject the strict model. |

**5.6 Empirical null population** 

The null tail must be built from the phenomena most likely to imitate lensing, not from Gaussian noise alone. The project will  combine four control populations: 

 Real complex-burst nulls: all usable multi-component events, excluding quarantined candidates and any event reserved for  validation. 

 Matched cross-event pseudo-pairs: components from different bursts matched on width, S/N, bandwidth, scattering, repeater  status, and masking. These estimate accidental morphological agreement. 

 Structure-preserving surrogates: block bootstrap, phase randomization, time-frequency permutation, or other transformations  that retain spectral envelopes and correlated backgrounds while destroying a true delayed-copy relationship.  Adverse simulations: intrinsic drifting components, overlapping peaks, chromatic echoes, differential DM, differential  scattering, scintillation-like modulation, RFI remnants, mask boundaries, and baseline errors. 

Because Catalog 2 includes multiple bursts from some sources, null resampling and validation splits will operate at the source level when morphology learned from one burst could leak into another. Repeater and apparent-nonrepeater strata will be checked  separately before pooling. 

**5.7 Point-lens injection campaign** 

Lensing injections will begin with real single-component bursts and real off-pulse backgrounds. Later rounds will also inject into  moderately complex events to test performance in adverse conditions. The injection space will include: 

 Delay Delta t, sampled densely near the temporal-resolution boundary and on a broader logarithmic grid.  Relative magnification mu, including faint secondary images near the detection boundary.

Project ECHO-FRB \- July 22, 2026 \- Page 6   
**PROJECT ECHO-FRB | RESEARCH PROPOSAL | VERSION 2.0** 

 Burst S/N, intrinsic width, scattering time, spectral occupancy, usable bandwidth, channel masks, and background quality.  Partial component overlap as an exploratory extension, clearly separated from the resolved-echo primary analysis.  Strict achromatic copies and a limited set of differential-propagation variants for robustness testing. For detection-efficiency mapping, Delta t and mu may be sampled independently to cover the observable domain. For physical  population inference, simulated events will obey the point-lens relationship among impact parameter, magnification ratio, delay,  and redshifted mass. Injection counts will be allocated adaptively: coarse coverage first, then denser sampling near threshold  boundaries and in cells with wide uncertainty. 

**5.8 Blind analysis protocol** 

1\. Quarantine the two named candidates after reproduction. 

2\. Split empirical controls by source into development, validation, and untouched test sets. 

3\. Have a blind controller or sealed script create a hidden mixture of lensed injections, unlensed complex bursts, and adverse  propagation cases. 

4\. Freeze the preprocessing version, search domain, primary statistic, nuisance parameters, robustness tests, thresholds, and  global-significance calculation in a timestamped preregistration. 

5\. Evaluate the hidden set. If the gate fails, revise the pipeline and generate an entirely new hidden set. 6\. After a successful blind validation, evaluate the two named candidates and then run the frozen catalog-wide search. 7\. Any post-unblinding change creates a new analysis version and cannot inherit the original significance calibration without fresh validation. 

**5.9 Detailed candidate inference** 

Only a small number of top-ranked events will receive expensive generative inference. The team will compare a restricted lens  model with prespecified intrinsic, propagation, and instrumental alternatives using explicit likelihoods, posterior predictive checks, and sensitivity to prior choices. Nested sampling or simulation-based inference may be used, but no opaque classifier probability  will be reported as discovery evidence. 

**6\. Statistical Framework** 

**6.1 Local and global significance** 

A local score is not a catalog-level significance. The global calculation must include every burst, source, tested delay, component  proposal, allowed window, and prespecified preprocessing branch that could produce the reported event. The primary frequentist  result will be an empirical family-wise false-alarm probability based on the maximum statistic produced by catalog-equivalent null searches. Source-level dependence will be preserved through cluster resampling or source-level null catalogs. 

Direct Monte Carlo will be used wherever practical. If an extreme-value tail model is required, it must be fitted on one set of null  realizations and validated on an untouched set. Both the empirical resolution limit and the model-dependent extrapolation will be  reported. The project will not convert a nominal autocorrelation peak into a sigma claim without this global calibration. 

**6.2 Detection efficiency** 

The recovery function will be estimated as: 

*epsilon \= epsilon(Delta t, mu, S/N, width, scattering, bandwidth, mask quality, overlap)* 

Each efficiency estimate will include binomial or hierarchical uncertainty. Adaptive simulation will continue until important  regions reach a preregistered precision target or the compute budget is exhausted. The final product will include both an  interpolated efficiency model and the underlying binned injection counts so that downstream limits can be audited. 

**6.3 Primary observable-space rate** 

The primary population parameter is the rate of detectable resolved echoes among observed Catalog 2 bursts over the declared  Delta t and mu domain. For a parametric echo population with rate parameters theta, the likelihood will combine candidate  probabilities and per-event efficiency. A zero-candidate result will be reported first as a catalog-conditioned upper limit, without  immediately translating it into a dark-matter fraction. 

The analysis will distinguish two selection processes: CHIME detection and catalog inclusion, and ECHO-FRB recovery from a  saved spectrum. The project directly calibrates the second. Catalog 2 population work has used 587,367 synthetic bursts injected  into the live CHIME/FRB search pipeline to characterize instrumental selection \[5\], but those injections were not designed  specifically for delayed lens images. Any combined selection model must therefore be separately justified.

Project ECHO-FRB \- July 22, 2026 \- Page 7 

**6.4 Conditional compact-object inference**   
**PROJECT ECHO-FRB | RESEARCH PROPOSAL | VERSION 2.0** 

Only after the observable-space analysis is frozen and validated will the team map delays and magnification ratios to a compact lens population. This stage will specify the point-mass lens model, source-redshift distribution, host-DM model, lens-redshift  distribution, magnification bias, impact-parameter cuts, and catalog-trigger response to double images. Results will be presented  across alternative plausible assumptions rather than as a single unconditional abundance number. 

For a surviving candidate, the inferred quantity is a redshifted lens-mass scale, not an exact intrinsic mass. For a null result, the  exclusion applies only to combinations of mass, abundance, and population assumptions that would have produced enough  cataloged and recoverable echoes. 

**6.5 Multiple analyses and robustness reporting** 

One analysis configuration will be designated primary. Alternative masks, smoothers, null constructions, priors, and candidate  models will be labeled sensitivity analyses. The proposal will report the complete robustness matrix rather than selecting the most  favorable result. Null-model disagreement is itself an uncertainty and must be propagated into candidate significance or limits. 

**7\. Candidate Evidence Standard** 

| Level  | Minimum standard  | Permitted language |
| :---- | :---- | ----- |
| Screening event  | Exceeds a permissive Tier 1 threshold calibrated  to retain high injection efficiency. | Internal triage only; no astrophysical claim. |
| Candidate  | Passes the frozen Tier 2 copy test, has catalog global false-alarm probability below 0.01, and  passes all mandatory robustness checks. | Publishable candidate requiring external review. |
| Strong candidate  | Candidate criteria plus stable detailed generative  evidence and no identified instrumental or  propagation explanation. | High-priority request for baseband and  instrument-team validation. |
| Confirmed lensing event  | Independent high-resolution data demonstrate an achromatic duplicated waveform and consistent  delay/magnification under a validated instrument model. | Would justify physical lens interpretation; still  not automatically a PBH or dark-matter  detection. |

The numerical candidate threshold is a project operating criterion, not a universal discovery standard. A claim of gravitational  lensing will require evidence stronger than a single catalog-level p-value and should include CHIME/FRB collaboration review  where instrument-specific information is material. 

**8\. Work Packages and Decision Gates**

| Work package  | Core activity  | Deliverable  | Gate |
| :---- | :---- | :---- | :---- |
| WP0 \- Data audit  | Download, hash, inventory,   benchmark, and manually validate a  reference subset. | Complete manifest; archive and  throughput report. | All required public products are  accessible and interpretable. |
| WP1 \- Reproduction  | Literal and clean-room reproduction  of the published candidate pipeline. | Reproducibility matrix and technical  note. | Reported candidates and intermediate  statistics are reproduced or   discrepancies are fully explained. |
| WP2 \- Statistic and nulls  | Develop copy statistic, empirical  controls, adverse simulations, and  source-aware validation. | Versioned analysis package and null  benchmark. | False-positive behavior is stable  across null constructions and known  artifacts are rejected. |
| WP3 \- Blind injections  | Generate a hidden mixture and  evaluate the frozen pipeline. | Blind-validation report.  | Recovery agrees with predicted  efficiency and predetermined false positive targets. |
| WP4 \- Catalog search  | Evaluate named candidates, then scan  all eligible bursts with the frozen  pipeline. | Candidate table, audit records, global  p-values. | No undocumented tuning; every  candidate is reproducible from hashes  and configuration. |
| WP5 \- Interpretation  | Detailed inference, high-resolution  follow-up requests, echo-rate   estimation, conditional compact object limits. | Candidate or null-result manuscript;  public efficiency products. | Population inference remains stable  under declared model alternatives. |

Project ECHO-FRB \- July 22, 2026 \- Page 8   
**PROJECT ECHO-FRB | RESEARCH PROPOSAL | VERSION 2.0** 

**8.1 Stop conditions** 

 Stop or redesign after WP1 if the public data cannot reproduce the claimed signal because essential inputs are unavailable or  undocumented. 

 Do not run the catalog-wide search if WP3 fails the hidden-injection gate. 

 Do not derive compact-object abundance if the combined catalog-selection and ECHO-FRB efficiency model is not  defensible. 

 Do not spend the full compute budget merely to increase simulation counts when null-model misspecification remains the  dominant uncertainty. 

**9\. Compute, Storage, and Software Plan** 

**9.1 Development hardware** 

The existing Linux workstation with 16 CPU cores, 64 GB RAM, and 16 GB GPU memory is sufficient for the reproduction audit, data preprocessing, the full lightweight catalog scan, development of the two-dimensional statistic, and an initial injection  campaign. The primary workload is embarrassingly parallel across bursts and injections and is expected to be CPU- and storage intensive rather than GPU-limited. 

| Resource  | Starting point  | Use  | Authorization rule |
| :---- | :---- | :---- | ----- |
| CPU  | Existing 16 cores  | Preprocessing, copy scans,   bootstrap nulls, most injections,  candidate likelihoods. | Scale temporarily only after   benchmark. |
| GPU  | Existing 16 GB VRAM  | Optional proposal network or  simulation-based inference. | Not required for primary statistic. |
| RAM  | Existing 64 GB  | Batch processing and cached  spectra. | Process in chunks; upgrade only if  profiling demonstrates a bottleneck. |
| Fast storage  | Conditional 2-4 TB NVMe  | Immutable archive cache, processed spectra, null catalogs, and   posteriors. | Purchase only after measured  footprint. |
| Cloud compute  | Conditional, within remaining  budget | Large catalog-equivalent null  simulations or targeted nested  sampling. | Release after blind-validation gate. |

**9.2 Simulation budget** 

 Development: approximately 10,000 injections and null examples, sufficient to debug recovery surfaces and failure modes.  Validation: approximately 100,000 examples, allocated adaptively and divided into development, validation, and hidden test  sets. 

 Production: expansion toward 1,000,000 examples only if required by uncertainty targets or global-tail estimation and only  after the pipeline passes WP3. 

These counts are planning ranges rather than promises. The stopping rule will be statistical precision, not a round number of  simulations. 

**9.3 Software architecture** 

 Python with NumPy, SciPy, Astropy, h5py, and xarray where labeled dimensions reduce indexing errors.  PyTorch or JAX only where acceleration or simulation-based inference is justified. 

 Validated inference software such as Dynesty, Bilby, or NumPyro for candidate-level modeling.  Dask, Ray, GNU Parallel, or Slurm-compatible job descriptions for burst-level parallelism. 

 Git, locked environments, containers, automated tests, and deterministic configuration files. 

 A permanent experiment database containing data hashes, masks, preprocessing versions, parameter grids, random seeds,  scores, posterior files, and global-significance calculations. 

**9.4 Data tiers** 

 Tier A \- immutable source files and checksums. 

 Tier B \- standardized spectra and masks, reproducible from Tier A. 

 Tier C \- candidate proposals, features, and null catalogs. 

 Tier D \- simulations, posterior samples, and publication tables.

Project ECHO-FRB \- July 22, 2026 \- Page 9   
**PROJECT ECHO-FRB | RESEARCH PROPOSAL | VERSION 2.0** 

Only Tier A and irreproducible metadata require permanent local retention. Large simulated products may be regenerated from  archived seeds and configurations if storage becomes limiting. 

**10\. Team, Governance, and Reproducibility** 

The minimum credible team combines computational implementation, radio-transient expertise, and statistical review. One person  may cover more than one role, but no final candidate claim should be made without independent technical review. 

| Role  | Responsibility |
| :---- | :---- |
| Computational lead  | Data ingestion, pipeline, simulation, software testing, experiment  records, and release engineering. |
| Radio-transient physicist  | Dedispersion, scattering, burst morphology, RFI, instrument artifacts,  and astrophysical interpretation. |
| Statistical advisor  | Global trials, source dependence, null construction, efficiency  uncertainty, and population limits. |
| Blind controller  | Maintains hidden injection labels or sealed random seed; verifies that  unblinding rules are followed. |
| CHIME/FRB collaborator or reviewer  | Instrument-specific validation and access pathway for nonpublic  baseband or polarization products if warranted. |

**10.1 Reproducibility rules** 

 Every figure and table must be generated from a versioned command or workflow file. 

 Every candidate must have a machine-readable audit record and a human-readable one-page summary.  Random seeds are stored; hidden-test seeds remain inaccessible until the blind gate is complete.  The preregistration, frozen thresholds, source exclusions, and all post-unblinding changes are publicly timestamped.  Released synthetic data must not expose restricted telescope products. Public releases will contain only redistributable inputs  or instructions to retrieve them from the authoritative archive. 

**11\. Risks and Mitigation**

| Risk  | Consequence  | Mitigation |
| ----- | :---- | :---- |
| The reported candidates do not reproduce  | Data versions, masks, or undocumented choices  may be decisive. | Publish a technical reproducibility result and use the discrepancy to define robust preprocessing  requirements. |
| Intrinsic morphology overwhelms the lens signal  | Complex bursts may frequently contain repeated looking components. | Use real complex bursts as the dominant null,  source-aware splits, and fine-structure residual tests. |
| Plasma propagation is too flexible for decisive  model comparison | No finite plasma model exhausts all propagation  behavior. | Treat plasma simulations as adverse tests, avoid  claiming plasma is ruled out generally, and require  strict achromaticity for lens classification. |
| Catalog time resolution is insufficient  | Fine structures may be unresolved and short delays  may overlap. | Restrict primary claims to resolved echoes and seek  baseband data for surviving candidates. |
| Look-elsewhere effect cannot be sampled deeply  enough | Extremely small p-values require many catalog equivalent nulls. | Report empirical resolution, validate any tail model  out of sample, and avoid discovery language  without independent data. |
| Selection function is incomplete for double images  | Standard CHIME injections may not capture  delayed-image triggering and catalog inclusion. | Lead with observable-space limits and gate  compact-object inference on a dedicated selection  analysis. |
| Candidate tuning leaks into development  | Known events can unconsciously shape filters and  thresholds. | Quarantine named candidates, split by source, use  fresh hidden sets after every material revision, and  timestamp decisions. |
| Compute is spent before methodology is credible  | Large simulation campaigns can mask conceptual  weaknesses. | Use staged authorization and statistical stopping  rules; purchase hardware only after profiling. |

Project ECHO-FRB \- July 22, 2026 \- Page 10   
**PROJECT ECHO-FRB | RESEARCH PROPOSAL | VERSION 2.0** 

**12\. Timeline, Deliverables, and Success Criteria** 

**12.1 Nominal ten-month schedule** 

| Period  | Milestone |
| :---- | :---- |
| Month 1  | WP0 data audit; archive manifest; reference-event inspection;  benchmark report. |
| Months 2-3  | WP1 literal and clean-room reproduction; sensitivity matrix;  reproduction note. |
| Months 3-5  | WP2 copy statistic, preprocessing tests, empirical nulls, and adverse  simulations. |
| Month 6  | Preregistration and WP3 hidden-injection validation. Revise only with a fresh hidden set. |
| Months 7-8  | WP4 named-candidate unblinding and frozen catalog-wide search. |
| Months 8-9  | Candidate-level generative inference, baseband queries, and  observable-rate estimation. |
| Month 10  | Conditional compact-object analysis, manuscripts, code release, and  archived data products. |

The schedule assumes sustained participation by a computational lead and recurring access to radio and statistical review. A  smaller part-time team should preserve the order of gates even if calendar duration increases. 

**12.2 Research products** 

 Candidate reproduction report: independent evaluation of FRB 20190131D, FRB 20211115A, and the published candidate selection chain. 

 Methods and blind-search paper: empirical null calibration, injection efficiency, catalog-global significances, and a public  candidate table. 

 Population result: observable-space echo-rate limit or measurement, with conditional compact-object interpretations clearly  separated. 

 Open-source pipeline, frozen configuration, simulation recipes, audit schema, and reproducible publication workflows. **12.3 Success criteria**   
The project will be considered scientifically successful if it produces at least one of the following: 

 A robust confirmation or refutation of the two reported candidates under an independently calibrated analysis.  A demonstrably better method for distinguishing delayed copies from intrinsic multi-component morphology.  A blind catalog search with valid global false-alarm control and a released candidate table. 

 A calibrated upper limit on detectable resolved echoes in Catalog 2\. 

 A defensible model-dependent constraint on a compact-object population, derived only after the selection gate. **12.4 Staged authorization**

| Stage  | Trigger  | Authorized work  | Required evidence |
| :---- | :---- | :---- | ----- |
| Authorization A  | Immediately  | WP0-WP1 on existing hardware;  limited storage as required. | Data are accessible and published  candidates can be meaningfully  reproduced. |
| Authorization B  | After reproduction gate  | WP2 development and initial  simulations. | Discrepancies are resolved;   preprocessing is stable and testable. |
| Authorization C  | After blind-validation gate  | Full catalog run and conditional  cloud compute. | Hidden recovery and false-positive  targets are met. |
| Authorization D  | After candidate or null search  | Candidate follow-up and compact object population modeling. | Instrumental review and selection  assumptions are adequate. |

Project ECHO-FRB \- July 22, 2026 \- Page 11   
**PROJECT ECHO-FRB | RESEARCH PROPOSAL | VERSION 2.0** 

**13\. Expected Scientific Impact** 

ECHO-FRB addresses a narrow but important problem with a strong data-method fit. The public catalog is large enough to make  rare-event searches meaningful, yet small enough that every candidate can be audited individually. The lensing hypothesis makes a precise morphological prediction, while the known complexity of FRBs creates a difficult and scientifically interesting false positive problem. 

A positive result would identify an intervening compact massive object and motivate high-resolution radio and foreground studies.  A null result would constrain the rate of resolved lensing-like echoes and test a class of compact-lens interpretations. A  methodological result would improve how the FRB community evaluates apparent echoes, repeating substructure, and  propagation-induced copies. Each outcome is publishable if the search is blinded, the null population is realistic, and the selection  claims remain appropriately limited. 

**Final assessment** 

Project ECHO-FRB is a high-upside, moderate-risk research program whose credibility depends more on disciplined  statistical design than on large compute. The recommended strategy is to spend intellectual effort first, validate on hidden data second, and scale simulations only after the pipeline proves that it can distinguish injected lenses from naturally complex FRB morphology. 

**References** 

**\[1\]** The CHIME/FRB Collaboration. "The Second CHIME/FRB Catalog of Fast Radio Bursts." The Astrophysical Journal Supplement  Series 283, 34 (2026). DOI: 10.3847/1538-4365/ae3828; arXiv:2601.09399. 

**\[2\]** Zhou, H., Li, Z., Shao, C.-G., Wang, X.-J., Liao, K., Gao, H., and Zhu, Z.-H. "Evidence for Intermediate-Mass Black Holes From  Microlensing Signatures in CHIME/FRB Catalog 2." arXiv:2605.19653 (2026). Associated public code repository: Huan-Zhou spec/MICRO-FRB. 

**\[3\]** Munoz, J. B., Kovetz, E. D., Dai, L., and Kamionkowski, M. "Lensing of Fast Radio Bursts as a Probe of Compact Dark Matter."  arXiv:1605.00008 (2016). 

**\[4\]** The CHIME/FRB Collaboration. "Updating the First CHIME/FRB Catalog of Fast Radio Bursts with Baseband Data."  arXiv:2311.00111 (2023). 

**\[5\]** McGregor, K., Hessels, J. W. T., Kaspi, V. M., et al. "Debiasing the Observed Fast Radio Burst Population with the CHIME/FRB  Selection Function." arXiv:2606.26334 (2026). 

**\[6\]** Li, R. N., Wang, Y. B., Yi, S. X., Zhou, X., and Wang, F. Y. "The Role of Plasma Lensing in Fast Radio Bursts." arXiv:2601.11122  (2026). 

**Appendix A. Preregistration Checklist** 

☐ Exact data release, file manifest, and checksum policy. 

☐ Eligibility and exclusion rules with reason codes. 

☐ Source-level development, validation, and test split. 

☐ Named-candidate quarantine procedure. 

☐ Primary preprocessing configuration and permitted robustness variants. 

☐ Search delay domain and component-proposal procedure. 

☐ Definition and implementation of the primary copy statistic. 

☐ Nuisance parameters, priors, and interpolation method. 

☐ Empirical null construction and source-dependence treatment. 

☐ Injection distributions, adaptive allocation rule, and hidden-set generation. 

☐ Screening threshold, candidate threshold, and mandatory robustness tests. 

☐ Global false-alarm calculation and any extreme-tail modeling. 

☐ Detection-efficiency uncertainty target and simulation stopping rule. 

☐ Candidate-level generative models and prior-sensitivity reporting. 

☐ Observable-rate model and conditions required for compact-object inference. 

☐ Rules for post-unblinding modifications and fresh validation. 

☐ Code, environment, audit-record, and public-release requirements.

Project ECHO-FRB \- July 22, 2026 \- Page 12   
**PROJECT ECHO-FRB | RESEARCH PROPOSAL | VERSION 2.0** 

**Appendix B. Minimum Candidate Audit Record** 

| Record group  | Required contents |
| :---- | :---- |
| Identity  | Catalog burst ID, source ID, repeater status, observation date, public  file identifiers. |
| Data integrity  | Source hashes, array dimensions, time/frequency axes, mask fractions, exclusion warnings. |
| Preprocessing  | Pipeline version, configuration hash, baseline/noise method, DM  value, smoothing and interpolation settings. |
| Search  | Component windows, delay range, number of trials, Tier 1 score, Tier  2 score, best delay, best magnification. |
| Significance  | Local score, source-level score, catalog-global p-value, empirical  resolution, tail-model details if used. |
| Robustness  | Per-band delays and ratios, residual diagnostics, leave-band-out,  window perturbation, rebinning, DM/scattering tests. |
| Model comparison  | Likelihoods or Bayes factors, priors, posterior samples, posterior  predictive checks, prior-sensitivity results. |
| External checks  | Baseband availability, polarization availability, instrument-team  review, localization and foreground-search limitations. |
| Decision  | Candidate grade, reasons for promotion or rejection, approver,  timestamp, and links to reproducible figures. |

**END OF PROPOSAL**

Project ECHO-FRB \- July 22, 2026 \- Page 13 