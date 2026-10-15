# Immutable formal preparation controller

Outer controller/evidence commit:
**`b07892c320e25e3465c50ea3a31d1a21bf722df3`**.
The unchanged inner helper remains
**`1efe9d1ba2ab8671ad1bf76c360e067fb63fd7ac`** in dot's existing reviewed
checkout. Do not change that checkout to the newer documentation head.

Standalone `prepare_runtime_only.py` SHA256:
**`7a1fbc9b364c8dd42faf6894450ae065a49d59a977d4c5470a3c2daffff50cc3`**.
Its template, tests, actual metadata/plan audits, proposed official EDF mapping
and accounting proposal are pinned in the same commit. The32 changed files
passed public immutable-URL byte readback; see `PUBLIC_READBACK_RUN01.json`.
139 new targeted synthetic tests passed; no old full suite or scientific work
was rerun. Preparation/installation has **not** been executed here.

## Small code retrieval for dot, after review

This only obtains the standalone public Python source and verifies its bytes;
it does not install a package or operate the scientific task. The assistant has
not run this command on the Pod. Do not refetch a correct existing copy or
overwrite another file. HTTPS/TLS verification remains enabled.

```bash
(
set -eu
P1_PREP_CONTROLLER=/tmp/paper1-prepare-runtime-b07892c3.py
if [ ! -e "$P1_PREP_CONTROLLER" ] && [ ! -L "$P1_PREP_CONTROLLER" ]; then
  curl -fSsL --proto '=https' --proto-redir '=https' --connect-timeout 10 --max-time 60 \
    https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/b07892c320e25e3465c50ea3a31d1a21bf722df3/research_runs/REDESIGN_HANDOFF_20261015/runtime_preparation/prepare_runtime_only.py \
    -o "$P1_PREP_CONTROLLER"
fi
test -f "$P1_PREP_CONTROLLER"
test ! -L "$P1_PREP_CONTROLLER"
printf '%s\n' \
  "7a1fbc9b364c8dd42faf6894450ae065a49d59a977d4c5470a3c2daffff50cc3  $P1_PREP_CONTROLLER" \
  | sha256sum -c -
)
```

Before execution, dot's parent reviews this exact controller SHA and the bounded
resolver/install/cost-handling policy, saves an actual approved review record,
and dot then issues the NEW valid slot. The committed PLAN_ONLY review template
cannot pass. No secret is needed in the command or review file.

The exact preparation invocation, input SHAs, required evidence returns and
failure behavior are in [DOT_PREPARATION_NEXT.md](DOT_PREPARATION_NEXT.md).
There is no new plan run. If required review/cost-handling or a valid slot is
absent, **do not execute preparation**. An approved technical preparation does
not settle the unknown old accounting or reset the$10/cumulative8GPU-hour caps.

After preparation, the parent's independent review of actual wheel resolution,
receipt, logs and hashes comes before any real-runtime source acceptance. GPU
imports/arithmetic, source/target input acceptance, old task/accounting/backup
and all model-fit gates remain separate and not passed by this deliverable.
The absolute deadline remains2026-10-16 09:54UTC. No Pod control, target download,
401 retry or alternate platform-balance access is included.
