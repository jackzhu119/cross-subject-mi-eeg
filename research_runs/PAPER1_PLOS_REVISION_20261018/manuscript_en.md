# Source-cohort expansion and weaker-class coverage in cross-subject motor-imagery EEG decoding

Ziyuan Zhu*

College of Artificial Intelligence Medicine, Chongqing Medical University, Chongqing, China

*Corresponding author: zzy2630816871@gmail.com

ORCID: https://orcid.org/0009-0005-1153-4926

Postal address: Jinyun Campus, Chongqing Medical University, 61 Daxuecheng Middle Road, Shapingba District, Chongqing 401331, China

Short title: Source expansion and two-class coverage in EEG decoding

## Abstract

Cross-subject motor-imagery decoders can attain moderate balanced accuracy while recognizing one imagery class poorly. We examined whether source-cohort expansion improves this weaker-class coverage under a fixed optimization budget. Three source configurations contained nine BNCI participants, those nine plus 20 Yang participants, or those nine plus all 51 Yang participants. An 18-channel, trial-wise dimensionless processing pipeline supported broadband and shared mu/beta EEGNet models. Eight source-only checkpoint-selection rules were evaluated through 90 validation and 18 final training trajectories. External evaluation involved 85 Dreyer participants, with three final seeds averaged within each person. The primary endpoint was the smaller of left- and right-hand recall, calculated within seed. Under the prespecified broadband/tail-recall configuration, expanding from nine to 60 source participants increased mean weaker-class recall from 27.31% to 48.48%: +21.17 percentage points (95% confidence interval, 17.12–25.21; paired two-sided p=8.88×10⁻¹⁷). Seventy-two participants improved, ten declined and three were unchanged. Balanced accuracy increased by 5.85 points (95% confidence interval, 4.13–7.58; Holm-adjusted p=5.34×10⁻⁹). The corresponding mean absolute difference between class recalls decreased from 62.01 to 31.38 points in a supplementary descriptive decomposition. Two secondary comparisons did not establish additional benefit: 60 versus 29 sources (−0.55 points) and tail-recall versus mean-balanced-accuracy selection (−0.87 points; both Holm-adjusted p=0.999859). Saved-prediction statistics passed 1,179 independent checks. These exploratory external results support source expansion as a practical route to better two-class coverage in the evaluated configuration. Source composition, trial availability and selected training duration changed together; prior target exposure was uncertain. The contribution is a controlled-budget evaluation with participant-level outcomes and a traceable selection-and-results chain.

## Introduction

Motor-imagery brain–computer interfaces translate intentional changes in EEG into control signals. Transferring a decoder across people can reduce the recordings needed from each new user, but performance depends on variation in anatomy, recording conditions and task execution. Reviews of EEG classification and reproducible multi-dataset benchmarks have documented the importance of evaluating complete processing pipelines across participants [1,2]. An important practical question is which changes improve recognition of both intended commands, rather than only the cohort-average score.

Recent domain-generalization studies pursue transferable representations through contrastive regularization, marginal and conditional alignment, and latent-distribution exploration with feature fusion [3–5]. These approaches make source diversity and selection policy especially relevant: a representation is trained on a particular source population, and its reported performance is also shaped by how its training checkpoint is selected. Selection bias and the uncertainty of brain-decoder evaluation are established methodological concerns [6,7]. Domain-generalization benchmarks explicitly include model selection in the evaluation protocol [8]; EEG-specific protocol work likewise examines subject partitions and random initialization [9]. A useful complementary contribution is therefore a transparent empirical account of how source expansion, checkpoint selection and participant-level class coverage interact.

Balanced accuracy weights both imagery classes equally, yet the same value can arise from different combinations of class recall. For a two-command interface, a decoder that recognizes one class reliably and rarely recognizes the other has a different operating profile from a decoder with similar recall for both. Reporting the smaller class recall alongside balanced accuracy makes this difference visible. It also separates improvements in average discrimination from recovery of the less-recognized command within each person.

We address these questions with three fixed source configurations and a single external acquisition cohort. Source pools comprise nine BNCI participants, the same nine plus a fixed 20-person Yang subset, and the nine plus all 51 Yang participants. Each full neural trajectory receives the same number of optimizer updates. Broadband and shared mu/beta pipelines use an established EEGNet backbone [10], with a conventional common-spatial-pattern (CSP) comparator [11]. Checkpoints are selected exclusively from held-out source participants. The primary comparison and three secondary comparisons are specified in the archived protocol, and the complete set of selection rules remains visible in the results.

The study makes four empirical and methodological contributions. First, it quantifies a source-expansion comparison under a common full-trajectory optimization budget, with an external participant-level estimate and uncertainty interval. Second, it combines weaker-class recall, balanced accuracy and individual paired changes to characterize two-command coverage. Third, it implements a common-channel, trial-wise dimensionless processing contract across three acquisition cohorts, with explicit handling of native-label eligibility and timing conventions. Fourth, it links source-validation curves, frozen checkpoint choices, prediction identities and independent statistical reconstruction in an inspectable evidence chain. The resulting contribution is an evaluation of source population and selection decisions using established decoders, rather than a new decoding architecture.

## Materials and methods

### Study design and datasets

The study compared three source configurations: S9, containing nine BNCI2014-001 participants [12]; S29, containing those nine and a fixed subset of 20 participants from the Yang motor-imagery dataset [13,14]; and S60, containing the nine BNCI participants and all 51 Yang participants. The source registry used seed 20261017. The eligible pools contained 2,592, 14,590 and 33,183 distinct trials, respectively (Table 1). S29 was one fixed intermediate subset. Adding Yang changed participant count, trial availability and acquisition-cohort composition jointly.

External evaluation used the first two acquisition runs of the Dreyer dataset [15–17]. Of 87 provider-listed participants, identifiers 17 and 41 were excluded under the frozen electrode-order eligibility rule, leaving 85 participants and 6,800 trials. Each participant supplied 80 trials, with 40 observations per hand class. The acquisition programme's A/B/C origin strata were retained as provider identities within one external dataset. Prior model exposure to this cohort could not be confirmed; its role is exploratory external evaluation. This designation applies even though the current comparison rules were fixed in the archived protocol before the current external predictions.

**Table 1. Source and external populations.** Trial counts are distinct eligible observations, not replacement-sampling draws or repeated prediction rows. The S9/S29/S60 pools are nested; the external cohort is held separate from source fitting and checkpoint selection.

| Configuration | BNCI participants | Yang participants | Total participants | Eligible trials | Role |
|---|---:|---:|---:|---:|---|
| S9 | 9 | 0 | 9 | 2,592 | Source |
| S29 | 9 | 20 | 29 | 14,590 | Source |
| S60 | 9 | 51 | 60 | 33,183 | Source |
| Dreyer | 0 | 0 | 85 | 6,800 | External evaluation |

### Native-data eligibility and analysis timing

Source and external files were bound to recorded provider identities, sizes and SHA-256 values. BNCI used both sessions and the binary hand-imagery trials. A fixed Yang registry linked all 153 session pairs to their original files. An eligibility amendment approved on 18 October 2026 at 01:53:31 UTC retained only events with explicit native class codes 1 or 2, retaining all 51 participants. Yang supplied 30,591 eligible trials: 15,295 class-1 and 15,296 class-2 events. Unknown code-255 events and missing-label/onset counts were retained in the event audit, rather than inferred or imputed. Five sessions contained fewer than the planned 100 trials per class. Native marker-9 delimiters defined operational segments; removing ineligible events did not repartition surviving observations into new groups of 40. The registry and per-session eligibility evidence are described in S1 Appendix.

All datasets used a six-second native-rate context and a two-second analysis crop. BNCI contexts and crops were referenced to the operational cue two seconds after the original trial-start marker. Dreyer contexts and crops were referenced to the native hand-imagery cue. For these datasets, the context was [−1.5,4.5) s and the crop [0.5,2.5) s relative to that cue. Yang used the fixed marker-relative context [0,6) s and crop [2,4) s. Its computational anchor, marker+1.5 s, reconciled processing coordinates without shifting recorded event times. The crop lies within the imagery periods under the two documented timing interpretations; exact physiological phase alignment remains uncertain. The external crop also includes part of the instructed feedback period described by the provider, so the task is interpreted as MI-containing EEG rather than isolated cortical imagery.

### Common-channel, dimensionless signal processing

The common montage contained 18 recorded channels: Fz, FC3, FC1, FCz, FC2, FC4, C5, C3, C1, Cz, C2, C4, C6, CP3, CP1, CP2, CP4 and Pz. Processing used common-average referencing over these channels, frozen fourth-order Butterworth second-order-section filters, forward/backward filtering with odd padding of 27 samples, polyphase resampling to 160 Hz, and a 320-sample crop. The three views were broadband (8–30 Hz), mu (8–13 Hz) and beta (13–30 Hz). Native sampling rates were 250 Hz for BNCI, 1,000 Hz for Yang and 512 Hz for Dreyer. Exact coefficients, initial conditions, context conventions and library locks accompany the frozen code.

Let z(v,c,t) be the cropped, temporally centered value for view v, channel c and time sample t. The scale for each trial was s = sqrt(mean over c,t of z(broad,c,t)²), and every view was represented as x(v,c,t)=z(v,c,t)/s. A zero or non-finite scale stopped preparation. This transform uses only the current trial; no centering or normalization parameters are estimated across target trials or participants. Its dimensionless output is invariant to a common positive amplitude multiplier applied to every channel/view of that trial: both numerator and denominator scale by the same factor. This algebraic property handles a shared scale factor, while leaving channel-specific calibration and timing questions separate. Yang's native header declared `?V`; the audited native numerical calibration was retained without assigning an unsupported physical voltage unit.

### Decoder pipelines and training budget

Both neural pipelines used the EEGNet implementation in Braindecode 1.5.1 [10,18], with F1=8, depth multiplier D=2, F2=16, kernel length 64 and dropout 0.25. BROAD used the broadband view. MU_BETA_SHARED passed the two band views through one shared backbone, concatenated them in the batch dimension and averaged their logits before the training loss and prediction. This is a complete-pipeline comparison: view exposure, computation and shared BatchNorm statistics differ between pipelines.

Each trajectory ran for 40 epochs, defined as 128 optimizer updates per epoch, for 5,120 updates. Batch size was 64; optimization used Adam with learning rate 0.001, zero weight decay and no learning-rate scheduler or mixed precision. Replacement sampling chose dataset, participant, class and trial successively. In mixed-source configurations, BNCI and Yang each received one-half of the sampling mass; participants within a dataset and classes within a participant received equal mass. This design fixes full-trajectory updates rather than the number of passes through the available distinct trials. Shared-view exposure also differs from broadband exposure at a given update count.

Five whole-participant source-validation folds and three validation seeds (20261021–20261023) produced 90 validation trajectories across three source configurations and two pipelines. Three separate final seeds (20261013–20261015) produced 18 all-source trajectories. Thus, the completed neural run contained 108 trajectories and 4,320 epoch checkpoints. The final trajectories supported multiple checkpoint-selection rules through explicit checkpoint reuse.

The conventional comparator used the same dimensionless broadband inputs. A fixed Helmert projection removed the common-average-reference constant direction, yielding 17 spatial dimensions. Trace-normalized trial covariances were averaged with equal participant mass within cohort and equal cohort mass. Fixed spherical shrinkage of 0.1 preceded the generalized eigendecomposition. The two smallest and two largest eigenvectors supplied four CSP components; features were log(var_k / Σ var_m), with the sum over the four selected components. Shrinkage LDA used the least-squares solver, automatic covariance shrinkage and equal class priors. A frozen 8,192-row replacement resample approximated equal cohort/class/person weighting for LDA. There were three source seeds per configuration, giving nine conventional fits. These were descriptive comparators outside the neural hypothesis-testing family.

### Source-only checkpoint selection and external prediction

Source-validation metrics were first averaged across validation seeds within each participant, then weighted equally across source datasets and equally across participants within each dataset. The eight rules were fixed epoch 20, mean cross-entropy, mean cross-entropy rank, mean balanced accuracy, mean weaker-class recall, and worst-tail versions of cross-entropy, balanced accuracy and weaker-class recall. For mean rank, each person's epochs were ranked by cross-entropy before weighted aggregation. A tail score used exactly the worst one-third of the weighted participant probability mass, splitting the boundary participant's mass where necessary. Cross-entropy objectives were minimized; recall and balanced-accuracy objectives were maximized. Objective ties within the frozen absolute tolerance of 10⁻¹² used highest mean balanced accuracy and then earliest epoch; mean-rank ties used the earliest minimum. S1 Appendix specifies each rule and reports every selected epoch.

The archived execution contract required source choices and final source trajectories to complete before current target prediction. Target recordings were processed using the fixed per-trial transform, and inference used evaluation mode with no BatchNorm updates. Event/class metadata supported eligibility and mapping; ground-truth outcomes were used for scoring. Target data did not determine epochs, thresholds, fitted normalization or model hyperparameters. Independent reconstruction of the source-selection arithmetic provides a check on the recorded choices, while the retained provenance defines the documented access sequence.

### Endpoints and statistical analysis

For participant i and final seed j, let rL and rR denote the two class recalls. Balanced accuracy was B(i,j)=(rL+rR)/2; weaker-class recall was W(i,j)=min(rL,rR). Each metric was calculated within seed and then averaged across three final seeds within participant. This is distinct from a logits ensemble or the minimum of seed-averaged class recalls. The inferential unit was the participant, n=85. Seeds, folds and repeated prediction rows were not additional participants.

The primary contrast was S60 minus S9 under BROAD with tail weaker-class-recall selection, evaluated on W. Paired two-sided t inference used 84 degrees of freedom and a 95% t confidence interval. Three secondary tests formed one Holm family [19]: tail-recall minus mean-balanced-accuracy selection within S60 on W; S60 minus S29 under BROAD/tail-recall on W; and S60 minus S9 under that configuration on B. A paired-participant percentile bootstrap used 10,000 resamples and seed 20261016 [20]. Confidence intervals are pointwise and unadjusted for multiplicity. Prespecification refers to the archived study configuration, not an external preregistration. Statistical uncertainty is conditional on the fitted trajectories and three-seed participant averages.

For interpretation, we added a descriptive algebraic decomposition during manuscript preparation. Within each seed, B−W=|rL−rR|/2. Consequently, twice the difference of cohort-mean B and W equals the mean absolute class-recall gap after the same participant/seed averaging. Values derived from this identity are labelled as supplementary descriptions; no additional hypothesis test, selection rule or interval was introduced. Participant improvement/decline counts are likewise descriptive.

### Research ethics and access scope

This secondary study used existing public research datasets and recruited no new participants. The author reports access to provider participant codes, age and basic metadata, without names, contact details or an identity-linkage key. Original acquisition procedures and participant-consent information are described by the source dataset publications and documentation [12–17]. The author confirms that neither new ethics approval nor an exemption was required for this secondary analysis; this is the author's assessment, for which no formal institutional determination document is available. Original collection records are kept distinct from the secondary-analysis statement. No committee decision, approval number or waiver is asserted for the present analysis. Dataset access versions and the limits of the available collection documentation are detailed in S1 Appendix.

### Evidence and reproducibility

The executed configuration, source registry, selection freeze, code identities and independent audit reports are public at the immutable result commit identified in the Data and code availability statement. The result archive includes all neural selection conditions, conventional summaries, participant metrics and saved predictions. Separate evidence layers address file/code integrity, source-selection arithmetic and external saved-prediction arithmetic. No scientific experiment was rerun for this manuscript revision. Fig 1 summarizes the design and evidence flow.

## Results

### Completed evaluation and checkpoint accounting

The recorded run completed 108 neural trajectories and nine conventional fits. Its 144 neural configuration-by-seed outputs arose from 48 source-level/pipeline/selection conditions and three final seeds. Several rules selected the same epoch: the outputs corresponded to 99 distinct source-level/pipeline/seed/epoch checkpoints from the 18 final trajectories. The archived neural and conventional tables contained 979,200 and 61,200 prediction rows, respectively, covering the same 85 external participants. These counts describe saved evaluations, not independent training replicates.

### Source expansion improved weaker-class coverage

Under BROAD/tail-recall selection, mean weaker-class recall increased from 27.3137% in S9 to 48.4804% in S60. The paired difference was +21.1667 percentage points (95% t CI, 17.1226–25.2107; t(84)=10.4084; two-sided p=8.8841×10⁻¹⁷). The paired-bootstrap interval was 17.1468–24.9512 points (Table 2; Fig 2). Descriptively, 72 participants improved, ten declined and three were unchanged; the median paired increase was 21.6667 points. Fig 3 displays all 85 paired changes.

Balanced accuracy increased from 58.3186% to 64.1716%, a difference of +5.8529 points (95% t CI, 4.1288–7.5771; Holm-adjusted p=5.3414×10⁻⁹). The two endpoints therefore convey complementary aspects of the same predictions: the larger weaker-class change documents improved coverage of the less-recognized class, while the balanced-accuracy change summarizes average discrimination.

**Table 2. Complete set of protocol-specified paired comparisons.** All rows contain 85 participant pairs and use two-sided paired t tests. Effects and pointwise 95% t intervals are in percentage points. The primary test is separate; the three secondary p values are adjusted together using Holm's method. Unadjusted intervals are not simultaneous confidence intervals.

| Comparison | Endpoint | Difference | 95% t CI | Raw p | Holm p |
|---|---|---:|---|---|---|
| S60−S9; BROAD/tail-recall | Weaker-class recall | +21.1667 | 17.1226 to 25.2107 | 8.8841×10⁻¹⁷ | Primary |
| Tail-recall−mean-BA selection; S60/BROAD | Weaker-class recall | −0.8725 | −3.4935 to 1.7484 | 0.509760 | 0.999859 |
| S60−S29; BROAD/tail-recall | Weaker-class recall | −0.5490 | −2.1604 to 1.0624 | 0.499929 | 0.999859 |
| S60−S9; BROAD/tail-recall | Balanced accuracy | +5.8529 | 4.1288 to 7.5771 | 1.7805×10⁻⁹ | 5.3414×10⁻⁹ |

### Expansion beyond the intermediate pool and selection-rule comparison

S29 achieved 49.0294% mean weaker-class recall under BROAD/tail-recall selection. S60−S29 was −0.5490 points, with a 95% t interval of −2.1604 to 1.0624 and Holm-adjusted p=0.999859. Within S60/BROAD, mean-balanced-accuracy selection achieved 49.3529% weaker-class recall, compared with 48.4804% for tail-recall selection. The corresponding difference was −0.8725 points (95% t CI, −3.4935 to 1.7484; Holm-adjusted p=0.999859). These comparisons locate the supported improvement in the S9-to-expanded-source contrast; they provide no evidence for additional benefit from S60 over S29 or from tail-recall over mean-BA selection. The intervals do not establish equivalence.

The primary configuration selected epoch 27 for S9 and epoch 5 for both S29 and S60. Although each trajectory had the same 40-epoch update budget, evaluated checkpoints therefore differed in training duration. All eight rules, including unfavorable external outcomes, are retained in S1 Data and S1 Appendix.

### Pipeline profiles and descriptive class-recall decomposition

Table 3 and Fig 4 show both endpoints for the two neural pipelines and the conventional comparator. Broadband and shared-view mean balanced accuracies were close in the expanded conditions; their ordering is descriptive because no additional pipeline test was added. CSP plus shrinkage LDA reached 65.3775% mean balanced accuracy in S60, compared with 64.1716% for BROAD/tail-recall. Its weaker-class recall was 47.8137%, compared with 48.4804% for BROAD/tail-recall. The two summaries thus capture different aspects of the comparator profiles.

**Table 3. External mean balanced accuracy and weaker-class recall across source pools.** Each cell is balanced accuracy / weaker-class recall (%), calculated within seed and averaged across seeds and participants. Neural rows use tail-recall selection; CSP is the fixed conventional comparator. Between-row comparisons are descriptive. Full condition-level summaries and intervals are supplied in S1 Data.

| Pipeline/selection | S9 | S29 | S60 |
|---|---:|---:|---:|
| BROAD / tail-recall | 58.3186 / 27.3137 | 64.1078 / 49.0294 | 64.1716 / 48.4804 |
| MU_BETA_SHARED / tail-recall | 60.1520 / 31.8529 | 63.6667 / 45.3922 | 63.8775 / 45.5686 |
| CSP + shrinkage LDA / fixed | 60.1324 / 33.9902 | 64.0196 / 45.2157 | 65.3775 / 47.8137 |

The full source-only epoch inventory is displayed in Fig 5.

The supplementary algebraic decomposition gave a mean absolute class-recall gap of 62.0098 points for S9/BROAD and 31.3824 points for S60/BROAD, a descriptive reduction of 30.6275 points. This follows directly from twice the difference between the corresponding balanced accuracy and weaker-class recall. It summarizes a change in the two-class operating profile, without attributing that change to a physiological mechanism.

### Independent numerical review and result traceability

The external saved-prediction audit passed 1,179 checks with zero failures, reproducing participant metrics, paired effects, confidence intervals, p values and Holm adjustment. It checked participant/trial/label identities against saved input audits and verified identical predictions for checkpoint aliases. A separate integrity/source-selection audit checked nine off-Pod checkpoint archives, payload hashes, 108 trajectory contracts, 23,520 validation rows, 1,680 aggregate scores and all 48 selection choices. The largest discrepancy in reconstructed aggregate scores was 7.1054×10⁻¹⁵.

These checks establish consistency across the archived evidence layers. Their scope is recorded explicitly: they reconstruct saved-result arithmetic and provenance, rather than reprocess raw EEG, replay checkpoint inference, inspect optimizer internals or establish signal-level duplicate absence. Complete small-table source data for every figure and table accompany this manuscript.

## Discussion

### Source expansion as a practical design lever

The central finding is a 21.17-point increase in mean weaker-class recall for the specified expanded-source broadband configuration, accompanied by a 5.85-point balanced-accuracy increase. The positive paired change in 72 of 85 participants gives the aggregate result a directly inspectable individual distribution. Source diversity and available observations are therefore useful design variables to evaluate alongside architecture and checkpoint-selection objectives. Here, a substantial improvement was obtained with an established compact decoder and a fixed full-trajectory update budget.

This result complements representation-learning work [3–5]. A method designed to suppress domain-specific information still depends on the examples from which transferable structure is learned. Our experiment provides a source-population comparison with a class-coverage endpoint and explicit selection accounting. It supplies evidence about a practical training configuration rather than an algorithmic ranking across published domain-generalization methods.

### Why two-class coverage adds information

The decomposition B=W+|rL−rR|/2 clarifies the difference between average discrimination and recognition of the weaker class. Moderate balanced accuracy can coexist with a large recall gap. In the primary comparison, the improvement in W was accompanied by a smaller mean absolute recall gap. This makes the practical nature of the observed change more specific: predictions covered the less-recognized command more effectively across the evaluated participants. The decomposition is a transparent interpretation of existing confusion outcomes, not a newly optimized metric or an additional confirmatory endpoint.

The conventional comparator further illustrates why multiple summaries matter. Its S60 balanced accuracy was descriptively higher than that of the primary neural configuration, while weaker-class recall was slightly lower. Reporting both avoids building the contribution around an architecture ranking that the study was not designed to test. Participant distributions, class recalls and fixed comparisons are more informative here than a single best table entry.

### Selection decisions and the evidence chain

The source-selected epochs differed substantially across configurations. As a result, source expansion and source-only checkpoint selection form the evaluated configuration together. The S60−S29 and tail-recall−mean-BA intervals also constrain a useful practical conclusion: the demonstrated gain does not require claiming a monotonic source-count law or a generally superior selector. Source diversity, dataset weighting and selection design are empirical decisions whose effects should be retained even when a proposed rule adds no measurable benefit.

The reproducibility contribution is the linkage among native-file identities, eligibility decisions, input contracts, source curves, checkpoint choices and saved external predictions. The 1,179 external checks and the separate source-selection audit cover distinct parts of that chain. Releasing their inputs and scope makes the statistical claims inspectable without confusing file-integrity evidence with an independent biological replication.

### Scope and future evaluation

The study has one fixed intermediate subset, one external acquisition programme, three final seeds and two pipelines from one backbone family. Expansion jointly changed cohort composition, distinct-trial availability, sampling frequency and selected duration; the result is a complete-configuration contrast rather than an isolated causal effect of participant count. Prior Dreyer exposure remains uncertain, and participant confidence intervals condition on the fitted models rather than fully representing source-population, subset and training uncertainty. Yang timing and absolute-voltage interpretation remain unresolved beyond the recorded analysis conventions and shared-scale invariance; the task windows do not establish an artifact-free physiological mechanism. Independent cohort replication, prospective source-subset variation and online evaluation would extend the present offline findings. Historical 19-channel and physiological analyses remain separately archived and are not pooled with this 18-channel experiment.

## Conclusions

Source-cohort expansion from nine to 60 participants, combined with source-only checkpoint selection, improved weaker-class recall and balanced accuracy in an 85-person exploratory external evaluation. Participant-level reporting and the class-recall decomposition show how the configuration improved two-command coverage. The complete comparison set identifies both the supported source-expansion gain and the absence of demonstrated additional benefit for the larger intermediate-to-full pool contrast or the tail-recall selector. A common processing contract and an auditable selection-to-prediction chain make these findings reproducible and useful for designing subsequent cross-subject EEG studies.

## Data and code availability

The immutable results and evidence are available at https://github.com/jackzhu119/cross-subject-mi-eeg/tree/040956085499ed788948de0d5a09cddd9eabca56/research_runs/ELIGIBLE_V3_RESULTS_20261018. This directory contains the executed configuration, source registry, selected-epoch freeze, original compressed prediction/result tables, audit code and independent audit outputs. The executed source snapshot is bound to commit 0539379578818b3d71f995192e5e8a81cf4d5aef in the archived provenance. S1 Data supplies compact figure/table source values, condition summaries, participant contrasts and selected epochs. Third-party raw EEG is obtained from the original providers [12–17] under their applicable terms and is not redistributed in this manuscript package. The reproducibility README identifies the public numerical evidence, code and separately indexed neural checkpoint archives.

## Funding

The author received no specific funding for this work.

## Competing interests

The author declares no competing interests.

## Author contributions

Ziyuan Zhu: Conceptualization, Methodology, Software, Validation, Formal analysis, Investigation, Data curation, Visualization, Writing – original draft, Writing – review & editing, Project administration. These roles describe the author's secondary analysis and manuscript work; original EEG collection was performed by the dataset providers.

## AI-assisted work

OpenAI ChatGPT and Codex tools assisted literature retrieval, manuscript drafting and language revision, analysis-code development, figure and document preparation, and organization of repository updates. The author reports checking and revising the scientific content and accepts responsibility for the manuscript. For this revision, numerical claims and figure values were checked against the frozen result tables and independent audit records. AI-generated prose or code was not treated as independent scientific evidence. Exact historical model-version information is not consistently recoverable from the retained records.

## Supporting information

S1 Appendix. Detailed preprocessing, selection definitions, execution and audit inventory, historical-study separation, and reproducibility boundaries.

S1 Data. Machine-readable frozen comparisons, condition summaries, participant changes, epoch selections and the complete numerical sources for the figures and tables.

## Figure captions

## Fig 1. Frozen source-expansion design and evidence flow.

**A**, Nested source configurations comprise nine BNCI2014-001 participants (S9), the same participants plus a fixed set of 20 Yang participants (S29), or all 51 eligible Yang participants (S60). Eligible source-trial counts are 2,592, 14,590 and 33,183, respectively. **B**, The processing recipe uses 18 common channels, common-average reference, 160-Hz sampling and 2-s crops. Each temporally centered spectral view is divided by the same trial's broadband root-mean-square amplitude. **C**, Five whole-participant validation folds and three validation seeds yield 90 trajectories; eight source-only checkpoint-selection rules yield 48 source-level/pipeline/rule choices. **D**, Three final seeds yield 18 final trajectories, each completed for 40 epochs with 128 updates per epoch. Selected evaluation checkpoints vary in duration: 144 condition-by-seed outputs reuse 99 distinct checkpoints. **E**, Exploratory external scoring uses 85 Dreyer participants and 6,800 unique trials. Event/class metadata support eligibility and class mapping; ground-truth labels support scoring rather than target fitting or model selection under the archived protocol. **F**, Integrity, selector-binding and saved-prediction arithmetic audits provide complementary evidence. The 1,179 external arithmetic checks do not constitute raw-EEG reconstruction or checkpoint-forward replay. This schematic reports the archived design and audit scope rather than a new experiment. Source data: `figure_data/Fig1_source_configurations.csv`; protocol and audit hashes: `figure_data/SOURCE_PROVENANCE.json`.

## Fig 2. All four frozen participant-paired external contrasts.

The filled circle denotes the primary BROAD/tail-weaker-class-recall contrast, S60 minus S9 in weaker-class recall. Open squares denote the three secondary contrasts: tail-weaker-class-recall versus mean-balanced-accuracy selection at S60, S60 minus S29 in weaker-class recall, and S60 minus S9 in balanced accuracy. Each point is the mean of 85 participant-paired differences, after averaging metrics across the three final seeds within each participant. Horizontal bars are two-sided, pointwise 95% *t* confidence intervals; they are not adjusted for simultaneous coverage. The primary *p* value is unadjusted; secondary *p* values are adjusted together by Holm's procedure. All four frozen comparisons are displayed, including the two estimates with intervals spanning zero. Intervals quantify participant uncertainty conditional on the fitted trajectories and seed-averaging scheme. Source data, including full-precision estimates, intervals, raw *p* values and Holm-adjusted *p* values: `figure_data/neural_recomputed_comparisons.csv`.

## Fig 3. Participant-level distribution of the primary weaker-class-recall change.

Bars show the S60 minus S9 difference in weaker-class recall for every Dreyer participant under BROAD with source-only tail-weaker-class-recall selection. Participants are ordered by the paired difference for display; the original provider-derived identifier and plot order remain available in the source CSV. All 85 observations are retained: 72 improve, 10 decline and three are unchanged. Squares on the zero line mark the unchanged observations. The dashed horizontal line is the frozen paired mean, +21.17 percentage points. Seed-wise weaker-class recall is calculated before averaging the three seeds within each participant. These counts and the ordered display describe heterogeneity and do not add a subgroup hypothesis test. Source data: `figure_data/Fig3_primary_participant_changes.csv`.

## Fig 4. External class coverage and balanced accuracy across source configurations.

**A**, Balanced accuracy; **B**, weaker-class recall; **C**, mean absolute left–right recall gap. BROAD and shared μ/β use the frozen source-only tail-weaker-class-recall selection rule; CSP with shrinkage LDA uses its fixed conventional-model configuration. Points in A and B are participant means with the stored pointwise 95% *t* intervals (*n* = 85). Panel C is a post hoc descriptive algebraic decomposition of those same means: the absolute recall gap equals twice balanced accuracy minus twice weaker-class recall when computed within each seed, and the identity is preserved by seed and participant averaging. No additional confidence interval or hypothesis test is introduced for C. For BROAD, the mean gap is 62.01 percentage points at S9 and 31.38 at S60. All three pipelines are retained; the figure does not add neural-versus-CSP inference. Source count, trial availability, cohort composition, sampling frequencies and selected checkpoint can vary together across configurations. Connecting lines guide the eye and do not imply a scaling law. Source data: `figure_data/Fig4_descriptive_endpoints.csv` and `figure_data/Fig4_posthoc_absolute_recall_gap.csv`.

## Fig 5. All 48 frozen source-only checkpoint selections.

Numbers give the selected epoch for each combination of eight rules, three source configurations and two neural pipelines. The color scale encodes epoch number rather than external performance. Selection uses held-out source participants only; the same selected epoch is applied to the three final seeds for each condition. Each complete neural trajectory ran 40 epochs × 128 updates = 5,120 optimizer updates, whereas the duration represented by the selected evaluation checkpoint varies. The outlined BROAD/tail-weaker-class-recall cells select epochs 27, 5 and 5 at S9, S29 and S60, respectively. Thus, equal complete-trajectory budgets do not isolate an equal-duration source-count effect. All choices, including early and late selections, are retained. Source data: `figure_data/Fig5_selected_epochs.csv`; these values also match the frozen `selection_freeze.json`.

## Figure-preparation assistance

ChatGPT assisted development of the plotting code and revision of figure labels and captions. The figures were rendered deterministically from the archived, audited numerical tables, with the algebraic descriptive decomposition in Fig 4C explicitly identified. AI was not used to generate EEG measurements, participant observations or inferential results. The author remains responsible for checking and approving the figures and their captions.

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
