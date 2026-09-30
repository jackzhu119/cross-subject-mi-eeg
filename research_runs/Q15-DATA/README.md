# Q15 private R2 data preparation

This stage prepares private long-term storage for Cho2017 and Lee2019_MI.
Large raw data must never pass through the user's Windows computer or enter Git.
The intended path is verified official provider → cloud streaming or one-file
temporary staging → private Cloudflare R2. No full-cohort local cache is planned.

## Current stage: blocked before data acquisition

The actual cloud instance has none of `R2_ACCESS_KEY_ID`,
`R2_SECRET_ACCESS_KEY`, `R2_ENDPOINT`, or `R2_BUCKET` set. The configuration
draft inspected in this task also has no R2 credential bindings. This is a
configuration observation, not a failed attempt to authenticate supplied keys.
No authenticated R2 bucket access, object listing, write, read, or delete was attempted.
After the account endpoint was supplied, an unsigned HTTPS connectivity check
failed at the network proxy with `CONNECT 403 Forbidden`, before reaching R2.
The R2 destination, endpoint, bucket suggestion and credential requirements
have been saved in the cloud environment draft. Saving a draft does not apply
it to this running instance or inject credential values.

Set credentials using the current cloud environment's secure secret mechanism;
never place values in chat, Git, Markdown, fixtures, shell command text, or files.
Set `R2_ENDPOINT` to the account's HTTPS S3 API endpoint and `R2_BUCKET` to
`eeg-research`. Keep the bucket private. Boto3 signs S3 requests locally using
Signature V4: proxy placeholder credentials alone are not evidence of a usable
local signing key. The real signed request must pass the preflight.

## Repeatable preflight

From `/workspace/cross-subject-mi-eeg`, use the prepared environment:

```bash
source .venv/bin/activate
python scripts/q15_r2_preflight.py
```

The script reports only variable names and present/missing status. It checks
bucket access and list permission, writes a unique 36-byte private probe,
reads back its body/length/SHA256 metadata, and deletes it. A subsequent
listing must confirm the probe key is absent. It never changes bucket policy.
Exit 0 requires every check to pass; exit 2 means blocked. Failed or uncertain
cleanup is recorded, including only the non-secret probe object key.
Prior receipts are archived before `r2_preflight.json` is refreshed.

No large download should start unless this receipt passes. An R2 credential
check does not establish official dataset provenance, licensing, raw schema,
cohort completeness, or preprocessing validity.

Validation completed: 10 isolated preflight tests and 32 existing Q15 tests
passed (42 total); Ruff and whitespace checks passed. These are mocked,
synthetic and CPU checks, not real R2 or external-cohort validation.

## Remaining stages

1. Reconfirm official DOI, license and live provider inventory independently;
   do not treat historical URLs or an expected count of 160 as verified evidence.
2. Implement resumable streaming/multipart or one-file transfer, hashes and
   readback verification; use `q15/cho2017/`, `q15/lee2019-mi/` and
   `q15/manifests/`. Keep all failures and transfer receipts.
3. Audit real raw files, trial boundaries, channels and event/label semantics.
   Investigate Cho pseudo-continuous padding and Lee train/test ground truth.
4. Freeze a versioned outcome-blind preprocessing contract using real metadata.
   Target data must never fit normalization, features or model selection.
5. Commit tested code and receipts; keep `fits_started = 0` until every gate
   in the user's Q15 data-preparation request passes. Prepare an AutoDL R2/CUDA
   runbook only after the data and scientific prerequisites are established.

Neither a frozen contract, a transfer manifest, nor successful dataset audits
has been produced at this blocked stage. No GPU has been started.

The previous Windows task has newer unpushed Q15 work (reported local commit
`2a216bca`). This checkout initially contained `adb2d406`; reconcile those
changes before implementing downstream raw-provider adapters or reusing an
older contract. Do not overwrite Q5–Q14 evidence or existing Q15 results.
