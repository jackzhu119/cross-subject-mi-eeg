# Q13-only Linux cloud release (Q15 excluded)

This versioned chain runs the frozen Q13-E001/E004/E005 **837 deep fits**,
their full independent 837-checkpoint replay, the additive Q13-E006 **27
deep fits**, its separate 27-checkpoint replay, and subject-level post-run
statistics. It preserves completed, hash-verified fits on resume. Q12/Q14
are not rerun. No Q15 metadata, source fit or external target prediction is
started by this chain.

Use an already reviewed and committed GitHub `main` checkout with a writable,
noninteractive allowlisted `origin`. Keep raw BNCI MAT files outside Git. On
the Linux host, after ensuring Python 3.12 and the pinned environment:

```bash
bash setup_paper_cu128.sh
export BNCI_MAT_DIR=/absolute/path/to/the/18/original/BNCI/MAT/files
bash scripts/run_q13_cloud.sh --execute --publish \
  --python "$PWD/.venv-paper/bin/python" --data-dir "$BNCI_MAT_DIR"
```

The launcher first runs `scripts/q13_cloud_chain.py --check-only`: real CUDA
operation, exact package versions, Q13 frozen source-only/Git gates, a
noninteractive Git push dry run, and **all 18 MAT file bytes versus frozen Q8
SHA-256 provenance** must pass before a training process is detached. It also
pins MOABB's download provider to `upstream` and verifies that MOABB resolves
all nine subjects to those same local MAT files; the NEMAR mirror is not used.
The background Python chain records its PID in
`results/Q13-RELEASE/supervisor.pid`, its launch log in `launcher.log`,
stage logs in the same directory, and a durable `batch_status.json`.
Check the process and status after launch; a successful shell exit alone is
not scientific completion.

The chain runs the original Q13 batch with `--publish`. It only starts E006
after `results/Q13-BATCH/batch_status.json=complete_validated` and the
independent validator reports 837 replayed checkpoints. After E006 it runs
the independent 27-checkpoint validator and the 11-contrast post-run script.
It attempts the allowlisted Git publisher for Q13/E006/results/logs on normal
success or caught failure; review each `publish_status.json` and
`skipped_files`. Files over 90 MiB are not put on GitHub, and a Git/network
failure leaves `pending_manual_publish` with local files intact. Do not
force-push or merge results with target-driven changes.

`nohup` plus `setsid` protects against closing SSH or the local laptop, **not**
cloud power loss, disk exhaustion, SIGKILL, lost paid-instance time, or an
unavailable GitHub remote. In those cases, restart the same command on the
same data and runtime to resume verified completed fits; check failure logs
first. A host shutdown is not requested or performed by this launcher.
