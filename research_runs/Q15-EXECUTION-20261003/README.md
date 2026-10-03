# Q15 manual RunPod execution

This release runs the complete prospective Q15 operational benchmark after
the user starts it on the intended RunPod. It is a new method revision declared
before any Q15 source fit or external prediction. Historical Q14 results and the
original Q15 planning files remain preserved.

## Prerequisites

- Keep the migrated persistent volume attached. The 52 Cho and 108 Lee originals
  must remain under `/workspace/q15-data/raw/Cho2017/` and
  `/workspace/q15-data/raw/Lee2019_MI/`, with the provider's relative filenames.
- Use the RunPod PyTorch template with Python 3.12, Torch and TorchAudio
  `2.8.0+cu128`, working CUDA 12.8 and one NVIDIA GPU. The launcher checks these
  before installing dependencies. It runs the two actual neural architectures
  on zero inputs before loading original EEG or constructing an optimizer.
- The current Pod API must report at least 25 GiB of purchased volume headroom
  beyond the measured files. The shared storage pool shown by `df` does not
  establish the purchased quota.
- Have a GitHub token scoped to `jackzhu119/cross-subject-mi-eeg`, with repository
  Contents read/write permission. Have a RunPod API key that can read and stop
  the current Pod. Enter both at hidden prompts, or set their environment
  variables through the server's secret configuration. Do not put values in
  chat, source files, terminal commands, or GitHub.

This release uses the originals already on the migrated volume; R2 credentials
are unnecessary. Missing BNCI originals are fetched directly from their official
server and checked against the committed Q8 SHA-256 records. Missing Cho/Lee
originals block the run with a saved failure report.

## Launch

Use the immutable launch URL in `RELEASE.json`. Download the script to
`/tmp/q15-full-launch.sh`, then execute:

```bash
bash /tmp/q15-full-launch.sh
```

After the hidden prompts, wait for `detached_worker_startup_verified` and
`gpu_runtime_preflight_verified: true`. Then the terminal/browser/local computer
can be closed. The supervisor continues on the running Pod. Closing the local
computer does not stop the Pod. Stopping the Pod interrupts computation.

The launcher prints the precise status and log paths. To inspect the newest job:

```bash
JOB=$(find /workspace/q15-execution/jobs -mindepth 1 -maxdepth 1 -type d | sort | tail -n 1)
cat "$JOB/job_status.json"
tail -n 30 "$JOB/supervisor.log"
```

For a read-only server/runtime preflight that does not load originals, fit models,
compute target predictions, or request a stop:

```bash
bash /tmp/q15-full-launch.sh --check-only
```

After an interruption, retain the same volume, code revision, runtime and GPU
configuration. Re-enter the hidden credentials and use the printed job ID:

```bash
bash /tmp/q15-full-launch.sh --job-id EXISTING_JOB_ID
```

Completed, verified source fits and per-person predictions are reused. An
interrupted individual fit restarts that fit. Changed artifacts, scientific
inputs, runtime provenance, or publication history block mixed-protocol resumes.
Duplicate supervisors never stop another active job.

If interruption occurs exactly after GitHub advances the result branch but before
the local publication receipt is saved, automatic resume reports a publication
HEAD mismatch. Leave the volume attached; reconcile the remote commit and local
receipt before restarting. The supervisor deliberately blocks further work and
does not claim that interrupted publication was verified.

## Automatic stages

1. Verify current Pod identity, repository write access, actual volume headroom,
   pinned Python/packages/CUDA and zero-input architecture execution.
2. Check all 18 BNCI and 160 Cho/Lee original files, complete labeled metadata,
   native event indices, class mappings, channels and trial context coverage.
3. Commit and read back both real metadata audits and all scientific inputs;
   separately commit and verify the preprocessing freeze. `fits_started = 0`
   through these gates.
4. Run 14 BNCI-only neural fits and one BNCI-only CSP fit. Source-only validation
   selects epochs. An independent validator checks the source partitions,
   training counters, curves, checkpoint shapes/hashes and complete artifact set.
5. Prepare both external cohorts with the same fixed transform, commit epoch
   provenance, then separately commit the inference freeze before predictions.
6. Evaluate 10,520 Cho and 10,800 Lee trials using the six frozen neural models
   and CSP. No target model or preprocessing parameters are fitted. An independent
   validator replays raw data, processed trials, predictions, person-level
   statistics and the two-cohort Holm correction.
7. Commit validation reports, CSV results, source checkpoints and provenance to
   `q15/run-JOB_ID`; read back GitHub tree and every published blob. Original MAT
   files and processed EEG arrays remain on the persistent volume.
8. Request **Stop** for the authenticated current Pod after verified final backup.
   This stops compute and preserves the attached volume. It does not delete the
   Pod/volume or remove continuing storage charges. API acceptance is recorded
   separately from physical shutdown confirmation.

Failures after verified startup publish a failure status and request Stop after
that backup succeeds. Startup identity/GPU failures or failed GitHub backup leave
the Pod running and report manual attention. A stop API failure reports
`manual_stop_required`. Inspect the final status; a launcher receipt is not a
scientific completion receipt.

## Scientific scope

The common transform selects the same 21 channels, applies their common-average
reference, filters each native six-second cue context `[-1.5, 4.5)` independently,
anti-alias resamples to 160 Hz, then retains `[0.5, 2.5)` (320 samples). Source and
both targets call the same transform. Fixed Helmert coordinates represent the
entire 20-dimensional CAR subspace for CSP; their basis is never estimated from
EEG. See `EXECUTION_CONTRACT.json` for the exact settings and evidence hashes.

**Native exported voltage calibration is unverified.** The operational adapter
declares native numeric values as microvolts; secondary loaders/toolboxes support
this convention but do not establish the original export calibration. Cho's
original hardware reference and hardware cue latency are also unverified. Its
numbered channel map is a reviewed assumption from the official paper figure;
physical run identities cannot be reconstructed. Lee uses explicit MATLAB
`t - 1` cue indexing and discloses the one-sample offset in supplied segments.

Successful output therefore has status `completed_with_calibration_limitations`,
with the claim restricted to this prospective operational adapter benchmark.
It does not establish physical calibration or silently replace the earlier plan.
The person is the inferential unit; Lee's two sessions are pooled per person.

## 中文操作说明

保留迁移过来的持久磁盘，在新服务器终端粘贴发布后的固定版本启动命令。
GitHub 与 RunPod 密钥各输入一次，输入时不回显。本版本会真正自动完成
“原始审计 → 提交冻结 → 来源训练 → 外部评估 → 独立复核 → GitHub 提交 → 停机”。
只有服务器原始审计和提交冻结通过，才会从 `fits_started = 0` 进入训练。
本地电脑可在启动验证成功后关闭。GitHub 结果保存在新结果分支，原始 EEG
及处理数组保留在云盘；停机后云盘仍可能计费。

当前代码的本地验证不等于新服务器 GPU 已验证，也不等于 Q15 已训练完成。
完整真实审计、CUDA 运行和科学结果将在服务器执行时验证。原始电压标定等
已知限制会保留在结果中，完成状态会注明 calibration limitations。
