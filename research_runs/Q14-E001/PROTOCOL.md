# Q14-E001/E002: matched binary source development and frozen external test

Status: **protocol and code preparation only**. No PhysioNet accuracy is known from this document. Q5–Q9 are four-class and cannot be directly compared with a binary external endpoint.

## Scientific question and fixed contrasts

Does a spatial-spectral EEGNet representation transfer from BNCI2014_001 to an independent motor-imagery cohort better than a broadband EEGNet? The external *primary* paired contrast is `MU_BETA_SHARED - BROAD_EEGNET` subject-level balanced accuracy. `CSP4_LDA` is a predeclared conventional contextual comparator; do not promote whichever method wins on PhysioNet to the primary analysis. A negative or chance-level transfer result must be reported.

## Independent external population

PhysioNet EEG Motor Movement/Imagery Database v1.0.0, subjects 1–109, only runs **4, 8, 12** (imagined unilateral left/right fist). In these runs `T1=left` and `T2=right`; `T0` rest and all execution/bilateral runs are excluded. Dataset documentation: <https://physionet.org/content/eegmmidb/1.0.0/>; MNE run definitions: <https://mne.tools/stable/generated/mne.datasets.eegbci.load_data.html>. PhysioNet official montage names include all 22 BNCI EEG channels (montage: <https://physionet.org/files/eegmmidb/1.0.0/64_channel_sharbrough.pdf>); loader must still assert their exact presence in every EDF run. No target subject may be discarded or added according to classifier performance.

The target loader verifies each EDF against the dataset's official versioned `SHA256SUMS.txt` (<https://physionet.org/files/eegmmidb/1.0.0/SHA256SUMS.txt>) before using the signal. This identifies corrupted or altered local files independently of the pipeline's own output hashes.

## Harmonization locked without seeing external accuracy

BNCI labels: left=1, right=2, both sessions of all nine subjects. BNCI event anchor is trial start, cue is at +2 s; its fixed [2.5, 5.5) s window is therefore cue-relative [0.5, 3.5) s. PhysioNet T1/T2 annotations are cue onsets, so use [0.5, 3.5) s there too. Order the 22 channels exactly as the BNCI `Q8-E001/results/data_audit.csv` audit, never infer channel intersection from target outcomes. Fixed Butterworth fourth-order, 8–30 Hz for CSP and broadband EEGNet, 8–13 and 13–30 Hz for shared-band EEGNet, run-local zero-phase offline filter; no learned denoising, artifact rejection, re-referencing, or dataset-specific normalization. BNCI is 250 Hz; deterministic polyphase resampling 16/25 gives 160 Hz and 480 samples; PhysioNet is natively 160 Hz. All model inputs are fixed volts-to-microvolts conversion. **Acquisition/reference hardware, cue presentation and source/target sample-rate/filter order still differ; this is an out-of-distribution test, not a controlled scanner effect.**

## Model and fit protocol

`BROAD_EEGNET`: EEGNet (22 channels, 480 samples, 2 classes, F1=8, D=2, F2=16, kernel=64, dropout=.25), 8–30 Hz input. `MU_BETA_SHARED`: the same single shared-weight EEGNet applied separately to 8–13 and 13–30 Hz input, arithmetic mean of two logits before cross-entropy. `CSP4_LDA`: four CSP log-variance features, source-fitted scaler and LDA; 8–30 Hz. Hyperparameters are fixed, not searched on target data. EEGNet uses fixed Adam lr .001, batch 64, max 40 epochs, deterministic selection seed 20260923 and final seeds 20260924/25/26. The first minimum mean within-source-fold rank of validation CE selects duration; no target stopping.

- **Q14-E001**: BNCI binary 9-fold LOSO development. For each outer BNCI target, sort eight source IDs, hold out four consecutive two-subject inner groups, train on six. Per EEGNet condition: 9×4=36 inner fits + 9×3=27 final fits. Two conditions = **126 deep fits**. CSP4+LDA has 9 source-only outer fits. Its outer target predictions are BNCI development evidence, not a fresh independent confirmation, because BNCI has been extensively explored already.
- **Q14-E002 source-freeze stage**: four predeclared all-nine-source validation groups `[1,2]`, `[3,4]`, `[5,6]`, `[7,8,9]`; train only their complements. Per EEGNet condition 4 inner + 3 all-nine-source final fits, hence **14 deep fits** for two conditions; one all-source CSP+LDA fit. Freeze code/config hashes, data provenance, selected epochs and checkpoint hashes **before any PhysioNet signal, label, or prediction is accessed**. The target stage has **zero target fits**.
- The full Q14-E001/E002 preparation is 140 new deep and 10 shallow fits; Q14-E002 only adds 14 deep and one shallow. Trial-level and seed-level values are not independent inference units; use external subjects for paired inference.

## Stage gates and deviations

1. Commit this protocol, config and all runnable code before executing Q14-E002 source fits.
2. Run and validate Q14-E001, then Q14-E002 source-freeze; `freeze_receipt.json` must exist with hashes and validation status before the external loader is allowed to fetch/open an EDF.
3. Target evaluation writes subject/run/trial predictions, probabilities, file hashes, logs and independent validation outputs under `results/Q14-E002/`. Existing data and failures are retained; resumable jobs skip only verified complete outputs.
4. No target-label selection, pseudo-label training, target covariance/reference fit, calibration, class balancing, seed choice, or prevalence-informed threshold adjustment. Any later adaptation is a **new experiment ID** and cannot replace this frozen zero-shot result.
5. If external data integrity fails (missing channels/files/events, nonfinite signals), stop and document the failure. Do not silently exclude difficult subjects. The eligibility rule, if amended, must be frozen as a new protocol version before examining outcomes.

After zero-shot results, a distinct `Q14-E003` within-PhysioNet source-only LOSO may test cohort-level robustness, but that experiment cannot be called zero-shot BNCI-to-PhysioNet transfer and must not retune Q14-E002.
