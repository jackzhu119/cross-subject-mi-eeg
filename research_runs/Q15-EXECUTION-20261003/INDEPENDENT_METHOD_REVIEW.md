# Independent review of a prospective Q15 execution method

Status: review only, non-authorizing. No EEG preprocessing, model fitting, prediction or performance calculation occurred. `fits_started = 0`. Historical Q14 and Q15 contract files were not changed.

The proposed separate execution contract is a defensible way to run a clearly defined adapter benchmark with calibration limitations. It must not be presented as proof that the original MAT export voltage units, original Cho reference or hardware/display event timing were recovered. Real cohort audits, an immutable pre-fit contract, independent numerical replay and validated source-only model outputs remain necessary gates.

## Cohort and integrity facts independently reconciled

The actual cloud observation report contains exactly the intended 52 Cho files and 108 Lee offline MI session containers, with no failures. Recorded file IDs, sizes, SHA-256 and content MD5 match the established transport inventory. Lee's 108 content MD5 values match the official checksum list. Cho's 49 single-part ETags match content MD5. Cho s07, s09 and s46 have multipart ETags and **no independent provider content MD5**; their hashes remain transport evidence, not a missing provider MD5 recovered by reinterpretation. Current official bucket and old catalogue byte-size disagreements for s32, s46 and s49 were already recorded; bind the exact current official objects rather than silently combining snapshots.

All 52 Cho files have 512 Hz, 68 signal rows, equal left/right class array shapes, 3,584 retained samples per trial and local zero-based marker index 1,023. Subjects 7, 9 and 46 have 120 trials per class; the other 49 have 100. This is 10,520 labeled MI trials. The stored trial arrays are artificially concatenated retained windows. They are not original continuous runs.

All 108 Lee containers have 1,000 Hz, the same stored 62-channel order, 100 strictly increasing cues and 50 observations for each stored code. This is 10,800 intended offline MI trials. The preparation observer verified basic schema and count relations but did not replay the full class-label semantics, one-hot consistency, supplied-epoch alignment, context bounds or finite EEG values. Those checks must occur on the actual bytes before clearance.

The Cho paper's original Figure 1 image was independently viewed in this review. Its 64-row map agrees with the retained transcription, including C3 row 13, Cz row 48 and C4 row 50 (MATLAB one-based). The paper establishes rows 1–64 as EEG and 65–68 as EMG. The MAT lacks in-file names; applying this acquisition montage to every compatible object remains an explicit provider-montage assumption. Lee has its 62 names in every inspected MAT; FCz is absent, and all the proposed 21 channels exist.

## Proposed transform and the claims it supports

Preserve the existing 21-channel order. Use binary output codes left=1 and right=2. Lee's native sample map is right=1 and left=2; therefore validate the per-file class map and remap it, rather than comparing native codes to BNCI codes directly.

Define each dataset's cue operationally and prospectively. Cho uses the stored nonzero marker without shift; do not alter it to agree with nominal frame labels or target scores. A marker-relative [0.5,2.5) window is 1,024 native samples. A [-1.5,4.5) context is chunk-local [255,3327), exactly 3,072 samples and entirely inside its 3,584-sample retained chunk.

Lee's archived official MATLAB segmentation directly uses MATLAB x(t+offset), whose offset-zero Python representation is x[t-1]. The supplied sample `smt` is instead exactly x[t:t+4000] across all 100 trials, and its stored `ival` is 1–4000. Choose one operational rule before fit and disclose the one-sample discrepancy. The recommended t-1 rule follows the primary MATLAB indexing semantics; a supplied-epoch-aligned t rule would instead define the benchmark relative to the provided epoch anchor, not prove t is a physical zero-based cue. Full cohort alignment replay must document whether either sample finding generalizes. Do not pick a rule by prediction accuracy.

Extract the same real context [-1.5,4.5) separately for every BNCI, Lee and Cho trial. For source/Lee, verify that context stays inside a true continuous run. For Cho, verify it stays inside one retained class chunk. Apply instantaneous CAR over exactly those 21 electrodes in all cohorts, then a separately applied native-rate SOS Butterworth bandpass for broad 8–30, mu 8–13 and beta 13–30 Hz. Specify 4th-order prototype, four SOS sections (8th-order bandpass), forward/backward filtering, odd padding and 27 native padding samples. Pin the resulting coefficients at each native rate and the numerical library versions.

Resample the entire 6-second context to 160 Hz using ratios 16/25 for BNCI, 5/16 for Cho and 4/25 for Lee. Pin the Kaiser parameter, FIR implementation, constant padding value and software version. The resulting context is 960 samples; crop half-open [320,640) to obtain the common 320-sample [0.5,2.5) input. This is a new source transform: earlier run-local-filtered source checkpoints cannot be reused as if they followed this method.

Fixed common-channel CAR removes a spatially common additive reference under uniform channel gains. It neither identifies the acquisition reference nor corrects unknown nonuniform gains. Cho's paper describes CAR in its own analysis, not proof that exported arrays already have that reference. Lee's paper establishes nasion acquisition reference and AFz ground; final-export provenance remains a separate fact.

Choose `include_all`. Do not implement physical-amplitude rejection from an unresolved native unit. Do not introduce fitted target normalization or label-dependent preprocessing. An explicitly named `native_microvolt_analysis_convention` may assign unscaled native values to the model's microvolt convention, corroborated by the acquisition/toolbox chain and pinned secondary loader behavior. Keep `calibration_verified=false`, `native_export_units_verified=false` and the associated evidence limits in the freeze and final report. This is a declared adapter assumption, not a verified physical unit.

## Run identity and inference

A Cho physical run mapping is unnecessary for independently filtered retained-trial prediction and person-level inference. Use subject, dataset session, class and retained-chunk ordinal; set physical run identity to null. The supplemental chronology has no authenticated run IDs or field linking timestamps to retained chunk ordinals. Candidate 40-trial blocks may be reported as candidate metadata, never as established physical run IDs. They must not determine fitted corrections, exclusions or an independent-sample count.

Lee includes only `EEG_MI_train` in both sessions. Its online/test fields, other paradigms, EMG, noise and resting data stay outside the fixed cohort. Per-person scores can pool its two equally sized balanced sessions or average their equal-size session scores; select and freeze the exact rule. Average the three seed scores within person, then compare the two neural models across people with equal person weight. People, not trials/runs/sessions/seeds, remain independent inference units. Source selection stays BNCI-only with 14 neural fits and one shallow fit; target fits remain zero.

## Completion wording

If the full actual-byte audits and the prospective immutable contract pass before any fit, and trained checkpoints plus external predictions and person-level statistics pass independent replay, `completed_with_calibration_limitations` is an honest completion category. The paper must say that external MAT voltage calibration was unverified and operational cue conventions were prospectively defined. It must not say the historical protocol was replicated exactly, provider units were proven, timing offsets were recovered, every Cho provider MD5 existed, or physical Cho runs were reconstructed.

The companion JSON records exact evidence paths, SHA-256 pins, cohort facts, selected channel indices, assumptions and true gates. It is not a metadata clearance receipt or a pre-fit freeze.
