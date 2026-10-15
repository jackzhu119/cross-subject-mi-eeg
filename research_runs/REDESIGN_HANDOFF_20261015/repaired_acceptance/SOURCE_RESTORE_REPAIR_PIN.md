# Fixed failure-bound source repair for dot

> **Superseded for this preflight compatibility:** the5c7e invocation failed before claiming. Do not rerun that wrapper, overwrite its failedouter or delete the oldtmp. Use [SOURCE_PREFLIGHT_COMPATIBILITY_PIN.md](SOURCE_PREFLIGHT_COMPATIBILITY_PIN.md) for the exact whitelisted records and separate new outer filename.

Execution commit: **`5c7e153d09cdba4ecf83d2a54991f34d032205c4`** on `research/paper1-handoff-20261014`.
All16 changed files and all12 small execution-bundle members passed immutable public byte readback (22 distinct paths). Exactly2 relevant synthetic tests passed. No server operation, raw EEG read, installation or scientific rerun occurred here.

## Deliver the isolated small code bundle

Do not use or overwrite the old0603 bundle or rerun its claim. Dot delivers only these public code/templates to a new directory; the repaired97-package environment and old1efe checkout remain untouched. No environment is created.

```bash
export P1_SOURCE_REPAIR_REVISION=5c7e153d09cdba4ecf83d2a54991f34d032205c4
export P1_SOURCE_REPAIR_DIR=/workspace/paper1-source-repair-code-5c7e153d
(
set -eu
mkdir -m 700 "$P1_SOURCE_REPAIR_DIR"
P1_SOURCE_REPAIR_BASE="https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/$P1_SOURCE_REPAIR_REVISION/research_runs/REDESIGN_HANDOFF_20261015/repaired_acceptance"
for P1_SOURCE_REPAIR_FILE in restore_source_once.py source_owned_measurement.py restore_source_after_failure_once.py RUN_SOURCE_RESTORE_REPAIR_ONCE.sh accept_repaired_runtime_source.py acceptance_gate.py AUTHOR_CPU_RECOVERY_48H_20261015.json AUTHOR_FINANCIAL_SUPERSESSION_20261015.json source_restore_repair_review.PLAN_ONLY.json source_restore_repair_slot.PLAN_ONLY.json source_acceptance_review.PLAN_ONLY.json source_acceptance_slot.PLAN_ONLY.json; do
  curl -fSsL --proto '=https' --tlsv1.2 --max-time 30 \
    "$P1_SOURCE_REPAIR_BASE/$P1_SOURCE_REPAIR_FILE" -o "$P1_SOURCE_REPAIR_DIR/$P1_SOURCE_REPAIR_FILE"
done
cd "$P1_SOURCE_REPAIR_DIR"
sha256sum -c <<'SHA256'
2ee6355f51b29bbeedd30f8422c078af76615c26873e16826156ebc015d7f220  restore_source_once.py
96221076dc8d13c5f30dca4c271c971935af671061498486aa018aaf6c553582  source_owned_measurement.py
b07902555e0f07efbdb4ee17e34ea25a1f4cc70a74b6dcb86014381966a7c3fb  restore_source_after_failure_once.py
8b4c49fd857525bf79ede17007e24f087fe2cf7219e296191512f379c8fd89d8  RUN_SOURCE_RESTORE_REPAIR_ONCE.sh
96de59deb33cb7b353b9fb197f450807fdd967eb36ed6165d708ef144456d279  accept_repaired_runtime_source.py
579067cf8eab2d3e6d20a00f54bc303f619796db04df9bd33eee4fdea066f528  acceptance_gate.py
ae0ee5135586a7c49bfd690946120455367b14d2c1426c5f7217347bedd12fb5  AUTHOR_CPU_RECOVERY_48H_20261015.json
d3a4e670332a9bf158da98abae0ab84702d092018c6043cbc36bf4f3f5fb7d90  AUTHOR_FINANCIAL_SUPERSESSION_20261015.json
8b2734be0d968ba03d6892abbb38ab3aada100ecf3ffe504eafa6062e18c55ab  source_restore_repair_review.PLAN_ONLY.json
006cf238a0bb31a92a61ba6e9f5ae32fef12d568ebcd4a038d70e65588487568  source_restore_repair_slot.PLAN_ONLY.json
e57ccf25702643a1edd9f250eb47f2d43bbf87920cd2133f742d4b5646fc257c  source_acceptance_review.PLAN_ONLY.json
6d79873e43d73ced4fb5b55b6f69133a945d9d331d85963f6aeb7bd810defa6a  source_acceptance_slot.PLAN_ONLY.json
SHA256
)
```

## Technical bindings and the precise entry

- The new repair review operation remains `source_raw_restore`; bind `operation_script_sha256` to **`b07902555e0f07efbdb4ee17e34ea25a1f4cc70a74b6dcb86014381966a7c3fb`** and `gate_sha256` to `579067cf8eab2d3e6d20a00f54bc303f619796db04df9bd33eee4fdea066f528`, with the exact new delivery commit above.
- Use `source_restore_repair_review.PLAN_ONLY.json` and the repair slot template as schemas only. Parent technical review must be real and later than2026-10-15 06:02:59.928544UTC; dot issues a fresh separate slot. Financial prerequisites remain `superseded-by-user`; no billing/balance investigation or repeated author approval is required.
- The actual original26831-byte failure archive must exist at `P1_SOURCE_RESTORE_FAILURE_ARCHIVE`. Its frozenSHA is `89f8b8b05dc2b94a97038e6800fb94238081e63657e2b1492361da2aa4d7c536`. Its current local path is supplied by dot, not guessed here.
- Execute [the complete new source repair command](SOURCE_RESTORE_REPAIR.md#fixed-delivery-and-new-source-repair-command) via `RUN_SOURCE_RESTORE_REPAIR_ONCE.sh`, not the inner Python worker. It binds one new claim to the old failure and same cache, verifies12 full SHAs and fetches only6 missing files.
- Keep all old/new records and both real exits. No Step B until actual18/18, successful new journal/controller-completion bindings and observed wrapper exit0 are independently reviewed.

## Later CPU acceptance, using the original technical gate

Only after actual repair success, bind the new repair receipt SHA in a post-outer-exit source_cpu_acceptance review; use the unchanged gateSHA above and updated acceptance scriptSHA **`96de59deb33cb7b353b9fb197f450807fdd967eb36ed6165d708ef144456d279`**. Dot issues its own fresh CPU slot.
Use [the precise updated acceptance command](SOURCE_RESTORE_REPAIR.md#only-after-actual-successful-repair-original-cpu-acceptance-gate), which points to `source_restore_repair_run01.json`. It reuses the already repaired environment and recovered historical evidence. No old RUNNING receipt, failed outerexit or consumed claim can authorize it.

Original1200s restore/300s acceptance,3GiB combined ownership,10GiB+actual Paper2 reserve,48-hour CPU window and GPU deadline are unchanged. This code commit grants no target EEG or GPU fit, and does not establish the real cause of the old FileNotFoundError. Dot remains sole Pod operator.
