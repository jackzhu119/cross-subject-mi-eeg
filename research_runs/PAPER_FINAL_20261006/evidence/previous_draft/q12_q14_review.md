# Executed Q12–Q14 evidence review

Review date: 2026-10-02; local Git `edf68d6edc524af3f48d1c154c3585e59ca4bf98` includes published Q13-E006 receipt commit `adb2d406`. Frozen experiment files were read only. No model was trained, preprocessed or replayed in this review. Existing raw/checkpoint validations are historical evidence; current review verifies artifact hashes and saved CSV arithmetic.

## Paper inclusion

Include complete Q12-E001/E002, Q13-E001/E004/E005/E006, Q14-E001 matched-binary development and final Q14-E002R2 external result. Exclude unrun/superseded Q13-E002/E003 and Q14-E003, and all prospective/data-only external-cohort work. Prepared/planned wording in protocol snapshots is historical; current passing receipts control eligibility. Do not count R1 and R2 as different external cohorts.

Four-class BNCI results are exploratory on nine already examined people. Q14 PhysioNet is independent external evidence, with a disclosed metadata amendment and an uncertain predeclared primary contrast. BA percentages and percentage-point differences are distinct. Binary and four-class BA cannot be directly compared.

## Q12 robustness: all arms complete and scientifically audited

Nine people, both target sessions, four classes, 5,184 unique trials, 576 trials/person. Three seeds averaged within person. Historical validator passed 216 inner + 162 final fits and 162 raw/checkpoint reconstructions; child audit checked 2,061 artifact hashes, all intact.

| Condition | Mean BA (%) | Comparator | Difference (pp) | Unadjusted bootstrap95%CI (pp) | Exploratory p | Holm p |
|---|---:|---|---:|---|---:|---:|
| SOURCE_POOLED_WHITEN | 44.3351 | Q8-E001 | +1.6654 | [-0.3922, +3.6651] | 0.179688 | 0.359375 |
| SOURCE_BALANCED_ERM | 43.1842 | Q8-E001 | +0.5144 | [-0.7073, +1.7747] | 0.476562 | 0.476562 |
| SOURCE_GROUP_DRO | 36.7348 | SOURCE_BALANCED_ERM | -6.4493 | [-11.4712, -1.7876] | 0.046875 | 0.140625 |
| CHANNEL_DROPOUT | 41.0044 | Q8-E001 | -1.6654 | [-4.5076, +0.6366] | 0.300781 | 0.761719 |
| GAIN_PERTURB | 43.4221 | Q8-E001 | +0.7523 | [-0.3408, +1.8583] | 0.253906 | 0.761719 |
| CHANNEL_AND_GAIN | 40.9208 | Q8-E001 | -1.7490 | [-5.0540, +0.9131] | 0.351562 | 0.761719 |

Correct frozen Q8 baseline mean BA: 42.6698%, from its 27 all-trial subject-seed rows. Never average the flagged/unflagged strata together. No Q12 contrast survives Holm. DRO-minus-balanced ERM matches runtime/sampler/update budget; Q12-minus-reused-Q8 lacks a same-runtime ordinary ERM retraining control and cannot cleanly attribute differences to a method. Preserve class collapse and whitening's single-class seed.

## Q13 sensitivity: old no-results status is stale

E001/E004/E005 completed; historical scientific report passed 837 checkpoint/raw prediction replays and 482,112 saved predictions. E006 completed; passed 27 replays / 15,552 predictions. This review verified 5,022 original and 162 E006 per-fit artifact hashes, re-scored saved final predictions/argmax/576 unique IDs, reconstructed subject means and all 11 contrasts; no model was loaded for fresh inference.

| Selection arm | Mean subject BA (%) |
|---|---:|
| Q8_FIXED20 | 43.9879 |
| Q8_RAW_CE_REUSE_Q5 | 33.7191 |
| Q9_SHARED_FIXED20 | 43.9751 |
| Q9_SHARED_RAW_CE | 40.0656 |
| Q8_RAW_CE_MATCHED (E006) | 33.9249 |

| Method | k=2 BA (%) | k=4 | k=6 | k=8 |
|---|---:|---:|---:|---:|
| Q8_BROAD | 32.9572 | 38.8905 | 43.1552 | 43.9879 |
| Q9_MU_BETA_SHARED | 34.7431 | 38.8889 | 42.4849 | 43.9751 |

Four source subsets × three seeds are averaged inside each target at k = 2/4/6. Natural updates360/720/1080/1440 and source trials1152/2304/3456/4608 at k = 2/4/6/8 jointly change source count and data exposure. Source-session means: Q8_BROAD 0train=42.2454%; Q8_BROAD 1test=41.4030%; Q9_MU_BETA_SHARED 0train=41.8081%; Q9_MU_BETA_SHARED 1test=41.8917%. Single-session conditions have 2,304 source trials and 720 updates; both target sessions remain held out.

| Exploratory contrast | Difference (pp) | Unadjusted bootstrap95%CI (pp) | Raw p | Family Holm p |
|---|---:|---|---:|---:|
| Q8_BROAD_k2_minus_k8 | -11.0307 | [-18.7951, -3.5604] | 0.031250 | 0.164062 |
| Q8_BROAD_k4_minus_k8 | -5.0974 | [-10.3604, -0.3826] | 0.144531 | 0.433594 |
| Q8_BROAD_k6_minus_k8 | -0.8327 | [-3.6716, +1.8889] | 0.566406 | 0.566406 |
| Q9_MU_BETA_SHARED_k2_minus_k8 | -9.2319 | [-15.4145, -3.1459] | 0.027344 | 0.164062 |
| Q9_MU_BETA_SHARED_k4_minus_k8 | -5.0862 | [-9.2834, -1.3085] | 0.058594 | 0.234375 |
| Q9_MU_BETA_SHARED_k6_minus_k8 | -1.4902 | [-3.4127, +0.4163] | 0.167969 | 0.433594 |
| Q8_BROAD_1test_minus_0train | -0.8423 | [-1.8904, +0.1931] | 0.175781 | 0.351562 |
| Q9_MU_BETA_SHARED_1test_minus_0train | +0.0836 | [-1.1381, +1.1833] | 0.851562 | 0.851562 |
| Q8_FIXED20_minus_Q8_RAW_CE_REUSE_Q5 | +10.2688 | [+0.9581, +21.6244] | 0.101562 | 0.156250 |
| Q9_SHARED_FIXED20_minus_Q9_SHARED_RAW_CE | +3.9095 | [+0.4437, +7.6198] | 0.078125 | 0.156250 |
| Q8_E006_RAW_CE_minus_Q8_FIXED20 | -10.0630 | [-21.5284, -0.6752] | 0.125000 | 0.125000 |

Historical Q5 reuse remains cross-runtime descriptive. E006 matches fixed20 Python/platform/packages/CUDA/GPU and all 18 raw-file receipts, changing only the historical source-only duration schedule without rerunning inner selection. E006-minus-fixed 20: −10.0630 pp, bootstrap CI [−21.5284, −0.6752] pp, sign-flip p = .125. Preserve interval and p; do not infer significance from interval exclusion alone. All 11 family-Holm p-values exceed .05.

## Q14: binary development and independent external cohort

BNCI binary development: 9 people / 2,592 trials. Mean subject BA: BROAD_EEGNET 68.2099%, CSP4_LDA 61.5355%, MU_BETA_SHARED 67.3483%. Shared-minus-broad=-0.8616pp; additional present-review exploratory CI[-2.0705,+0.2958], sign-flip p=0.21875. This extra calculation is not the archived external primary.

External source stage froze8 inner+6 final neural fits and1 CSP fit before target access; all 7 final model hashes remain intact. Source-selected epochs: broad 18 / shared 17. Source validation checks metadata/manifests/CE epoch selection/model hashes/saved development predictions; do not describe it as independent raw/checkpoint inference replay.

| PhysioNet model | Mean subject BA (%) |
|---|---:|
| BROAD_EEGNET | 61.8146 |
| CSP4_LDA | 54.4617 |
| MU_BETA_SHARED | 62.3879 |

109 people, runs 4/8/12, 4,918 unique trials, 34,426 saved model-seed rows, zero target fits. Primary shared-minus-broad=+0.5733pp ; 20,000-draw subject 95% CI[-0.0967,+1.2416]pp ; two-sided sign-test p=0.06446359, with 63 positive / 43 negative / 3 tied. The interval includes zero; an external advantage is not established. CSP is contextual, not the primary contrast.

R1 stopped at S088 on 128-Hz header mismatch. R2 preserves 87 byte-identical outputs and adds 22 subjects; only S088/S092/S100 resampled 128→160 Hz. The 106 native-rate people give a descriptive +0.5750 pp, and the three resampled people +0.5139 pp. Neither stratum replaces the 109-person primary.

Final authoritative report:`results/Q14-E002R2V1/validation_report.json`, portable independent external validation passed. It rechecked 327 official EDF checksums/event identities, immutable custody, saved probabilities/argmax, confusion and statistics; generated zero new inference rows. Inference RTX 4080 SUPER / PyTorch 2.8.0+cu128 and validation vGPU-32GB / PyTorch 2.8.0 run on different hosts/kernels. Disclose metadata resampling, CSV probability precision erratum and validation-portability amendment.

## Primary evidence paths and SHA-256

Full absolute paths, hashes, sizes, runtime receipts, exact effects and validation scope appear in the JSON companion.

| Source | SHA-256 |
|---|---|
| [results/Q12-BATCH/scientific_validation.json](/workspace/cross-subject-mi-eeg/results/Q12-BATCH/scientific_validation.json) | `739910ee03b008fb374c7b026bbade0dc6b6d8ef0016cda3fac19a071c53e7e6` |
| [results/Q12-BATCH/paired_subject_contrasts.json](/workspace/cross-subject-mi-eeg/results/Q12-BATCH/paired_subject_contrasts.json) | `3f32f1321ff833bc2a74b93bde40312bd4a5c96eca4b89321d8080cfadd4d97d` |
| [results/Q13-BATCH/validation_report.json](/workspace/cross-subject-mi-eeg/results/Q13-BATCH/validation_report.json) | `3d21dbb98d775a19f8328dc4ad4a5d285c6c4ee18204b22543561c4ee14a0266` |
| [results/Q13-E006/validation_report.json](/workspace/cross-subject-mi-eeg/results/Q13-E006/validation_report.json) | `ef60b412b8724dd51d648c8bc51e8f74ad5ace470bca93c0f2327ac959dd1ddd` |
| [results/Q13-E006/postrun_statistics/paired_contrasts.csv](/workspace/cross-subject-mi-eeg/results/Q13-E006/postrun_statistics/paired_contrasts.csv) | `81ef4b4236c08f1bf597cc3001bda9d0877d6cdbfcc5daf74698226bc20d0239` |
| [results/Q14-E001/validation_report.json](/workspace/cross-subject-mi-eeg/results/Q14-E001/validation_report.json) | `f96296e2dec3bb45f1eddca2deb0fa4b200f2ab3066f60e4e646232b6e414d53` |
| [results/Q14-E002/freeze_receipt.json](/workspace/cross-subject-mi-eeg/results/Q14-E002/freeze_receipt.json) | `829eb1d100781c091c4fbfb36bbc230eb3b54f9d45b3140cf3b3ed32b5008b9e` |
| [results/Q14-E002R2V1/validation_report.json](/workspace/cross-subject-mi-eeg/results/Q14-E002R2V1/validation_report.json) | `1ed3959b303c06672257963ef177f8c7ef619bcac01e4a263cfd587e7d9b5320` |
| [results/Q14-E002R2V1/external/subject_metrics.csv](/workspace/cross-subject-mi-eeg/results/Q14-E002R2V1/external/subject_metrics.csv) | `2199c89b591d7f0c87fbb02ed3fd8146e7f27c174ccd6c6bd2399db487ce5e54` |
| [results/Q14-R2PORT/completion_receipt.json](/workspace/cross-subject-mi-eeg/results/Q14-R2PORT/completion_receipt.json) | `84696c87baf1aed8b53759144ecb5d996a90f0ba62a8f0ab4478c89e13bb1be7` |

## Calculation grain and reproducibility

Use all-trial rows, arithmetic seed means inside held-out person, then equal-person mean. For Q13 saved predictions, BA is the mean of four class recalls; verify probability argmax , 576 unique trial IDs, source-target separation and every per-fit receipt artifact SHA. k2/4/6 subsets average within person before group analysis. Reconstruct 11 paired contrasts from subject tables; bootstrap with archived seeds (Q12/Q14 external 20260924, Q13/E006 20260926), enumerate 512 sign patterns at n = 9 and Holm-adjust within frozen families. Q14external sign test excludes ties. Unadjusted bootstrap intervals resample fixed subject scores, not fitted pipelines. The present review does not repeat historical raw checkpoint/EDF scientific validation.
