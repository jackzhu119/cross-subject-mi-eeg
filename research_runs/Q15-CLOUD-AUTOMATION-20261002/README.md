# RunPod cloud download and stop workflow — 2 October 2026

This workflow prepares a detached RunPod job to download the existing 160 Cho2017 / Lee2019_MI original MAT objects from private Cloudflare R2, verify every byte, save progress back to R2, and stop the Pod after its final verified backup. Downloads stay between cloud services. It does not run on the user's Windows computer.

**Current scientific state:** the real MAT metadata adapter and complete cohort audit are not implemented, the preprocessing contract is not frozen, and Q15 source fitting remains blocked. The current job must therefore finish in a documented blocked state after transport verification, with `fits_started = 0`. It must not describe that state as completed training. Downloaded Cho/Lee files are external audit/evaluation data; source training also needs 18 separately verified BNCI2014_001 files.

## Start on the Pod

Use the pinned, checksum-verified launch command provided with the deployment receipt. Execute it in the Pod's Jupyter Terminal. The bootstrap prompts for any missing variables with hidden terminal input:

- `R2_BUCKET`
- `R2_ENDPOINT`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`
- `RUNPOD_API_KEY`

Use real R2 credentials from Cloudflare and a RunPod API key authorized for this Pod. The credentials configured for Codex are not automatically present on RunPod and must not be copied from a proxy placeholder. Do not send values in chat or paste them into shell commands. The bootstrap stores them in a local file with mode 0600 outside the Git checkout and starts a detached job. The Pod ID must match the intended Pod.

Confirm the reported PID and progress state on the Pod before relying on the job to continue after closing the browser or local computer. A prepared script or GitHub commit alone is not evidence of a deployed job. The actual purchased volume quota must be large enough for approximately 70.36 GiB of originals plus temporary files and working space; the huge shared `df` capacity does not prove the Pod quota.

## Evidence and behavior

The workflow restores an existing private R2 provenance archive with SHA-256:

```text
332b878514894f7e6543c652e4138be13d8125ac8da20099ae9ca8641684fa0b
```

Its authenticated storage verification inventory describes 160 files totaling 75,551,469,122 bytes. Archive extraction rejects unsafe paths and links. Each original is checked against its declared byte count, SHA-256, and MD5 before being marked complete. An already downloaded file is reusable only after rechecking its full hash. Completing these checks provides transport evidence, not permission to fit a model.

Progress and final receipts are stored under a new private `q15/cloud-jobs/` prefix. Final backup objects are read back and hashed before a stop request. Errors use sanitized event names rather than request URLs, authentication headers, or credential values.

Automatic stopping uses the official RunPod Pod stop API, not a container shutdown command. The job stops after a verified final backup on either successful completion of its supported work or a recorded scientific block, so a blocked pipeline does not keep an idle GPU running. If backup verification fails or the API rejects the request, the job cannot claim the Pod stopped. Stopping the Pod can leave volume storage charges in place.

## Continue the research

Implement and independently review real provider adapters and inventory authentication, audit all 160 originals, resolve the preprocessing amendments, verify source BNCI data, and commit the actual freeze inputs and pre-fit receipt on the final execution machine. Only then can the reviewed Q15 source runner train. Existing dry-run/audit commands can return exit code zero while reporting a block; checking exit code alone is insufficient.

The trained source runner also requires independent source validation and checkpoint freezing before any external Q15 evaluation. This automation is not evidence that those stages exist or have completed.

Paper archive: [PR #1](https://github.com/jackzhu119/cross-subject-mi-eeg/pull/1). Research handoff: [`CONTINUE_IN_ANOTHER_CHAT.md`](https://github.com/jackzhu119/cross-subject-mi-eeg/blob/paper/non-q15-manuscript-20261002/research_runs/PAPER_PUBLICATION_20261002/CONTINUE_IN_ANOTHER_CHAT.md).

## Prepared release verification

39 no-network tests passed, including simultaneous local log/status/stdout ENOSPC and verified backup before Pod stop. The pinned code commit is `5e86353017ef9465866a49508f5b75d2a29fa52f`. `PREPARATION_RECEIPT.json` explicitly records that this workflow is prepared and has not been deployed. `LAUNCH_ON_RUNPOD.sh` fetches and checks both production-script hashes before launch.

The launcher now selects the current server from `RUNPOD_POD_ID`, validates that ID with the official API, and binds stop requests to the same current environment. A cached or historically hard-coded Pod ID cannot select the server. Missing or mismatched current identity prevents any stop request. The latest user attempt was NOT_STARTED; this update is still not proof of a deployed worker.
