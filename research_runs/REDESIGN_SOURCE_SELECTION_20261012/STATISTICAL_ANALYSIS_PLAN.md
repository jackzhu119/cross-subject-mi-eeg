# Prospective statistical analysis plan: source-only selection reliability

Version: 2026-10-13. Status: **pre-outcome neural design; no new neural fits or independent-cohort predictions have been run**. This file fixes the statistical decisions proposed for the new research programme. The primary candidate cohort is Dreyer2023, 87 archived people from one data-collection programme; the current eligibility ceiling is **85**, after A17/A41 technical exclusions for unrecoverable electrode order. Metadata, sham-run eligibility, raw-file and prior-exposure audits remain required. The separately reported ten fresh traditional CSP source fits are retrospective diagnostics and do not supply independent-cohort confirmation. A signed/committed statistics plan alone does not establish independent validation or open the experimental gate.

## 1. Scientific question and interpretation

The principal question is whether a source-only mean-rank training-duration rule changes person-level left/right motor-imagery balanced accuracy relative to a source-only mean-loss rule in one genuinely independent cohort. Historical BNCI, PhysioNet, Cho2017 and Lee2019 outcomes have already been seen and are developmental/retrospective evidence. Repeated analyses, alternative participant splits, or a new seed on those cohorts cannot convert them into independent confirmation.

The design is a 2 architecture × 3 selection-rule grid: Broad EEGNet and the fixed shared-input μ/β pipeline, each with a fixed duration, mean-loss duration and mean-rank duration. The source is the nine-person binary left/right BNCI cohort. The proposed new common processing contract uses the true 19-channel intersection, CAR over those 19 channels, 0.5–2.5 s relative to cue and 160 Hz. The fixed duration is 20 epochs and the source-only selection grid is epochs 1–40. These are new pre-outcome design choices, not claims of universal optimality. Duration rules, tie rule, primary source grouping and random seeds are locked from source information alone. Shared versus Broad at the same duration is a matched-duration **complete-pipeline contrast**: filtering, views, normalization exposure, architecture, capacity and compute can still differ. It does not identify a single spectral-sharing or parameter-sharing causal effect.

## 2. Independent unit and endpoint

The independent inference unit is the participant. For participant i, architecture a, duration rule r and frozen training seed s:

`BA_iars = 0.5 × (TPR_left_iars + TPR_right_iars)`.

All eligible left/right trials from all included sessions are pooled **within participant and class** to calculate each seed's BA. Repeated sessions, files, runs and overlapping EEG windows are not new independent participants. Then:

`Y_iar = 100 × mean_s(BA_iars)`.

The endpoint is seed-averaged single-model performance, not an ensemble prediction. Final all-source seeds are 20261013, 20261014 and 20261015; each receives equal weight and a favourable seed cannot be selected. Source duration selection uses one prespecified trajectory seed, 20261012, for each architecture/fold. Its single-seed limitation is reported rather than hidden by treating the final seeds as extra source folds. Target labels are used only for eligibility/mapping under a locked data contract and final scoring, not for epochs, hyperparameters, seeds, normalization, exclusion thresholds or model selection.

The primary estimand is the equally participant-weighted mean of:

`D_i = Y_i,Broad,mean_rank − Y_i,Broad,mean_loss`.

Effects are reported in percentage points (pp), with positive differences favouring the first-named method. The inference is conditional on the actual frozen source participants and source-trained models. Three training seeds do not justify inference about an unlimited population of source cohorts or training procedures.

## 3. Hypotheses and multiplicity

### Single primary hypothesis

- H1 null: the independent-cohort mean participant-level Broad mean-rank-minus-mean-loss BA difference is zero.
- Alternative: the difference is nonzero, in either direction. A detrimental mean-rank result is a valid outcome; benefit is not assumed.
- Two-sided significance level: 0.05.

### Prespecified secondary confirmation family

Only these three contrasts belong to the secondary confirmation family:

1. Broad fixed-duration minus Broad mean-loss.
2. Broad fixed-duration minus Broad mean-rank.
3. Shared fixed-duration minus Broad fixed-duration, with the same prespecified fixed epoch.

Each has a two-sided zero-difference null. Use Holm correction at family α = 0.05. To control the complete primary-plus-secondary confirmatory sequence, the family opens only if H1 is rejected at α = 0.05. This fixed-sequence gate cannot be bypassed because a secondary contrast looks promising. When the gate is closed, all secondary estimates, unadjusted p-values and intervals remain reported, but no secondary confirmatory rejection is declared. This explicitly separates complete reporting from confirmatory decision-making.

The conditional gate preserves strong family-wise error control: if H1 is true, any confirmatory claim requires its rejection; if H1 is false, Holm controls false secondary rejections. This convention can sacrifice confirmation of a real secondary effect when H1 is null; that is a predeclared cost, not a reason to change the gate after scoring.

Holm-adjusted p-values are accompanied by ordinary 95% estimation intervals labelled **unadjusted**, and conservative 98.333% Bonferroni simultaneous intervals for the three secondary differences. An ordinary 95% interval alone does not establish a multiplicity-controlled secondary claim. The power table includes α = 0.05/3 as a conservative secondary planning boundary; Holm does not have a single common effective α.

### Exploratory quantities

Shared mean-rank versus Shared mean-loss, selected-duration Shared versus Broad, architecture-by-rule difference-in-differences, subgroup/session differences, other cohorts, prediction collapse, tail performance, timing and all grouping sensitivity analyses are secondary descriptive/exploratory unless a future independent amendment designates them before target outcomes are accessed. Do not add new confirmatory test families after observing results.

There is **no noninferiority or equivalence hypothesis**. A nonsignificant difference cannot establish that fixed duration is “not worse”, that models are interchangeable, or that performance is equivalent. Such a future hypothesis would require an independently justified scientific margin, a new pre-outcome design and suitable power; a margin must not be chosen from observed target differences or interval widths.

## 4. Estimation, testing and assumptions

For the primary cohort calculate the complete vector of paired participant differences, its sample mean, sample SD, median, minimum, maximum and all individual values. Primary testing uses the paired t statistic `mean(D) / (sd(D)/sqrt(n))`, df = n−1, with a two-sided p-value and 95% t interval for the mean. Secondary t tests use their own paired participant differences and the correction above.

The paired t model assumes independent participants and is exact for Gaussian differences. For small or skewed cohorts it is not assumption-free. Report the empirical distribution and influence diagnostics without switching the primary test in response to its p-value. A leave-one-participant-out **descriptive** estimate shows concentration but is not a new test or a participant-exclusion rule. If every paired difference is identical, handle the zero-variance case explicitly in the implementation and report the degeneracy rather than returning a misleading finite standard error.

As a sensitivity analysis, calculate a percentile bootstrap interval from 20,000 equally sampled participant indices using analysis RNG seed 20261016. Resample the complete paired seed-averaged difference, not trials, sessions or training seeds. The bootstrap interval is not selected over the t interval according to significance. Its small-sample and discrete-support limitations remain explicit. A sign-flip sensitivity test, if ever added by amendment, would additionally require sign-exchangeability/symmetry; it must not be advertised as universally distribution-free.

Individual participant plots show method scores and paired differences. Trial-pooled accuracy, class recalls, confusion matrices and probability summaries may be reported as descriptive diagnostics with their distinct weighting explicitly identified. They cannot replace the equally weighted primary participant endpoint.

## 5. Cohort separation and cross-dataset generalization

The primary candidate is Dreyer2023, at most 85 currently eligible participants from the same 87-person origin programme, using the two sham-feedback runs specified in the dataset audit, nominally 80 trials per person. A17/A41 are technically ineligible because their electrode order cannot be recovered; this exclusion is determined before performance is examined. Five other provider-flagged participants (A04, A09, A29, B78, B79) are retained for the planned primary cohort pending raw QC rather than automatically removed: the first three flagged FC5/CP5 channels outside the common 19, while the latter two remain subject to the prespecified raw/QC audit. Their actual inclusion cannot be certified without that audit. Administrative subdivisions A/B/C are not three independent replications or three separately sampled target datasets. Raw event semantics, the sham-run identifiers, the participant inventory, task/channel compatibility and lack of earlier performance exposure must pass the data-audit gate before this analysis can be called confirmatory. The final eligible inventory is fixed before predictions are examined. The 87-person power scenario is a sensitivity reference, not the current eligible cohort size.

Additional independent cohorts receive separate participant-level estimates and intervals. Historical external cohorts are separate retrospective extensions. Do not pool four-class internal BA, binary left/right MI BA and right-hand-versus-rest BA. Do not pool incompatible external experiments as repeated trials of one decoder protocol. If participant overlap across repositories cannot be resolved from provenance, retain the uncertainty and do not claim proven identity independence.

With only a few datasets, any random-effects estimate of cross-dataset heterogeneity is unstable and exploratory. Dataset-averaged effects do not automatically describe a population of future EEG datasets. No primary result is promoted or replaced by an apparently stronger effect in a secondary cohort.

## 6. Failure and class-dominance diagnostics

For participant i and seed s, define prediction dominance as:

`q_is = max(number_predicted_left, number_predicted_right) / number_valid_predictions`.

A prespecified participant-level class-dominance flag is `mean_s(q_is) ≥ 0.95`. The threshold is an engineering failure sentinel, not a validated physiological or clinical boundary. Each seed's predicted class and q are retained because different seeds can favour different classes. The primary definition is **mean of seed-wise dominance**, not dominance of an ensemble or pooled across-seed predictions. The definition is frozen without target performance.

Report the equally weighted participant flag proportion and its numerator/denominator per method; all per-seed counts are descriptive nested information. Pairwise differences in flags and below-chance mean BA proportions are exploratory. Collapse is an observed failure outcome and does not justify deleting the participant. Minimum and 10th-percentile participant BA are descriptive, cohort-size-dependent tail summaries, not prevalidated clinical utility metrics.

Differences in source/target feature distributions, CSP probability bias and model class recalls are hypothesis-generating diagnostics. Posthoc demeaning, probability thresholds, target normalization or label swaps must not alter primary target predictions. Any label-dependent diagnostic is clearly identified as post-outcome and cannot be used to rescue the deployed pipeline.

## 7. Missingness, exclusions and unsuccessful runs

Eligibility/QC excludes only conditions locked before model outcomes: incompatible event semantics/channel mapping, duplicate acquisition units, unreadable or nonfinite source data, and other explicit data-contract failures. Participants must have both eligible classes to define BA; counts and reasons are logged before predictions are read. Neither low BA nor predicted-class dominance permits exclusion.

The primary comparison uses the same independently eligible participant set for every condition. A failed model or missing prediction must not silently produce a smaller favourable complete-case sample. Record all attempted runs, technical failures, retries and missing participants. A genuinely unresolved numerical/model-output failure blocks complete experimental validation; it is reported as such rather than imputing a favourable BA or dropping the condition. An infrastructure retry can resume the same precommitted model/seed/configuration; changing hyperparameters or seeds after target scoring requires a documented nonblind amendment and cannot preserve the original confirmatory status.

## 8. Source-validation grouping sensitivity

The historical primary grouping is S1–S2, S3–S4, S5–S6, S7–S9: sizes 2/2/2/3, with equal fold weighting. The new source-only design may retain this explicit primary grouping for continuity. Equal fold weighting is a defined training-duration selection estimand and differs from equal weighting over source participants. It must not be changed after target results are known.

There are exactly 1,260 distinct unordered 2/2/2/3 partitions of nine source people: `9! / ((2!)^3 × 3! × 3!)`. Register the primary grouping and any alternative groupings before training; select alternatives without source or target performance ranking. Grouping sensitivity first examines source-only selected durations and score curves. It cannot be used to choose the most successful target grouping or to redefine the primary source rule. Target performance for alternative groupings, if separately authorized and frozen, is an exploratory extension whose complete outputs must be reported.

One grouping requires 2 architectures × 4 source folds × the single prespecified source-CV seed = 8 source training trajectories when the source candidate epoch grid can be obtained from saved checkpoints of each trajectory. The primary G0 grouping therefore has 8 inner trajectories. Five additional source-only grouping sensitivity variants require 40 further inner trajectories and are an optional budget extension; they are **not executed or implied by this plan**. The registry seed is 20261017 and the primary grouping is included independently of this random draw. Final all-source training is nominally 2 architectures × 3 rules × 3 seeds = 18 condition/seed fits; an identical selected-epoch model within the same architecture/seed can be byte-identically reused with a declared mapping rather than falsely counted as a new fit. Thus the core design has 26 nominal training trajectories/fits, before optional sensitivity. Creating a partition registry is CPU planning; training all 1,260 partitions is not a lightweight diagnostic. The final permitted number belongs in the execution budget and must not be chosen from target outcomes.

## 9. Actual planning calculations

`scripts/power_and_sensitivity.py` computes exact two-sided paired-t planning power under independent Gaussian participant differences. The SD values below are **assumed scenarios**, not new target estimates. α = 0.05, desired power = 0.80. Neither trials nor seeds inflate n.

| Independent participants | MDE if paired SD = 5 pp | MDE if SD = 10 pp | MDE if SD = 15 pp |
|---:|---:|---:|---:|
| 10 | 4.980 pp | 9.960 pp | 14.940 pp |
| 21 | 3.214 pp | 6.428 pp | 9.641 pp |
| 60 | 1.839 pp | 3.677 pp | 5.516 pp |
| 85 | 1.537 pp | 3.074 pp | 4.611 pp |
| 87 | 1.519 pp | 3.038 pp | 4.557 pp |

| Assumed paired SD | Required n for 2 pp | Required n for 3 pp | Required n for 5 pp |
|---:|---:|---:|---:|
| 5 pp | 52 | 24 | 10 |
| 10 pp | 199 | 90 | 34 |
| 15 pp | 444 | 199 | 73 |

The complete CSV contains 72 planning rows: 45 fixed-n MDE cases and 27 fixed-effect sample-size cases across primary α = 0.05 and conservative family boundaries 0.025 and 0.05/3. The 0.025 cases are sensitivity planning for a hypothetical two-comparison family, not an extra active analysis family. Exact power has been independently checked against a normal/chi-square mixture integral at five planning points (including the 85-person eligibility ceiling), and all 79 numerical checks passed. A machine-readable verification record contains both calculations. At the current n ≤ 85 ceiling, SD = 10 pp gives a primary MDE of 3.074 pp and a conservative three-comparison MDE of 3.571 pp; further eligibility losses reduce power.

For example, with n = 21 and paired SD = 10 pp, the design is powered for approximately 6.43 pp, not a 2 pp effect. If available independent cohorts are too small, present the experiment as a precision-limited independent estimate, not proof of absent gains or equivalence. A small negative or null result must not trigger outcome-driven cohort replacement, sample-size reinterpretation, a new favourable endpoint or selective retraining. Recruiting or adding an independently specified additional cohort requires a prospective amendment with a justified new analysis plan; it is not repeated testing until significance.

## 10. Analysis traceability and independent verification

Before target results are released, commit/hash the primary dataset inventory, participant identity/de-duplication evidence, eligibility rules, source split registry, all model/selection settings, random seeds, contrasts and analysis script. After inference, preserve immutable per-trial outputs and per-person per-seed metrics. Reconstruct the primary estimate from those files, verify each participant/class denominator and model/checkpoint identity, and independently reproduce all contrasts and corrected p-values. Record negative outcomes and numerical failures with the same provenance as favourable ones.

The present files are planning artifacts only. No new independent confirmation, confirmatory p-value, noninferiority conclusion, clinical claim or causal mechanism is produced by this calculation. The existing frozen Q1–Q16 results and historical manuscript numbers remain unchanged.

## 11. Analysis-input schema and software acceptance

`scripts/analyze_redesign_scores.py` does not train or infer. Its input is a locked event inventory and an immutable per-trial CSV covering every retained person × two architectures × three selectors × three seeds. Inventory entries contain `subject_id`, session/run-qualified `event_id`, binary `ytrue`, and the SHA-256 of the exact processed EEG window. CSV rows additionally contain `model_arch`, `selector`, `seed`, `ypred`, `p_left`, `p_right`, and `checkpoint_sha256`. Event IDs must distinguish repeated sessions/runs/trials; all six conditions and all three seeds use the same eligible acquisition windows. Identical window fingerprints are flagged as duplicates; a performance-based exclusion is not available. Labels are compared with the locked inventory; real-cohort contracts require at least 20 eligible trials per class per participant, as fixed in the raw-QC protocol. Probability finiteness, range, normalization, argmax consistency, condition/seed checkpoint consistency, and complete cell coverage are checked before estimates are formed. The classifier tie rule is the first (left) class for equal probabilities. The execution exporter must map core identifiers `BROAD_EEGNET`→`broad`, `MU_BETA_SHARED`→`shared`, and `fixed20`→`fixed` in the analysis CSV/contract; this is a documented identifier translation, not a different architecture or free choice of fixed duration. Its source checkpoint audit must verify that `fixed` is exactly 20 epochs. All other selector and seed identities are unchanged.

Real-data scoring is blocked unless all seven named gates in the script are recorded as passed. Each JSON evidence receipt contains `gate_name`, `passed: true`, and `locked_contract_sha256`; independent prediction validation also binds `predictions_sha256`. The gate manifest binds the byte hashes of the contract, prediction CSV and audit receipts. It enumerates all 18 condition/seed checkpoint identities with `source_only: true`, integer `target_fit_count: 0`, a `checkpoint_file`, and its SHA-256. Checkpoint bytes are hashed without deserialization or inference, and each prediction row must reference its corresponding checkpoint. Verifying those identities preserves a declared evidence chain; it does not independently certify truthful author attestations, raw task semantics or participant identity. Those scientific judgments require the actual cited audits. A favorable statistical threshold cannot replace a failed or absent gate.

The actual cohort independence, author prior-exposure attestation, original-file/conversion comparison and raw event/channel audits are still pending. No real independent target score is authorized by the software validation. The `--allow-synthetic-fixture` switch permits invented software fixtures only; their output is labelled `synthetic_planning_only` and cannot declare primary or secondary confirmation even when its nominal p-value is small. It is not a bypass for real EEG outcomes.

Software acceptance uses invented labels and probabilities for 12 fictitious participants, deliberately unequal class/trial counts, all three seeds and all six conditions. The test suite checks participant/class/seed weighting against an independent calculation, paired-t estimates against SciPy, Holm ordering, deterministic participant bootstrapping, the primary-gated secondary family, zero-variance degeneracy, class-dominance grain, malformed inputs, duplicate/label/window/checkpoint guards, missing or failed audit receipts, and CLI failure closure. Run `python tests/test_redesign_statistics.py --write-evidence` from this study directory. `evidence/statistical_software_validation.json` records actual executed test counts and code hashes; passing software fixtures is not scientific confirmation.
