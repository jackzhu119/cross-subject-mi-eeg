# Q14-E002R2 independent-validator precision erratum

This is a technical validator correction, **not** a change to the frozen
protocol, source models, external predictions, eligibility, metric, seeds, or
the post-freeze sampling-rate amendment. Keep the original R2
`failed_stopped` receipt and supervisor log as historical evidence.

## Observed failure and diagnosis

The R2 inference completion receipt records 109 external subjects, 4,918
unique trials, 34,426 model/seed prediction rows, 87 byte-identical migrated
subject files, 22 newly inferred subjects, and zero target fits. The batch
stopped in `q14_r2_validate.py` after independently reading all 327 EDF
headers/checksums because an exact floating-point comparison of a
second-serialized aggregate CSV to the per-subject CSVs failed for `p_left`.
Pandas reported **0.31081% unequal rows**, not a 0.31 percentage-point
probability difference.

An independent comparison of the committed CSVs found:

- All 10 non-probability columns, including subject/run/trial identity, label,
  model, seed, and `predicted_label`, agree for all 34,426 rows in order.
- Original decimal CSV text differs in `p_left`/`p_right` only by at most
  `2e-16`; the largest difference after local pandas parsing is
  `3.3881317890172014e-21`.
- Every published predicted class remains the argmax of its two probabilities.
  The minimum binary decision margin is approximately `1.621e-05`.
- The published aggregate hash still matches the original completion receipt
  in Git/LF form. Windows Git with `core.autocrlf=true` checks tracked CSVs
  out as CRLF, changing the on-disk SHA-256 without changing the Git blob;
  offline checks normalize only that line-ending conversion before comparing
  the original receipt hash.

The aggregate was built by reading the per-subject CSVs and writing them a
second time. `check_exact=True` on the re-parsed probability columns is thus
too strict. The corrected validator still requires every non-probability
field and row order to match exactly. Only `p_left` and `p_right` may differ,
with `rtol=0`, `atol=5e-16`, finite values required. The existing per-subject
probability, argmax, EDF trial reconstruction, source freeze, and file-hash
checks remain in force. A synthetic `1e-8` probability corruption, a changed
label/prediction, or a row shuffle must fail the new regression tests.

## Artifact-only numerical audit, not the final scientific pass

`python -m scripts.q14_r2_offline_audit` verifies the published subject and
aggregate receipt hashes, all 109 subjects and seven arms per trial, unchanged
trial IDs/classes, probability validity, and independently recomputes the
subject-level endpoints without any raw EDF or GPU. It returned:

- Mean subject BA: broadband EEGNet `0.6181459187`, shared μ/β EEGNet
  `0.6238788808`, CSP4+LDA `0.5446171980`.
- Frozen primary paired BA difference (shared minus broadband):
  `+0.0057329621`; 20,000 subject bootstrap draws (seed `20260924`) yield
  percentile 95% CI `[-0.0009668274, 0.0124155510]`.
- 63 positive, 43 negative, 3 tied subjects; two-sided sign-test
  `p=0.06446359` excluding ties.

These are **provisional audit numbers** until the full independent validator
reruns on the original checksum-verified EDFs in the matching cloud runtime.
The interval crosses zero; no external advantage is established by this
artifact-only analysis. The three resampled people must also remain a
descriptive sensitivity stratum, never a post hoc exclusion or model-choice
criterion.

## Remaining completion gate

On the next cloud start, use the same published checkpoints and prediction
files and run only the amended full validator. Do **not** retrain BNCI source
models or repeat 109-subject inference. The full validator must verify all 327
official EDFs, original 87 copied predictions, 22 new predictions, runtime and
source freeze, subject/class metrics, CI, sign test, confusion tables, and
failure-history custody. Only then may a new passing validation report and
publication receipt be added; the earlier failed receipt is not rewritten.

The validation-only entrypoint is plan-only by default:

```bash
python scripts/q14_r2_finalize.py
python scripts/q14_r2_finalize.py --execute --data-dir /root/autodl-tmp/physionet
```

The second command is for a later **explicitly authorized** cloud session with
the original data path, matching runtime, committed amendment, and working
noninteractive GitHub publication. It creates a separate `Q14-R2FINAL` batch
receipt/log; it does not restart inference or request machine shutdown. A
missing original EDF cache or mismatched runtime is a hard stop, not a reason
to edit the frozen run configuration.
