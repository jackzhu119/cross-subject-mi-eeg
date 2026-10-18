# Methods and Results revision: exploratory source expansion

This is a standalone revision section for the completed `paper1_source_expansion_18ch_dimensionless_eligible_v3_20261018` run, not a complete submission manuscript. It does not replace historical manuscripts. Numerical statements follow the frozen configuration and the independently audited saved predictions. “Prespecified” below refers to the archived protocol; the audits do not establish external preregistration or first use of the evaluation cohort.

## Methods

### Source cohorts, eligibility, and external evaluation

Three source conditions included nine BNCI2014-001 participants (S9), those nine participants plus a fixed subset of 20 Yang participants (S29), and those nine plus all 51 Yang participants (S60). Eligible trial counts were 2,592, 14,590, and 33,183, respectively. The source registry used seed 20261017. These conditions changed both source cohort composition and available participant/trial counts.

An explicitly approved eligibility amendment retained all 51 Yang participants while including only events with explicit native labels 1 or 2. Unknown code-255 events and missing-label counts were retained as audit evidence; labels and missing onset times were not inferred. Five sessions contained fewer than the planned 100 observations per class. Native marker-9 delimiter positions were retained for operational segmentation instead of repartitioning the surviving events into groups of 40; the delimiters were not taken as independently established physiological annotations. A fixed registry bound all 153 session pairs to their original file identities. The clock handling did not shift event times. Compatible previously prepared arrays retained their original embedded provenance, with compatibility documented separately.

The external dataset comprised 85 Dreyer participants (provider identifiers 1–87, excluding 17 and 41). Each contributed 80 trials, balanced between left- and right-hand labels, across two acquisition runs. Prior exposure to Dreyer was uncertain; this analysis is therefore exploratory external evaluation, not first-use independent confirmation.

### Signal processing and fitted models

The frozen processing used 18 common channels, common-average referencing, filtering, resampling to 160 Hz, and 320-sample analysis crops. Broadband, mu, and beta views covered 8–30, 8–13, and 13–30 Hz. Within each trial, each channel/view was temporally centered; all views were divided by that trial's broadband RMS across channels and samples. The resulting features were dimensionless, without normalization statistics pooled across trials or people.

For Yang, the crop remained marker-relative [2,4) s within a [0,6) s context. The computational 1.5-s anchor was an analysis convention, not a verified physiological onset. Conflicting timing interpretations and the native `?V` header limit claims about exact motor-imagery phase alignment and physical amplitudes. The fixed normalization cancels a common positive amplitude multiplier; it does not resolve those physiological uncertainties.

The BROAD and MU_BETA_SHARED pipelines used the frozen EEGNet backbone family (Braindecode 1.5.1; F1=8, D=2, F2=16, kernel length 64, dropout 0.25). Each trajectory used 40 epochs with 128 updates per epoch (5,120 updates), batch size 64, and Adam with learning rate 0.001, zero weight decay, and no scheduler. Sampling with replacement selected dataset, participant, class, and trial in succession; when Yang was present, dataset sampling mass was 50:50. The two pipelines are not independent architecture replications.

Five whole-participant source folds and three validation seeds (20261021–20261023) yielded 90 validation trajectories. Three final seeds (20261013–20261015) across three source levels and two pipelines yielded 18 final trajectories. The completed run therefore contained 108 neural trajectories and 4,320 epoch checkpoints. A separately summarized CSP plus shrinkage-LDA baseline comprised nine fits; it was not added to the neural hypothesis-testing family.

### Source-only selection and statistical analysis

The archived protocol specified source-only selection before external prediction, with no target-driven choice of epochs, thresholds, normalization, architecture, or hyperparameters. Source validation metrics were averaged across validation seeds within participant, then aggregated with equal dataset mass and equal participant mass within dataset. Eight frozen rules included fixed epoch 20, mean/tail cross-entropy, mean rank, mean/tail balanced accuracy, and mean/tail weaker-class recall. Tail aggregation used the worst one-third probability mass. Independent source-selection arithmetic reproduced the frozen selector choices; this does not by itself prove every historical target-access event.

Balanced accuracy was the mean of the two class recalls. Weaker-class recall was their minimum, computed separately within each final seed and then averaged across the three seeds for each participant. This was neither an ensemble formed by averaging logits nor a minimum taken after averaging class recalls across seeds. The statistical unit was the external participant (n=85), not the seed, fold, or trial.

The prespecified primary contrast was S60 minus S9 under BROAD and tail_min_recall, evaluated on weaker-class recall. Paired two-sided t tests and 95% t confidence intervals used 84 degrees of freedom. Paired participant percentile bootstrap intervals used 10,000 resamples with seed 20261016. Three prespecified secondary tests formed one Holm family: tail_min_recall versus mean_ba within S60 on weaker-class recall; S60 versus S29 on that endpoint; and S60 versus S9 on balanced accuracy. Confidence intervals remained pointwise and unadjusted for multiplicity.

## Results

The run recorded completion at 2026-10-18 04:26:19.986827 UTC, with 108 neural trajectories and nine conventional fits. There were 979,200 neural prediction rows and a further 61,200 CSP prediction rows. The 144 neural condition-by-seed outputs reused 99 distinct selected level/pipeline/seed/epoch checkpoints from 18 final trajectories. Alias predictions were identical; these outputs are not 144 independent training replicates.

For the primary comparison, mean weaker-class recall increased from 27.3137% in S9 to 48.4804% in S60: a paired difference of **21.1667 percentage points** (95% t CI, **17.1226 to 25.2107**; t(84)=10.4084; two-sided p=8.8841×10⁻¹⁷). The paired bootstrap interval was 17.1468 to 24.9512 percentage points. Descriptively, 72 participants improved, 10 declined, and three were unchanged; this count was not an additional prespecified test.

Important null findings accompanied the primary contrast. S60 did not show evidence of improvement over S29 on weaker-class recall, and tail_min_recall did not show evidence of improvement over mean_ba within S60. These are not equivalence findings.

| Frozen secondary contrast | Difference, percentage points | Unadjusted p | Holm p |
|---|---:|---:|---:|
| S60 tail_min_recall minus mean_ba; weaker-class recall | −0.8725 | 0.509760 | 0.999859 |
| S60 minus S29, BROAD/tail_min_recall; weaker-class recall | −0.5490 | 0.499929 | 0.999859 |
| S60 minus S9, BROAD/tail_min_recall; balanced accuracy | +5.8529 | 1.7805×10⁻⁹ | 5.3414×10⁻⁹ |

Descriptive mean balanced accuracies were:

| Pipeline/selection | S9 | S29 | S60 |
|---|---:|---:|---:|
| BROAD / tail_min_recall | 58.3186% | 64.1078% | 64.1716% |
| MU_BETA_SHARED / tail_min_recall | 60.1520% | 63.6667% | 63.8775% |
| CSP + shrinkage LDA / fixed | 60.1324% | 64.0196% | 65.3775% |

No new neural-versus-CSP hypothesis test was introduced. Other frozen selection rules remain in the audit tables and were not promoted to the primary method based on external performance.

### Interpretation and audit scope

The primary contrast supports improved weaker-class recall for the specified S60 configuration relative to S9 in this exploratory cohort. It does not isolate a causal effect of participant count: source composition, distinct trial availability, and sampling distribution changed together. The null S60–S29 result precludes a claim that more source data was consistently better, and the selector comparison does not establish superiority of the proposed selection rule. A single fixed intermediate subset does not characterize subset variability. These results do not establish universal effectiveness or causal superiority of an algorithmic innovation.

The intervals describe variation among these 85 participants conditional on the fitted trajectories and three-seed averages. They do not fully capture training randomness, source-population sampling, intermediate-subset selection, or cross-dataset uncertainty. The 18-channel dimensionless protocol is not numerically interchangeable with historical 19-channel analyses.

The independent external audit passed **1,179 checks with zero failures**, reconstructing saved-prediction metrics, paired differences, confidence intervals, p values, and Holm adjustment. It checked participant/trial/label identities, label-array hashes against saved input audits, and alias equality. A separate integrity/source-selection audit checked all nine off-Pod checkpoint archives and their payload hashes, 108 trajectory contracts, 23,520 source-validation rows, 1,680 aggregates (maximum absolute discrepancy 7.1054×10⁻¹⁵), and 48 frozen selector choices.

These are distinct evidence layers: code and archive integrity, source-selection arithmetic, and saved-prediction arithmetic. Neither audit reprocessed raw EEG or replayed inference from checkpoints; neither establishes signal-level duplicate absence, model optimizer internals, or all historical leakage controls. The importer verified the supplied audit files and their input hashes against the archived results, rather than rerunning these audits or re-reading all nine large checkpoint archives. R2 destination/full-GET verification remains unresolved; the Pod has not been stopped.

## Evidence supporting this revision

- [Frozen executed configuration](indexed/provenance/study.json) and [execution identity](indexed/provenance/execution_identity.json).
- [Independent external audit](audits/external/AUDIT_SUMMARY_zh.md), [machine-readable results](audits/external/audit_results.json), and [recalculation script](audits/external/audit_external.py).
- [Independent integrity/source-selection audit](audits/paper1-independent-integrity-source-selection-audit-20261018.json) and [108-trajectory off-Pod verification](audits/paper1-eligible-v3-all108-offpod-verification.json).
- [Importer verification and content hashes](AUDIT_IMPORT_VERIFICATION.json). The original result ZIP and historical reports remain unchanged.
