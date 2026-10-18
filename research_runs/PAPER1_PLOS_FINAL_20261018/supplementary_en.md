# S1 Appendix. Source expansion, class coverage and reproducibility

Ziyuan Zhu

Companion to “Source-cohort expansion improves weaker-class coverage in cross-subject motor-imagery EEG decoding”.

## 1. Scope of this manuscript revision

The principal experiment is the completed 18-channel, dimensionless source-expansion run `paper1_source_expansion_18ch_dimensionless_eligible_v3_20261018`. Its frozen results are at commit `040956085499ed788948de0d5a09cddd9eabca56`. This appendix supplements the main Methods. The second-round update adds four explicitly post hoc comparisons of saved participant metrics in a separate Holm family; it introduces no training experiment or target inference pass. Figures use archived outcomes, including the labelled algebraic class-recall decomposition.

Historical results remain in their original directories and Git history. The new experiment differs from earlier 19/21/22-channel and four-class protocols in its montage, normalization, sources, endpoint and selection design. Their values are not pooled into the new external estimate. The earlier submission materials remain historical artifacts, rather than components of the current submission package.

## 2. Source registry and native eligibility

The source registry fixes BNCI participants 1–9 and Yang participants 1–51. The S29 Yang subset contains provider identifiers 2, 9, 10, 11, 14, 16, 17, 20, 22, 23, 28, 32, 34, 35, 36, 38, 41, 42, 48 and 51. The complete order, fold assignment and source-level membership are retained in `indexed/provenance/source_registry.json` within the frozen result directory. Registry seed 20261017 fixes the subset and fold construction. All sessions belonging to a person remain in the same source-validation fold. The new five-fold selection design weights people within datasets; it is distinct from the earlier four-group Q14/Q15 design.

BNCI contributes 2,592 distinct binary hand-imagery trials, 288 per person. The 153 Yang session pairs contribute 30,591 explicitly labelled trials across 51 people: native class 1 has 15,295 observations and class 2 has 15,296. Relative to the planned total, five class-1 and four class-2 observations are absent from the eligible set. These counts do not justify imputing unknown class labels. Native code 255, missing observations and segment boundaries remain in the event evidence. The approved rule accepts only explicit class codes 1/2, with no inferred label or onset. Five sessions contain fewer than the planned 100 observations per class. The frozen eligibility manifest has SHA-256 `5291d362185a8db9bf45ddc95d9cb49d40de57893d2fd4da8681a802b5ab36f9`.

The native marker-9 delimiters retain the original operational grouping. Filtering out ineligible events does not move a later trial into a different artificial group of 40. A fixed registry binds each session to its original file identity and native positions. Thirty-one compatible previously prepared participant arrays were reused with their original embedded provenance retained and a separate compatibility binding to the current run. Reuse is recorded as reuse, not as a fresh acquisition or a new preprocessing execution.

The Dreyer roster comprises provider participants 1–87 except 17 and 41, retaining 85 participants. Each contributes two acquisition runs, 80 eligible trials and 40 trials per class. Later adaptive online runs are outside this experiment. Identity correspondence and class counts are checked against saved input audit records, not treated as independent signal-level duplicate analysis.

## 3. Timing, scale and numerical implementation

The main text gives native context/crop timing and the complete channel order. Yang timing follows marker+[2,4) s, preserving the original event clock. The 1.5-s computational anchor is an analysis reference; the exact imagery phase is not established by that convention. The native `?V` unit string is preserved. Dataset-specific header calibration is decoded numerically without assigning an unsupported voltage unit or treating an EDF conversion as identical to a different raw-file format.

Each 18-channel context is common-average referenced before frozen filtering, polyphase resampling and cropping. Frozen Butterworth coefficients and initial conditions are stored in the archived `provenance/code/config/filter_bank18.json`, together with the required numerical-library identities. Odd forward/backward padding is 27 native samples. Resampling uses `scipy.signal.resample_poly` with a Kaiser window (beta 5.0), constant padding and zero padding value. Arrays are ordered trial × view × channel × time, with views broadband/mu/beta, 18 channels and 320 samples at 160 Hz. Preparation stops for missing/changed file identities, missing expected observations, invalid numerical values or zero trial scale.

After view/channel-wise temporal centering, all views are divided by the same trial's broadband RMS. For any positive scalar a, x(az)=az/s(az)=az/(a·s(z))=x(z). This deterministic identity concerns a common scalar across the trial, not channel-specific distortions, nonlinear calibration, timing equivalence or physical-amplitude recovery. No learned dataset alignment, across-trial target centering or target covariance fitting is introduced.

The frozen `uv.lock`, runtime inventory and execution identity accompany the original result archive. They describe the executed scientific environment; the editorial rendering environment used for this package is separately recorded in `evidence/build_receipt.json`. Rendering dependencies are not substituted for scientific dependencies. The manuscript update reads result tables only.

## 4. Selection rules and metric order

**S1 Table. Source-only checkpoint-selection objectives.** Each objective uses seed-averaged held-out source participant metrics, then equal dataset mass and equal participant mass within dataset. “Tail” is the worst one-third of this weighted distribution, with fractional weight at the boundary. Selection is conducted separately for each source level and neural pipeline.

| Frozen rule | Objective | Direction |
|---|---|---|
| fixed20 | Epoch 20 | Fixed |
| mean_ce | Weighted mean cross-entropy | Minimize |
| mean_rank | Weighted mean within-person cross-entropy rank across epochs | Minimize |
| mean_ba | Weighted mean balanced accuracy | Maximize |
| mean_min_recall | Weighted mean smaller class recall | Maximize |
| tail_ce | Weighted upper-tail cross-entropy | Minimize |
| tail_ba | Weighted lower-tail balanced accuracy | Maximize |
| tail_min_recall | Weighted lower-tail smaller class recall | Maximize |

All rules use candidate epochs 1–40. Score ties within absolute tolerance 10⁻¹² use highest mean balanced accuracy and then the earliest epoch, except mean-rank ties, which use the earliest minimum directly. The same selected epoch is applied to each of the three final seeds. These are source-validation operations; the complete external table is not used to choose a preferred rule.

For each participant and seed, balanced accuracy B is (rL+rR)/2 and weaker-class recall W is min(rL,rR). Both are computed from that seed's predictions before averaging over seeds. In general, mean over seeds of min(rL,rR) differs from min of the two seed-averaged recalls. The archived implementation uses the former. Equal logits are assigned class 0; probability-only cross-entropy uses a fixed numerical clipping convention, documented in the archived metric implementation.

The identity |rL−rR|=2(B−W) holds within each seed and survives linear seed/participant averaging. Fig 4C is a post hoc descriptive calculation from existing endpoint means. It adds neither a test of class-gap reduction nor a prospective outcome. Complete precision is retained in its figure-data CSV.

## 5. Completed execution and inference inventory

**S2 Table. Counts at their actual observational grain.** The result archive records completion at 2026-10-18 04:26:19.986827 UTC. A process exit code was not collected in the archived wait record and is not inferred from the completion status.

| Evidence unit | Count | Interpretation |
|---|---:|---|
| Source-validation neural trajectories | 90 | 3 source levels × 2 pipelines × 5 folds × 3 seeds |
| Final neural trajectories | 18 | 3 source levels × 2 pipelines × 3 seeds |
| Full neural trajectories | 108 | 40 epochs × 128 updates each |
| Epoch checkpoints | 4,320 | Repeated states within trajectories |
| Source-validation rows | 23,520 | Person/seed/epoch metrics |
| Aggregate source scores | 1,680 | Selection arithmetic audit |
| Source-level/pipeline/rule choices | 48 | 3 × 2 × 8 |
| Selected condition-by-seed outputs | 144 | Multiple rules can share a checkpoint |
| Distinct selected checkpoint identities | 99 | Level/pipeline/seed/epoch combinations |
| Conventional fits | 9 | 3 source levels × 3 seeds |
| Saved neural prediction rows | 979,200 | 144 outputs × 6,800 trials |
| Saved conventional prediction rows | 61,200 | 9 outputs × 6,800 trials |
| Statistical participant pairs | 85 | Unit for every paired test |

The audit verified update-count receipts and trajectory contracts. The sum of receipt updates is not a new independent inspection of optimizer internal state. The number of rows, checkpoints or seeds does not expand the inferential sample size beyond 85 participants.

The four fixed inferential contrasts are reproduced in main Table 2 and `tables/Table2_frozen_comparisons.csv`. Their raw p values, Holm-adjusted secondary p values, pointwise t intervals and percentile-bootstrap intervals retain their original precision in S1 Data. CIs describe participant sampling conditional on the fitted trajectories and seed averages. They do not jointly quantify every source subset, initialization or acquisition-cohort uncertainty. No subgroup, neural-versus-CSP equivalence, or new selection-rule test was added. The new four-comparison source-expansion family is documented separately in Section 11.

## 6. Complete neural-condition tables

The tables below retain every frozen neural rule under all three source configurations. Columns show selected epoch and external means for balanced accuracy (BA) and weaker-class recall (W), in percent. Comparisons beyond main Table 2 are descriptive. Full-precision means, standard deviations, t intervals and bootstrap intervals are provided in `tables/S1_all_neural_condition_summaries.csv` and S1 Data.

**S3 Table. Complete BROAD selection conditions.**

| Source pool | Selection rule | Epoch | BA (%) | W (%) |
|---|---|---:|---:|---:|
| S9 | fixed20 | 20 | 58.6667 | 27.2451 |
| S9 | mean_ce | 3 | 61.3235 | 38.5980 |
| S9 | mean_rank | 8 | 61.5392 | 39.3333 |
| S9 | mean_ba | 27 | 58.3186 | 27.3137 |
| S9 | tail_ce | 3 | 61.3235 | 38.5980 |
| S9 | tail_ba | 27 | 58.3186 | 27.3137 |
| S9 | mean_min_recall | 27 | 58.3186 | 27.3137 |
| S9 | tail_min_recall | 27 | 58.3186 | 27.3137 |
| S29 | fixed20 | 20 | 64.0784 | 48.3725 |
| S29 | mean_ce | 5 | 64.1078 | 49.0294 |
| S29 | mean_rank | 5 | 64.1078 | 49.0294 |
| S29 | mean_ba | 26 | 63.0539 | 43.4314 |
| S29 | tail_ce | 1 | 54.5931 | 13.6667 |
| S29 | tail_ba | 39 | 62.2696 | 40.8824 |
| S29 | mean_min_recall | 5 | 64.1078 | 49.0294 |
| S29 | tail_min_recall | 5 | 64.1078 | 49.0294 |
| S60 | fixed20 | 20 | 63.2108 | 44.3137 |
| S60 | mean_ce | 7 | 64.2304 | 48.1961 |
| S60 | mean_rank | 7 | 64.2304 | 48.1961 |
| S60 | mean_ba | 35 | 63.6618 | 49.3529 |
| S60 | tail_ce | 1 | 54.2794 | 14.4902 |
| S60 | tail_ba | 39 | 63.1029 | 46.8039 |
| S60 | mean_min_recall | 7 | 64.2304 | 48.1961 |
| S60 | tail_min_recall | 5 | 64.1716 | 48.4804 |

**S4 Table. Complete MU_BETA_SHARED selection conditions.**

| Source pool | Selection rule | Epoch | BA (%) | W (%) |
|---|---|---:|---:|---:|
| S9 | fixed20 | 20 | 58.1176 | 24.7745 |
| S9 | mean_ce | 3 | 61.2941 | 39.1078 |
| S9 | mean_rank | 9 | 60.1520 | 31.8529 |
| S9 | mean_ba | 20 | 58.1176 | 24.7745 |
| S9 | tail_ce | 3 | 61.2941 | 39.1078 |
| S9 | tail_ba | 9 | 60.1520 | 31.8529 |
| S9 | mean_min_recall | 18 | 58.3529 | 25.4804 |
| S9 | tail_min_recall | 9 | 60.1520 | 31.8529 |
| S29 | fixed20 | 20 | 64.2647 | 48.1373 |
| S29 | mean_ce | 7 | 63.1275 | 44.6863 |
| S29 | mean_rank | 7 | 63.1275 | 44.6863 |
| S29 | mean_ba | 27 | 63.6520 | 45.9608 |
| S29 | tail_ce | 1 | 52.1029 | 4.8039 |
| S29 | tail_ba | 37 | 64.2647 | 49.5294 |
| S29 | mean_min_recall | 17 | 64.2010 | 47.9706 |
| S29 | tail_min_recall | 9 | 63.6667 | 45.3922 |
| S60 | fixed20 | 20 | 64.6225 | 49.6471 |
| S60 | mean_ce | 3 | 63.7402 | 46.7353 |
| S60 | mean_rank | 9 | 64.0686 | 46.5980 |
| S60 | mean_ba | 31 | 63.4118 | 46.5882 |
| S60 | tail_ce | 1 | 52.9216 | 8.2745 |
| S60 | tail_ba | 34 | 63.8480 | 47.9804 |
| S60 | mean_min_recall | 7 | 63.8775 | 45.5686 |
| S60 | tail_min_recall | 7 | 63.8775 | 45.5686 |


## 7. Historical evidence retained separately

**S5 Table. Earlier research findings and their distinct roles.** These observations motivated the redesign and remain available in their original frozen records. They are not additional participants or replication cohorts for the current 18-channel source-expansion estimate.

| Archived analysis | Retained finding | Role in the current manuscript |
|---|---|---|
| BNCI four-class mean-rank versus mean-loss development | BA 33.72% to 42.67%; S3/S8 contributed 87.57% of signed aggregate gain | Exploratory motivation for participant-level reporting |
| Fixed20 versus matched-runtime historical loss-schedule replay | Mean BA difference +10.06 pp; four of nine improved | Earlier schedule sensitivity, separate protocol |
| Corrected robustness controls | No corrected established gain | Retained null evidence |
| PhysioNet shared-minus-broad | +0.573 pp; superiority not established | Historical complete-pipeline contrast |
| Cho2017 shared-minus-broad | −1.513 pp balanced accuracy | Historical adverse complete-pipeline contrast |
| Lee2019 shared-minus-broad | +0.204 pp; uncertain, not equivalence | Historical complete-pipeline contrast |
| BNCI sensor-level physiology | Descriptive baseline-relative mu/beta power and association; n=9 | Separate physiological description, no decoder-mechanism attribution |

Pointers: `../PAPER_FINAL_20261006/`, `../PLOS_ONE_SUBMISSION/`, `../PLOS_ONE_POSTSUBMISSION_REVIEW_20261010/` and `../REDESIGN_SOURCE_SELECTION_20261012/`. Q1–Q16 results, frozen numeric files, figures and audit contracts are preserved. The earlier physiological analysis used 10 log10(Ptask/Pbaseline), unequal baseline/task Welch segment counts and a different window from decoder input. Signed laterality is not absolute contralateral ERD, sensor topography is not cortical localization, and the descriptive association does not identify a learned decoder mechanism. It supplies no external physiological replication for the current experiment.

## 8. Independent audit scope and archive identities

The external arithmetic audit passed 1,179 checks with zero failures. It reconstructed metrics and inference from saved predictions, checked expected participant/trial/label identities and alias equality, and matched saved input-audit label hashes. The integrity/source-selection review checked nine off-Pod neural checkpoint archives (212,762,651 bytes in total), their payload hashes, the complete epoch inventory, 108 trajectory contracts, 23,520 validation rows, 1,680 aggregates and 48 choices. The largest aggregate numerical difference was 7.1054×10⁻¹⁵. The nine conventional model artifacts are in the original evidence package.

The result importer independently checked the supplied audit files and their source identities against the archived result package; it did not rerun model inference or reread all nine large neural archives. This manuscript preparation likewise does not rerun EEG preprocessing, fitting or prediction. The checks provide byte identity, source-selection reconstruction and saved-statistic consistency, with no claim of independent raw-signal duplication screening or verification of every historical target access.

The original public result ZIP is 21,240,637 bytes, SHA-256 `df8fdc4a43139acb4236ead749b74736a5bedaea6d8606c3bcc69234755fe02f`. It contains 57 members with per-member identities. The outer final evidence package is separately identified as 21,250,082 bytes, SHA-256 `36b47206748b364eabc8f9a6d193d9e13fa54c0a96372b912cfca8179573df5e`; these are different packages. The public result ZIP and immutable Git commit support inspection of the published numerical results. Large-model storage and durable R2 full-GET verification remain separate archive tasks in the release checklist, not completed DOI deposits.

## 9. Data access, ethics and reuse

The exact acquisition sources are the BNCI competition files, Yang Figshare+ v5 (DOI 10.25452/figshare.plus.22671172.v5), and the Dreyer NEMAR nm000250 v1.0.5 acquisition EDF representation. Original Dreyer data also have Zenodo DOI 10.5281/zenodo.8089820; different raw formats and conversions are not assumed to have identical bytes. The source publications and provider records are cited in the main reference list. The current v3 provenance documents preparation and execution on 18 October 2026. This observed activity date does not establish a participant recruitment date or the researcher's first-ever access date. Earlier dataset access and migrations remain in their own archived records.

The author reports only secondary access to participant codes, age and basic metadata, with no direct identity-linkage key, new recruitment, intervention or contact. The author confirms that the research administration office of Chongqing Medical University (科研处) determined on 17 October 2026 that this secondary use of BNCI, Yang and Dreyer data was exempt from ethics review under Article 32(1) of the 2023 Measures for the Ethical Review of Life Science and Medical Research Involving Human Participants. This supersedes the earlier author-only assessment. The statement records the author-confirmed institution, date, basis and scope; the signed institutional record was not independently inspected in this editorial task, and no determination identifier is invented. Original collection approvals and consent remain attributed to the providers.

Original manuscript material and author-owned derived outputs follow the previously authorized CC BY 4.0 terms; author-owned original software follows MIT. Provider EEG and third-party software retain their original terms. The accompanying data package contains derived result tables, not raw EEG. A repository commit is not a repository DOI, and a model checksum is not proof of durable public model availability.

## 10. Reproducing the presentation without scientific reruns

The package's `scripts/build_figures.py` reads the frozen result archive and audit summaries; it writes plot sources and publication figures. `scripts/export_manuscript.py` renders the authored Markdown into editable DOCX and review PDF artifacts. `scripts/validate_delivery.py` checks numerical identities, citation coverage, figure metadata, output integrity and preservation of historical tracked content. None of these editorial commands starts a model fit or loads neural checkpoints. Commands and file identities appear in `REPRODUCIBILITY.md` and the build/validation receipts.

The AI-assistance disclosure in the main text and captions covers plotting-code and document-preparation assistance. Tool outputs are checked against archived numerical evidence; author approval of this new manuscript, tables, figures and portal-rendered PDF remains an author-level submission action.

## 11. Review-triggered supplementary source-expansion comparisons

Following the supplied second-round report, four comparisons were specified before their calculation from saved metrics, with their post-outcome status explicit. They compare S29−S9 under BROAD/tail-recall and S60−S9 under fixed CSP–LDA, each on weaker-class recall and balanced accuracy. Their full-precision results, pointwise 95% t intervals and separately Holm-adjusted four-test p values are in `tables/review2_posthoc_comparisons.csv`; the 340 paired participant differences, plan and execution receipt are included in S1 Data. The original primary comparison and original secondary Holm family remain unchanged. These new calculations use 85 paired three-seed means and no EEG, checkpoint or model inference.

The fixed S29 pool showed +21.7157 pp weaker-class recall and +5.7892 pp balanced accuracy relative to S9. CSP–LDA S60−S9 changes were +13.8235 and +5.2451 pp, respectively. All four planned supplementary comparisons are reported in main Table 4 and Fig 6. A single intermediate subset identifies its observed configuration, not a universal source-count saturation point; the two evaluated decoder families show same-direction gains without a neural-versus-CSP equivalence claim.

## 12. Historical diagnostic detail and statistical conventions

The archived S3 four-cell training-duration diagnostic gave 26.10% and 25.69% balanced accuracy at two epochs for raw and source-normalized inputs, respectively, and 67.71% and 65.86% at 16 epochs. These participant-specific development observations motivate duration and class-recall diagnostics. They use the historical protocol and are not pooled with the new three-cohort experiment. The original table and audit remain in `../PLOS_ONE_POSTSUBMISSION_REVIEW_20261010/`.

For the old mean-rank development result, cite the archived nine-person sensitivity as p=0.1797 when describing the original report, explicitly labelling its inclusion of ties. The conventional tie-excluding sign sensitivity is p=0.015625 (seven nonzero participant changes), and the paired t result is p=0.111. These are different procedures on historical data, not interchangeable routes to a preferred conclusion. They do not enter the current source-expansion families.

The historical Cho2017 shared-input deployment shifted left recall from 46.79% to 37.52% while right recall rose from 72.86% to 79.10%. This identifies an asymmetric-recall operating pattern in that complete frozen pipeline contrast. It remains a historical cohort-specific observation rather than a new analysis or a frequency-sharing mechanism claim.

## 13. Exact prediction supporting files

S2 Data (`S2_Neural_Predictions.csv.gz`) and S3 Data (`S3_CSP_Predictions.csv.gz`) are exact member copies from the original frozen result ZIP. Their byte lengths and SHA256 values are recorded in `evidence/prediction_supporting_files.json`. Each is below the journal's 20 MB supporting-file limit. They provide trial-level outputs for saved-prediction reconstruction; source tables and post hoc calculations remain in the compact S1 Data.

## 14. Complete descriptive expansion inventory and common-duration controls

The review-triggered inventory specifies all S29−S9 and S60−S9 comparisons, both neural pipelines, all eight frozen rules and both endpoints (64 rows), plus four conventional-model rows. Its plan was recorded after outcomes were already known and before this descriptive extraction. The complete 68-row table,36 fixed20 seed means,24 fixed20 seed differences, code and receipt are included in S1 Data. No extra confidence intervals, bootstrap analyses or significance tests were added.

The fixed20 comparisons hold the selected checkpoint at 20 epochs and 2,560 updates within each neural pipeline. They preserve source composition, sampler and all other original frozen settings for each actual trajectory. All 24 seed-specific cohort-mean changes are positive. Three training seeds characterize these fitted trajectories on the same 85 people and are not three independent external replications.

Across the entire eight-rule grid, seven rules give positive mean changes in each pipeline/expansion/endpoint group. The exception is tail_ce: its expanded pools selected epoch 1 while S9 selected epoch 3, producing all eight negative cells. These outcomes remain in the full table. This selection dependence is visible alongside the equal-duration control, without selecting a new rule from target performance. Aggregate direction labels use 1e−10 pp only to distinguish numerical zero for display; this does not change any frozen hashes, estimates or scientific thresholds.

## 15. Precision note on supplementary sign counts

The four-test post hoc receipt preserves its originally specified exact-floating sign-count convention. In its S29−S9 balanced-accuracy row, two mathematically tied participant values have residual differences approximately +5.55×10⁻¹⁵ and −1.11×10⁻¹⁴ pp. This affects only the ancillary sign-count labels; it does not affect reported mean differences, intervals or p values. The manuscript does not use those ancillary counts. The original plan,receipt and table are retained rather than silently overwritten.


## Additional editorial-stage descriptive reconstruction

This additional analysis was specified after the original results had been inspected. It introduces no new hypothesis tests and leaves the original primary, three-test secondary and four-test post hoc families unchanged. All 979,200 neural and 61,200 conventional saved trial predictions were read. Each participant/seed contributed 40 labelled trials per class; both classes, all 85 participants and all three seeds were retained. Metrics were computed within seed before averaging seeds within participant. For joint improvement, both the balanced-accuracy and weaker-class-recall paired differences had to exceed 10⁻¹² on the fraction scale.

In the primary S60−S9 BROAD/tail-recall contrast, 66/85 participants improved on both endpoints, 71 improved in balanced accuracy and 72 improved in weaker-class recall. The mean absolute recall gap declined by 49.39% relative to S9; the gap narrowed in 72 participants, widened in 12 and was unchanged in one. Mean right-hand recall changed from 31.01% to 59.64%, while left-hand recall changed from 85.63% to 68.71%. The larger weaker-class gain is therefore a rebalancing result, not a claim that both fixed physical classes improved.

S4 Data retains all 34 configuration-level comparisons against S9, including adverse and unchanged outcomes, their joint-benefit counts and label-specific changes. It also provides all 85 primary participant changes, the analysis plan, implementation and checksum-bound verification receipt. Every one of the 68 corresponding expansion-by-endpoint means in the previous complete inventory was reproduced within 10⁻¹⁰ percentage points. The source prediction files were unchanged.
