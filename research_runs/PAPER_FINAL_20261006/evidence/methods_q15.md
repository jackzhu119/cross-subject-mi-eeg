# Q15 implemented-methods audit

This record describes the executed adapter, not the initial planning shorthand. The scientific source is the committed execution contract and its byte-bound processing code. No new fitting, inference, or raw-data download was performed for this manuscript audit.

## Input and source-only model policy

Q15 used 21 ordered EEG channels at **160 Hz**, yielding **320 samples over the cue-relative half-open interval [0.5, 2.5) s**. It was a separately trained model family; the frozen Q14 PhysioNet models instead accepted 22 channels and 480 samples over [0.5,3.5) s. Q14 and Q15 cannot be described as one unchanged-model experiment, nor combined into a single external significance test.

The Q15 channel order was Fz, FC3, FC1, FC2, FC4, C5, C3, C1, Cz, C2, C4, C6, CP3, CP1, CPz, CP2, CP4, P1, Pz, P2, POz. FCz was removed from the BNCI montage. No missing channel was interpolated.

Source training retained all 2,592 binary left/right BNCI trials across nine persons and both sessions, including 246 artifact-flagged trials. The two neural conditions used the same configured EEGNet (F1=8, D=2, F2=16, temporal kernel=64, dropout=.25), Adam (.001), batch size 64, zero weight decay and cross-entropy. The shared mu/beta condition passed both fixed band views through one network and averaged logits before loss or softmax; there were no independent band networks, attention weights or target-statistic updates.

Four source-person validation groups ([1,2], [3,4], [5,6], [7,8,9]) selected the training duration from 40 epochs. CE values were ranked within each group, ranks averaged equally between groups, and the earliest minimizing epoch chosen. Broad and shared models selected 14 and 19 epochs, respectively. Three final seeds were fixed at 20260924, 20260925 and 20260926. The total 15 source fits comprised eight inner neural fits, six final neural fits and one CSP fit. The migration reused these fits and created zero new source or target fits.

## Retained external cohort

Cho2017 retained 52 persons and 10,520 imagery trials from `imagery_left` and `imagery_right`. Subjects 7,9,46 provided 120 trials per class; the remaining persons provided 100. Only the first 64 EEG rows of the 68-row native arrays were eligible; the four EMG rows were excluded. The MAT arrays lack native electrode labels, so the predeclared row map followed the original paper's numbered Figure 1 montage. This is a reviewed mapping assumption, not an independently measured electrode map. Original physical run identities could not be reconstructed. Seven-second retained chunks and nonzero imagery-event markers defined operational trial identities.

Lee2019_MI retained 54 persons, both sessions, 108 original files and 10,800 trials. **Only the offline `EEG_MI_train` fields were evaluated**: 100 labeled trials per file, 50 per class. The `EEG_MI_test`, ERP and SSVEP fields were excluded by design. Native code 1=right and code 2=left were remapped to canonical right=2 and left=1. The declared MATLAB cue convention was `t-1`; the supplied `smt` segments aligned to Python `x[t:t+4000]`, a one-native-sample (1 ms) discrepancy disclosed without outcome-based adjustment. This analysis is not an evaluation of every available OpenBMI MI trial.

## Uniform operational preprocessing

Each trial used the complete six-second native context [-1.5,4.5) s. After selecting the fixed 21 channels, common-average referencing was applied at each sample. Broad (8–30 Hz), mu (8–13 Hz) and beta (13–30 Hz) contexts were filtered separately at each dataset's native rate (BNCI250, Cho512, Lee1000 Hz) using a fourth-order Butterworth prototype implemented as four SOS sections and forward-backward filtering with odd padding of 27 native samples. Polyphase anti-aliased resampling (`resample_poly`, Kaiser beta5, constant zero padding) produced 960 context samples at160 Hz; [320:640] was cropped to the final epoch. Only final tensors were cast to float32. Cho's artificially concatenated trial chunks were never filtered across chunk boundaries. Missing context, nonfinite values, class-map disagreement or schema mismatch caused an abort rather than silent exclusions.

No baseline correction, target normalization, alignment, fitted target transform or target channel interpolation was used. The reference operation is predetermined by channel count and is not target fitting. The broad CSP comparator first applied fixed Helmert coordinates for the rank20 CAR subspace, then source-fitted CSP4 (`reg=None`, `cov_est=concat`, `rank=full`, log-power, no trace normalization), source-fitted StandardScaler and SVD LDA. The basis is fixed analytically; it is not estimated from target data.

## Estimands and inference

For each model seed, Lee's two sessions were pooled within person before balanced accuracy was computed. Each person's three neural seed scores were then averaged; probabilities were not pooled into an ensemble. Cohort means gave every person equal weight. The primary contrast was shared-minus-broad balanced accuracy, separately for the two cohorts. Seeds, trials and sessions were not counted as independent persons.

Paired-person percentile bootstrap confidence intervals used 20,000 draws (seed20260924). Two-sided paired-person sign flips used 20,000 Monte Carlo draws (seed20261003) and `(extreme+1)/20001`. Holm adjustment covered exactly the two predeclared cohort tests. CSP comparisons, session breakdowns and other within-person summaries are contextual/descriptive unless separately labeled exploratory. Sign-flip inference assumes sign exchangeability of person-level paired effects under the null; it is not proof that heterogeneous acquisition settings are experimentally randomized.

## Timing and claim boundaries

The pre-fit freeze was committed at2026-10-04 01:33:03 UTC (`fc0e7d54`), before source completion at01:52:42 UTC. The separate inference and statistical freeze was committed at2026-10-05 09:31:05 UTC (`2ad479f5`), before inference completion at10:57:19 UTC. Complete metadata and primary-source review informed the processing amendment; it is false to call the adapter blind to raw metadata, externally preregistered, or independent of all prior project findings. The historical plan files were preserved while the explicit six-second trial-context/CAR amendment governed execution.

The calibrated wording is: **Q15 evaluates a prospectively fixed operational adapter under a native-numeric-as-microvolt convention. Native export voltage calibration, the original Cho acquisition reference, and hardware cue latency were not independently verified.** Common-average referencing cannot recover an unknown original hardware reference or prove physical voltage equivalence. Zero-phase filtering and full six-second contexts also make this an offline benchmark; online causal latency or clinical performance was not tested.

The inference-completion receipt intentionally remained `inference_complete_pending_independent_raw_prediction_replay`; completed scientific validation is established by the separate final `validation_report.json`, whose status is `completed_with_calibration_limitations`, with original metadata, raw-to-epoch tensors, frozen predictions and statistics replayed. Software replay guards implementation consistency; it is not independent laboratory replication.
