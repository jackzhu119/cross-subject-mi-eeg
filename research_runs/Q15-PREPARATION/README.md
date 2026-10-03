# Q15 cloud migration preparation

This release prepares data and publishes observations. **It does not train,
freeze preprocessing, score a cohort, or stop a Pod.** The scientific gates in
`scripts/q15_source.py` remain intact. A migration does not release those gates.

The command fetches 18 official BNCI2014_001 MAT originals using HTTPS and
verifies the exact Q8 sizes/SHA-256 plus an independent persisted-file reread.
Existing verified source files are reused. It then streams SHA-256/MD5 over the
160 retained Cho/Lee originals and extracts metadata from actual MAT bytes,
one file at a time. It writes observations, not authorizing audit receipts.
No EEG arrays or model outputs are published. Source originals remain local/R2.

Lee inspection reads only `EEG_MI_train`; Cho inspection preserves the distinction
between retained, class-concatenated trials and original continuous acquisition.
Native units, cue-index conversion, artificial boundaries and run mapping are
not silently inferred. The current real scientific adapter and independent
source-output validator are missing; the final state is consequently
`blocked_scientific_audit_and_freeze`, with `fits_started = 0`.

## New Pod

Mount the original volume at `/workspace`. Originals should be in
`/workspace/q15-data/raw/Cho2017` and `/workspace/q15-data/raw/Lee2019_MI`.
The launcher verifies its pinned checkout in a private `/tmp` directory, installs
only observation dependencies in a private venv, and detaches the preparation
worker. It uses the same shared lock as the raw-download job. It does not depend
on old Pod IDs, old container-local credentials or a Windows computer.

For automatic GitHub publication, configure `GH_TOKEN` in the Pod environment
using a fine-grained GitHub token restricted to
`jackzhu119/cross-subject-mi-eeg`, with **Contents: read and write**. Alternatively
enter it at the launcher's hidden prompt. Never paste it into a chat, a command
argument, a screenshot or a shared-volume file. Pressing Enter skips GitHub
publication; the launch receipt explicitly records that fact.

The token exists only in the process environment. The worker creates a new
`q15/preparation-<job-id>` branch with one atomic commit containing exactly three
allowlisted JSON reports, then reads every report back at the immutable commit.
It neither changes `main` nor merges a PR. A failed publication leaves the local
reports and a failure receipt; it is not reported as a successful GitHub backup.

Reports and progress are retained at
`/workspace/q15-preparation/jobs/<job-id>/`. A detached PID is not scientific
completion. Read `preparation_status.json`, `failure.json` if present, and
`github_publication_receipt.json` to distinguish data preparation, blockage and
verified publication. Launcher dependencies and reports contain no R2 or RunPod
credentials; no old shared credential cache is read.

## Validation boundary

Preparation unit tests cover resumed hash checks, corrupt/incomplete downloads,
symlink/path rejection, atomic GitHub branches, exact report reread, secret
exclusion and native MAT schema observation. Both an actual Lee sample and an
actual Cho sample were observed successfully with zero fits. These observations
do not establish full-cohort clearance. Do not write fixtures into Q15-V001/V002,
change a receipt status manually, or bypass the source runner's freeze gate.

The separate `BNCI_R2_SOURCE_RECEIPT_20261003.json` records the original files
obtained and backed up by the managed cloud executor, with full R2 readbacks.
It does not assert that a new Pod already has those files or has run this job.
