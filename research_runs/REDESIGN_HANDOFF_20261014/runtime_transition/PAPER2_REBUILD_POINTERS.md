# Paper 2 recovery pointers after the reported container replacement

This is a **public-record metadata inventory and recovery plan**, not an audit of
newly downloaded model binaries, an observation of the current Pod, or a release
to execute another fit. No R2 object, private credential, raw EEG, or live Pod was
accessed for this document. Archived code and receipts were read through public
HTTPS at fixed Git commits only.

## Incident and scope boundary

The user reports that Pod `52ivinpjwv947i` replaced container `b5646c12356b` with
`a7d3f0e408a4` at **2026-10-14 14:59:11 UTC**. `/workspace` reportedly contains
only `.cache`; root overlay reportedly changed from 30 GiB to 50 GiB. The cause
has not been verified. The user reports no Stop/Restart by dot, six completed
paper 2 fits backed up outside the container / in R2, and **no seventh fit**.

These are user-reported incident facts, not a fresh server preflight. Historical
Python, venv, repository, locks, result paths and temporary SSH installation are
**stale paths, not evidence that those paths still exist**. Do not reinstall SSH,
add keys, create credentials, restore security settings or extend authorization.
Use the existing HTTPS/browser route only. The existing 48-hour authorization
expires at **2026-10-16 09:54 UTC**, unchanged by recovery.

The recovery scope preserves the existing scientific project, seeds, source-only
data scope, completed results, failures, and accounting history. Rebuilding an
environment does not reinitialize the experiment, authorize refitting completed
seeds, release the next job, or renew a clock/budget. Dot remains the sole server
operator; this document requests no Pod action and no training.

## Fixed public recovery roots

- Repository: `jackzhu119/few-shot-mi-eeg`.
- Public receipt / fifth-result acknowledgement root:
  `f49a9779b53defbe38479d6ad7789b441cc4ad21` (Git committer timestamp
  2026-10-14 14:15:48 UTC).
- Historical runtime-metadata root, also appearing in archived dispatch paths:
  `90f674ff393871032eeafd9935cab8414d15e583` (2026-10-14 10:09:58 UTC).
  Its environment files and development scientific config hashes equal the
  corresponding files at `f49a9779…`; it predates the development queue files.
  The old directory name `paper2-90f674f` is a historical path label, not proof of
  a current clean checkout or a current execution revision.
- Exact executed sources, training config and input receipt remain inside each
  immutable fit archive. Recovery must bind those bytes per fit, rather than
  relabeling old checkpoints with the new receipt commit.

Public URLs below use the fixed receipt root:

- [Accepted ledger](https://github.com/jackzhu119/few-shot-mi-eeg/blob/f49a9779b53defbe38479d6ad7789b441cc4ad21/research_logs/kumar_development_queue_20261014/accepted_jobs.json)
- [Exact environment lock](https://github.com/jackzhu119/few-shot-mi-eeg/blob/f49a9779b53defbe38479d6ad7789b441cc4ad21/environments/gpu/uv.lock)
- [Frozen development queue](https://github.com/jackzhu119/few-shot-mi-eeg/blob/f49a9779b53defbe38479d6ad7789b441cc4ad21/configs/kumar_development_queue_plan_20261014.json)
- [Fifth fit reception and acceptance evidence](https://github.com/jackzhu119/few-shot-mi-eeg/tree/f49a9779b53defbe38479d6ad7789b441cc4ad21/research_logs/kumar_development_queue_20261014/sub-4-seed-20261013)

## Exact paper 2 environment conditions

The public first-fit provenance records the following runtime; the lock and
project specification resolve the same principal versions. This is a historical
condition to rebuild and then observe afresh, not a claim that it exists now.

| Component | Required paper 2 condition |
|---|---|
| Python | 3.11.16; GPU lock permits only Python 3.11 |
| NumPy / SciPy | 2.2.6 / 1.15.3 |
| scikit-learn / MNE | 1.7.2 / 1.10.2 |
| PyTorch / torchaudio | 2.8.0+cu128 / 2.8.0+cu128 |
| Braindecode | 1.2.0 |
| boto3 | 1.43.111 |
| Lock-resolved pandas / skorch / h5py | 3.0.6 / 1.4.0 / 3.16.0 |
| Numeric thread policy | existing source config `threads=1`; historical queue launcher `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1` |
| Determinism setting | historical `CUBLAS_WORKSPACE_CONFIG=:4096:8` |
| Parallel fitting | one common GPU reservation; maximum one actual fit at a time |

The complete transitive pins, platform wheel URLs and wheel hashes are in
`environments/gpu/uv.lock`, SHA256
`11682d951fe204e32859da12d9cc0ac73c6e63c1bce061d9834f8f68ebfe72e0`.
The corresponding `pyproject.toml` SHA256 is
`90a3d349023ef448f731990abcad5f3015be3f84ad338be4473d2ef790550089`.
Lock-selected CUDA dependencies include cuBLAS 12.8.4.1, CUDA runtime 12.8.90,
cuDNN 9.10.2.21, cuFFT 11.3.3.83, cuRAND 10.3.9.90, cuSOLVER 11.7.3.90,
cuSPARSE 12.5.8.93, NCCL 2.27.3, cuSPARSELt 0.7.1, cuFile 1.13.1.3,
NVRTC / NVJitLink / NVTX 12.8.93 and CUPTI 12.8.90. These are wheel runtime
libraries; the historical reported driver `580.159.04` is not a fresh driver
check and need not be fabricated as a reconstructed observation.

Paper 1 requires NumPy 2.3.5 / SciPy 1.17.0. A paper 2 venv cannot satisfy that
gate, and neither environment may be silently repinned to the other's versions.
The shared torch/torchaudio CUDA versions alone do not establish reuse safety.
Any proposed common CUDA component store needs a new measured file/version/hash
inventory, compatible Python ABI, correct package-origin checks and distinct
paper-specific numeric sites. Its old filesystem paths are unavailable. Do not
use `--system-site-packages` or whole-venv overlays to inherit an uncontrolled
NumPy/SciPy or Braindecode version. Do not copy/install a second full CUDA stack
before the combined recovery disk plan is accepted.

The historical `scripts/setup_paper2_gpu.sh` is environment preparation only. It
requires pre-existing `uv`, checks 18 GiB free, installs Python 3.11.16, then uses
`uv sync --project environments/gpu --locked --python 3.11.16 --extra deep
--extra dev --no-cache`. Those old paths and the historical roughly 12 GiB env
allowance are not measured current sizes. The script is a recovery reference,
**not an instruction to execute now**; a common-store plan may need an explicitly
reviewed operational amendment while keeping the full scientific lock unchanged.

## Frozen config / input identities

| Artifact at `f49a9779…` | SHA256 |
|---|---|
| `configs/kumar_eegnet_gpu_development_20261014.json` | `14c291ca9762cb676a5f61608ab7b895435fdb957b7396056093c8310435856d` |
| `configs/kumar_development_queue_plan_20261014.json` | `0d23a47952fe286cd47a5e4eed69ae29e7317f63edf83ea41866495686f83a5b` |
| `configs/kumar_development_queue_runtime_20261014.json` | `290b815e1aa6fb2fd9459499d84c84e48b0969c9945000704922a749a38092e5` |
| `configs/kumar_development_queue_https_20261014.json` | `10aa69b50a935587fcdaa38e4eb7424f7d3d92ab650f07f851a5083f000aaa1f` |
| `research_logs/gpu_preparation_20261014/eegnet_data_plan.json` | `b8dd6c8872f03a661b34d50fb826ef05e88e5502e9987290fec1301a4cb85363` |
| `research_logs/kumar_development_queue_20261014/accepted_jobs.json` | `66d83c24cf3e8c8263710c5955cd69c2bfe4e4c1f720f3c9c79580a94212322f` |

The frozen source development input is **127 files / 98,743,492 bytes**, including
18 EDFs from Kumar2024 NEMAR `nm000177` v1.0.5. The split SHA256 is
`ac6e9f2cdd66b3c26814cfc04edf5f8e08eb592ca523c7ab029a2fa56ffd0b28`.
It contains source TRAIN/validation only; query access is false. The prior
complete data receipt must accompany a restore and all file content hashes must
match. A backup HEAD, file size or ETag is not full-content verification.

The public frozen HTTPS manifest references the official
`https://data.nemar.org/nm000177/v1.0.5/` source with exact file hashes. It is a
credential-free alternative **only if separately chosen by dot after recovery
planning**, not a fallback to fetch now. Do not restore the full 360-EDF cohort,
45 GB cumulative data catalog, MIND, source-query or target-query data.

## Completed-result inventory and unresolved sixth result

The fixed public ledger contains **five** accepted entries. Each ledger entry's
result archive length/SHA below agrees with its public full-GET receipt. This
checks consistency of public metadata; this task did **not** GET these R2
objects, load weights or independently revalidate their scientific predictions.

| Fit | Subject / seed | Archive bytes | Immutable archive SHA256 |
|---|---|---:|---|
| 1 | sub-1 / 20261012 | 143360 | `2a4d0dd291f1f93bc0560e39b99b2e76fbf6bcba0d3a363ceb522fb4afea0f62` |
| 2 | sub-1 / 20261013 | 184320 | `d3a7858c54aab0295954be6a6431509d5acdea687171474d5d406a211d7dd2dc` |
| 3 | sub-1 / 20261014 | 194560 | `c31785de7b61c187ae3690a6d16cce8d89e5edf93be0bae6bcfce2b81a0fb309` |
| 4 | sub-4 / 20261012 | 174080 | `f889999e47b3d4f4d58604c0d4daca95578dac83d0776ba3bac629e23a3268a1` |
| 5 | sub-4 / 20261013 | 174080 | `4c8f923a0e706c7e30962415a2dd0293e13096d0a9b27b866e339b1382be1076` |

Fit 1 key:
`few-shot-mi-eeg/experiments/kumar2024/gpu-source-20261014/sub-1-seed-20261012-run01.tar`.
Fits 2–5 keys use
`few-shot-mi-eeg/experiments/kumar2024/gpu-development-20261014/`
followed by `sub-N-seed-SEED-run01.tar` as in the table. Public per-fit receipt,
acknowledgement, accepted job ID, dispatch record and manifest pointers are in
the fixed accepted ledger; preserve those bindings instead of inventing new IDs.

Fit 5 also has a separate dispatch archive, 51,200 bytes, SHA256
`3efd10b5bb87bfc8a3eb59242f99c397c0fb84a8d42e03da2de91de171304b97`.
Public reception records enumerate 14 result payloads + manifest and 8 dispatch
payloads + manifest; keep result and dispatch hashes distinct.

At `f49a9779…`, the sixth result was still planned:

- subject / seed: `sub-4` / `20261014`;
- job ID: `fe495208cd04aff921403e3e0d8c9f3e065d477deff26b28fbfe4480d9ada6c2`;
- expected result key:
  `few-shot-mi-eeg/experiments/kumar2024/gpu-development-20261014/sub-4-seed-20261014-run01.tar`;
- old planned local output:
  `/workspace/paper2-results/development-queue/sub-4/seed-20261014` (**stale**).

The user now reports fit 6 completed and backed up. Its exact archive bytes/hash,
manifest, executed revision, source input audit, result receipt and parent
acknowledgement are **pending independent binding** in this public-record review.
Do not append an invented accepted entry, infer its selected epoch or score, or
rerun fit 6 because the fixed ledger has only five entries. Do not dispatch fit 7.
A six-entry ledger requires an append-only, audited sixth acknowledgement while
the first five entries and their receipt hashes remain unchanged.

## Recovery gates, without a training command

1. Preserve the incident report and historical records outside the rebuilt root.
   Record fresh container/mount/free-space observations only when dot actually
   performs the authorized browser preflight. Do not attribute a cause or record
   an old process as live.
2. Restore clean, fixed Git source into a new path, bind all executed source
   snapshots per historical result, and verify config/lock/split hashes before
   imports. Keep original failed/interrupted records; no `reset`, directory
   overwrite or registration deletion.
3. Measure combined paper 1 / paper 2 environment, source, receipt, log and
   reserve capacity before any installation. Treat 50 GiB as reported total
   capacity, not free capacity. Preserve both numeric dependency contracts.
4. Through the existing authorized HTTPS/browser backup route only, bind all six
   archived results to manifests, source receipts and full-GET hashes. Preserve
   sixth-result reception as pending until actually audited. No new secrets,
   key files, security restoration or credential copying is part of this plan.
5. Restore only the 127 frozen development source files and receipts if needed;
   hash exact existing content and never overwrite conflicts. No query reads.
6. Reconcile the six completed job identities and append-only accepted ledger.
   Completed fits are recovered, never refit. Old lock absence on a new overlay
   is not queue authorization. Reconcile shared GPU reservation and both papers'
   accounting/authorization histories before a future dispatch.
7. A separate fresh runtime verification and parent dispatch gate must establish
   actual versions, package origins, determinism, CUDA availability, idle GPU and
   remaining authorization. Environment recovery alone does not pass these gates.
   No seventh fit or automatic queue loop is authorized by this document.

The historical whole scientific plan remains 18 participants × 3 seeds (54 fits,
maximum 16,200 optimizer updates). The released development queue remains six
development participants × 3 seeds (18 total development fits), one fit per
explicit dispatch, maximum 100 epochs / 300 updates per fit. No scientific rule,
source-only access rule, numeric thread setting, budget or stopping policy was
changed by this metadata inventory. A historical paper 2 statement of no monetary
ceiling does not remove paper 1's independent eight-hour/US$10 budget gate or
extend the common 48-hour authorization.
