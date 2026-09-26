# Q14 validation → Q12 → Q13 detached Linux GPU queue

The first stage checks the frozen Q14-R2 external predictions against the
original 327 EDF files under a **versioned validation-only portability
amendment**. It does not train or infer any new Q14 trial. A failed Q14 audit
is recorded and does not suppress the scientifically independent BNCI stages.
Q12 and Q13 are post-hoc, exploratory BNCI2014_001
mechanism analyses. Their frozen condition matrices contain 378 and 837 new
deep fits, respectively. The queue does not choose conditions, seeds, epochs,
or source subjects from held-out target scores.

Use a clean public-repository `main` checkout with the prepared commit, raw
BNCI cache, a validated CUDA/PyTorch/Braindecode environment, and noninteractive
GitHub write access. The queue uses the existing Q12 and Q13 batch scripts,
which perform their own runtime, source-only provenance and Git preflights.
It does **not** install packages, move raw EEG, or run in a browser process.

To inspect the exact plan without training:

```bash
/root/autodl-tmp/.venv-paper/bin/python scripts/paper_cloud_queue.py \
  --data-dir /root/autodl-tmp/data/raw \
  --physionet-dir /root/autodl-tmp/physionet
```

To start it detached from SSH and the local computer:

```bash
bash scripts/run_paper_cloud.sh --execute --publish \
  --python /root/autodl-tmp/.venv-paper/bin/python \
  --data-dir /root/autodl-tmp/data/raw \
  --physionet-dir /root/autodl-tmp/physionet
```

The launcher gives the PID, startup log, and durable status paths. A second
connection can independently confirm the PID and increasing job logs before
the operator disconnects. `nohup` plus a new process session protects it from
SSH logout and local-computer shutdown; it does **not** survive cloud-instance
poweroff, account/billing suspension, or host loss. Do not use it as evidence
that any fit or scientific validator has passed.

The durable summary is `results/Q12-PAPERQUEUE2/paper_queue_status.json`; stage logs
are `paper_queue_q14_portable_validation.log`, `paper_queue_q12.log`, and
`paper_queue_q13.log` beside it. Q14, Q12 and Q13
retain their own `batch_status.json`, fit-level checkpoints, validation
reports, publication receipts, and logs. The supervisor stops at the first
nonzero **Q12 or Q13** stage, preserves all partial records, and attempts one additional
noninteractive publication of its summary/logs even on failure. It does not
delete data or automatically shut down the instance. Publication can fail
independently of scientific validation; in that case the cloud files remain
and `publish_status.json` records a retryable pending state.

On a later same-host restart, use the same command. The manifest checks source
file hashes, data path, interpreter, stage order, and fit budget. A completed
stage is skipped only when its original scientific and batch receipt hashes
still match. Interrupted/failed stages defer to the existing fit-level resume
rules of their batch runners. The Q14 stage is validation-only and keeps the
historical failed receipt; it does not silently turn an old run into a pass.
Never edit a prior manifest to bypass a mismatch;
record and review a new amendment instead.

The first 2026-09-26 launcher attempt is preserved in `results/Q12-BATCH`.
Its supervisor mistakenly dereferenced the virtualenv Python symlink when
building child commands, so Q14 and Q12 exited before validation or fitting
with `ModuleNotFoundError: mne`. The new `Q12-PAPERQUEUE2` receipt separates
the corrected launch from that failed attempt; it passes the virtualenv
executable path unchanged to every child. No Q12/Q13 fit was completed in the
first attempt.
