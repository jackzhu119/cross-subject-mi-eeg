# Q14-E002R2V1: validation-only host portability amendment

Date: 2026-09-26. This amendment was prepared **after** the 109-subject R2
prediction files and completion receipt existed. It does not amend the frozen
source models, PhysioNet target eligibility, event/epoch rules, sampling-rate
amendment, predictions, primary contrast, metric, bootstrap seed, or inference
runtime. The historical failed R2 validation batch remains intact.

## Reason and narrow scope

The original R2 independent validator requires its **current** Python,
package, CUDA, platform and GPU receipt to equal the receipt from the prior
inference host (RTX 4080 SUPER). A new AutoDL validation host has a different
GPU/platform. Requiring equality would stop the validator before checking the
327 official EDF files, although the work to be done is only a reconstruction
of event identities and a re-score of **existing immutable predictions**. No
model is loaded for prediction, trained, selected, or adapted to PhysioNet.

`scripts/q14_r2_validate.py` retains its original strict mode by default.
Only the explicit `--portable-output-root results/Q14-E002R2V1` mode replays
the **saved R2 inference runtime** solely inside the historical R1-to-R2
custody comparison. It records the actual validation runtime separately and
does not claim the two hosts or runtimes are identical. The R1/R2 historical
kernel difference, every other historical package/runtime field, code hash,
source freeze, subject receipt, prediction checksum, official EDF checksum,
native event sample/label and result reconstruction remain checked. The
portable mode writes tables, figures and report only to a new results child;
it does not write into `results/Q14-E002R2`.

## Gate and interpretation

The versioned validation report may say `passed` only after the original
109 subject predictions, 87 inherited custody copies, 22 new R2 copies,
all 327 official EDF files, 4,918 unique trials, 34,426 prediction rows,
source freeze, class decisions, subject-level BA, paired contrast, bootstrap,
sign test, and sensitivity figures pass the full independent check. Its
separate report includes the historical inference runtime, observed
validation runtime, this amendment hash, and zero new fits/inference rows.
Any failure stops the attempt and retains the log; no result is silently
dropped. The external effect remains whatever the frozen contrast yields,
including a null or negative result. Different validation-library versions
could change parsing or numerical display; such a discrepancy must be
reported, not used to retune the models or predictions.

The historical R2 inference provenance must always be cited separately from
this later validation attempt. This is a portability exception for auditing
already-published predictions, **not** authority to run new external
inference in a changed runtime or relax future source-only protocols.

On the persistent AutoDL volume, with the committed code on `main`, run:

```bash
python scripts/q14_r2_portable_finalize.py --execute --data-dir /root/autodl-tmp/physionet
```

Without `--execute`, the entrypoint is a dry run. Successful or failed attempts
are recorded under `results/Q14-R2PORT`; reconstructed tables and the
versioned report are under `results/Q14-E002R2V1`. The launcher makes two
noninteractive publication attempts around its completion receipt. If GitHub
is unavailable, local results remain and the publication receipt records that
fact rather than claiming publication.
