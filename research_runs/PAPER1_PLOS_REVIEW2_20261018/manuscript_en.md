# Source-cohort expansion improves weaker-class coverage in cross-subject motor-imagery EEG decoding

Ziyuan Zhu*

College of Artificial Intelligence Medicine, Chongqing Medical University, Chongqing, China

*Corresponding author: zzy2630816871@gmail.com

ORCID: https://orcid.org/0009-0005-1153-4926

Postal address: Jinyun Campus, Chongqing Medical University, 61 Daxuecheng Middle Road, Shapingba District, Chongqing 401331, China

Short title: Source expansion and two-class coverage in EEG decoding

## Abstract

Adding a second source acquisition cohort can improve recognition of the less accurately decoded motor-imagery class. We quantified this strategy using nine BNCI participants alone (S9), those nine plus 20 Yang participants (S29), and the nine plus all 51 Yang participants (S60). Each neural trajectory received 5,120 optimizer updates; eight source-only checkpoint-selection rules were applied to broadband and shared mu/beta EEGNet pipelines. The completed experiment comprised 108 neural trajectories and nine conventional CSP–LDA fits. External evaluation used 85 Dreyer participants, with metrics averaged across three final seeds within person. In the prespecified broadband/tail-recall comparison, mean weaker-class recall increased from 27.31% to 48.48% with S60: +21.17 percentage points (95% CI 17.12–25.21; paired p=8.88×10⁻¹⁷). Seventy-two of 85 participants improved. Balanced accuracy increased by 5.85 points (95% CI 4.13–7.58; Holm-adjusted p=5.34×10⁻⁹). Supplementary post hoc comparisons showed gains of 21.72 points for S29 weaker-class recall (95% CI 17.72–25.71) and 13.82 points for S60 CSP weaker-class recall (95% CI 9.20–18.45). Descriptively, at the common epoch-20 checkpoint, S60−S9 weaker-class gains were 17.07 and 24.87 points for broadband and shared-view models, respectively. An algebraic decomposition showed the mean absolute class-recall gap decreasing from 62.01 to 31.38 points in the primary broadband comparison. A common 18-channel dimensionless transform, source-only checkpoint choices and participant-level predictions connect the design to independently reconstructed statistics. The exploratory external findings identify source-cohort expansion as an effective configuration change for improving two-class coverage under a fixed full-trajectory update budget. The principal advance is a quantified source-design strategy supported by duration-matched controls, two decoding approaches and a reproducible selection-to-prediction record.

## Introduction

Source-cohort design offers a direct route to better cross-subject motor-imagery EEG decoding. In this study, adding a second acquisition cohort to nine BNCI source participants increased external weaker-class recall by 21.17 percentage points and balanced accuracy by 5.85 points, with weaker-class improvement in 72 of 85 evaluated participants. At a common 20-epoch checkpoint, the broadband and shared-view S60 configurations also increased weaker-class recall by 17.07 and 24.87 points, respectively. This addresses a practical problem: a two-command decoder should recognize both intended classes, whereas a cohort-average classification score can conceal poor recognition of one command. EEG classification reviews and reproducible cross-dataset benchmarks provide the methodological foundation for examining this problem at the participant level [1,2].

Our contribution is an empirical source-design strategy with five linked components: a three-level source-expansion comparison under 5,120-update full neural trajectories; equal-duration checkpoint controls that compare the same 2,560 selected updates; joint assessment of balanced accuracy, weaker-class recall and individual changes; common-channel, trial-wise dimensionless processing across acquisition cohorts; and a reproducible chain from held-out source curves to frozen checkpoints and external predictions. Supplementary comparisons quantify the improvement already observed with the fixed 20-person Yang subset and its occurrence in a conventional spatial-filtering pipeline. Together, these components connect a concrete performance improvement to its source composition, class-coverage profile and reproducible implementation.

Recent domain-generalization methods learn transferable EEG representations through contrastive regularization, marginal and conditional alignment, and latent-distribution exploration with feature fusion [3–5]. Source-population design complements these algorithmic approaches: the training population determines which variations are represented, and checkpoint selection determines which learned state is deployed. Established work on model-selection bias and brain-decoder evaluation motivates keeping these decisions within source data [6,7]. Domain-generalization benchmarks treat selection as part of the evaluated pipeline [8], and EEG protocol research emphasizes participant partitions and random initialization [9]. Here we evaluate the resulting source-design choices with a fixed primary comparison, complete condition tables and participant-paired inference.

The smaller of the two class recalls measures coverage of the less-recognized command within each person. Combined with balanced accuracy, it also yields an interpretable decomposition of class asymmetry. This endpoint makes the operational profile of a decoder visible without relying solely on its average score. We use an established EEGNet backbone [10] and a conventional common-spatial-pattern (CSP) pipeline [11] to examine source expansion across two different decoding approaches. The central question is how adding Yang recordings to a BNCI source pool changes external two-class coverage while full-trajectory optimization updates remain fixed.

## Materials and methods

### Study design and datasets

The study compared three source configurations: S9, containing nine BNCI2014-001 participants [12]; S29, containing those nine and a fixed subset of 20 participants from the Yang motor-imagery dataset [13,14]; and S60, containing the nine BNCI participants and all 51 Yang participants. The source registry used seed 20261017. The eligible pools contained 2,592, 14,590 and 33,183 distinct trials, respectively (Table 1). The fixed S29 subset and source membership were determined by the recorded registry.

External evaluation used the first two acquisition runs of the Dreyer dataset [15–17]. Of 87 provider-listed participants, identifiers 17 and 41 were excluded under the frozen electrode-order eligibility rule, leaving 85 participants and 6,800 trials. Each participant supplied 80 trials, with 40 observations per hand class. The acquisition programme's A/B/C origin strata were retained as provider identities within one external dataset. Dreyer served as an exploratory external evaluation cohort because its prior model exposure was unconfirmed. The current comparison rules were recorded before the current external predictions.

**Table 1. Source and external populations.** Trial counts refer to distinct eligible observations. The S9/S29/S60 pools are nested; the external cohort is held separate from source fitting and checkpoint selection.

| Configuration | BNCI participants | Yang participants | Total participants | Eligible trials | Role |
|---|---:|---:|---:|---:|---|
| S9 | 9 | 0 | 9 | 2,592 | Source |
| S29 | 9 | 20 | 29 | 14,590 | Source |
| S60 | 9 | 51 | 60 | 33,183 | Source |
| Dreyer | 0 | 0 | 85 | 6,800 | External evaluation |

### Native-data eligibility and analysis timing

Source and external files were bound to recorded provider identities, sizes and SHA-256 values. BNCI used both sessions and the binary hand-imagery trials. A fixed Yang registry linked all 153 session pairs to their original files. An eligibility amendment approved on 18 October 2026 at 01:53:31 UTC retained only events with explicit native class codes 1 or 2, retaining all 51 participants. Yang supplied 30,591 eligible trials: 15,295 class-1 and 15,296 class-2 events. Unknown code-255 events and missing-label/onset counts were retained in the event audit; eligibility used only observed class labels and onsets. Five sessions contained fewer than the planned 100 trials per class. Native marker-9 delimiters defined operational segments; removing ineligible events did not repartition surviving observations into new groups of 40. The registry and per-session eligibility evidence are described in S1 Appendix.

All datasets used a six-second native-rate context and a two-second analysis crop. BNCI contexts and crops were referenced to the operational cue two seconds after the original trial-start marker. Dreyer contexts and crops were referenced to the native hand-imagery cue. For these datasets, the context was [−1.5,4.5) s and the crop [0.5,2.5) s relative to that cue. Yang used the fixed marker-relative context [0,6) s and crop [2,4) s. Its computational anchor, marker+1.5 s, reconciled processing coordinates without shifting recorded event times. The crop lies within the imagery periods under the two documented timing interpretations; exact physiological phase alignment remains uncertain. The external crop also includes part of the instructed feedback period described by the provider, so the evaluated signal is MI-containing task EEG.

### Common-channel, dimensionless signal processing

The common montage contained 18 recorded channels: Fz, FC3, FC1, FCz, FC2, FC4, C5, C3, C1, Cz, C2, C4, C6, CP3, CP1, CP2, CP4 and Pz. Processing used common-average referencing over these channels, frozen fourth-order Butterworth second-order-section filters, forward/backward filtering with odd padding of 27 samples, polyphase resampling to 160 Hz, and a 320-sample crop. The three views were broadband (8–30 Hz), mu (8–13 Hz) and beta (13–30 Hz). Native sampling rates were 250 Hz for BNCI, 1,000 Hz for Yang and 512 Hz for Dreyer. Exact coefficients, initial conditions, context conventions and library locks accompany the frozen code.

Let z(v,c,t) be the cropped, temporally centered value for view v, channel c and time sample t. The scale for each trial was s = sqrt(mean over c,t of z(broad,c,t)²), and every view was represented as x(v,c,t)=z(v,c,t)/s. A zero or non-finite scale stopped preparation. This transform uses current-trial statistics exclusively, with the same fixed formula applied independently to every trial. Its dimensionless output is invariant to a common positive amplitude multiplier applied to every channel/view of that trial: both numerator and denominator scale by the same factor. The invariant concerns a common trial-wide scale factor. Yang's native header declared `?V`; the audited native numerical calibration was retained in its recorded unit convention.

### Decoder pipelines and training budget

Both neural pipelines used the EEGNet implementation in Braindecode 1.5.1 [10,18], with F1=8, depth multiplier D=2, F2=16, kernel length 64 and dropout 0.25. BROAD used the broadband view. MU_BETA_SHARED passed the two band views through one shared backbone, concatenated them in the batch dimension and averaged their logits before the training loss and prediction. This is a complete-pipeline comparison: view exposure, computation and shared BatchNorm statistics differ between pipelines.

Each trajectory ran for 40 epochs, defined as 128 optimizer updates per epoch, for 5,120 updates. Batch size was 64; optimization used Adam with learning rate 0.001, zero weight decay and no learning-rate scheduler or mixed precision. Replacement sampling chose dataset, participant, class and trial successively. In mixed-source configurations, BNCI and Yang each received one-half of the sampling mass; participants within a dataset and classes within a participant received equal mass. An epoch is therefore an update-count unit; the available distinct-trial pools are given in Table 1. Shared-view exposure also differs from broadband exposure at a given update count.

Five whole-participant source-validation folds and three validation seeds (20261021–20261023) produced 90 validation trajectories across three source configurations and two pipelines. Three separate final seeds (20261013–20261015) produced 18 all-source trajectories. Thus, the completed neural run contained 108 trajectories and 4,320 epoch checkpoints. The final trajectories supported multiple checkpoint-selection rules through explicit checkpoint reuse.

The conventional comparator used the same dimensionless broadband inputs. A fixed Helmert projection removed the common-average-reference constant direction, yielding 17 spatial dimensions. Trace-normalized trial covariances were averaged with equal participant mass within cohort and equal cohort mass. Fixed spherical shrinkage of 0.1 preceded the generalized eigendecomposition. The two smallest and two largest eigenvectors supplied four CSP components; features were log(var_k / Σ var_m), with the sum over the four selected components. Shrinkage LDA used the least-squares solver, automatic covariance shrinkage and equal class priors. A frozen 8,192-row replacement resample approximated equal cohort/class/person weighting for LDA. There were three source seeds per configuration, giving nine conventional fits. The conventional fits supplied the parallel source-expansion comparator. Supplementary inference for that comparator is specified below.

### Source-only checkpoint selection and external prediction

Source-validation metrics were first averaged across validation seeds within each participant, then weighted equally across source datasets and equally across participants within each dataset. The eight rules were fixed epoch 20, mean cross-entropy, mean cross-entropy rank, mean balanced accuracy, mean weaker-class recall, and worst-tail versions of cross-entropy, balanced accuracy and weaker-class recall. For mean rank, each person's epochs were ranked by cross-entropy before weighted aggregation. A tail score used exactly the worst one-third of the weighted participant probability mass, splitting the boundary participant's mass where necessary. Cross-entropy objectives were minimized; recall and balanced-accuracy objectives were maximized. Objective ties within the frozen absolute tolerance of 10⁻¹² used highest mean balanced accuracy and then earliest epoch; mean-rank ties used the earliest minimum. S1 Appendix specifies each rule and reports every selected epoch.

The archived execution contract required source choices and final source trajectories to complete before current target prediction. Target recordings were processed using the fixed per-trial transform, and inference used evaluation mode with no BatchNorm updates. Event/class metadata supported eligibility and mapping; ground-truth outcomes were used for scoring. Target data did not determine epochs, thresholds, fitted normalization or model hyperparameters. Independent reconstruction of the source-selection arithmetic provides a check on the recorded choices, while the retained provenance defines the documented access sequence.

### Endpoints and statistical analysis

For participant i and final seed j, let rL and rR denote the two class recalls. Balanced accuracy was B(i,j)=(rL+rR)/2; weaker-class recall was W(i,j)=min(rL,rR). Each metric was calculated within seed and then averaged across three final seeds within participant. The seed-specific metric is the averaging input in every reported comparison. The inferential unit was the participant, n=85. The inferential sample consists of 85 participant pairs.

The primary contrast was S60 minus S9 under BROAD with tail weaker-class-recall selection, evaluated on W. Paired two-sided t inference used 84 degrees of freedom and a 95% t confidence interval. Three secondary tests formed one Holm family [19]: tail-recall minus mean-balanced-accuracy selection within S60 on W; S60 minus S29 under BROAD/tail-recall on W; and S60 minus S9 under that configuration on B. A paired-participant percentile bootstrap used 10,000 resamples and seed 20261016 [20]. Confidence intervals are pointwise and unadjusted for multiplicity. Prespecification refers to the archived study configuration, not an external preregistration. Statistical uncertainty is conditional on the fitted trajectories and three-seed participant averages.

The supplied second-round report also motivated four supplementary post hoc contrasts: S29−S9 under BROAD/tail-recall on weaker-class recall and balanced accuracy, and S60−S9 under fixed CSP–LDA on the same two endpoints. A written analysis specification was saved before calculation, after outcomes were already known. These contrasts used the archived three-seed participant means, paired two-sided t tests and pointwise 95% t intervals. Holm adjustment was applied within this separate four-test exploratory family. The original primary test and three-test secondary family were preserved. A separate complete descriptive inventory covered both expansions against S9, all eight selectors and both endpoints in the two neural pipelines (64 contrasts), plus four conventional contrasts. At the fixed epoch-20 checkpoint, we also summarized the three seed-specific paired-cohort differences for both expansions, pipelines and endpoints. This inventory introduced no confidence intervals or significance tests. The supplemental calculations used Python 3.12.14, NumPy 2.3.5 and SciPy 1.17.0 on saved metrics.

For interpretation, we added a descriptive algebraic decomposition during manuscript preparation. Within each seed, B−W=|rL−rR|/2. Consequently, twice the difference of cohort-mean B and W equals the mean absolute class-recall gap after the same participant/seed averaging. This decomposition and participant improvement/decline counts are descriptive summaries of the saved predictions.

### Research ethics and access scope

The research administration office of Chongqing Medical University confirmed on 17 October 2026 that this secondary analysis of public BNCI, Yang and Dreyer EEG data was exempt from ethics review under Article 32(1) of the 2023 Measures for the Ethical Review of Life Science and Medical Research Involving Human Participants. The date, office, basis and dataset coverage were confirmed by the author for this manuscript. The study used provider participant codes and basic metadata, with no recruitment, intervention or access to a direct identity-linkage key. Original collection procedures and consent information remain attributed to the respective provider records [12–17]. S1 Appendix records the secondary-use determination and original-data provenance separately.

### Evidence and reproducibility

The executed configuration, source registry, selection freeze, code identities and independent audit reports are public at the immutable result commit identified in the Data and code availability statement. The result archive includes all neural selection conditions, conventional summaries, participant metrics and saved predictions. Separate evidence layers address file/code integrity, source-selection arithmetic and external saved-prediction arithmetic. No scientific experiment was rerun for this manuscript revision. Fig 1 summarizes the design and evidence flow.

### AI-assisted preparation

OpenAI ChatGPT and Codex assisted literature retrieval, manuscript drafting and language revision, analysis-code development, figure and document preparation, and repository updates. The author reviewed and revised the scientific content, checked numerical statements and plotted values against frozen tables and audit records, and takes responsibility for the final manuscript.

## Results

### Completed evaluation and checkpoint accounting

The recorded run completed 108 neural trajectories and nine conventional fits. Its 144 neural configuration-by-seed outputs arose from 48 source-level/pipeline/selection conditions and three final seeds. Several rules selected the same epoch: the outputs corresponded to 99 distinct source-level/pipeline/seed/epoch checkpoints from the 18 final trajectories. The archived neural and conventional tables contained 979,200 and 61,200 prediction rows, respectively, covering the same 85 external participants. These counts describe saved evaluations, not independent training replicates.

### Source expansion improved weaker-class coverage

Under BROAD/tail-recall selection, mean weaker-class recall increased from 27.3137% in S9 to 48.4804% in S60. The paired difference was +21.1667 percentage points (95% t CI, 17.1226–25.2107; t(84)=10.4084; two-sided p=8.8841×10⁻¹⁷). The paired-bootstrap interval was 17.1468–24.9512 points (Table 2; Fig 2). Descriptively, 72 participants improved, ten declined and three were unchanged; the median paired increase was 21.6667 points. Fig 3 displays all 85 paired changes.

Balanced accuracy increased from 58.3186% to 64.1716%, a difference of +5.8529 points (95% t CI, 4.1288–7.5771; Holm-adjusted p=5.3414×10⁻⁹). The paired changes show improvement in both average discrimination and coverage of the less-recognized command.

**Table 2. Complete set of protocol-specified paired comparisons.** All rows contain 85 participant pairs and use two-sided paired t tests. Effects and pointwise 95% t intervals are in percentage points. The primary test is separate; the three secondary p values are adjusted together using Holm's method. Unadjusted intervals are not simultaneous confidence intervals.

| Comparison | Endpoint | Difference | 95% t CI | Raw p | Holm p |
|---|---|---:|---|---|---|
| S60−S9; BROAD/tail-recall | Weaker-class recall | +21.1667 | 17.1226 to 25.2107 | 8.8841×10⁻¹⁷ | Primary |
| Tail-recall−mean-BA selection; S60/BROAD | Weaker-class recall | −0.8725 | −3.4935 to 1.7484 | 0.509760 | 0.999859 |
| S60−S29; BROAD/tail-recall | Weaker-class recall | −0.5490 | −2.1604 to 1.0624 | 0.499929 | 0.999859 |
| S60−S9; BROAD/tail-recall | Balanced accuracy | +5.8529 | 4.1288 to 7.5771 | 1.7805×10⁻⁹ | 5.3414×10⁻⁹ |

### Pipeline profiles and descriptive class-recall decomposition

Table 3 and Fig 4 show both endpoints for the two neural pipelines and the conventional comparator. The two neural pipelines both achieved higher mean balanced accuracy and weaker-class recall in the expanded source configurations. CSP plus shrinkage LDA reached 65.3775% mean balanced accuracy in S60, compared with 64.1716% for BROAD/tail-recall. Its weaker-class recall was 47.8137%, compared with 48.4804% for BROAD/tail-recall. These values provide the neural and conventional operating profiles on the same external participants.

**Table 3. External mean balanced accuracy and weaker-class recall across source pools.** Each cell is balanced accuracy / weaker-class recall (%), calculated within seed and averaged across seeds and participants. Neural rows use tail-recall selection; CSP is the fixed conventional comparator. Between-row comparisons are descriptive. Full condition-level summaries and intervals are supplied in S1 Data.

| Pipeline/selection | S9 | S29 | S60 |
|---|---:|---:|---:|
| BROAD / tail-recall | 58.3186 / 27.3137 | 64.1078 / 49.0294 | 64.1716 / 48.4804 |
| MU_BETA_SHARED / tail-recall | 60.1520 / 31.8529 | 63.6667 / 45.3922 | 63.8775 / 45.5686 |
| CSP + shrinkage LDA / fixed | 60.1324 / 33.9902 | 64.0196 / 45.2157 | 65.3775 / 47.8137 |

The full source-only epoch inventory is displayed in Fig 5.

The supplementary algebraic decomposition gave a mean absolute class-recall gap of 62.0098 points for S9/BROAD and 31.3824 points for S60/BROAD, a descriptive reduction of 30.6275 points. The reduction follows directly from twice the difference between the corresponding balanced accuracy and weaker-class recall, making the recovery of two-class coverage explicit.

### Improvement with the intermediate source pool and conventional decoder

The fixed S29 source pool already achieved 49.0294% mean weaker-class recall under BROAD/tail-recall selection. In the supplementary post hoc comparison against S9, the increase was +21.7157 points (95% t CI, 17.7228–25.7086; separate four-test Holm p=5.5300×10⁻¹⁷). Balanced accuracy increased by +5.7892 points (95% t CI, 4.1233–7.4551). Thus, substantial improvement was present in the specific intermediate source configuration, alongside the improvement in the full S60 configuration.

CSP plus shrinkage LDA also benefited from expansion: weaker-class recall increased from 33.9902% to 47.8137%, a paired gain of +13.8235 points (95% t CI, 9.1980–18.4490; separate four-test Holm p=6.3276×10⁻⁸). Balanced accuracy increased by +5.2451 points (95% t CI, 3.5345–6.9557). The shared direction across a compact neural decoder and a spatial-filtering decoder makes source-cohort design a useful empirical performance lever across the two evaluated approaches (Table 4; Fig 6).

**Table 4. Supplementary post hoc source-expansion comparisons requested during manuscript review.** All rows use 85 participant pairs and archived three-seed participant means. Confidence intervals are pointwise; the four p values form a separate Holm family. These analyses were specified after outcomes were known and supplement the original protocol comparisons.

| Source expansion and decoder | Endpoint | Difference (pp) | 95% t CI (pp) | Post hoc Holm p |
|---|---|---:|---|---|
| S29−S9; BROAD/tail-recall | Weaker-class recall | +21.7157 | 17.7228 to 25.7086 | 5.5300×10⁻¹⁷ |
| S29−S9; BROAD/tail-recall | Balanced accuracy | +5.7892 | 4.1233 to 7.4551 | 2.6111×10⁻⁹ |
| S60−S9; CSP–LDA/fixed | Weaker-class recall | +13.8235 | 9.1980 to 18.4490 | 6.3276×10⁻⁸ |
| S60−S9; CSP–LDA/fixed | Balanced accuracy | +5.2451 | 3.5345 to 6.9557 | 6.3276×10⁻⁸ |



### Gains at an equal-duration checkpoint

The fixed20 rule supplies a common selected duration: each evaluated checkpoint represents 20 epochs and 2,560 optimizer updates. For BROAD, S29−S9 weaker-class recall increased by 21.1275 points and S60−S9 by 17.0686 points. For MU_BETA_SHARED, the respective increases were 23.3627 and 24.8725 points. Balanced accuracy improved in all four configurations (Table 5). All 24 seed-specific expansion-by-pipeline-by-endpoint differences were positive across the three final seeds (Fig 7). These are descriptive summaries within the same 85-person external cohort.

**Table 5. Complete fixed20 source-expansion control.** Values are differences of participant-averaged, three-seed means in percentage points. Every row compares checkpoints with the same 20 epochs and 2,560 updates within its pipeline. These supplementary descriptive contrasts add no significance tests or confidence intervals.

| Expansion | Pipeline | Balanced-accuracy gain (pp) | Weaker-class-recall gain (pp) | Selected epochs |
|---|---|---:|---:|---|
| S29−S9 | BROAD | +5.4118 | +21.1275 | 20 / 20 |
| S60−S9 | BROAD | +4.5441 | +17.0686 | 20 / 20 |
| S29−S9 | MU_BETA_SHARED | +6.1471 | +23.3627 | 20 / 20 |
| S60−S9 | MU_BETA_SHARED | +6.5049 | +24.8725 | 20 / 20 |

### Independent numerical review and result traceability

The external saved-prediction audit passed 1,179 checks with zero failures, reproducing participant metrics, paired effects, confidence intervals, p values and Holm adjustment. It checked participant/trial/label identities against saved input audits and verified identical predictions for checkpoint aliases. A separate integrity/source-selection audit checked nine off-Pod checkpoint archives, payload hashes, 108 trajectory contracts, 23,520 validation rows, 1,680 aggregate scores and all 48 selection choices. The largest discrepancy in reconstructed aggregate scores was 7.1054×10⁻¹⁵.

The checks connect recorded input identities, source selections and saved-prediction statistics. Complete numerical sources for the tables and figures accompany the manuscript; S1 Appendix details the scope of each evidence layer.

Across the complete selection-rule inventory, seven of eight rules gave positive mean changes for each neural pipeline, expansion and endpoint; tail cross-entropy was the exception. The original S60−S29 and selector contrasts had intervals spanning zero (Table 2); full results remain in S1 Data.

## Discussion

### Source-cohort design improves two-command coverage

Adding the Yang acquisition cohort to the nine-person BNCI source pool improved external weaker-class recall by 21.17 points in the primary broadband configuration. The corresponding 5.85-point balanced-accuracy gain and improvement in 72 participants show that the configuration change affected both average discrimination and recognition of the less-recognized command. This is an actionable design finding for cross-subject decoding: source composition deserves explicit evaluation alongside decoder architecture and checkpoint-selection policy.

The full neural trajectories received 5,120 updates at every source level. When Yang was added, the sampler assigned it half of the dataset mass, reducing BNCI's sampling mass from one to one-half. The gain therefore accompanied broader acquisition diversity within the same full-trajectory update allocation. The common epoch-20 controls strengthen this interpretation: improvement remained present when selected duration was also held constant within each pipeline. This is an important practical distinction between the source-design contribution and checkpoint-duration selection.

### Gains observed in the intermediate pool and two decoder families

The fixed intermediate pool reached 49.03% weaker-class recall, with a supplementary S29−S9 estimate of +21.72 points. This makes the S29 configuration a concrete, reproducible example of effective source expansion. Reporting its composition, counts and source-selected epoch allows subsequent work to examine how much additional acquisition diversity is useful in other populations. The S29 and S60 means locate the main observed gain between the BNCI-only and mixed-source configurations.

The conventional CSP–LDA decoder gained 13.82 points on weaker-class recall and 5.25 points on balanced accuracy from S9 to S60. Source-expansion improvement was therefore observed in both the neural and conventional approaches evaluated here. Large-scale MOABB benchmarking likewise identifies training-data availability and strong conventional approaches as relevant to decoder comparisons [21]. The fixed20 seed profiles add a complementary consistency check: all three fitted seeds showed the same positive direction in both neural pipelines and both endpoints. The S60 endpoint profiles were also informative: CSP had higher mean balanced accuracy, while BROAD/tail-recall had slightly higher weaker-class recall. Joint reporting directs attention to useful class coverage across decoding approaches instead of making architecture ranking the centre of the study.

### A measurable class-coverage improvement

The identity B=W+|rL−rR|/2 separates two-class coverage from class asymmetry. In the primary comparison, the mean absolute left–right recall gap decreased by 30.63 points. This decomposition explains why weaker-class recall conveyed a larger numerical improvement than balanced accuracy: recognition of the less-recognized command improved while class asymmetry narrowed. All 85 paired changes and both endpoints remain visible, connecting the cohort result to individual operating profiles.

The contribution complements domain-generalization representation learning [3–5] through explicit source-design and checkpoint-selection accounting. The common 18-channel processing contract and current-trial normalization give the cross-cohort comparison a reproducible numerical basis. Held-out source metrics, frozen choices and external participant predictions then link the design to the reported gains. This combination supplies a reusable evaluation pattern for assessing future source populations and decoding approaches.

### Scope and future evaluation

The findings concern complete source configurations: cohort composition, trial availability, sampling frequency and selected duration varied together, with primary checkpoints at epochs 27/5/5 for S9/S29/S60. One fixed intermediate subset, one external acquisition programme and three final seeds define the current evidence; the conditional intervals support neither a universal 20-person threshold nor decoder-family equivalence. The Dreyer evaluation remains exploratory, Yang timing and absolute-voltage interpretation follow the documented conventions, and the task windows include feedback-related activity. Prospective source-subset variation and independent acquisition cohorts are the next tests of the observed source-design strategy; original historical analyses and their results remain separately archived.

## Conclusions

Adding a second source acquisition cohort improved weaker-class recall by 21.17 percentage points and balanced accuracy by 5.85 points in the primary 85-person external comparison. The improvement also appeared at equal-duration checkpoints, in the fixed intermediate pool and in the conventional CSP decoder. Participant-level changes and the class-recall decomposition show that this improvement includes better recognition of the weaker command and reduced class asymmetry. The study provides a concrete source-design strategy, a common processing contract and a reproducible selection-to-prediction record for advancing cross-subject motor-imagery EEG decoding.

## Data and code availability

The immutable results and evidence are available at https://github.com/jackzhu119/cross-subject-mi-eeg/tree/040956085499ed788948de0d5a09cddd9eabca56/research_runs/ELIGIBLE_V3_RESULTS_20261018. This directory contains the executed configuration, source registry, selected-epoch freeze, original compressed prediction/result tables, audit code and independent audit outputs. The executed source snapshot is bound to commit 0539379578818b3d71f995192e5e8a81cf4d5aef in the archived provenance. S1 Data supplies compact figure/table source values, condition summaries, participant contrasts and selected epochs. S2 Data and S3 Data provide exact copies of the saved neural and CSP prediction files, respectively. Third-party raw EEG is obtained from the original providers [12–17] under their applicable terms and is not redistributed in this manuscript package. The reproducibility README identifies the public numerical evidence, code and separately indexed neural checkpoint archives.



## Author contributions

Ziyuan Zhu: Conceptualization, Methodology, Software, Validation, Formal analysis, Investigation, Data curation, Visualization, Writing – original draft, Writing – review & editing, Project administration. These roles describe the author's secondary analysis and manuscript work; original EEG collection was performed by the dataset providers.

## Supporting information

S1 Appendix. Detailed preprocessing, selection definitions, execution and audit inventory, historical-study separation, and reproducibility boundaries.

S1 Data. Machine-readable frozen comparisons, condition summaries, participant changes, epoch selections and the complete numerical sources for the figures and tables.

S2 Data. Saved neural trial predictions for all 144 condition-by-seed outputs (979,200 rows).

S3 Data. Saved conventional CSP–LDA trial predictions (61,200 rows).

## Figure captions

## Fig 1. Frozen source-expansion design and evidence flow.

**A**, The nested source configurations contain nine BNCI2014-001 participants (S9), BNCI plus a fixed set of 20 Yang participants (S29), or BNCI plus all 51 eligible Yang participants (S60): 2,592, 14,590 and 33,183 eligible trials, respectively. **B**, One 18-channel processing recipe produces dimensionless spectral inputs using each trial's broadband root-mean-square amplitude. **C**, Five whole-participant validation folds and three seeds yield 90 trajectories and 48 source-only checkpoint choices. **D**, Three final seeds yield 18 complete trajectories at 5,120 updates each; S29/S60 assign half the training-sampling mass to each source cohort. The 144 selected outputs reuse 99 distinct checkpoints. **E**, Exploratory external scoring covers 85 Dreyer participants and 6,800 unique trials; event/class metadata determine eligibility and mapping, and ground-truth labels support scoring only. **F**, Source-integrity, selector-binding and saved-prediction arithmetic checks establish the archived evidence links; raw-signal reconstruction and checkpoint-forward replay fall outside this audit. Source data: `figure_data/Fig1_source_configurations.csv`; provenance: `figure_data/SOURCE_PROVENANCE.json`.

## Fig 2. All four frozen participant-paired external contrasts.

The primary contrast (filled circle) shows the 21.17-percentage-point increase in weaker-class recall from S9 to S60 under BROAD/tail-weaker-class-recall selection. Open squares show all three frozen secondary contrasts, including selector and S60–S29 comparisons. Points average 85 participant-paired differences after within-participant averaging over three seeds. Horizontal bars are pointwise, unadjusted 95% *t* confidence intervals conditional on the fitted trajectories. The primary *p* value is unadjusted; the three secondary *p* values form one Holm-adjusted family. Source data: `figure_data/neural_recomputed_comparisons.csv`.

## Fig 3. Participant-level improvement in weaker-class recall.

Weaker-class recall increases for 72 of 85 Dreyer participants under the S60 versus S9 BROAD comparison. Bars display every paired change in ascending order, including 10 declines and three unchanged observations (squares). The dashed line marks the frozen mean increase of 21.17 percentage points. Metrics are calculated within seed and then averaged across three seeds for each participant. This descriptive display retains original participant identifiers and plot order in `figure_data/Fig3_primary_participant_changes.csv`.

## Fig 4. External class coverage and balanced accuracy across source configurations.

**A**, Balanced accuracy; **B**, weaker-class recall; **C**, mean absolute left–right recall gap. BROAD and shared μ/β use source-only tail-weaker-class-recall selection; CSP with shrinkage LDA uses its fixed configuration. A/B show participant means and stored pointwise 95% *t* intervals (*n* = 85). Source expansion raises weaker-class recall while reducing recall imbalance: for BROAD, the mean gap falls from 62.01 percentage points at S9 to 31.38 at S60, with similar means at S29 and S60. Panel C is a post hoc descriptive decomposition, `2 × (balanced accuracy − weaker-class recall)`, calculated within seed and preserved by averaging; no extra interval or test is introduced. The comparison retains all three pipelines and concerns complete source configurations, including their selected checkpoints. Lines guide the eye. Source data: `figure_data/Fig4_descriptive_endpoints.csv` and `figure_data/Fig4_posthoc_absolute_recall_gap.csv`.

## Fig 5. All 48 frozen source-only checkpoint selections.

The matrix retains all eight selection rules across three source configurations and two pipelines. Numbers and shading encode source-selected epoch; the same epoch is applied to the three final seeds. The primary BROAD rule selects epochs 27, 5 and 5 for S9, S29 and S60 (outlined cells). Each complete trajectory used 40 epochs × 128 updates = 5,120 optimizer updates; evaluation uses the rule-specific checkpoint duration. Source data: `figure_data/Fig5_selected_epochs.csv`, matched to the frozen `selection_freeze.json`.

## Fig 6. Source-expansion gains in the additional paired analyses.

The additional S29–S9 BROAD comparison shows increases of 21.72 percentage points in weaker-class recall and 5.79 points in balanced accuracy. Within CSP with shrinkage LDA, S60–S9 gains are 13.82 and 5.25 points, respectively. These four comparisons were defined for this post hoc review after the original outcomes were known, then calculated together without changing selection rules or fitted models. Each contrast uses the same 85 participants and three-seed within-participant averages. Horizontal bars are pointwise, unadjusted 95% *t* intervals conditional on the fitted models; the four displayed *p* values form a separate Holm-adjusted family. The original frozen primary and secondary comparisons remain unchanged. Source data: `figure_data/Fig6_review2_posthoc_comparisons.csv`.

## Fig 7. Source-expansion gains at a common 20-epoch checkpoint.

At the fixed20 checkpoint, every displayed source expansion improves both balanced accuracy (**A**) and weaker-class recall (**B**) relative to S9. Bars show the three-seed mean paired difference for S29–S9 and S60–S9 under both BROAD and shared μ/β; numerical labels give the bar heights in percentage points. The 24 overlaid points show all three seed-specific cohort-mean differences, using the same 85 participants. All compared checkpoints represent 20 epochs and 2,560 optimizer updates, providing a common-duration descriptive control alongside source-selected comparisons. This post hoc display includes all eight fixed20 condition/endpoint combinations, rather than selecting the best checkpoint or seed; no additional interval or hypothesis test is introduced. Seed consistency is conditional on the same cohort and does not represent independent replication. The complete 68-row source-expansion inventory, including other selectors and negative differences, remains available in `figure_data/Fig7_complete_source_expansion_inventory.csv`; seed data: `figure_data/Fig7_fixed20_seed_differences.csv`.

## Figure-preparation assistance

ChatGPT assisted plotting-code development and revision of labels and captions. Figures were rendered from archived, audited numerical tables; Fig 4C is explicitly identified as a descriptive algebraic decomposition. The author is responsible for verification and final approval.

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
