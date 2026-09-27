# Q15 metadata-only audit entrypoint and current stop gate

The local entrypoint is `scripts/q15_metadata_audit.py`. It has **no network downloader, model import, target prediction, balanced-accuracy calculation, or training action**. It reads only explicitly listed local raw files and a local expected-file inventory; it streams each file through SHA-256 and writes a versioned JSON receipt. The plan is [Q15_CONTRACT.json](Q15_CONTRACT.json).

## Current scientific state

No real Lee2019_MI or Cho2017 raw metadata adapter has been implemented or tested against those provider files. The MOABB v1.7.2 Lee channel catalogue suggests `FCz` is absent, but catalogue text does not verify every file's actual channel table. Therefore **a real MAT file is always `blocked_raw_adapter_unverified` in the current code**, even when its listed hash matches. No receipt from this entrypoint currently authorizes Q15-E005 source training or Q15-E006/E007 external prediction. The synthetic JSON adapter exists only to test the fail-closed logic and returns the distinct status `metadata_passed_non_authorizing_synthetic_fixture`, with `provider_inventory_verified=false`. No consumer may treat that status as a real cohort audit.

The script also cannot authenticate a provider's complete file inventory merely because a caller supplies a manifest. `provider_manifest_sha256` is the hash of that *locally supplied manifest*, not proof that its list came from the data provider. `provider_inventory_verified` stays false until a separately reviewed provider-inventory adapter checks an official checksum manifest or equivalent provider record. Do not set this flag by hand.

## Input and receipt contract

The user-supplied inventory JSON has `schema_version: 1`, exact `dataset` (`Lee2019_MI` or `Cho2017`), pinned `provider_version`, `loader_version`, `license`, `provider_inventory_source`, `expected_file_ids`, and `files`. Each listed file has unique `file_id`, `path`, expected lower-case SHA-256, adapter name, subject, session, and run. The source of `expected_file_ids` must ultimately be independently checked against provider inventory; a shortened self-generated list is not sufficient. The file path may be absolute or relative to the inventory's directory. The script never searches broadly for files or downloads missing ones.

Future reviewed raw adapters must extract from **actual file bytes**, not a manually supplied summary: channel names/order, acquisition rate, native unit, loader-output unit and conversion, reference, cue/event sample origin, labeled left/right MI run type, event counts/identities, available cue-relative task interval, subject/session/run IDs, and file hash. Lee's online test runs are not labeled for scoring. Source-only harmonization can begin only when both cohorts' actual 21-channel and `[0.5,2.5)`-second contracts are proven before any external model output is read.

Before a real adapter can issue any passing metadata receipt, its independent
review must also compare the receipt **field by field against a second replay
of the actual raw bytes**, and compare each subject/session's complete run IDs
and counts with an authenticated provider inventory. Counting sessions alone
is insufficient: one surviving run per session is not a complete cohort.
Negative tests must reject a forged receipt with plausible channel/event/unit
fields but unchanged file hashes. Today's source preflight cannot satisfy
this future real-data requirement and therefore remains blocked.

Every receipt includes `status`, `raw_hashes_verified`, `provider_inventory_verified`, `synthetic_fixture`, `auditor_sha256`, absolute `provider_manifest_path`, `provider_manifest_sha256` (null when that file is absent), per-file absolute `path` and actual `sha256`, `blocking_reasons`, `metadata_only=true`, both `predictions_computed=false` and `model_predictions_computed=false`, `performance_metrics_computed=false`, `target_fits=0`, and `external_prediction_authorized=false`. A failed file or metadata discrepancy is retained in the receipt; it is never silently dropped from the cohort. A structurally passed metadata receipt still requires independent raw replay and a separately frozen source-checkpoint gate before scientific validation.

For a future, explicitly provided inventory, the syntax is:

```bash
python scripts/q15_metadata_audit.py --manifest /absolute/path/to/provider_inventory.json --output results/Q15-V001/metadata_audit_receipt.json
```

At present this writes a **blocked**, non-authorizing receipt for real Lee/Cho MAT files. The `--synthetic-fixture` flag is for automated tests only and must never be used for a scientific release. No cloud run or Git publication is triggered by the command.

Local verification: `python -m pytest -q tests/test_q15_metadata_audit.py tests/test_q15_prospective_contract.py`. Passing these tests demonstrates only schema/integrity stop rules on tiny synthetic fixtures, not real cohort compatibility.
