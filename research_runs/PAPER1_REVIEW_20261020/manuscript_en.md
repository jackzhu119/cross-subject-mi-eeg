# Source-cohort expansion improves weaker-class coverage in cross-subject motor-imagery EEG decoding

Ziyuan Zhu*

College of Artificial Intelligence Medicine, Chongqing Medical University, Chongqing, China

*Corresponding author: zzy2630816871@gmail.com

ORCID: https://orcid.org/0009-0005-1153-4926

Postal address: Jinyun Campus, Chongqing Medical University, 61 Daxuecheng Middle Road, Shapingba District, Chongqing 401331, China

Short title: Source-cohort expansion and class coverage in motor-imagery EEG

## Abstract

Adding a second source acquisition cohort improved recognition of the weaker motor-imagery class in an external electroencephalographic evaluation. We tested source-cohort expansion as a data-design strategy using nine BNCI participants alone, those nine plus 20 Yang participants, and the nine plus all 51 Yang participants. Two EEGNet input pipelines and eight source-only checkpoint rules were evaluated under a common 5,120-update full-trajectory budget; common-duration controls used 2,560 updates. The experiment comprised 108 neural trajectories and nine conventional spatial-filtering fits, with exploratory external evaluation in 85 Dreyer participants. In the prespecified broadband/tail-recall comparison, expansion from nine to 60 source participants increased weaker-class recall from 27.31% to 48.48%: +21.17 percentage points (95% confidence interval 17.12–25.21; paired p<0.001). Balanced accuracy increased by 5.85 points (95% confidence interval 4.13–7.58; Holm-adjusted p<0.001). Weaker-class recall improved in 72/85 participants; an additional descriptive analysis found simultaneous improvement in both endpoints in 66/85. The mean absolute class-recall gap narrowed from 62.01 to 31.38 points, a 49.39% reduction. At the common 20-epoch checkpoint, weaker-class gains were 17.07 and 24.87 points in the broadband and shared-view pipelines. Supplementary post hoc analyses also identified gains in the fixed intermediate source pool and the conventional decoder. Source-cohort expansion therefore improved weaker-command coverage and overall discrimination in the evaluated cross-dataset setting. The study combines controlled source composition, matched-duration checks and participant-level benefit profiles to establish a reproducible empirical strategy for improving cross-subject decoding.

## Introduction

Cross-subject motor-imagery EEG decoding must recognize both hand commands reliably, yet balanced accuracy can obscure poor recall for one command. The composition of the source acquisition population may therefore matter as much as the average accuracy used to summarize an external test cohort [1,2]. We evaluated adding Yang recordings to a BNCI source pool and found a 21.17-percentage-point improvement in weaker-class recall and a 5.85-point improvement in balanced accuracy in the primary exploratory Dreyer comparison. Weaker-class recall improved in 72 of 85 participants, and the mean left–right recall gap nearly halved.

The study's principal contribution is a controlled evaluation of source-cohort expansion as a decoder-design choice. Three nested source pools separate the BNCI-only configuration from two mixed-cohort configurations, each under the same full-trajectory update budget. Matched-duration checkpoint comparisons then test whether the gains remain when selected training duration is also fixed. Joint participant-level endpoints distinguish improvements shared by the same people from improvements appearing only in separate cohort averages. A common-channel, trial-wise dimensionless processing protocol was used across recording systems. The comparisons quantify the effect of the evaluated source configurations; cohort membership, trial availability and dataset sampling mass were not varied independently.

Recent domain-generalization methods learn transferable EEG representations through contrastive regularization, marginal and conditional alignment, and latent-distribution exploration with feature fusion [3–5]. Source-population design complements these approaches: the training population determines which recorded variations are available, while checkpoint selection determines the deployed state. Established work on model-selection bias and brain-decoder evaluation motivates keeping these decisions within source data [6,7]. Domain-generalization benchmarks treat selection as part of the evaluated pipeline [8], and EEG protocol research emphasizes participant partitions and random initialization [9]. Our design extends this framework to the combined effects of source expansion, weaker-command coverage and participant-level benefit under explicitly controlled training budgets.

We used an established EEGNet backbone [10] and conventional common spatial patterns (CSP) with linear discriminant analysis (LDA) [11] to evaluate the source-design strategy across two decoding approaches. The objective was to determine whether adding Yang recordings to a BNCI source pool improved external weaker-class recall and balanced accuracy, and whether these gains persisted at a common selected duration. The completed comparisons supported both improvements; the following analyses quantify their size, distribution and dependence on the evaluated configuration.

## Materials and methods

### Study design and datasets

The study compared three source configurations: S9, containing nine BNCI2014-001 participants [12]; S29, containing those nine and a fixed subset of 20 participants from the Yang motor-imagery dataset [13,14]; and S60, containing the nine BNCI participants and all 51 Yang participants. The source registry used seed 20261017. The eligible pools contained 2,592, 14,590 and 33,183 distinct trials, respectively (Table 1). The fixed S29 subset and source membership were determined by the recorded registry.

**Table 1. Source and external populations.** Trial counts refer to distinct eligible observations. The S9/S29/S60 pools are nested; the external cohort is held separate from source fitting and checkpoint selection.

| Configuration | BNCI participants | Yang participants | Total participants | Eligible trials | Role |
|---|---:|---:|---:|---:|---|
| S9 | 9 | 0 | 9 | 2,592 | Source |
| S29 | 9 | 20 | 29 | 14,590 | Source |
| S60 | 9 | 51 | 60 | 33,183 | Source |
| Dreyer | 0 | 0 | 85 | 6,800 | External evaluation |

External evaluation used the first two acquisition runs of the Dreyer dataset [15–17]. Of 87 provider-listed participants, identifiers 17 and 41 were excluded under the predefined electrode-order eligibility criterion, leaving 85 participants and 6,800 trials. Each participant supplied 80 trials, with 40 observations per hand class. The acquisition programme's A/B/C origin strata were retained as provider identities within one external dataset. Dreyer outcomes were interpreted as exploratory because independence from earlier project-level model exposure could not be confirmed. Checkpoints and model choices were based on source-validation data rather than these external test labels.

### Native-data eligibility and analysis timing

Source and external files were bound to recorded provider identities, sizes and SHA-256 values. BNCI used both sessions and the binary hand-imagery trials. A fixed Yang registry linked all 153 session pairs to their original files. Yang eligibility retained events with explicit native class codes 1 or 2 and valid observed onsets, retaining all 51 participants. Yang supplied 30,591 eligible trials: 15,295 class-1 and 15,296 class-2 events. Unknown code-255 events and missing-label/onset counts were retained in the event audit; eligibility used only observed class labels and onsets. Five sessions contained fewer than the planned 100 trials per class. Native marker-9 delimiters defined operational segments; removing ineligible events did not repartition surviving observations into new groups of 40. The registry and per-session eligibility evidence are described in S1 Appendix.

All datasets used a six-second native-rate context and a two-second analysis crop. BNCI contexts and crops were referenced to the operational cue two seconds after the original trial-start marker. Dreyer contexts and crops were referenced to the native hand-imagery cue. For these datasets, the context was [−1.5,4.5) s and the crop [0.5,2.5) s relative to that cue. Yang used the marker-relative context [0,6) s and crop [2,4) s, which corresponds arithmetically to [0.5,2.5) s after the 1.5-s computational anchor. The original events were not shifted; this coordinate convention does not establish exact physiological-phase equivalence across acquisition paradigms. Dreyer's crop extends beyond the 1.25-s cue presentation into the provider-described visual-feedback interval, so the evaluation uses motor-imagery task EEG that may also contain feedback-related activity.

### Common-channel, dimensionless signal processing

The common montage contained 18 recorded channels: Fz, FC3, FC1, FCz, FC2, FC4, C5, C3, C1, Cz, C2, C4, C6, CP3, CP1, CP2, CP4 and Pz. Processing used common-average referencing over these channels, fixed fourth-order Butterworth second-order-section filters, forward/backward filtering with odd padding of 27 samples, polyphase resampling to 160 Hz, and a 320-sample crop. The three views were broadband (8–30 Hz), mu (8–13 Hz) and beta (13–30 Hz). Native sampling rates were 250 Hz for BNCI, 1,000 Hz for Yang and 512 Hz for Dreyer. Exact coefficients, initial conditions, context conventions and library locks accompany the archived processing implementation.

Let z(v,c,t) be the cropped, temporally centered value for view v, channel c and time sample t. For C channels and T crop samples, the trial scale was s = √[(1/(CT)) ∑_{c=1}^{C} ∑_{t=1}^{T} z(broad,c,t)²], and each view was represented as x(v,c,t) = z(v,c,t)/s. A zero or non-finite scale stopped preparation. This transform uses current-trial statistics exclusively, with the same fixed formula applied independently to every trial. Its dimensionless output is invariant to a common positive amplitude multiplier applied to every channel/view of that trial: both numerator and denominator scale by the same factor. Yang's native header contained the literal unit string `?V`, which was not interpreted as an unambiguous `µV` designation; audited numerical calibration retained the recorded native convention.

### Decoder pipelines and training budget

Both neural pipelines used the EEGNet implementation in Braindecode 1.5.1 [10,18], with F1=8, depth multiplier D=2, F2=16, kernel length 64 and dropout 0.25. The broadband pipeline (BROAD) used the 8–30 Hz view. The shared mu/beta pipeline (MU_BETA_SHARED) passed the two band views through one common backbone, concatenated them in the batch dimension and averaged their logits before the training loss and prediction. This is a complete-pipeline comparison: view exposure, computation and shared BatchNorm statistics differ between pipelines.

Each trajectory ran for 40 epochs, defined as 128 optimizer updates per epoch, for 5,120 updates. Batch size was 64; optimization used Adam with learning rate 0.001, zero weight decay and no learning-rate scheduler or mixed precision. Replacement sampling chose dataset, participant, class and trial successively. In mixed-source configurations, BNCI and Yang each received one-half of the sampling mass; participants within a dataset and classes within a participant received equal mass. An epoch is therefore an update-count unit; the available distinct-trial pools are given in Table 1. Shared-view exposure also differs from broadband exposure at a given update count.

Five whole-participant source-validation folds and three validation seeds (20261021–20261023) produced 90 validation trajectories across three source configurations and two pipelines. Three separate final seeds (20261013–20261015) produced 18 all-source trajectories. Thus, the completed neural run contained 108 trajectories and 4,320 epoch checkpoints. The final trajectories supported multiple checkpoint-selection rules through explicit checkpoint reuse.

The conventional comparator used the same dimensionless broadband inputs. A fixed Helmert projection removed the common-average-reference constant direction, yielding 17 spatial dimensions. Trace-normalized trial covariances were averaged with equal participant mass within cohort and equal cohort mass. Fixed spherical shrinkage of 0.1 preceded the generalized eigendecomposition. The two smallest and two largest eigenvectors supplied four CSP components; features were log(var_k / Σ var_m), with the sum over the four selected components. Shrinkage LDA used the least-squares solver, automatic covariance shrinkage and equal class priors. An 8,192-draw sample with replacement approximated equal cohort, class and participant weights for LDA. This is a stochastic approximation rather than an exact weighted LDA solution; draws can repeat some trials and omit others. There were three source seeds per configuration, giving nine conventional fits. The conventional fits supplied the parallel source-expansion comparator. Supplementary inference for that comparator is specified below.

### Source-only checkpoint selection and external prediction

Source-validation metrics were first averaged across validation seeds within each participant, then weighted equally across source datasets and equally across participants within each dataset. The eight rules were fixed epoch 20, mean cross-entropy, mean cross-entropy rank, mean balanced accuracy, mean weaker-class recall, and worst-tail versions of cross-entropy, balanced accuracy and weaker-class recall. For mean rank, each person's epochs were ranked by cross-entropy before weighted aggregation. A tail score used exactly the worst one-third of the weighted participant probability mass, splitting the boundary participant's mass where necessary. Cross-entropy objectives were minimized; recall and balanced-accuracy objectives were maximized. Objective ties within the specified absolute tolerance of 10⁻¹² used highest mean balanced accuracy and then earliest epoch; mean-rank ties used the earliest minimum. S1 Appendix specifies each rule and reports every selected epoch.

Source-held-out validation determined checkpoint selection. External recordings used the fixed per-trial transform and evaluation-mode inference without BatchNorm updates. Event/class metadata defined eligibility and mapping; ground-truth outcomes were used for scoring, not for choosing epochs, thresholds, fitted normalization or hyperparameters. The archived validation and prediction records document this procedure; earlier project-level external exposure remains a separate qualification.

### Endpoints and statistical analysis

For participant i and final seed j, let rL and rR denote the two class recalls. Balanced accuracy was B(i,j)=(rL+rR)/2; weaker-class recall was W(i,j)=min(rL,rR). Each metric was calculated within seed and then averaged across three final seeds within participant. Each inferential comparison used 85 participant pairs after within-participant seed averaging.

The primary contrast was S60 minus S9 under BROAD with tail weaker-class-recall selection, evaluated on W. Paired two-sided t inference used 84 degrees of freedom and a 95% t confidence interval. Three secondary tests formed one Holm family [19]: tail-recall minus mean-balanced-accuracy selection within S60 on W; S60 minus S29 under BROAD/tail-recall on W; and S60 minus S9 under that configuration on B. A paired-participant percentile bootstrap used 10,000 resamples and seed 20261016 [20]. Confidence intervals are pointwise and unadjusted for multiplicity. The archived study configuration defines the prespecified comparisons. Statistical uncertainty is conditional on the fitted trajectories and three-seed participant averages.

Four supplementary post hoc contrasts evaluated the following: S29−S9 under BROAD/tail-recall on weaker-class recall and balanced accuracy, and S60−S9 under fixed CSP–LDA on the same two endpoints. These exploratory comparisons were defined after inspection of the original outcomes. These contrasts used the archived three-seed participant means, paired two-sided t tests and pointwise 95% t intervals. Holm adjustment was applied within this separate four-test exploratory family. The original primary test and three-test secondary family were preserved. A separate complete descriptive inventory covered both expansions against S9, all eight selectors and both endpoints in the two neural pipelines (64 contrasts), plus four conventional contrasts. At the fixed epoch-20 checkpoint, we also summarized the three seed-specific paired-cohort differences for both expansions, pipelines and endpoints. This inventory introduced no confidence intervals or significance tests. The supplemental calculations used Python 3.12.14, NumPy 2.3.5 and SciPy 1.17.0 on saved metrics.

We also report a descriptive algebraic decomposition. Within each seed, B−W=|rL−rR|/2. Consequently, twice the difference of cohort-mean B and W equals the mean absolute class-recall gap after the same participant/seed averaging. This decomposition and participant improvement/decline counts are descriptive summaries of the saved predictions. Additional post hoc analyses reconstructed joint improvement in B and W, participant changes in recall gap, and label-specific recalls from the saved neural and conventional prediction tables. The descriptive results cover all 34 source-expansion-by-pipeline-by-selector comparisons against S9, including adverse outcomes, without additional hypothesis tests. A numerical tie tolerance of 10⁻¹² on the fraction scale defines unchanged observations. The relative gap reduction is 100 × (G(S9)−G(S60))/G(S9), where G is the mean seed-specific absolute recall gap. S4 Data contains the complete descriptive inventory, paired primary changes and calculation script.

### Research ethics and access scope

This study involved secondary analysis of publicly available EEG datasets (BNCI2014-001, Yang, and Dreyer). No new participants were recruited, and no interventions or additional data collection were conducted. The analysis used publicly released coded research data without access to directly identifying participant information or identity-linkage keys.

According to Article 32(1) of the 2023 Measures for the Ethical Review of Life Science and Medical Research Involving Human Participants issued by the National Health Commission of China, research using lawfully obtained publicly available data may be exempt from ethics review when the applicable conditions are satisfied. On this basis, no additional ethics review was sought for the present secondary analysis.

The ethical approvals and informed-consent procedures for the original data collection are described in the respective dataset publications [12–17]. No institutional ethics approval or exemption certificate is claimed for this secondary analysis.

### Evidence and reproducibility

The executed configuration, source registry, selected epochs, code identities and scripted verification reports are public at the immutable result commit identified in the Data and code availability statement. The result archive includes all neural selection conditions, conventional summaries, participant metrics and saved predictions. Separate evidence layers address file/code integrity, source-selection arithmetic and external saved-prediction arithmetic. The manuscript analysis uses the archived outputs. Fig 1 summarizes the design and evidence flow.

**Fig 1. Source-expansion design and evidence flow.** **A**, Nested S9/S29/S60 source pools contain 9/29/60 participants and 2,592/14,590/33,183 eligible trials. **B**, One 18-channel, trial-wise dimensionless transform supplies the spectral inputs. **C–D**, Five participant-held-out folds, three validation seeds and three final seeds produce 90 validation trajectories, 18 final trajectories and 48 checkpoint choices. Full trajectories receive 5,120 updates; 144 evaluated outputs reuse 99 distinct checkpoints. **E**, External scoring uses 85 Dreyer participants and 6,800 trials. **F**, Archived checks link input identities, source selections and prediction statistics. Source data: `figure_data/Fig1_source_configurations.csv`; audit scope: S1 Appendix.

### AI-assisted preparation

OpenAI ChatGPT and Codex assisted literature retrieval, manuscript drafting and language revision, analysis-code development, figure and document preparation, and repository updates. The author reviewed and revised the scientific content, checked numerical statements and plotted values against frozen tables and audit records, and takes responsibility for the final manuscript. ChatGPT assisted plotting-code development and revision of labels and captions. Figures were rendered from archived numerical tables; the class-recall-gap panel is identified as a descriptive algebraic decomposition. The author is responsible for verification and final approval.

## Results

### Source expansion improved weaker-class coverage

Under BROAD/tail-recall selection, mean weaker-class recall increased from 27.3137% in S9 to 48.4804% in S60. The paired difference was +21.1667 percentage points (95% t CI, 17.1226–25.2107; t(84)=10.4084; two-sided p<0.001). The paired-bootstrap interval was 17.1468–24.9512 points. Balanced accuracy increased from 58.3186% to 64.1716%, a difference of +5.8529 points (95% t CI, 4.1288–7.5771; Holm-adjusted p<0.001). The paired changes show improvement in both average discrimination and coverage of the less-recognized command. The complete prespecified comparisons are shown in Table 2.

**Table 2. Complete set of protocol-specified paired comparisons.** All rows contain 85 participant pairs and use two-sided paired t tests. Effects and pointwise 95% t intervals are in percentage points. The primary test is separate; the three secondary p values are adjusted together using Holm's method. Intervals are pointwise. Exact p values are retained in S1 Data.

| Comparison | Endpoint | Difference | 95% t CI | Raw p | Holm p |
|---|---|---:|---|---|---|
| S60−S9; BROAD/tail-recall | Weaker-class recall | +21.1667 | 17.1226 to 25.2107 | <0.001 | Primary |
| Tail-recall−mean-BA selection; S60/BROAD | Weaker-class recall | −0.8725 | −3.4935 to 1.7484 | 0.509760 | 0.999859 |
| S60−S29; BROAD/tail-recall | Weaker-class recall | −0.5490 | −2.1604 to 1.0624 | 0.499929 | 0.999859 |
| S60−S9; BROAD/tail-recall | Balanced accuracy | +5.8529 | 4.1288 to 7.5771 | <0.001 | <0.001 |

Fig 2 displays the complete set of frozen primary and secondary comparisons.

**Fig 2. All four prespecified participant-paired contrasts.** The filled circle shows the primary 21.17-point weaker-class-recall gain from S9 to S60 under BROAD/tail-recall selection. Open squares show all three secondary contrasts. Points average 85 paired participant differences after within-participant averaging across three final seeds. Bars are pointwise 95% t intervals. The primary p value is unadjusted; secondary p values use one Holm family. Source data: `figure_data/neural_recomputed_comparisons.csv`.

Weaker-class recall improved in 72 of 85 participants (84.71%), with a median paired increase of 21.6667 points. Ten participants declined and three were unchanged. An additional post hoc descriptive reconstruction found balanced-accuracy improvement in 71 participants and simultaneous improvement in both endpoints in 66 (77.65%). Fig 3 displays all 85 weaker-class changes; S4 Data supplies the paired joint-improvement inventory.

**Fig 3. Participant-level improvement in weaker-class recall.** Bars show all 85 S60−S9 BROAD/tail-recall changes in ascending order: 72 improvements, ten declines and three ties. The dashed line marks the mean increase of 21.17 points. Metrics are calculated within seed, then averaged across three seeds within participant. Participant identifiers and plot order are retained in `figure_data/Fig3_primary_participant_changes.csv`. Joint changes in both endpoints are provided in S4 Data.

### Completed evaluation and checkpoint accounting

Across the evaluated source levels, pipelines and source-only selection rules, 144 scored neural outputs reused checkpoints from 18 fitted final trajectories. Statistical comparisons treated the 85 external participants as paired observational units, not the number of checkpoints or saved prediction rows. Detailed execution and file accounting appear in S1 Appendix.

### Pipeline profiles and descriptive class-recall decomposition

Table 3 shows both endpoints for the two neural pipelines and the conventional comparator. The two neural pipelines both achieved higher mean balanced accuracy and weaker-class recall in the expanded source configurations. CSP plus shrinkage LDA reached 65.3775% mean balanced accuracy in S60, compared with 64.1716% for BROAD/tail-recall. Its weaker-class recall was 47.8137%, compared with 48.4804% for BROAD/tail-recall. At S60, CSP–LDA had 1.21 points higher mean balanced accuracy than broadband EEGNet, whereas broadband EEGNet had 0.67 points higher weaker-class recall; these untested between-decoder differences are descriptive.

**Table 3. External mean balanced accuracy and weaker-class recall across source pools.** Each cell is balanced accuracy / weaker-class recall (%), calculated within seed and averaged across seeds and participants. Neural rows use tail-recall selection; CSP is the fixed conventional comparator. Between-row comparisons are descriptive. Full condition-level summaries and intervals are supplied in S1 Data.

| Pipeline/selection | S9 | S29 | S60 |
|---|---:|---:|---:|
| BROAD / tail-recall | 58.3186 / 27.3137 | 64.1078 / 49.0294 | 64.1716 / 48.4804 |
| MU_BETA_SHARED / tail-recall | 60.1520 / 31.8529 | 63.6667 / 45.3922 | 63.8775 / 45.5686 |
| CSP + shrinkage LDA / fixed | 60.1324 / 33.9902 | 64.0196 / 45.2157 | 65.3775 / 47.8137 |

Fig 4 displays these endpoint profiles and the corresponding class-recall gap.

**Fig 4. Class coverage and balanced accuracy across source configurations.** **A**, Balanced accuracy; **B**, weaker-class recall; **C**, mean absolute class-recall gap. Neural rows use source-only tail-recall selection; CSP–LDA uses the fixed comparator configuration. A/B show participant means and pointwise 95% t intervals (n=85). C is the descriptive decomposition `2 × (balanced accuracy − weaker-class recall)`. For BROAD, the gap falls from 62.01 to 31.38 points, a 49.39% reduction. Lines guide the eye. Source data: `figure_data/Fig4_descriptive_endpoints.csv` and `figure_data/Fig4_posthoc_absolute_recall_gap.csv`.

The full source-only epoch inventory is displayed in Fig 5.

**Fig 5. All 48 source-only checkpoint choices.** The matrix shows eight selection rules across three source pools and two neural pipelines. Numbers indicate the epoch applied to all three final seeds. The outlined primary BROAD/tail-recall cells select epochs 27, 5 and 5 for S9, S29 and S60. Each full trajectory contains 40 epochs × 128 updates; evaluation uses its rule-specific checkpoint. Source data: `figure_data/Fig5_selected_epochs.csv` and the archived source-selection record.

The mean absolute class-recall gap decreased from 62.0098 points for S9/BROAD to 31.3824 points for S60/BROAD: a reduction of 30.6275 points, or 49.39% relative to the baseline gap. The gap narrowed in 72 of 85 participants, widened in 12 and was unchanged in one. This post hoc descriptive decomposition follows from twice the difference between balanced accuracy and weaker-class recall. Label-specific reconstruction showed right-hand recall rising from 31.01% to 59.64%, accompanied by left-hand recall falling from 85.63% to 68.71%. Thus, the average coverage gain reflects class rebalancing alongside higher balanced accuracy; complete changes for every evaluated configuration are supplied in S4 Data.

### Improvement with the intermediate source pool and conventional decoder

The fixed S29 source pool already achieved 49.0294% mean weaker-class recall under BROAD/tail-recall selection. In the supplementary post hoc comparison against S9, the increase was +21.7157 points (95% t CI, 17.7228–25.7086; separate four-test Holm p<0.001). Balanced accuracy increased by +5.7892 points (95% t CI, 4.1233–7.4551). Thus, substantial improvement was present in the specific intermediate source configuration, alongside the improvement in the full S60 configuration.

CSP plus shrinkage LDA also benefited from expansion: weaker-class recall increased from 33.9902% to 47.8137%, a paired gain of +13.8235 points (95% t CI, 9.1980–18.4490; separate four-test Holm p<0.001). Balanced accuracy increased by +5.2451 points (95% t CI, 3.5345–6.9557). The conventional result extends the observed mixed-source benefit beyond the neural pipeline, without establishing superiority of either decoder family (Table 4).

**Table 4. Supplementary post hoc source-expansion comparisons.** All rows use 85 participant pairs and archived three-seed participant means. Confidence intervals are pointwise; the four p values form a separate Holm family. These post hoc analyses supplement the original protocol comparisons.

| Source expansion and decoder | Endpoint | Difference (pp) | 95% t CI (pp) | Post hoc Holm p |
|---|---|---:|---|---|
| S29−S9; BROAD/tail-recall | Weaker-class recall | +21.7157 | 17.7228 to 25.7086 | <0.001 |
| S29−S9; BROAD/tail-recall | Balanced accuracy | +5.7892 | 4.1233 to 7.4551 | <0.001 |
| S60−S9; CSP–LDA/fixed | Weaker-class recall | +13.8235 | 9.1980 to 18.4490 | <0.001 |
| S60−S9; CSP–LDA/fixed | Balanced accuracy | +5.2451 | 3.5345 to 6.9557 | <0.001 |

Fig 6 displays the four supplementary paired comparisons.

**Fig 6. Supplementary post hoc source-expansion comparisons.** S29−S9 BROAD/tail-recall gains are 21.72 points for weaker-class recall and 5.79 points for balanced accuracy; corresponding S60−S9 CSP–LDA gains are 13.82 and 5.25 points. All four exploratory contrasts use the same 85 participants with three-seed within-participant averages. Bars are pointwise 95% t intervals; displayed p values use a separate four-test Holm family. Source data: `figure_data/Fig6_review2_posthoc_comparisons.csv`.

### Gains at an equal-duration checkpoint

The fixed20 rule supplies a common selected duration: each evaluated checkpoint represents 20 epochs and 2,560 optimizer updates. For BROAD, S29−S9 weaker-class recall increased by 21.1275 points and S60−S9 by 17.0686 points. For MU_BETA_SHARED, the respective increases were 23.3627 and 24.8725 points. Balanced accuracy improved in all four configurations (Table 5).

**Table 5. Complete fixed20 source-expansion control.** Values are differences of participant-averaged, three-seed means in percentage points. Every row compares checkpoints with the same 20 epochs and 2,560 updates within its pipeline. These supplementary descriptive contrasts add no significance tests or confidence intervals.

| Expansion | Pipeline | Balanced-accuracy gain (pp) | Weaker-class-recall gain (pp) | Selected epochs |
|---|---|---:|---:|---|
| S29−S9 | BROAD | +5.4118 | +21.1275 | 20 / 20 |
| S60−S9 | BROAD | +4.5441 | +17.0686 | 20 / 20 |
| S29−S9 | MU_BETA_SHARED | +6.1471 | +23.3627 | 20 / 20 |
| S60−S9 | MU_BETA_SHARED | +6.5049 | +24.8725 | 20 / 20 |

All 24 seed-specific expansion-by-pipeline-by-endpoint differences were positive across the three final seeds (Fig 7). These are descriptive summaries within the same 85-person external cohort.

**Fig 7. Source-expansion gains at a common 20-epoch checkpoint.** **A**, Balanced accuracy; **B**, weaker-class recall. Bars display all S29−S9 and S60−S9 mean changes in BROAD and shared-view pipelines at 20 epochs and 2,560 updates. The 24 points show three seed-specific cohort-mean differences for every expansion/pipeline/endpoint combination; all are positive. This duration-matched descriptive control uses the same 85 external participants. The complete 68-contrast inventory, including negative outcomes under other rules, is retained in `figure_data/Fig7_complete_source_expansion_inventory.csv`; seed data: `figure_data/Fig7_fixed20_seed_differences.csv`.

### Selection-rule sensitivity

The complete source-only selection results include configurations with adverse external outcomes. Validation objectives selected markedly different epochs; Table 2 reports that tail-recall selection did not show a demonstrated advantage over mean-balanced-accuracy selection in the prespecified S60 broadband comparison.

Automated numerical reconstruction, archive checks and their precise scope are documented in S1 Appendix and the public repository, rather than treated as additional scientific outcomes.

Across the complete selection-rule inventory, seven of eight rules gave positive mean changes for each neural pipeline, expansion and endpoint. Tail cross-entropy supplied the eight adverse neural endpoint contrasts; full results remain in S1 Data.

## Discussion

### Source-cohort expansion as an effective decoder-design choice

The principal result is a 21.17-point increase in external weaker-class recall alongside a 5.85-point increase in balanced accuracy. This combination improves recognition of the less-recognized command while increasing overall discrimination. The added participant-level analysis sharpens that result: 66 of 85 people improved on both endpoints simultaneously, and 72 improved on weaker-class recall. Thus, the two positive cohort averages also represent concurrent gains for most evaluated participants. The practical contribution is a reproducible source-design change that can be assessed alongside representation learning and model selection.

Full neural trajectories received 5,120 updates at every source level, and the 20-epoch controls matched 2,560 updates within each neural pipeline. However, S9 sampled only BNCI, whereas S29 and S60 allocated half the training draws to BNCI and half to Yang. Thus, the S9-to-mixed-source differences combine changes in provider composition, participant/trial availability and sampling weights; duration matching does not isolate a causal effect of participant count. Within the two mixed-source pools, S29 and S60 achieved 49.03% and 48.48% weaker-class recall (S60−S29: −0.55 points, 95% CI −2.16 to 1.06), with similar balanced accuracy (64.11% versus 64.17%). The data therefore do not support a monotonic source-size gain or identify the cause of this near-plateau.

### Consistency across source configurations and decoding approaches

The fixed intermediate source pool reached 49.03% weaker-class recall, with a supplementary S29−S9 estimate of +21.72 points. This identifies a concrete mixed-source configuration in which substantial improvement was already present. The source roster, eligible-trial inventory and selected checkpoint are supplied, enabling direct reproduction and later tests of alternative source subsets.

The conventional CSP–LDA decoder gained 13.82 points in weaker-class recall and 5.25 points in balanced accuracy from S9 to S60. It also achieved somewhat higher S60 balanced accuracy than broadband EEGNet (65.38% versus 64.17%), demonstrating the continued value of a strong regularized spatial-filtering baseline; the between-model difference was not an inferential contrast. Its LDA stage used an 8,192-draw weighted-sampling approximation, rather than exact weighted fitting. Large-scale MOABB benchmarking likewise emphasizes conventional comparators [21]. All three fitted seeds showed positive mean source-expansion effects at the common 20-epoch neural checkpoint, but none of these observations proves an architecture ranking.

### Class rebalancing explains the coverage gain

The identity B=W+|rL−rR|/2 relates average discrimination to weaker-class coverage and recall asymmetry. In the primary comparison, the mean absolute recall gap decreased by 30.63 points, or 49.39%; it narrowed in 72 of 85 participants. This explains why the numerical increase in weaker-class recall was much larger than the increase in balanced accuracy. Right-hand recall rose from 31.01% to 59.64%, while left-hand recall fell from 85.63% to 68.71%. The narrower gap is therefore consistent with less asymmetric hard-label predictions, not improvement in both hand classes. These class-recall summaries alone cannot distinguish improved score discrimination from a shifted decision threshold; score-level and threshold-calibration comparisons would be needed.

Source-cohort design complements EEG domain-generalization methods [3–5], but the common montage and per-trial amplitude scaling do not remove cross-dataset spatial covariance differences. The analyses did not compare target-statistics approaches, such as Euclidean alignment or unsupervised score calibration, so their effects relative to the observed source-configuration change are unknown.

### Scope and next validation

The evidence concerns three source configurations, one exploratory external cohort, one fixed Yang subset and three fitted seeds. Source-validation objectives chose very different training durations: for broadband tail weaker-class recall, epochs 27, 5 and 5 in S9, S29 and S60; for broadband S29/S60, tail cross-entropy chose epoch 1 while tail balanced accuracy chose epoch 39. These are observed selection outcomes, not proof that early training was intrinsically better or that a specific optimization mechanism caused later decline. The S60−S29 and selector contrasts remained uncertain; tail cross-entropy produced adverse external results, ten participants lost weaker-class recall, and the Yang timing and Dreyer feedback intervals constrain interpretation. Yang-only training, alternative provider weights, unsupervised calibration, covariance alignment and additional independent external cohorts were not evaluated and remain targets for future study.

## Conclusions

Source-cohort expansion increased weaker-class recall by 21.17 percentage points and balanced accuracy by 5.85 points in the primary 85-person external comparison. Sixty-six participants improved on both endpoints, and the mean class-recall gap nearly halved. Benefits were also present at equal-duration checkpoints, in the fixed intermediate source pool and in the conventional decoder. These results establish a concrete source-design strategy for improving weaker-command recognition in the evaluated cross-dataset setting, supported by controlled update budgets, complementary decoding approaches and an auditable participant-level record.

## Data and code availability

The immutable results and evidence are available at https://github.com/jackzhu119/cross-subject-mi-eeg/tree/040956085499ed788948de0d5a09cddd9eabca56/research_runs/ELIGIBLE_V3_RESULTS_20261018. This directory contains the executed configuration, source registry, selected-epoch records, original compressed prediction/result tables, audit code and scripted verification outputs. The executed source snapshot is bound to commit 0539379578818b3d71f995192e5e8a81cf4d5aef in the archived provenance. S1 Data supplies compact figure/table source values, condition summaries, participant contrasts and selected epochs. S2 Data and S3 Data provide exact copies of the saved neural and CSP prediction files, respectively. Third-party raw EEG is obtained from the original providers [12–17] under their applicable terms and is not redistributed in this manuscript package. The reproducibility README identifies the public numerical evidence, code and separately indexed neural checkpoint archives. S4 Data contains the post hoc descriptive reconstruction; the archived predictions and original hypothesis tests are unchanged.

## Author contributions

Ziyuan Zhu: Conceptualization, Methodology, Software, Validation, Formal analysis, Investigation, Data curation, Visualization, Writing – original draft, Writing – review & editing, Project administration. These roles describe the author's secondary analysis and manuscript work; original EEG collection was performed by the dataset providers.

## References

1. Lotte F, Bougrain L, Cichocki A, Clerc M, Congedo M, Rakotomamonjy A, et al. A review of classification algorithms for EEG-based brain–computer interfaces: a 10 year update. J Neural Eng. 2018;15(3):031005. doi:10.1088/1741-2552/aab2f2

2. Jayaram V, Barachant A. MOABB: trustworthy algorithm benchmarking for BCIs. J Neural Eng. 2018;15(6):066011. doi:10.1088/1741-2552/aadea0

3. Zhi H, Yu T, Gu Z, Lin Z, Che L, Li Y, et al. Supervised Contrastive Learning-Based Domain Generalization Network for Cross-Subject Motor Decoding. IEEE Trans Biomed Eng. 2025;72(1):401-412. doi:10.1109/TBME.2024.3432934

4. Zhong XC, Wang Q, Liu D, Chen Z, Liao JX, Sun J, et al. EEG-DG: A Multi-Source Domain Generalization Framework for Motor Imagery EEG Classification. IEEE J Biomed Health Inform. 2025;29(4):2484-2495. doi:10.1109/JBHI.2024.3431230

5. Song H, She Q, Fang F, Liu S, Chen Y, Zhang Y. Domain generalization through latent distribution exploration for motor imagery EEG classification. Neurocomputing. 2025;614:128889. doi:10.1016/j.neucom.2024.128889

6. Cawley GC, Talbot NLC. On Over-fitting in Model Selection and Subsequent Selection Bias in Performance Evaluation. J Mach Learn Res. 2010;11:2079-2107. Available from: https://www.jmlr.org/papers/v11/cawley10a.html [cited 2026 Oct 18].

7. Varoquaux G, Raamana PR, Engemann DA, Hoyos-Idrobo A, Schwartz Y, Thirion B. Assessing and tuning brain decoders: Cross-validation, caveats, and guidelines. NeuroImage. 2017;145:166-179. doi:10.1016/j.neuroimage.2016.10.038

8. Gulrajani I, Lopez-Paz D. In Search of Lost Domain Generalization. International Conference on Learning Representations. 2021. Available from: https://openreview.net/forum?id=lQdXeXDoWtI [cited 2026 Oct 18].

9. Borra D, Magosso E, Ravanelli M. A protocol for trustworthy EEG decoding with neural networks. Neural Networks. 2025;182:106847. doi:10.1016/j.neunet.2024.106847

10. Lawhern VJ, Solon AJ, Waytowich NR, Gordon SM, Hung CP, Lance BJ. EEGNet: a compact convolutional neural network for EEG-based brain–computer interfaces. J Neural Eng. 2018;15(5):056013. doi:10.1088/1741-2552/aace8c

11. Ramoser H, Muller-Gerking J, Pfurtscheller G. Optimal spatial filtering of single trial EEG during imagined hand movement. IEEE Transactions on Rehabilitation Engineering. 2000;8(4):441-446. doi:10.1109/86.895946

12. Brunner C, Leeb R, Müller-Putz GR, Schlögl A, Pfurtscheller G. BCI Competition 2008 – Graz data set A. 2008. Available from: https://www.bbci.de/competition/iv/desc_2a.pdf [cited 2026 Oct 18].

13. Yang B, Rong F, Xie Y, Li D, Zhang J, Li F, et al. A multi-day and high-quality EEG dataset for motor imagery brain-computer interface. Sci Data. 2025;12(1):488. doi:10.1038/s41597-025-04826-y

14. Yang B, Rong F. WBCIC-SHU Motor Imagery Dataset. [data set]. Version 5. Figshare+; 2024. doi:10.25452/figshare.plus.22671172.v5

15. Dreyer P, Roc A, Pillette L, Rimbert S, Lotte F. A large EEG database with users’ profile information for motor imagery brain-computer interface research. Sci Data. 2023;10(1):580. doi:10.1038/s41597-023-02445-z

16. Dreyer P, Roc A, Rimbert S, Pillette L, Lotte F. A large EEG database with users' profile information for motor imagery Brain-Computer Interface research. [data set]. Version To use (1). Zenodo; 2023. doi:10.5281/zenodo.8089820

17. Dreyer P, Roc A, Pillette L, Rimbert S, Lotte F. Dreyer et al. 2023 — A large EEG database with users' profile information for motor imagery brain-computer interface research. [data set]. Version 1.0.5. NEMAR; 2026. doi:10.82901/nemar.nm000250

18. Schirrmeister RT, Springenberg JT, Fiederer LDJ, Glasstetter M, Eggensperger K, Tangermann M, et al. Deep learning with convolutional neural networks for EEG decoding and visualization. Hum Brain Mapp. 2017;38(11):5391-5420. doi:10.1002/hbm.23730

19. Holm S. A Simple Sequentially Rejective Multiple Test Procedure. Scand J Stat. 1979;6(2):65-70. Available from: https://www.jstor.org/stable/4615733 [cited 2026 Oct 18].

20. Efron B. Bootstrap Methods: Another Look at the Jackknife. Ann Stat. 1979;7(1):1-26. doi:10.1214/aos/1176344552

21. Chevallier S, Carrara I, Aristimunha B, Guetschel P, Sedlar S, Lopes B, et al. The largest EEG-based BCI reproducibility study for open science: the MOABB benchmark. arXiv [Preprint]. 2024 [cited 2026 Oct 18]. Available from: https://arxiv.org/abs/2404.15319 doi:10.48550/arXiv.2404.15319

## Supporting information

S1 Appendix. Detailed preprocessing, selection definitions, execution and audit inventory, historical-study separation, and reproducibility boundaries.

S1 Data. Machine-readable frozen comparisons, condition summaries, participant changes, epoch selections and the complete numerical sources for the figures and tables.

S2 Data. Saved neural trial predictions for all 144 condition-by-seed outputs (979,200 rows).

S3 Data. Saved conventional CSP–LDA trial predictions (61,200 rows).

S4 Data. Complete additional post hoc descriptive inventory, joint endpoint changes, verification receipt and reproducible calculation script.
