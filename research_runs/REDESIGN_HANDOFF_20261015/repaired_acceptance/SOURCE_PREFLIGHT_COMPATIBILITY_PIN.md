# Fixed exact-tmp compatibility pin

Execution commit: **`86022658247a30c43953561a2f29f730731eb597`** on `research/paper1-handoff-20261014`.
All13 changed files and the12 bundle members passed immutable public readback (21 distinct paths). Three focused synthetic ownership tests passed. No Pod, real cache, installation or science was executed here.

This does not repeat a consumed repair claim: the authenticated preflight failed before creating one. The old failedouter remains immutable; the new wrapper writes only `source_restore_repair_run01.compat_outer_exit.json`. No additional unknown member is allowed.

## Small fixed delivery

Dot uses a new code-only directory. Retain all previous deliveries, old metadata/tmp and failedouter. The97-package environment and old1efe checkout are unchanged.

```bash
export P1_SOURCE_REPAIR_REVISION=86022658247a30c43953561a2f29f730731eb597
export P1_SOURCE_REPAIR_DIR=/workspace/paper1-source-repair-code-86022658
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
dcbbfb50088795c6667834d86e02cc7a343c32a0b8370b3da065acf41b6147c6  restore_source_after_failure_once.py
32f591fc9b4be45ee50ccb200be1ff2f7a1d52fe567a0a6675e630563ed4aef9  RUN_SOURCE_RESTORE_REPAIR_ONCE.sh
a48b3ffb655b4fb85cc94f9310c0fff9908982405d54fd497af0ac4b38c6fff9  accept_repaired_runtime_source.py
579067cf8eab2d3e6d20a00f54bc303f619796db04df9bd33eee4fdea066f528  acceptance_gate.py
ae0ee5135586a7c49bfd690946120455367b14d2c1426c5f7217347bedd12fb5  AUTHOR_CPU_RECOVERY_48H_20261015.json
d3a4e670332a9bf158da98abae0ab84702d092018c6043cbc36bf4f3f5fb7d90  AUTHOR_FINANCIAL_SUPERSESSION_20261015.json
dc32271ca04a0c7c91c740170695501971427168b1f1a06d744c546057373647  source_restore_repair_review.PLAN_ONLY.json
006cf238a0bb31a92a61ba6e9f5ae32fef12d568ebcd4a038d70e65588487568  source_restore_repair_slot.PLAN_ONLY.json
e57ccf25702643a1edd9f250eb47f2d43bbf87920cd2133f742d4b5646fc257c  source_acceptance_review.PLAN_ONLY.json
6d79873e43d73ced4fb5b55b6f69133a945d9d331d85963f6aeb7bd810defa6a  source_acceptance_slot.PLAN_ONLY.json
SHA256
)
```

## Bind the existing technical review/slot and execute

- Restore review: operation `source_raw_restore`, this exact delivery commit, controller SHA **`dcbbfb50088795c6667834d86e02cc7a343c32a0b8370b3da065acf41b6147c6`**, unchanged gate SHA `579067cf8eab2d3e6d20a00f54bc303f619796db04df9bd33eee4fdea066f528`. Actual review must follow2026-10-15 06:37:36.134424UTC; dot issues a fresh slot. Do not promote PLAN_ONLY templates or request financial/time authorization again.
- Retained identity: exact old0-byte tmp `source_restore_run01.json.tmp-a0f96cd0b1ed43c0967091e562c9884a`; failedouter SHA `112aac0310e0dd5d239e81c88414361a501e6b26a4fcb5189521afe9b60329e9`; new preflight package SHA `89569e3a18402665d81f74064a420de522c74115458883b9af9eac6d5bfe8dab`.
- Execute [the complete fixed command](SOURCE_PREFLIGHT_COMPATIBILITY.md#fixed-source-command-for-dot). `P1_SOURCE_RESTORE_FAILURE_ARCHIVE` still names the existing original26831-byte archive SHA89f8b8b0..., not the newer63678-byte evidence. No new private key or download is required.
- The wrapper SHA is `32f591fc9b4be45ee50ccb200be1ff2f7a1d52fe567a0a6675e630563ed4aef9`. It cannot overwrite the oldfailedouter. The oldtmp is preserved read-only and becomes a mandatory unchanged record; no arbitrary `.tmp` allowance was added.

Step B stays blocked until actual full18/18 and successful journal/controllercompletion/new compatouterexit0 are verified. Its actual post-success review uses updated acceptance SHA **`a48b3ffb655b4fb85cc94f9310c0fff9908982405d54fd497af0ac4b38c6fff9`** and binds the new source receipt. The full conditional CPU command in `SOURCE_RESTORE_REPAIR.md` is unchanged; use this bundle/revision, whose adapter consumes the new compatouter and preserves all old evidence.

Only12 retained files are fully rehashed/reused; only6 missing originals may be fetched. No claim reset, old failure rewrite, extra framework, environment, scientific change, fees/balance analysis, target EEG, fit or Pod control is introduced.
