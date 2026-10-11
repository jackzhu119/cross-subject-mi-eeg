### S1. Full internal model inventory and participant effects

Table S1 lists all completed nine-person Q4–Q11 four-class conditions, including shallow spectral/geometric controls and source-clean/source-normalized variants. The inventory is descriptive; a higher target mean does not select a method for a confirmatory claim. Accompanying CSV/JSON files provide participant values, fixed seeds, primary all-trial populations and source file hashes. The complete inventory contains 61 Q4–Q14 condition records, with repeated endpoints and the four single-person diagnostic cells identified. These records are neither independent replications nor a cumulative fit count. Robustness conditions appear in Table 5, source-composition means in the complete CSV, and the corresponding statistical families in Table S2.

**Table S1. Completed nine-person Q4–Q11 four-class conditions.**

| Archived condition | Mean BA (%) | Subject SD (pp) |

| --- | --- | --- |

| Q4-E001/BroadCSP LDA | 39.04 | 14.18 |

| Q4-E001/BroadCSP SVM | 37.50 | 12.66 |

| Q4-E001/FBCSP LDA | 38.12 | 7.69 |

| Q4-E001/FBCSP MI8 LDA | 31.37 | 4.26 |

| Q4-A001/FBCSP MI16 LDA | 34.65 | 8.45 |

| Q4-A001/FBCSP MI32 LDA | 36.75 | 8.86 |

| Q4-A001/FBCSP MI72 LDA | 38.12 | 7.69 |

| Q4-A001/FBCSP MI8 LDA | 31.37 | 4.26 |

| Q5-E001 | 33.72 | 11.58 |

| Q6-E001 | 37.93 | 15.68 |

| Q8-E001 | 42.67 | 16.04 |

| Q9-A001/PSD44 LDA | 36.28 | 8.17 |

| Q9-A001/PSD44 LINEAR SVM | 35.78 | 8.39 |

| Q10-A001/BROAD LOGE LOGREG | 35.32 | 10.74 |

| Q10-A001/BROAD LOGE MDM | 29.49 | 8.73 |

| Q10-A001/MUBETA LOGE LDA | 36.00 | 10.75 |

| Q10-A001/MUBETA LOGE SVM | 35.47 | 8.83 |

| Q9-E001/BETA 13 30 | 31.53 | 10.05 |

| Q9-E001/MID 8 30 | 44.55 | 17.17 |

| Q9-E001/MU 8 13 | 43.30 | 16.22 |

| Q9-E001/MU BETA SHARED | 42.19 | 14.10 |

| Q9-E002/MID 8 30 Q8 EPOCHS | 42.73 | 15.73 |

| Q9-E002/MU BETA SHARED Q8 EPOCHS | 43.50 | 15.82 |

| Q9-E004/MU BETA SHARED SOURCE CLEAN | 42.11 | 15.23 |

| Q9-E005/MU BETA SHARED SOURCE NORM | 41.53 | 13.88 |

| Q10-E001/MU BETA CSP8 EEGNET | 41.48 | 16.04 |

| Q10-E001/MU BETA PCA8 EEGNET | 42.06 | 15.51 |

| Q11-E001/BROAD CAPACITY MATCHED | 42.19 | 14.05 |

| Q11-E001/FOUR BAND SHARED | 39.80 | 11.58 |

| Q11-E001/TWO BAND EARLY STACK | 42.66 | 16.23 |

| Q11-E001/TWO BAND INDEPENDENT | 42.99 | 17.38 |

Neural seeds are averaged within person; shallow arms evaluate one model per fold. Q4-A001 reuses fitted CSP feature caches but refits scaler/LDA. Its k8/k72 predictions reproduce earlier Q4 endpoints and add no independent outcomes. Condition IDs record protocol order rather than a leaderboard ranking. The four S3 diagnostic cells appear separately in Fig 2C, outside the nine-person rows.

### S2. Robustness heterogeneity

Figure S1. Participant-level robustness differences for all nine people in fixed order. Colours and annotations show balanced-accuracy percentage points. GroupDRO uses balanced ERM as its control; all other rows use the historical Q8 mean-rank baseline and cross runtimes. The display is descriptive, with no target-based exclusions or significance stars.

### S3. Duration, source-count, and source-session statistical families

**Table S2. Archived exploratory Q13/E006 paired contrasts.**

| Contrast | Δ (pp) | 95% CI (pp) | Holm p |

| --- | --- | --- | --- |

| Broad k2 minus k8 | −11.03 | [−18.80, −3.56] | 0.1641 |

| Broad k4 minus k8 | −5.10 | [−10.36, −0.38] | 0.4336 |

| Broad k6 minus k8 | −0.83 | [−3.67, +1.89] | 0.5664 |

| Shared k2 minus k8 | −9.23 | [−15.41, −3.15] | 0.1641 |

| Shared k4 minus k8 | −5.09 | [−9.28, −1.31] | 0.2344 |

| Shared k6 minus k8 | −1.49 | [−3.41, +0.42] | 0.4336 |

| Broad 1test minus 0train | −0.84 | [−1.89, +0.19] | 0.3516 |

| Shared 1test minus 0train | +0.08 | [−1.14, +1.18] | 0.8516 |

| Fixed20 minus Historical CE | +10.27 | [+0.96, +21.62] | 0.1562 |

| Shared FIXED20 minus Shared RAW CE | +3.91 | [+0.44, +7.62] | 0.1562 |

| Matched CE minus Fixed20 | −10.06 | [−21.53, −0.68] | 0.1250 |

Each row summarizes nine people after averaging fixed seeds and, where applicable, source subsets within person. The historical CE contrast crosses runtimes; the separately declared matched-CE-minus-fixed20 contrast controls runtime. Intervals are unadjusted, and p-values are corrected within each declared family. Signs follow the archived contrasts; Fig 3B reverses the matched contrast for readability.

### S4. Audit and reporting boundaries

The manuscript-number audit reaggregates stored predictions independently and records the CSV hashes used. Historical scientific replay counts are reported only when supported by a passing scientific receipt. The Q9 top-level batch report documents orchestration, and the versioned external portability validator adds no inference. CRLF-to-LF matches are identified explicitly. The paper bundle contains the source-snapshot manifest, review input hashes, independent numerical audit, generated tables, figure sources and rendering checks. These records document existing analyses; they do not authorize training or establish an external outcome-selected method freeze. For completed Q15, the final scientific validator binds 221 artifacts and verified result publication binds 223 artifacts at the committed snapshot. The manuscript independently checks these bindings, 52 source-artifact bindings and 10 frozen checkpoint/transform bindings; freeze and manifest documents are checked separately. Status files can change after the result commit, so each hash is checked at the commit named by its receipt. An intermediate receipt marked pending does not override the final passing validator.

The original mean-rank follow-up reports a bootstrap interval of [+1.048,+19.959] pp (20,000 draws, seed 20260923); independent reanalysis with 200,000 draws and seed 20261002 gives [+1.067,+19.952] pp. The main text retains the original interval. The saved nine-person sign sensitivity includes zero changes in its denominator; the conventional tie-excluding sensitivity is reported separately. Both implementation and resampling differences are disclosed to explain the small numerical discrepancy.

The external primary sign test retains the archived exact-zero rule. S10 has a saved shared-minus-broad difference of approximately −1.11 × 10^−16 and counts as negative: 63 positive, 43 negative and three zero differences, p = 0.06446. With a numerical tolerance of 10^−14, that difference becomes a tie, giving 63 positive, 42 negative, four ties and p = 0.05044. The primary rule remains unchanged. Neither calculation establishes superiority at the conventional 0.05 threshold.

### S5. Earlier binary calibration, artifact, and EOG checks

The earlier pipeline checks concern left/right imagery and are reported separately from the four-class analysis. P2-E001 contains 2,346 expert-clean trials. Within-session leave-run-out and cross-session models use labelled trials from the evaluated person; cross-subject LOSO excludes both target sessions. Within-session/LOSO evaluate all 2,346 trials, whereas cross-session evaluates 1,183 later-session trials. P2-SMOKE-S1B is a single-person technical check, not a population replication. P2-E002-ALLTRIALS includes 2,592 trials in both source and target populations. Some retained metadata still carries an earlier clean-population name; interpretation follows the actual trial populations.

P3-E001 compares CSP4, Welch PSD88 and their 92-feature fusion with source-all and source-expert-clean training. Its primary endpoint uses the same 2,346 expert-clean target trials; all 2,592 trials and the 246 flagged trials are secondary strata. P4-E001B is the successful EOG-processing retry. Regression coefficients fitted on clean source data are applied to three synchronous target EOG channels, without target parameter fitting. The method therefore requires these additional sensors. Clean-target balanced accuracy was 62.57% versus 62.85% without correction, establishing neither a decoding benefit nor selective ocular-artifact removal. The failed original P4 attempt remains in the technical record.

**Table S3. Earlier binary QC primary endpoints; all nine participants.**

| Stage / model | Split / source policy | Target trials | BA (%) |

| --- | --- | --- | --- |

| P2-E001 / CSP+LDA | cross session; expert clean only | 1183 | 76.06 |

| P2-E001 / CSP+linearSVM | cross session; expert clean only | 1183 | 75.05 |

| P2-E001 / CSP+LDA | cross subject; expert clean only | 2346 | 62.76 |

| P2-E001 / CSP+linearSVM | cross subject; expert clean only | 2346 | 62.09 |

| P2-E001 / CSP+LDA | within session; expert clean only | 2346 | 78.06 |

| P2-E001 / CSP+linearSVM | within session; expert clean only | 2346 | 78.21 |

| P2-E002-ALLTRIALS / CSP+LDA | cross subject; all trials | 2592 | 61.50 |

| P2-E002-ALLTRIALS / CSP+linearSVM | cross subject; all trials | 2592 | 60.57 |

| P3-E001 / CSP4+PSD88 + LDA | cross subject; all trials | 2346 | 64.10 |

| P3-E001 / CSP4 + LDA | cross subject; all trials | 2346 | 61.92 |

| P3-E001 / PSD88 + LDA | cross subject; all trials | 2346 | 58.55 |

| P3-E001 / CSP4+PSD88 + LDA | cross subject; expert clean only | 2346 | 64.63 |

| P3-E001 / CSP4 + LDA | cross subject; expert clean only | 2346 | 62.85 |

| P3-E001 / PSD88 + LDA | cross subject; expert clean only | 2346 | 58.19 |

| P4-E001B / EOG regression | cross subject; source train fitted EOG regression | 2346 | 62.57 |

| P4-E001B / Uncorrected CSP4 + LDA | cross subject; uncorrected | 2346 | 62.85 |

All rows are binary, with 50% chance. Within-session and cross-session rows use target-person labelled calibration. P3/P4 rows use expert-clean targets; P2 all-trial rows use all trials. CSV supplements retain all/flagged secondary endpoints, target-information notes, and the single-person smoke. These modes and populations are not pooled into a calibration-free score.

### S6. Selection-curve analyses and technical history

Q8-A001/A002/A003 inspect archived source-validation curves without further fitting. Leave-one-inner-fold-out sensitivity and six candidate aggregation rules generate hypotheses; they are not six target-evaluated decoder conditions. P1-E001 is a single-subject acquisition audit. P2-SMOKE-S1 and the original P4-E001 retain failure receipts followed by successful retries. Q13-E002/E003 and Q14-E003 were not run and have no performance values. The partial 87-person external attempt is not an additional cohort alongside the completed 109-person evaluation. The completed-experiment inventory records each analysis’s evidential role, reuse, validation scope and technical failures.

### S7. External adapter, freeze chronology, and cohort-level sensitivity

The companion supplementary_methods.md specifies the 21-channel montage, six-second native context, deterministic cue indexing, native-rate filters, two-second crop, Helmert coordinates, provider label maps, raw audits, source validation groups, 15 original fits and source/inference freeze chronology. Cho2017 retains labelled imagery: 49 people contribute 200 trials each, and S7, S9, S46 contribute 240. Lee2019 includes offline-training runs only, with 100 trials per session. All primary participants are retained, and Q15 interpretations retain the stated calibration limitations.

Figure S2. Participant-level Q15 transfer heterogeneity. Saved seed-averaged shared-minus-broad effects and within-person three-seed sample standard deviations (106 paired effects and 212 dispersion points; CSP omitted) are displayed separately for 52 Cho and 54 Lee people. Participant order is descriptive and does not define subgroups or target selection. Repeated seeds and the two Lee sessions are not additional inference units.

Shared input had greater descriptive seed dispersion than broad input: mean within-person seed SD was 6.014 versus 4.550 pp on Cho, and 3.798 versus 2.887 pp on Lee. These SDs summarize three fixed source-model seeds, not a population distribution of training randomness, and are not additional confirmatory hypotheses. Person/seed metrics and class recalls are supplied in q15_external_subjects.csv, q15_seed_metrics.csv and q15_model_summary.csv.

### S8. Reproducible manuscript materials

The submission materials contain the manuscript, supporting information, standalone figures, frozen derived data and validation evidence. All manuscript-preparation model fits and checkpoint-inference counts are zero. Operational cloud logs are not scientific endpoints. Author declarations and final submission checks are maintained separately from the scientific results.

### S9. Descriptive BNCI-only Physiological Characterization

The separate Q16 methods specify native raw-file/hash and event checks, fixed Welch parameters, trial-level dB aggregation, hand descriptors, artifact/session strata and all-nine-person associations with saved Q14-E001 binary LOSO scores. The specification follows known decoder outcomes. It adds no external physiology, p-values, subgroup selection, decoder fits or decoder inference. The public parameter freeze is 050e01b028aaab8e3d745934b13b2d17e9bb0a7a. Independent validation passed for the central-channel raw power replays, all saved aggregation tables and all six signed correlations. The bundle retains the freeze/readback, raw and execution receipts, summary, validation, person/session/artifact tables and figure input/export hashes.

**Table S4. All six descriptive physiology–balanced-accuracy associations.**

| Saved binary LOSO model | Band | Spearman rho | People | Context |

| --- | --- | --- | --- | --- |

| Broad EEGNet | Mu | −0.150 | 9 | Designated descriptive endpoint |

| Broad EEGNet | Beta | +0.600 | 9 | Designated descriptive endpoint |

| Shared mu/beta EEGNet | Mu | −0.083 | 9 | Context |

| Shared mu/beta EEGNet | Beta | +0.483 | 9 | Context |

| CSP4 + LDA | Mu | +0.067 | 9 | Context |

| CSP4 + LDA | Beta | +0.317 | 9 | Context |

Spearman rho is the Pearson correlation of average ranks. Each person contributes one equal-session signed C3/C4 hand descriptor and one saved Q14-E001 binary LOSO balanced-accuracy score: a three-seed mean for neural models and one CSP fit. All nine people are retained. Positive rho associates higher balanced accuracy with a larger signed descriptor, which is less relatively suppressive when negative. Coefficients are rounded to three decimals here and retained at full precision in the data tables. These post-decoder-outcome associations have no p-values, confirmatory claims or external physiological test.

Figure S3. All six descriptive BNCI associations. Every model/band panel shows the same nine people, labelled by person ID. The horizontal axis is signed C3/C4 hand laterality; the vertical axis is saved Q14-E001 binary LOSO balanced accuracy. Neural scores average three seeds within person; CSP uses one frozen fit. The physiology window [0.5,2.5) s differs from the decoder window [0.5,3.5) s. All points are retained, with no fitted lines, p-values, subgroup thresholds or decoder updates. Positive beta correlations associate higher balanced accuracy with less-negative laterality. These post-outcome descriptions establish neither mechanism nor causality and do not validate a biomarker.

## Detailed reproducible methods

### Supplementary methods

Companion to *Source-only model selection and limits of fixed spectral-sharing pipelines in cross-subject motor-imagery EEG decoding*. Revision dated 7 October 2026. This document describes completed decoder analyses including Q15 and the completed, independently checked descriptive BNCI-only Q16 analysis. Decoder source snapshot: 7af1a137e2676a018e1e880ab076de6cae4ce30b. The earlier manuscript inventory is retained as historical evidence rather than treated as the final dataset definition.

### S1. Study sequence and units of evidence

Source-only decoding procedures were developed on nine BNCI2014_001 participants and evaluated as frozen binary pipelines on separate external acquisition cohorts held out from fitting. Participant identity nonoverlap across providers was not independently established. The four-class development task, Q14 binary PhysioNet evaluation and Q15 binary Cho2017/Lee2019_MI evaluation use different input contracts, so balanced accuracies are reported separately. No pooled accuracy across tasks or combined external participant-level significance test was specified.

Strict zero-calibration is defined within each evaluation fit: the current target person's recordings and labels do not estimate or select weights, BatchNorm state, shallow coefficients, preprocessing coefficients, training duration, seeds, thresholds or model choice for that fit. Source-fitted transformations are applied unchanged. Fixed filtering, channel selection, resampling, CAR and analytical Helmert coordinates compute functions of target signals without fitting a target-dependent decoder. Event and class metadata implement declared eligibility and canonical label maps; labels score predictions. Separate Q16 summaries read native BNCI signals and labels without changing any decoder. This information contract does not imply that the development programme was designed without prior BNCI outcomes, that target labels were never accessed, or that physical voltage calibration is known. Q4–Q13 are development and sensitivity analyses on repeatedly used participants. Q15's pre-fit freeze was committed on 4 October 2026 at 01:33:03 UTC (fc0e7d54006076bec7701064e1045034c02d06a4), before source completion at 01:52:42 UTC. Its separate inference/statistics freeze was committed on 5 October at 09:31:05 UTC (2ad479f5bccb4f92cd6c77bc78a8ba9b620604c1), before target inference completion at 10:57:19 UTC. This chronology is documented in the repository, rather than in an independently registered clinical or trial registry.

The inventory distinguishes evaluated conditions, fitted models, reused endpoints, metadata audits and unsuccessful or unrun branches. Its 61 historical Q4–Q14 condition rows and 34 earlier quality-control rows are not 95 independent replications. Q15 adds six external model-by-cohort endpoints. Three source-model records document the separate source fit/freeze stage and carry no external performance claim.

### S2. Historical BNCI development and quality-control analyses

BNCI2014_001 contains 5,184 trials from nine people, two sessions each, and four classes. Each participant contributes 576 trials; the local complete metadata audit records 488 expert artifact-flagged trials. The primary four-class analyses include all trials and consequently do not use the original competition's artifact-free evaluation population. Within-session and cross-session P2 checks use labelled calibration from the evaluated participant, whereas cross-subject analyses exclude both target sessions. These calibration modes remain separate in the inventory.

The primary historical neural pipeline filters native 250-Hz recording runs with a fourth-order Butterworth prototype in zero-phase mode. Its half-open epoch is [2.5,5.5) s after stored trial start, or [0.5,3.5) s after the imagery cue: 22 EEG channels and 750 samples. There is no baseline subtraction, additional reference, or additional notch in that primary pipeline. MNE-loaded volt values are converted to numerical microvolt inputs. Q5/Q8 use 4–40 Hz; the restricted broad Q9 arm uses 8–30 Hz. The shared model uses fixed 8–13-Hz and 13–30-Hz views.

Each outer LOSO fold excludes both sessions of one person. The remaining eight sorted source IDs form four consecutive two-person validation groups. Inner fits train on six people and validate on two; final fits train on eight and evaluate the held-out person. Q5 chooses the earliest minimum of equal-fold mean validation cross-entropy. Q8 chooses the earliest minimum of the equal-fold mean within-fold cross-entropy rank, with average ranks for ties, across epochs 1–40. It reuses 36 Q5 inner trajectories and performs 27 final fits. Representation-specific conditions generally recompute source-only trajectories; fixed-duration controls retain their documented epoch schedule.

Three final neural seeds, 20260924, 20260925, and 20260926, are averaged within person. Source-subset repetitions are also aggregated within target person before population summaries. Neither seeds nor overlapping source subsets are treated as independent participants. Detailed historical controls and their limits are preserved in supplementary_inventory.md and the locally retained historical method audit at evidence/previous_draft/methods_and_references.md.

The Q5 raw-versus-Q6 source-normalized comparison changes both the input scaler and two selected schedules: S3 changes from two to 16 epochs and S5 from 13 to 12. The population normalization delta therefore does not isolate normalization alone. Q7's raw/normalized × two/16-epoch four-cell diagnostic fixes duration within each pair for S3, but supplies only a one-person diagnostic. Earlier within-person P2 analyses use labelled target-person calibration and remain outside strict zero-calibration endpoints.

The P3 clean/all/flagged strata overlap and must not be added as independent samples. P4-E001B is the successful EOG-assisted retry: regression coefficients are estimated from clean source data and applied with synchronous target EOG. A lower EEG–EOG correlation is not proof of selective ocular artifact removal. The failed P4-E001 channel-selection attempt is retained separately. Q9 orchestration success supports execution bookkeeping; it does not by itself establish raw-to-checkpoint replay. Later Q12/Q13 replay receipts have experiment-specific scopes.

### S3. Shared spectral representation and comparator definitions

The shared μ/β pipeline supplies two fixed filtered views to the same EEGNet and averages their class-logit vectors. Training cross-entropy is computed from the averaged logits; inference applies softmax to that average. Both views form one two-view mini-batch, sharing BatchNorm parameters and running statistics as well as convolutional weights. Dropout is applied per view during training. This imposes an input and parameter-sharing constraint. It does not learn attention, train two independent networks or average probabilities.

The configured EEGNet uses F1=8, D=2, F2=16, a 64-sample temporal kernel, and dropout 0.25. Training uses Adam, learning rate 0.001, batch size 64, weight decay 0, and cross-entropy without a learning-rate scheduler. Model evaluation and inference mode prevent target examples from updating BatchNorm. Parameter counts depend on input duration and output classes; the historical 22×750 four-class model's 2,932 parameters must not be copied to a different Q15 architecture without checking it.

Historical shallow comparators are implementation-specific. The Q4 filter-bank controls use OAS regularization and shrinkage LDA or linear SVM. Q14/Q15 CSP4+LDA instead use unregularized CSP, concatenated covariance estimation, log power, no trace normalization, full-rank coordinates, mutual-information component order, source-fitted StandardScaler, and LDA with the SVD solver. These comparators are not interchangeable. Q15's fixed Helmert coordinates, described below, address the rank loss induced by its common-average reference.

### S4. Q14 external evaluation on PhysioNet

Q14 uses separate binary BNCI source models trained on left/right imagery only: 2,592 trials, 288 per source participant. Native filtering and 750-sample historical epochs precede polyphase resampling from 250 to 160 Hz, producing 22×480 inputs. All-nine-source duration selection uses validation groups [1,2], [3,4], [5,6], and [7,8,9]. Their training complements contain seven, seven, seven, and six people. Equal-fold weighting is retained despite unequal group sizes. Selected durations are 18 epochs for broad EEGNet and 17 for shared μ/β. This source stage comprises eight inner and six final neural fits, plus one CSP fit. The 18/17-epoch contrast compares complete selected pipelines rather than isolating parameter sharing.

The completed external Q14-E002R2 evaluation uses all 109 PhysioNet participants and imagery runs 4, 8, and 12 only. T1 maps to left-hand imagery and T2 to right-hand imagery; rest, executed movements, and bilateral tasks are excluded. It comprises 327 EDF files and 4,918 distinct trials. Two neural models × three seeds plus one deterministic CSP model produce 34,426 prediction rows. Those rows do not represent 34,426 independent observations.

The metadata-driven R2 amendment handles three native 128-Hz participants (88, 92, and 100); the remaining 106 are native 160 Hz. Native filtering/epoching precedes deterministic resampling to 480 samples. The full 109-person endpoint supersedes the partial 87-person R1 attempt. A later portable validator replays archived event identities, saved probabilities, and statistics in its documented validation runtime; that scope should not be described as the Q15 full raw/checkpoint replay. No target fit, target normalization, or target-based duration choice occurs.

### S5. Q15 source and target cohort definitions

Q15 is an explicitly amended 21-channel external benchmark, not an unchanged rerun of the Q14 preprocessing. Q15-E005 performs source-only fitting on the nine BNCI participants, preserving the binary population of 2,592 trials across both sessions. The new input is 21×320 at 160 Hz. Raw-file audits and a committed pre-fit freeze precede every source fit. The source validator verifies eight inner plus six final neural fits and one shallow fit. Its selected durations are 14 epochs for broad EEGNet and 19 epochs for shared μ/β. These are distinct from the Q14 18/17 durations. The Q15 broad/shared contrast includes both the input design and unequal source-selected schedules, so it is a complete-pipeline comparison rather than a causal sharing effect.

Cho2017 includes 52 people and 52 raw MAT files. The retained imagery_left and imagery_right signals comprise 10,520 trials. Most participants have 100 trials per class; participants 7, 9, and 46 have 120 per class. Imagery event indices use the audited zero-based nonzero event-array samples, with no added timing shift. Data concatenated by class are split into independently retained trial contexts. The study does not reconstruct original physical run identities; retained_labeled_MI is an analysis label, not a verified acquisition run identifier.

Lee2019_MI includes 54 people, two sessions each, and 108 MAT files. Only EEG_MI_train is evaluated: 100 labelled trials per file and 10,800 trials overall. EEG_MI_test and other tasks are excluded. Cue indices use stored MATLAB t minus one. The native class convention is mapped as 1→canonical right=2 and 2→canonical left=1. The stored segmented smt alignment differs from this explicit cue convention and is not silently substituted for it. Both sessions are pooled within person for the primary metric.

The retained source/target channel order is Fz, FC3, FC1, FC2, FC4, C5, C3, C1, Cz, C2, C4, C6, CP3, CP1, CPz, CP2, CP4, P1, Pz, P2, and POz. FCz from the BNCI 22-channel montage is omitted by the frozen common-channel rule. No channel interpolation, imputation, or target-fitted montage correction is used.

### S6. Q15 numerical preprocessing contract

For every dataset, the adapter retains a complete half-open six-second native context [−1.5,4.5) s relative to the audited cue. A missing or truncated context is an error; it is not shortened or padded into an accepted trial. Channel selection precedes an instantaneous arithmetic common-average reference across the 21 selected channels. Referencing and filtering operate in float64. Each retained trial context is processed independently, avoiding filtering across artificial class-concatenation boundaries in Cho2017.

Three native-rate filters are fixed: broad 8–30 Hz, μ 8–13 Hz, and β 13–30 Hz. scipy.signal.butter(4, ..., btype="bandpass", output="sos") supplies a fourth-order low-pass prototype, yielding an eighth-order bandpass represented by four second-order sections. sosfiltfilt applies forward/backward filtering with odd extension and padlen=27 native samples. The coefficient tables for 250, 512, and 1,000 Hz and the NumPy/SciPy versions are embedded in the freeze. Zero-phase filtering is offline and noncausal; these results do not establish online causal performance.

The complete filtered context is resampled with scipy.signal.resample_poly, a Kaiser window parameter of 5.0, constant boundary extension, and cval=0. Ratios are 16/25 for BNCI at 250 Hz, 5/16 for Cho2017 at 512 Hz, and 4/25 for Lee2019_MI at 1,000 Hz. The common context contains exactly 960 samples. A half-open slice [320:640] yields the [0.5,2.5)-s cue-relative window and 320 model samples. Final inputs are contiguous float32. No baseline correction, artifact rejection, target moment fitting, target covariance alignment, or target-based duration/seed selection is introduced.

The 21-channel common-average signal has at most 20 spatial degrees of freedom. Before Q15 CSP, the complete referenced subspace is represented by the fixed 20×21 orthonormal Helmert matrix scipy.linalg.helmert(21, full=False). This basis depends only on channel count; it is not estimated from either dataset. The source-only CSP pipeline then retains four components. The basis is not target adaptation and is not a learned dimension-selection result.

The declared convention is native numerical values interpreted as microvolts. Provider file identities, hashes, shapes, channels, sampling grids, cues and label conventions were audited; physical export voltage calibration was not independently established. The original Cho hardware reference and cue latency also remain unverified. Common-average referencing defines numerical coordinates without authenticating the original hardware reference. Q15 is therefore reported as completed_with_calibration_limitations: an adapter benchmark under a stated input convention. Amplitudes and between-dataset differences do not establish voltage equivalence or a controlled acquisition mechanism.

### S7. External inference, statistics, and validation

Six final neural checkpoints and one deterministic shallow model are frozen before target inference. Each target trial has seven prediction rows: two neural models with three seeds each and one shallow model. Cho2017 contains 73,640 rows for 10,520 distinct trials; Lee2019_MI contains 75,600 rows for 10,800 trials. Original source fits total 15; migration performs zero new source fits and zero target fits. Reuse is established by the checkpoint/artifact bindings and preserved source validation, rather than inferred from a launcher receipt.

For person i and neural seed s, balanced accuracy is the mean of left-class and right-class recall. Lee sessions are pooled within person before scoring; session scores remain descriptive. The three seed-specific balanced accuracies are then averaged within person, and cohort balanced accuracy averages those person values equally despite Cho's unequal trial counts. The primary paired contrast is shared μ/β minus broad EEGNet within person. CSP4+LDA provides context and is outside the predeclared primary family.

For each cohort, the 95% interval is the percentile interval from 20,000 bootstrap resamples of whole people, preserving the pairing, with seed 20260924. The two-sided sign-flip Monte Carlo test independently assigns a random ±1 sign to each person's paired difference, uses 20,000 draws and seed 20261003, and applies the plus-one p-value correction. This tests a sign-exchangeability null; it does not turn correlated training seeds or individual trials into independent observations. Holm adjustment covers exactly the two predeclared cohort contrasts. The procedure is frozen before target predictions, and no pooled-cohort effect, post-hoc target tuning, equivalence margin, or target-based model selection is claimed.

Cho2017 mean balanced accuracy is 59.8237% for broad EEGNet, 58.3104% for shared μ/β, and 51.9904% for CSP4+LDA. The shared-minus-broad contrast is −1.5134 percentage points, 95% CI [−2.2490,−0.8045], with Holm-adjusted p=0.000099995. Lee2019_MI means are 65.5123%, 65.7160%, and 52.7685%, respectively; its contrast is +0.2037 percentage points, 95% CI [−0.5154,+0.9691], Holm-adjusted p=0.60367. The Cho result opposes a general shared-band superiority claim. The Lee result provides no clear paired advantage; absence of a significant difference does not establish equivalence.

The final independent computational Q15 validator replays the raw metadata audit, raw-to-epoch transformation, frozen checkpoint predictions, coverage, labels, and statistical calculations. It verifies unchanged neural model state and a shallow-model digest before/after inference. Probability replay uses atol=10⁻⁷ and rtol=10⁻⁶, with exactly matching argmax predictions. The passing results/Q15-EXTERNAL/validation_report.json supersedes the temporal inference-completion status as completion evidence. Intermediate statistics.json, holm_two_cohorts.json, and completion_receipt.json retain their pre-validation pending labels by design; their numeric/hash bindings are checked by the final validator. This replay verifies computational consistency and state immutability; it is not an additional cohort or independent laboratory replication.

### S8. Runtime and provenance

Source fitting completed on 4 October 2026 in the origin job 20261004T005335Z-9b3bce30277a. Q15 continuation completed and was validated in the migration job 20261005T050511Z-migration-from-r2-b82ad79b. The scientific revision is 271af288a2f3863430ab80e3145c2dee9bd5571d; the source/artifact continuation base is 782d2d0070a50c37d13c8e9f1cab3b3b81bac4fc. Final scientific-results publication was read back at bc48b257eb44f412ad069f50d0f1a72a33c3c520; the inspected results branch snapshot is 7af1a137e2676a018e1e880ab076de6cae4ce30b.

The source runtime records Python 3.12.3, Linux/glibc 2.39, NVIDIA RTX 4000 Ada Generation, PyTorch 2.8.0+cu128, CUDA runtime 12.8, Braindecode 1.5.1, MNE 1.13.2, MOABB 1.7.2, NumPy 2.5.3, SciPy 1.18.1, and scikit-learn 1.9.1. The continuation status records h5py 3.16.0, joblib 1.6.0, pandas 3.0.6, skorch 1.4.0, matplotlib 3.11.2, and threadpoolctl 3.7.0. These are recorded run versions, not a promise that later dependency resolution will produce identical binaries. Historical Q5 and later development runtime changes remain visible in their receipts; they limit contrasts that are not matched for runtime.

Migration restored source artifacts from the pinned GitHub snapshot and reconstituted external epochs from checksum-verified R2 originals. The public restoration provenance records 160 verified external originals and 106 epoch-person artifacts. This should not be conflated with the broader 178-file transport inventory, which additionally contains 18 BNCI source originals. R2 is transport/storage infrastructure, not a fifth research dataset. The decoder-number audit recomputes metrics from committed predictions without loading raw EEG or checkpoints. The separate Q16 analysis reads native BNCI raw EEG for spectral summaries. Both preserve historical fit counts and perform zero decoder fits and zero new decoder-inference rows; external raw files are not newly reprocessed by this manuscript revision.

### S9. Interpretation boundaries

Development comparisons repeatedly use the same nine BNCI people and often reuse inner trajectories, checkpoints, source subsets or endpoints. They describe sensitivity within this development benchmark rather than independent confirmatory experiments. Q14 and Q15 have different channel/window/reference contracts and are not unchanged-protocol replications. The fixed frequency split and logit-average architecture establish neither physiological source separation nor artifact causality, domain invariance, clinical benefit or online readiness. Calibrated acquisition metadata, prespecified hardware harmonization, independent cohorts and causal preprocessing are questions for future work, not completed analyses.

### S10. Descriptive BNCI-only physiological characterization (Q16)

Q16-P001 executes the BNCI component of the earlier physiology proposal. Its explicit estimator, aggregation, coverage, plotting and association specification was fixed on 6 October 2026 after decoder outcomes were available and before the new raw-power calculation. It is descriptive, not independent prospective registration or a new decoder experiment. The controlling protocol is research_runs/Q16-P001-BNCI-20261006/PROTOCOL.md. External physiological analysis remains unrun; BNCI results cannot establish an external neural mechanism or resolve the acquisition limitations of Q15.

The declared population retains all 18 original BNCI MAT files, nine people, both sessions, 108 labelled motor-imagery runs and 5,184 four-class trials. The hand subset comprises 2,592 trials. Provider flags remain annotations: the primary population includes the 488 flagged four-class and 246 flagged hand trials. Unflagged and session summaries are sensitivity descriptions rather than a replacement population. All 18 originals matched their archived source SHA-256 and byte counts; raw schema, labels, artifact flags, finite samples, all 5,184 event identities and complete windows passed the metadata gate. All 228,096 trial-channel-band rows were eligible, with no nonfinite or nonpositive power failure. No trial, person or required session was excluded.

Native sample rate is 250 Hz. MATLAB one-based trial starts are converted by subtracting one; the imagery cue is 500 samples later. Baseline cue [−1.5,−0.5) s corresponds to native trial-start offsets [125,375), while task cue [0.5,2.5) s corresponds to [625,1125). Both windows must stay in the same native labelled run. Previous nominal imagery ends at cue +4 s; the metadata gate checks separation from that interval and treats first trials separately. Those checks establish nominal timing feasibility, not observed physiological recovery or independently recorded rest.

Use the provider-ordered 22 EEG columns, excluding three EOG columns: Fz, FC3, FC1, FCz, FC2, FC4, C5, C3, C1, Cz, C2, C4, C6, CP3, CP1, CPz, CP2, CP4, P1, Pz, P2 and POz. This montage is documented from the provider, not supplied as individual MAT column-name strings. C3, Cz and C4 occupy zero-based columns 7, 9 and 11. Native signals receive no additional digital bandpass, notch, resampling, CAR, source scaler or learned projection. Provider acquisition filtering and reference remain part of the recordings. Numeric amplitudes are not newly authenticated physical microvolts; PSD has native-numeric squared per Hz units, integrated powers native-numeric squared units, and the task/baseline log ratio is dimensionless dB.

Welch uses float64 samples; a one-second 250-sample periodic Hann taper (fftbins=True); 125-sample overlap; 250-point FFT; per-segment linear detrending; one-sided density scaling; and arithmetic segment averaging. The frequency grid is 1 Hz. Integrate inclusive 8–13-Hz mu and 13–30-Hz beta masks using trapezoidal integration in Hz. The common 13-Hz endpoint supplies half-bin weights to each adjacent band integral rather than a duplicated full-bin sum. Every trial/channel/band requires finite, strictly positive baseline and task power. Invalid pairs are reported explicitly; no arbitrary epsilon, clipping or outcome-based window changes are permitted.

The trial metric is 10 log10(Ptask/Pbaseline). Negative estimates mean lower task power relative to this window and estimator; positive estimates mean higher power. First average trial dB within person × session × class × channel × band, then average the two sessions equally within person, and then weight people equally. This averages log ratios and differs from the logarithm of mean powers. Preserve per-trial powers and validity, session means, person means and medians. Hand-specific C3/C4 eligibility is paired. Four-class, flagged/unflagged and session summaries remain descriptive.

The baseline has one Welch segment and the task three overlapping segments, with different estimator variances. Because the logarithm is concave, this difference can produce a positive dB offset even when stationary power is unchanged; overlap also correlates the task segments. The ratio is therefore a fixed-window descriptive estimate, not an unbiased ERD estimator or a mechanistic test. The baseline was not redesigned after results were inspected.

The signed hand descriptor is L = 0.5 × [(C3right − C4right) + (C4left − C3left)], calculated from the person-level dB means. A negative descriptor means relatively more negative contralateral than ipsilateral change; it can occur through ipsilateral increases without absolute contralateral suppression. Report the four constituent values, contralateral/ipsilateral means and Cz alongside it. Neither scalp topography nor this descriptor localizes a cortical source or proves that EEGNet uses the depicted signals. Relative ratios cancel only a constant multiplicative gain; they do not repair reference, timing, montage or artifact assumptions.

The primary contextual association uses each person's already saved three-seed mean balanced accuracy for the Q14-E001 matched-binary BNCI LOSO broad EEGNet. Shared EEGNet and CSP are retained as context, giving six Spearman coefficients across three fixed models and two fixed bands. Every person contributes 288 binary trials to that archived endpoint. All-nine-source fitted models and external outcomes are ineligible for this association. There are no physiological p-values, tertiles, high/low-accuracy groups, decoder correctness strata, favourable-person exclusions or model/band selection by correlation. Nine people remain nine person-level records despite seeds, sessions and trials, and overlapping LOSO source sets limit independence. The decoder uses cue [0.5,3.5) s while Q16 uses [0.5,2.5) s.

Scalp maps use a frozen schematic standard-1020 geometry for all 22 sensors, anterior upward and left scalp on viewer left, with linear triangulation restricted to the sensor convex hull. All hand/band maps share symmetric −6 to +6 dB colour limits; outside-hull regions remain blank and actual clipping counts are reported. Template positions are not digitized participant anatomy. Show C3/Cz/C4 person values, both-band laterality distributions and all nine broad-score association points; shared/CSP contexts remain in tables or supplement. No separately unspecified time-frequency method is introduced after outcomes are inspected.

A separate numerical review passed before manuscript insertion. The controlling parameter freeze is commit 050e01b028aaab8e3d745934b13b2d17e9bb0a7a, published and read back before raw-power execution on 6 October 2026. Its preprocessing_freeze.json SHA-256 is c07a25e5de0c608cf405e728c0c85d1e0fae74e8e916d36e2cffad17d2ee3c01. The complete execution run_manifest.json binds the scripts, native input receipt and 11 output artifacts; its SHA-256 is 2fe8b8d1df751c440f35c7311691220668857d45ecac6734220fb12c8dc379d5. Exact bindings are preserved with the freeze/readback, raw receipt, metadata audit, execution manifest and independent_validation.json in evidence/q16_analysis/. This repository freeze follows known decoder outcomes and is not independent preregistration.

Independent raw spectral replay covered every C3/Cz/C4 trial-band pair: 31,104 pairs and 62,208 baseline/task comparisons. An independently written closed-form linear detrend, explicit periodic Hann taper, NumPy real FFT, one-sided periodogram scaling and manual trapezoid integration reproduced the fixed estimator. Maximum relative power difference was 1.847193004695259e-15; maximum absolute dB difference was 7.105427357601002e-15, within the fixed 1e-10 tolerances. This raw FFT replay covers the three central channels rather than all 22 spectra. All 228,096 output rows had their identities and eligibility checked, and every saved session, person, artifact-stratum, laterality and six-coefficient association table was recomputed (aggregation absolute tolerance 1e-11). The saved-performance review rechecked 63 Q14 prediction files, 18,144 prediction rows and 135 source-only LOSO fit manifests. It loaded no model and generated no prediction. This is computational validation of the fixed descriptive estimator, not a new external experiment or independent laboratory replication.

The completed equal-person hand summaries are:

**Methods table M1. Equal-person hand power summaries.**

| Band | Mean contralateral dB | Mean ipsilateral dB | Mean signed L dB | Person L range dB | Negative / positive people |

| --- | --- | --- | --- | --- | --- |

| Mu, 8–13 Hz | −0.308011 | −0.058326 | −0.249685 | −1.432246 to +0.336434 | 6 / 3 |

| Beta, 13–30 Hz | −0.439499 | −0.271624 | −0.167875 | −0.519318 to +0.132853 | 8 / 1 |

Values repeat the independently checked Q16 results; no additional analysis is performed.

Both group absolute components were negative, but this was not true for every person. S2 illustrates the distinction: mu L was −0.202912 dB while contralateral and ipsilateral changes were +1.490894 and +1.693806 dB. Session, hand and flagged/unflagged cells remain available in the independently checked tables; these records do not establish artifact-free physiology or replace the primary all-trial population. The scalp-map export receipt records zero sensor and interpolated-grid values clipped by the fixed ±6-dB scale in each of the four hand/band maps.

All six signed physiology–accuracy Spearman coefficients are reported without p-values:

**Methods table M2. All descriptive physiology–accuracy coefficients.**

| Saved Q14-E001 binary LOSO model | Mu rho | Beta rho | People |

| --- | --- | --- | --- |

| Broad EEGNet, designated descriptive endpoint | −0.150000 | +0.600000 | 9 |

| Shared mu/beta EEGNet, context | −0.083333 | +0.483333 | 9 |

| CSP4+LDA, context | +0.066667 | +0.316667 | 9 |

Values repeat the independently checked Q16 results; no additional analysis is performed.

Positive beta rho associates higher balanced accuracy with a larger, less-negative signed laterality descriptor. It therefore does not indicate that stronger relative contralateral suppression improved balanced accuracy. The same nine people appear in all six panels, without exclusions, fitted lines, p-values or subgroup thresholds. Figures use the independently verified table values, with input/output hashes in evidence/figures_q16.json.

This signal analysis adds zero decoder fits and zero checkpoint-inference rows, and does not modify archived decoder checkpoints, predictions, statistical plans or tests. External physiology was not computed. The nine-person associations remain post-decoder-outcome descriptive context and do not localize cortical sources, establish decoder attribution or validate a biomarker.

### S11. Post-submission archived-output CSP diagnostic audit

This section adds a read-only audit of already frozen predictions. No model was loaded, no new source model was fitted, no target input transform was estimated and no prediction inference was run for this revision. A separate supplied technical report dated 10 October 2026 describes new source fits and mean-centering operations; its claims are distinguished from independently traceable evidence in Revision_Issue_Matrix.md. It is not a formal journal decision or proof that every implementation error has been excluded.

**Table S5. Archived CSP diagnostic summaries and aggregation units.**

| Cohort | Persons / trials | Mean person BA (%) | Pooled BA (%) | Pooled left predictions (%) | Median stored p(left) |

| --- | --- | --- | --- | --- | --- |

| Cho2017 | 52 / 10,520 | 51.99 | 51.98 | 92.07 | 0.669 |

| Lee2019 | 54 / 10,800 | 52.77 | 52.77 | 83.21 | 0.633 |

Values reconstruct unchanged saved CSP outputs. Cho trials differ between people, so its pooled and equal-person means differ. These diagnostic summaries are not new confirmatory tests or calibration estimates. Full precision is retained in the diagnostic audit JSON and participant CSV.

Pooled confusion counts have rows actual left/right and columns predicted left/right: Cho2017 actual-left row (4947,313) and actual-right row (4739,521); Lee2019 actual-left row (4643,757) and actual-right row (4344,1056). S1 Data includes every participant confusion matrix and the audit script. Stored labels agree with argmax of the two original probability columns. All 52 source-bound and 221 external-bound files match their archived validation digests. These checks assess declared numerical consistency, not biological truth of every acquisition assumption.

For exhaustive binary classes, complementing predicted labels yields BA_complement = 1 − BA_original. Cho gives 48.0096153846% with equal-person weighting and 48.0228136882% when pooling trials; Lee gives 47.2314814815% for both. The supplied report’s Cho 48.02% is compatible with trial pooling, whereas its Lee 47.22% is not the rounding of these frozen files (47.23%). No complement was selected or saved as a new primary predictor. Inspecting target outcomes to choose a label flip would be target-driven tuning.

The supplied technical report describes source resubstitution, a newly fitted nine-fold source LOSO assessment and post hoc mean-centred target-input processing. Those new scores are not included as verified scientific results here because source prediction files, fit/partition manifests, computation code, hashes and the exact centering rule were not supplied. The report-reported numbers and missing artifacts are enumerated in Revision_Issue_Matrix.md. Resubstitution does not establish held-out transfer. New LOSO evaluation requires additional source fitting; target-input centering estimates a transform from targets and changes the original information budget even without labels. None of these claims replaces a frozen endpoint or supports a proved CSP failure mechanism.

The earlier, separately frozen binary source CSP LOSO result is 61.5354938272% under its 22-channel preprocessing. It is not the new reported 21-channel result and must not be relabelled as evidence for the latter. Cho’s electrode row order remains based on the published numbered montage rather than payload channel-name strings. Matching preprocessing functions and successful replay do not independently resolve original reference, voltage calibration or hardware cue latency.

### S12. Internal identifiers and manuscript traceability

**Table S6. Semantic descriptions and archived experiment identifiers.**

| Manuscript description | Archived identifier | Existing record root |

| --- | --- | --- |

| traditional-baseline | Q4 | outputs/Q4-E001/ |

| mean-loss development | Q5 | results/Q5-E001/ |

| source-normalization | Q6 | research_runs/Q6-E001/ |

| single-person duration diagnostic | Q7 | research_runs/Q7-E001/ |

| mean-rank follow-up | Q8 | research_runs/Q8-E001/ |

| spectral-input control | Q9 | results/Q9-E001/ |

| spatial-projection control | Q10 | results/Q10-E001/ |

| architecture control | Q11 | results/Q11-E001/ |

| robustness | Q12 | results/Q12-E001/ |

| matched-runtime/source-composition | Q13 | results/Q13-E001/ |

| earlier PhysioNet/binary-source | Q14 | results/Q14-E001/ |

| Cho2017/Lee2019 transfer | Q15 | results/Q15-E005/; results/Q15-EXTERNAL/Q15-E006/; results/Q15-EXTERNAL/Q15-E007/ |

| BNCI physiology | Q16 | research_runs/Q16-P001-BNCI-20261006/ |

Representative existing paths are listed; related validation/control records are retained in the original experiment inventory. No historical identifier or script is renamed. P1/P2 in the 21-channel montage are electrode names, not experiment labels.

### S13. Primary-literature protocol comparison

The literature audit distinguishes unseen-person and unseen-dataset transfer from pooled-window splits, within-person prediction and target-adapted models. Primary papers support architectural and information-budget context, not a SOTA leaderboard. The formal 2024 journal version of the divergence study supersedes its 2023 preprint title/year; the formal 2022 BEETL publication is distinct from the competition year. Zhang’s detailed calibration protocol could not be verified from accessible full text, and its inclusion supports only the indexed original abstract’s target fine-tuning statement.

SMMTM and RMETNet are formally published PLOS ONE examples [28,29]. The accuracy-cost paper (DOI 10.1371/journal.pone.0234178) was reviewed as a selected-participant, within-person compute/selection study and was not used as a quantitative external baseline. The metadata and protocol evidence matrix retains all nine requested works, including papers not needed as main-text comparators.

## References

1. Brunner C, Leeb R, Müller-Putz GR, Schlögl A, Pfurtscheller G. BCI Competition 2008 – Graz data set A. Official competition dataset description. 2008. Available from: https://www.bbci.de/competition/iv/desc_2a.pdf [cited 2026 Oct 8].
2. Tangermann M, Müller KR, Aertsen A, Birbaumer N, Braun C, Brunner C, et al. Review of the BCI Competition IV. Front Neurosci. 2012;6. doi:10.3389/fnins.2012.00055
3. Jayaram V, Barachant A. MOABB: trustworthy algorithm benchmarking for BCIs. J Neural Eng. 2018;15(6):066011. doi:10.1088/1741-2552/aadea0
4. Lotte F, Bougrain L, Cichocki A, Clerc M, Congedo M, Rakotomamonjy A, et al. A review of classification algorithms for EEG-based brain–computer interfaces: a 10 year update. J Neural Eng. 2018;15(3):031005. doi:10.1088/1741-2552/aab2f2
5. Schalk G, McFarland DJ, Hinterberger T, Birbaumer N, Wolpaw JR. EEG Motor Movement/Imagery Dataset. dataset. 2009. doi:10.13026/C28G6P
6. Schalk G, McFarland DJ, Hinterberger T, Birbaumer N, Wolpaw JR. BCI2000: A General-Purpose Brain-Computer Interface (BCI) System. IEEE Trans Biomed Eng. 2004;51(6):1034-1043. doi:10.1109/TBME.2004.827072
7. Cho H, Ahn M, Ahn S, Kwon M, Jun SC. EEG datasets for motor imagery brain–computer interface. GigaScience. 2017;6(7). doi:10.1093/gigascience/gix034
8. Cho H, Ahn M, Ahn S, Kwon M, Jun SC. Supporting data for "EEG datasets for motor imagery brain computer interface". dataset. 2017. doi:10.5524/100295
9. Lee MH, Kwon OY, Kim YJ, Kim HK, Lee YE, Williamson J, et al. EEG dataset and OpenBMI toolbox for three BCI paradigms: an investigation into BCI illiteracy. GigaScience. 2019;8(5). doi:10.1093/gigascience/giz002
10. Lee MH, Kwon OY, Kim YJ, Kim HK, Lee YE, Williamson J, et al. Supporting data for "EEG Dataset and OpenBMI Toolbox for Three BCI Paradigms: An Investigation into BCI Illiteracy". dataset. 2019. doi:10.5524/100542
11. Gulrajani I, Lopez-Paz D. In Search of Lost Domain Generalization. International Conference on Learning Representations. 2021. Available from: https://iclr.cc/virtual/2021/poster/2998 [cited 2026 Oct 8].
12. Ramoser H, Muller-Gerking J, Pfurtscheller G. Optimal spatial filtering of single trial EEG during imagined hand movement. IEEE Trans Rehabil Eng. 2000;8(4):441-446. doi:10.1109/86.895946
13. Ang KK, Chin ZY, Wang C, Guan C, Zhang H. Filter Bank Common Spatial Pattern Algorithm on BCI Competition IV Datasets 2a and 2b. Front Neurosci. 2012;6. doi:10.3389/fnins.2012.00039
14. Ang KK, Chin ZY, Zhang H, Guan C. Filter Bank Common Spatial Pattern (FBCSP) in Brain-Computer Interface. 2008 IEEE International Joint Conference on Neural Networks (IEEE World Congress on Computational Intelligence). 2008:2390-2397. doi:10.1109/IJCNN.2008.4634130
15. Lawhern VJ, Solon AJ, Waytowich NR, Gordon SM, Hung CP, Lance BJ. EEGNet: a compact convolutional neural network for EEG-based brain–computer interfaces. J Neural Eng. 2018;15(5):056013. doi:10.1088/1741-2552/aace8c
16. Schirrmeister RT, Springenberg JT, Fiederer LDJ, Glasstetter M, Eggensperger K, Tangermann M, et al. Deep learning with convolutional neural networks for EEG decoding and visualization. Hum Brain Mapp. 2017;38(11):5391-5420. doi:10.1002/hbm.23730
17. Zhong XC, Wang Q, Liu D, Chen Z, Liao JX, Sun J, et al. EEG-DG: A Multi-Source Domain Generalization Framework for Motor Imagery EEG Classification. IEEE J Biomed Health Inform. 2025;29(4):2484-2495. doi:10.1109/jbhi.2024.3431230
18. Zheng Y, Wu S, Chen J, Yao Q, Zheng S. Cross-Subject Motor Imagery Electroencephalogram Decoding with Domain Generalization. Bioengineering (Basel). 2025;12(5):495. doi:10.3390/bioengineering12050495
19. Jiang WB, Zhao LM, Lu BL. Large Brain Model for Learning Generic Representations with Tremendous EEG Data in BCI. The Twelfth International Conference on Learning Representations. 2024. Available from: https://openreview.net/forum?id=QzTpTRVtrP [cited 2026 Oct 8].
20. Wang G, Liu W, He Y, Xu C, Ma L, Li H. EEGPT: Pretrained Transformer for Universal and Reliable Representation of EEG Signals. Advances in Neural Information Processing Systems. 2024;37. doi:10.52202/079017-1239
21. Pfurtscheller G, Lopes da Silva FH. Event-related EEG/MEG synchronization and desynchronization: basic principles. Clin Neurophysiol. 1999;110(11):1842-1857. doi:10.1016/s1388-2457(99)00141-8
22. Pfurtscheller G, Neuper C. Motor imagery activates primary sensorimotor area in humans. Neurosci Lett. 1997;239(2-3):65-68. doi:10.1016/s0304-3940(97)00889-6
23. Roots K, Muhammad Y, Muhammad N. Fusion Convolutional Neural Network for Cross-Subject EEG Motor Imagery Classification. Computers. 2020;9(3):72. doi:10.3390/computers9030072
24. Luo J, Li J, Mao Q, Shi Z, Liu H, Ren X, et al. Overlapping filter bank convolutional neural network for multisubject multicategory motor imagery brain-computer interface. BioData Min. 2023;16(1):19. doi:10.1186/s13040-023-00336-y
25. Smedemark-Margulies N, Wang Y, Koike-Akino T, Liu J, Parsons K, Bicer Y, et al. Improving subject transfer in EEG classification with divergence estimation. J Neural Eng. 2024;21(6):066031. doi:10.1088/1741-2552/ad9777
26. Zhang K, Robinson N, Lee SW, Guan C. Adaptive transfer learning for EEG motor imagery classification with deep Convolutional Neural Network. Neural Netw. 2021;136:1-10. doi:10.1016/j.neunet.2020.12.013
27. Wei X, Faisal AA, Grosse-Wentrup M, Gramfort A, Chevallier S, Jayaram V, et al. 2021 BEETL Competition: Advancing Transfer Learning for Subject Independence and Heterogenous EEG Data Sets. Proc Mach Learn Res. 2022;176:205–219. Available from: https://proceedings.mlr.press/v176/wei22a.html [cited 2026 Oct 10].
28. Cao D, Yu Z, Wang J, Wu Y. SMMTM: Motor imagery EEG decoding algorithm using a hybrid multi-branch separable convolutional self-attention temporal convolutional network. PLOS ONE. 2025;20(10):e0333805. doi:10.1371/journal.pone.0333805
29. Zhao Y, He D, Ren F, Xia Q, Xu L, Xie G, et al. RMETNet: A cross-subject motor imagery EEG signal classification model based on TSLANet and riemannian geometry features. PLOS ONE. 2026;21(4):e0347671. doi:10.1371/journal.pone.0347671
30. Sonntag J, Yu L, Wang X, Schack T. Neurophysiological predictors of deep learning based unilateral upper limb motor imagery classification. Front Hum Neurosci. 2025;19:1617748. doi:10.3389/fnhum.2025.1617748
31. Sagawa S, Koh PW, Hashimoto TB, Liang P. Distributionally Robust Neural Networks for Group Shifts: On the Importance of Regularization for Worst-Case Generalization. International Conference on Learning Representations. 2020. Available from: https://openreview.net/forum?id=ryxGuJrFvS [cited 2026 Oct 8].
32. Efron B. Bootstrap Methods: Another Look at the Jackknife. Ann Stat. 1979;7(1). doi:10.1214/aos/1176344552
33. Winkler AM, Ridgway GR, Webster MA, Smith SM, Nichols TE. Permutation inference for the general linear model. Neuroimage. 2014;92:381-397. doi:10.1016/j.neuroimage.2014.01.060
34. Holm S. A Simple Sequentially Rejective Multiple Test Procedure. Scand J Stat. 1979;6(2):65–70. Available from: https://www.jstor.org/stable/4615733 [cited 2026 Oct 8].
35. Goldberger AL, Amaral LAN, Glass L, Hausdorff JM, Ivanov PC, Mark RG, et al. PhysioBank, PhysioToolkit, and PhysioNet: Components of a New Research Resource for Complex Physiologic Signals. Circulation. 2000;101(23). doi:10.1161/01.CIR.101.23.e215
36. Pollard T, Moody BE, Lehman LwH, Gow BJ, Fernandes C, Xie C, et al. PhysioNet as a global platform for biomedical research. Nat Health. 2026;1(8):792-795. doi:10.1038/s44360-026-00096-z
