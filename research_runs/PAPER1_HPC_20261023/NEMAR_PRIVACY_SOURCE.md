# Official privacy-corrected Yang source: explicit input version

Approved by the user on 25 October 2026: “同意新增隐私修正版清单并继续（推荐）”. This approval covers a separate official NEMAR input identity, retaining the original Figshare contract and results. It does not certify that corrected files have their ancestors' SHA256.

## Direct school download

The existing installer accepts `--yang-source nemar-privacy-v1`. Add this option to the fixed `RUN_SINGLE_JOB_ON_SCHOOL.sh` command, together with `--restart-transfer --gpus 2 --memory 128G --replace-job 771084`. GitHub authorization is reused only when its existing private configuration is valid; `--reauthorize` requests fresh hidden input. No token belongs in code or chat.

The selected flow downloads to shared school storage on login1, then submits **one Slurm job, one node, two GPUs, total 24 CPUs and 128G RAM** in `hpc_gpu`. No R2 service, local-PC data copy, or compute-node Internet access is required. Download completion, input preparation, real optimizer updates and checkpoints remain distinct stages.

- Existing BNCI and Dreyer files, partials and receipts remain in `paper1-risk-v1/raw/` and are reused by directory links.
- Corrected Yang files are stored separately under `paper1-risk-v1/raw-nemar-privacy-v1/yang/`.
- Corrected Yang person caches use `cache_dir/yang-nemar-privacy-v1/`; other dataset caches retain their original locations.
- Prepared model inputs use `paper1-risk-v1/data/prepared-nemar-privacy-v1/`. Old paths, failed attempts and original Yang files are retained.
- First activation checks that no same-project scheduler job or old scientific checkpoint is active. This prevents mixing input versions. Subsequent resume reuses the selected version and its checkpoints; it does not repeat the initial migration or scientific tests.
- Interrupted transfers resume partial bytes and reuse stat-bound, SHA-verified receipts. Transient network errors use the existing backoff. Hash/length/metadata changes and genuine access refusals remain visible failures, rather than being reported as completed work.

## Fixed provenance and independent checks

Official source: [NEMAR nm000348](https://nemar.org/dataexplorer/detail?dataset_id=nm000348), version `v1.0.5`, dataset Git commit `ff0a1f44675fc7d8083d764f6611607309aa2a1d`.

Official manifest: `https://data.nemar.org/nm000348/v1.0.5/manifest.json`, 887450 bytes, SHA256 `8a3d6062deccba604f252cda6aaa8f5de883bfd888c07ebcfc622e911d01aa3d`.

The provider's [privacy-correction policy](https://docs.nemar.org/policies/privacy-corrections/) changes patient and recording identification fields at BDF byte ranges `[8,88)` and `[88,168)`. Its provenance links all 306 original native file hashes to the original Figshare v5 inventory. Provider statements about payload preservation are distinguished from our independent checks:

1. One full signal/event pair was independently downloaded from both original and corrected sources. Both versions passed their own full SHA256. Every byte outside `[8,168)` was identical, including the complete signal/event payload after byte 256. This is a two-file whole-payload comparison, not an independent comparison of all 306 original payloads.
2. All 306 corrected full record headers were retrieved and hashed; all original data/event clocks matched exactly. Header hashes in the new registry are actual corrected-header hashes.
3. All 153 corrected event files passed full new SHA256 and the unchanged clock/event qualification rules: 51 people and 30591 qualified cues, with frozen labels, onsets and eligibility retained. The original transient HTTP500 attempt and its bounded missing-file recovery are preserved separately.
4. All six metadata files passed their original size/CRC and official Git-object identity checks; the new contract additionally pins their actual full SHA256.
5. All 174 Dreyer official URLs returned HEAD200 with frozen size/SHA ETag declarations. This is provider metadata verification; each downloaded EDF must still pass its actual full frozen SHA256.

No identity field is restored or printed. No EEG samples are patched, no array is changed to fit a hash, and the original SHA/ZIP CRC values for corrected BDF files are recorded only as ancestry. The corrected files have their own mandatory full SHA256 checks. The six unchanged metadata files retain original CRC checks as well.

## Contracts and scientific policy

- `config/yang_nemar_privacy_v1.json`: 312 selected native files, actual new hashes and original ancestry. SHA256 `8cdf62ce36a0541b1e043e3b6c7bc973bb44669846a7f62c94c49fb4854e6a04`.
- `config/yang_clock_registry_nemar_privacy_v1.json`: new file/header identities with unchanged clocks. SHA256 `3c0028572761b1b7f17b29cab1d16e0274359399390b0d8ffa799107c5a9242c`.
- `config/eligibility_manifest_nemar_privacy_v1.json`: new event-file identities, unchanged session/event/eligibility fields. SHA256 `3743fdde0e566e5ed0237094301771375836918c83fd004352f8e2dc524de305`.

The isolated policy adapter validates the original policy-code hashes, uses the original clock-registry implementation with the separate corrected registry, and restores module bindings afterward. It neither disables validation nor presents corrected bytes under original hashes. Runtime implementation hashes are evidence, not mutable scientific input identities that invalidate checkpoints after operational fixes.

Original vendor code, subjects, trial counts, event mapping, unit convention, windows, channels, filters, architecture, schedules, seeds, source-only model selection and statistical rules remain unchanged. No target data enters duration selection, normalization fitting or BatchNorm updates. This delivery does not claim new training or scientific results.

## School observations

```bash
cat /public/home/zhuziyuan/projects/paper1-risk-v1/state/login_pipeline_status.json
```

```bash
tail -n 30 /public/home/zhuziyuan/projects/paper1-risk-v1/logs/login-pipeline.log
```

The route probe reads one event byte. `NEMAR_PRIVACY_NATIVE_ROUTE_VERIFIED` establishes a route only. Native completion requires all 504 selected objects with the appropriate versioned hashes. Submission acceptance is not evidence of training; use actual steps and checkpoint progress.
