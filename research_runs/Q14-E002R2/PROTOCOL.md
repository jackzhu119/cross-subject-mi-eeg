# Q14-E002R2: metadata-driven continuation, not a new fitted model

Status at protocol creation: Q14-E002R1 stopped at S088 after publishing complete,
hash-addressed predictions and receipts for S001–S087. The frozen loader rejected
the first 128-Hz EDF because it assumed all external recordings were 160 Hz.
The new container also changed its kernel string from Linux 5.15.0-25 to
5.4.0-153; package/runtime fields other than `platform` must remain identical.
R1's failure and Q14-E002's original protocol are retained unchanged.

Before this amendment, the remaining 66 official PhysioNet EDF headers for
S088–S109 (runs 04, 08, 12) were inspected **without prediction values or
classification scores**. All three runs for S088, S092 and S100 declare 128 Hz;
all other remaining runs declare 160 Hz. The source models, CSP model, epochs,
seeds, channels, frequency bands, event map, model contrast, 109-subject cohort,
and evaluation metric are unchanged. [The official dataset](https://physionet.org/content/eegmmidb/1.0.0/)
describes 160-Hz recording in general; [MOABB's PhysionetMI documentation](https://moabb.neurotechx.com/docs/generated/moabb.datasets.PhysionetMI.html)
also notes the S088 exception. The runner must independently verify every EDF
against the versioned PhysioNet SHA256SUMS before accepting its metadata.

## Frozen amendment and custody gates

1. Verify the original Q14 source-freeze receipt and every frozen checkpoint.
2. Verify the R1 run configuration, its 55-subject migration receipt, exactly
   S001–S087 complete R1 subjects, all prediction/receipt SHA-256 hashes, and
   all 261 underlying EDF hashes against the official manifest. Require only
   the audited kernel string change; no package/library or GPU drift.
3. Fetch the remaining 66 imagery EDFs, verify all official hashes, channel
   metadata, and native sample rates **before any new prediction is made**.
   Require 128 Hz for S088/S092/S100 and 160 Hz for every other remaining run.
   Reject any mismatch. Save a deterministic metadata-only preflight receipt.
4. Hash-copy S001–S087 receipt/prediction pairs byte-for-byte to a new R2
   result directory. The original Q14-E002 and R1 directories are immutable.
5. For the nine checksum-verified 128-Hz runs only, apply the unchanged
   physical-Hz fourth-order run-local filter, extract the same cue-relative
   [0.5, 3.5) s epoch at the native rate (384 samples), and use the same
   `scipy.signal.resample_poly` pattern as the frozen BNCI source loader
   (5/4 along time) to create 480 samples. Event sample coordinates stay in
   native EDF samples. For 160-Hz runs, use the frozen Q14 loader unmodified.
   Do not reject subjects/trials, fit target statistics,
   use external labels to select a method, or alter thresholds.
6. Checkpoint every new subject atomically. Verify existing receipt/prediction
   hashes before skipping on restart. Auto-publish each new completed subject,
   and publish a complete or failed batch receipt at supervisor termination.

The rate harmonization is a **post-freeze, metadata-driven protocol amendment**;
do not describe the combined output as a pristine execution of the original
Q14-E002 protocol. Report the predeclared 109-subject paired contrast and the
three resampled subjects separately from the 106 native-160-Hz subjects as a
descriptive sensitivity analysis. This sensitivity is not a new selection
criterion. Negative results and failure history remain public.

The independent validator must re-read all 327 official EDFs, reconstruct all
trial identities (including post-resampling event sample coordinates), audit
the seven frozen model/seed predictions for every trial, confirm 87 identical
copies and 22 new subjects, and reproduce the subject-level metrics, paired
bootstrap CI, sign test, and confusion tables. Only a passing report plus a
verified GitHub push is evidence of completion. Abrupt host loss can still
interrupt an in-flight download, but previously completed subjects remain
locally and are incrementally published.
