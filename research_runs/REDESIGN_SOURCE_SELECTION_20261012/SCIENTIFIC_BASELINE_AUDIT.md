# Scientific baseline audit for the source-only selection redesign

Audit date: 12 October 2026. Historical source revision: `39ab4fe0492f4d2ab4c679c752634d3f74bb7bc8`. This is a new, retrospective evidence audit, not a new EEG training experiment, an independent target evaluation, or an alteration of Q1–Q16.

## Executive assessment

The retained artifacts support a focused methodological question: whether source-only duration selection is reliable across heterogeneous people and acquisition cohorts. They do **not** yet establish an independently replicated improvement from mean-rank selection, a general benefit of fixed 20-epoch training, or a causal effect of parameter sharing. The strongest historical observations are concentrated internal recovery, sensitivity of the source-validation schedules, inconsistent complete-pipeline transfer, and class-asymmetric CSP output. An appropriately frozen new experiment can test those observations; re-evaluating the four already inspected datasets cannot turn them into previously unseen confirmation.

The user reports a JNE editorial rejection without external review and a PLOS ONE duplicate-submission-policy rejection. These are different decisions, not two independent negative scientific reviews. No journal system or decision letter was authenticated by this audit. A subsequent submission must be exclusive; resubmission to PLOS ONE would require checking its treatment of the previous policy decision.

## What was actually checked

The executable audit is `scripts/historical_reaggregate.py`. It writes only within this redesign directory and does not read raw EEG, deserialize models, call a training library, generate new model predictions, access R2, or contact a journal.

The tracked-file inventory covers historical Q1–Q16 directories, early P1–P4/Q4 output directories, configurations, documentation, the final scientific paper sources, the original PLOS submission directory, and the prior revision's evidence. There are no separate experiment directories named Q1, Q2, or Q3: the earliest stages are recorded as P1, P2, and P3. These names are mapped here rather than inventing missing Q-prefixed runs.

* **17,091 files** were read for byte hashes and file inventory.
* **4,515 JSON files** were fully parsed for structure, recorded keys, statuses and receipt fields.
* **9,620 CSV/CSV.GZ files** were fully parsed. Every recognized prediction table was checked for missing labels/predictions, duplicate identities at its recorded evaluation grain, probability finiteness/range/sum and probability-to-label consistency when probability columns were present.
* **336 text files** were fully decoded. This is not a claim that every historical line of prose was independently reviewed for scientific meaning.
* Seven main frozen prediction files were independently reaggregated from trial-level decisions into participant/seed balanced accuracy, then participant means. All nine source-selected mean-loss and mean-rank schedules were reconstructed from the **1,440** stored source-validation rows (nine outer folds × four inner folds × 40 epochs).
* Both Q15 participant-bootstrap intervals, Monte Carlo sign-flip p-values and the frozen two-cohort Holm correction were independently reconstructed. The source validation binds **52** matching artifact hashes; the final external validation binds **221** matching artifact hashes.
* All **228,096** stored Q16 power rows were checked for log-ratio arithmetic. All six stored participant-level rank correlations were reconstructed without p-values. This is a saved-power check, not a new raw spectral calculation or a claim of fresh laboratory replication.

The exact paths, hashes, sizes, parsing scope and errors are recorded in `evidence/historical_read_scope_ledger.json`. There were zero parse errors and zero flagged recognized prediction-table identity/probability checks after respecting `mode`, `fold_id` and `training_policy`. Repeated trial rows across calibration modes, source policies, models and seeds are legitimate repeated measurements, not new people.

The critical semantic review included the original submitted main narrative, its methods/results/discussion, relevant detailed supplementary methods, the Q6/Q7 reports, all Q8 selection/influence/rule reports, Q9–Q14 protocols, Q15 contracts/freeze/validation records, the Q16 protocol and original independent validation, both author-supplied review reports, and the prior claim-by-claim CSP review. The itemized semantic-review scope is in `evidence/baseline_audit.json`. Full parsing is explicitly distinguished from detailed scientific interpretation; this audit does not promise that every archived implementation error has been excluded.

## Historical stages and their scientific role

| Historical stage | Actual evidence and scope | Appropriate role in the redesign |
| --- | --- | --- |
| Early data inspection (P1; Q1-stage background) | Recorded BNCI subject-1 structures, channels, events, acquisition and artifact handling | Data provenance/QC; not algorithm efficacy |
| Early binary baselines (P2; Q2-stage background) | Nine-person expert-clean LOSO plus within-person/cross-session calibration modes; all-trial sensitivity is separate | Supplementary historical comparator context; calibration modes must not be pooled with zero-calibration |
| Spectral/feature checks (P3; Q3-stage background) | CSP, PSD and fusion; expert-clean/all-trial populations and training policies retained | Exploratory historical context; not independent spectral efficacy confirmation |
| EOG regression (P4) | Source-fitted coefficients applied using synchronous target EOG; successful retry and failure retained | Supplement; extra sensors, no claim of selective neural-information preservation |
| Four-class traditional controls (Q4) | All 5,184 trials; CSP/FBCSP-inspired models and source MI feature-count checks | Historical conventional controls, with dimensionality/classifier differences explicit |
| Mean-loss EEGNet (Q5) | Nine held-out people, 36 source-validation fits, three final seeds/person; extremely short schedules for S2/S3/S8 | Main methodological development anchor |
| Source normalization (Q6) | Source-only scalers; duration changes for S3/S5; heterogeneous outcomes | Diagnostic support; not a population causal normalization comparison |
| S3 four-cell check (Q7) | Raw/normalized × two/16 epochs, two reused and two newly recorded cells | One-person computational diagnostic; not a physiological or population mechanism |
| Selection audit and rank follow-up (Q8) | Historical loss curves, fold influence/rule sensitivity, 27 final rank-selected fits | Main historical hypothesis-generating evidence; not independent algorithm confirmation |
| Spectral input controls (Q9) | Band restrictions/shared inputs, representation-specific selection and copied source schedules, source-clean/source-normalized controls | Secondary pipeline controls; duration control does not isolate sharing or compute |
| Spatial/geometry controls (Q10) | Source CSP/PCA projections and log-Euclidean shallow geometry | Supplement, unless a precise new hypothesis needs these controls |
| Capacity/fusion controls (Q11) | Early stacking, independent branches, four bands, approximate capacity matching | Supplement; no architecture winner selected for confirmation from old target scores |
| Robustness controls (Q12) | Whitening, balanced ERM, GroupDRO, channel/gain perturbations; no corrected established gain | Preserve null/adverse evidence; match runtimes when attributing effects |
| Duration/source composition (Q13) | Fixed 20 epochs, source-count/subset/session designs, separate matched-runtime historical CE schedule replay | Main reliability context; trials/updates and identity must remain distinguished |
| Earlier binary external evaluation (Q14) | PhysioNet, 22-channel/3-s separate source freeze, rate and portability amendments | Historical external complete-pipeline evidence, not new blind validation |
| Later frozen external evaluation (Q15) | Cho2017/Lee2019, 21-channel/2-s CAR/context adapter, 15 original source fits and zero target fits; raw-to-prediction validation | Main historical transfer limits and output-failure diagnostics |
| Sensor physiology (Q16) | Native BNCI power, nine people, post-decoder-outcome design, no physiological p-values | Mostly supplement; descriptive context outside the core selection hypothesis |

An orchestration success receipt is not a scientific replay. For example, `results/Q9-BATCH/validation_report.json` explicitly reports `passed_orchestration_only`; later numerical reviews and experiment-specific artifacts must supply the scientific evidence rather than upgrading that receipt. Failed starts and earlier pending receipts are retained and are not confused with the final validated output.

## Independently reconstructed historical results

### Source-selection recovery and concentration

From original trial-level predictions, equal-participant mean balanced accuracy is **33.7191358%** for historical mean loss and **42.6697531%** for the rank follow-up. Their mean difference is **+8.9506173 percentage points**, median **+1.8518519 pp**, with seven improved people and two unchanged. S3 and S8 account for **87.5718391%** of the summed signed gain. Replaying the original 20,000 participant-bootstrap draws (seed 20260923) gives **[+1.0480967,+19.9588477] pp**.

The records confirm that the ranks were selected using source curves before the corresponding new final evaluations. The candidate rule nevertheless arose after earlier outcomes on the same nine people. Source-only fitting within each split is not protection against outcome-informed method development across the research programme. Repeated fits, epochs, trials and sessions do not expand the sample beyond nine people; outer source sets overlap.

The historical report's nine-person binomial sensitivity retains two ties and gives p = 0.179688. The conventional tie-excluding sign test uses seven nonzero effects and gives p = 0.015625. The submitted manuscript already distinguishes these conventions. This audit preserves both historical interpretations rather than editing a frozen p-value or selecting whichever test is favourable.

### Fixed duration: mean gain is not a typical-person or universal benefit

Broad fixed 20-epoch training gives **43.9879115%** balanced accuracy. The separate same-runtime replay of the historical mean-loss schedule gives **33.9248971%**. The paired mean is **+10.0630144 pp**, but the median is **−0.1736111 pp**: four people improve and five worsen. Its 10,000-draw interval (seed 20260926) is **[+0.6751543,+21.5284208] pp**; exhaustive nine-person sign-flip sensitivity gives **p = 0.125**. The large mean is not evidence that a typical new person benefits.

The recorded Python, platform, package versions, CUDA runtime and GPU name match between these two later conditions. Their raw-data and final-seed policies match; the older mean-loss epoch counts were replayed, not reselected under the newer runtime. A newly reselected mean-loss/mean-rank/fixed-duration comparison is still required to isolate the operational selection strategy under one execution contract.

A new retrospective reaggregation of fixed 20 minus the historical rank predictions gives mean **+1.3181584 pp**, median **−0.4629630 pp**, three improved and six worsened people. This is a **cross-run description**, not a matched-runtime algorithm test, noninferiority or equivalence result. The Q8 configuration declares `device=cpu`, but its archived runner automatically selects CUDA when available; an authenticated Q8 effective runtime manifest was not found. It would be incorrect to assert a verified CPU-versus-GPU contrast solely from the configuration, or to assert matched actual runtimes for fixed 20 versus rank.

### External results must remain distinct

| Historical evaluation | Source/target input and selection | Equal-person shared-minus-broad effect | Frozen uncertainty |
| --- | --- | --- | --- |
| PhysioNet (Q14) | Binary; 22×480 at 160 Hz; cue [0.5,3.5) s; run filtering; no additional Q15 CAR; source durations broad18/shared17 | **+0.5732962 pp**, n=109 | Original 95% CI **[−0.0966827,+1.2415551] pp**; archived exact-zero sign p=0.0644636 |
| Cho2017 (Q15) | Binary; 21×320 at 160 Hz; cue [0.5,2.5) s after fixed native context/CAR; broad14/shared19 | **−1.5133547 pp**, n=52 | CI **[−2.2489583,−0.8044872] pp**; raw Monte Carlo p=0.0000499975, two-cohort Holm p=0.0000999950 |
| Lee2019_MI (Q15) | Same Q15 source/adapters; 54 people, two offline-training sessions pooled/person | **+0.2037037 pp**, n=54 | CI **[−0.5154321,+0.9691358] pp**; raw/Holm p=0.6036698 |

The latest Q15 values and frozen procedures replay without changing any scientific file. PhysioNet superiority remains unestablished; Cho is an adverse complete-pipeline result; Lee is uncertain and does not establish equivalence. There is no valid pooled 215-person primary test or three-dataset meta-analysis pretending these are repeated measurements of an identical experiment. Four-class internal balanced accuracy and binary external balanced accuracy have different label spaces/chance levels and must remain separate.

**Numerical sensitivity identified in the historical PhysioNet sign count.** The original saved S010 difference is −1.1102230246251563×10^−16. The archived exact-zero rule counts that as negative, giving 63 positive/43 negative/3 ties and p=0.0644636. Reaggregation of the discrete class-recall counts with a 10^−12 numerical tie tolerance gives 63/42/4 and exploratory p=0.0504422. The effect and interval are unchanged, and neither test establishes superiority at 0.05. The frozen primary p-value remains untouched; the new protocol should define numerical tie handling before results, preferably using exact count-based scores for sign determination. This is a reproducibility sensitivity, not a retrospective opportunity to change the primary test.

### Matched durations and algorithm validation are not already available externally

Q14 and Q15 external evaluations compare source-selected **complete pipelines**. Broad/shared differ in duration, band views, shared BatchNorm exposure, preprocessing and computation. Q15 has no authenticated final all-nine-source broad/shared pair at the same fixed duration. An inference-only rerun cannot create a missing matched-duration model: additional **source training** is required, although target fitting must remain zero. Internal copied-schedule controls do not solve the external all-source matched-duration question.

Q14/Q15 both select external source durations from `[S1,S2]`, `[S3,S4]`, `[S5,S6]`, `[S7,S8,S9]`, with 2/2/2/3 people and equal fold weighting. This was a frozen design, not a computation error. Its grouping/weighting sensitivity was not prospectively tested; it is a well-defined reliability question for the redesign.

## Q15 fitting, chronology, validation and CSP evidence

The final Q15 source validator records eight neural inner fits, six final neural fits and one shallow fit: **14 deep + 1 shallow = 15 original source fits**. It records `source_only=true`, target fits zero, and selected epochs broad14/shared19. All 52 bound source artifacts and all 221 bound final external artifacts match their saved SHA-256 digests in this checkout. Migration used existing models and has zero new source fits; original 15 source fits are not zero. The external inference freeze and final validation are separate from launcher/startup messages.

The older `completion_receipt.json` says inference complete pending independent replay and `scientific_validation_passed=false`. The later `validation_report.json` says `scientific_validation_passed=true`, independently reconstructed statistics, unchanged model state and raw-to-epoch/frozen-checkpoint replay. An earlier pending receipt is not the final scientific status. That final status is **completed with calibration limitations**: native export voltage calibration, original Cho reference and hardware cue latency were not independently established. The read-only audit here verifies the stored chain and predictions, not a new raw replay.

The newly supplied CSP report has been read in full. It documents claims rather than supplying all new execution artifacts. Verified archived CSP endpoints are **51.9903846%** participant-mean BA on Cho and **52.7685185%** on Lee. Left-prediction share is **92.0722433%** and **83.2129630%** when trials are pooled. Cho's equally weighted person-mean left share is different: **92.1121795%**. The median stored p(left) values are **0.669354233** and **0.632938737**. For the explicit interval [0.45,0.55], **10.1996198%** and **16.6944444%** of trials lie within it. These are descriptive probability summaries, not calibrated confidence.

The report's **63.04%** source resubstitution, **61.65%** new nine-fold same-Q15 source LOSO, and **52.39%/54.18%** target-centering results still lack their authentic prediction tables, partition/transform manifests, execution code hashes and runtime records. They therefore are not verified scientific outcomes in the redesign. Resubstitution is not held-out performance; a new nine-fold source LOSO entails **nine additional source fits**; unlabeled target-derived centering is **target adaptation**, even if no target labels are fitted. Historical Q14/P3/P2 CSP values cannot substitute for these missing records because their pipelines/populations differ.

For frozen binary outputs, swapping both predicted class labels algebraically gives `1−BA`. Cho's primary person-mean complement is **48.0096154%** (48.01% rounded), whereas the trial-pooled complement is **48.0228137%** (48.02%). Lee's complement is **47.2314815%** (47.23%), not the untraceable 47.22% in the supplied report. No labels were swapped in the primary files and no alternate decoder was fitted or selected.

Declared mappings and the recorded raw-to-prediction replay provide consistency checks, not proof that every implementation error is absent. Above-chance neural scores cannot establish that every mapping/reference/timing assumption is correct; neither weak post-centering scores nor CSP asymmetry isolates a unique cross-device mechanism. The supported conclusion is class-asymmetric near-chance transfer of this particular frozen CSP pipeline, with domain shift as one plausible explanation requiring direct feature/covariance evidence.

## Q16: preserve the record, reduce its role in the main hypothesis

The Q16 descriptor and score calculations reproduce from saved tables. All 228,096 stored log-ratio rows agree with `10 log10(Ptask/Pbaseline)` within **5.33×10^−15 dB**; this tolerance-level arithmetic agreement is not a fresh raw Welch validation. Mean signed laterality remains **−0.2496850334 dB** for mu and **−0.1678745394 dB** for beta. All six nine-person Spearman coefficients match, including broad beta rho=0.6, with **no p-values**.

The original separate raw central-sensor spectral validator remains the evidence for raw Welch replay. The physiology design followed decoder outcomes, uses nine BNCI people, and has unequal baseline/task Welch segment counts. It differs from the decoder's three-second crop and has no external physiological replication, decoder feedback, neural mechanism attribution, biomarker confirmation or cortical localization. Most detail belongs in Supporting Information; retaining a short contextual statement is optional if it helps the core reliability question. No additional physiological model training is warranted by the current hypothesis.

## Evidence gaps and actionable follow-up

| Gap | Consequence | Appropriate next action |
| --- | --- | --- |
| No new independent selection-rule evaluation | Historical rank gain is not independently confirmed | Freeze architecture × selection rules and evaluate a newly audited task-matched cohort |
| No matched-duration final Q15 source models | The adverse Cho effect cannot be attributed to sharing alone | New source-only matched-budget training under a frozen protocol; target outcomes on old cohorts remain retrospective |
| Missing new CSP source/centering run artifacts | New diagnostic report numbers cannot be promoted to verified results | Recover existing predictions/partitions/code; otherwise run a separately recorded diagnostic if authorized, never overwrite old results |
| Unauthenticated Q8 effective runtime record | Cross-run fixed20-versus-rank cannot be certified as matched runtime | One new execution environment for all prospectively compared rules |
| Cross-provider identities not independently linked | Separate datasets are not proof of nonoverlapping people | Check provider recruitment/source lineage and duplicate recordings before new independent-cohort claims |
| Source grouping sensitivity not independently tested | Equal-fold 2/2/2/3 design may affect schedules | Freeze source grouping repetitions/aggregation before inference; treat old-curve sensitivity as retrospective |
| Physical export/reference/cue uncertainties | Tensor matching does not authenticate acquisition equivalence | Source documentation and metadata/QC audit with explicit unresolved assumptions |
| Legacy paper inventory contains stale paths | Some old wrapper references are not directly navigable | New SI/reproducibility pointers should link the retained `outputs/`, `results/` and final evidence explicitly |

The stale `research_runs/PAPER_DRAFT_20261002/...` references in `completed_experiment_inventory.csv` are absent from this checkout; the stated snapshot `ac75a339...` also does not expose the tested paths. This is a wrapper provenance/navigation gap, not proof that the numerical outputs are missing: the original experiment directories, participant predictions and final numerical tables remain readable. This audit records the gap without editing the historical inventory or reconstructing a false contemporaneous receipt.

## Decision boundary for the next phase

Historical numerical observations are sufficiently traceable to justify hypotheses and a strictly specified new study. The unresolved claims above do not justify manufacturing a stronger story. Retrospective saved-output analysis can quantify concentration, collapse, and source-curve sensitivity now; causal disentangling and independent selection-rule confirmation require additional source training and genuinely new task-matched data. No result currently warrants clinical, online, universal zero-calibration, SOTA, physiological-mechanism, or broad equivalence claims.

The new study must retain failed and unfavourable cells, prespecify participants as its inference units, bind source partitions and model selection before target outcomes, and distinguish a historical extension from independent confirmation. Scientific readiness for the redesigned final manuscript remains pending the new data/code/training/result gates rather than established by this successful historical artifact audit.

## Reproduction

From the repository root:

```bash
python research_runs/REDESIGN_SOURCE_SELECTION_20261012/scripts/historical_reaggregate.py --inventory
```

Inputs and output schemas are recorded in the script and JSON ledger. The new results are `results/historical_internal_paired.csv`, `results/historical_participant_seed_cells.csv`, `results/historical_participant_metrics.csv`, `results/historical_source_schedule_replay.csv`, and `results/historical_q16_association_replay.csv`. `evidence/historical_reaggregation.json` contains numerical checks and frozen-resampling replays. This command needs NumPy, Pandas and SciPy only and does not invoke any model fit or inference.
