# Container rebuild: restoration dependencies and conditional GPU storage plan

This is a **plan only**. No Pod inspection, HTTP request to the Pod, environment
installation, GPU-wheel fetch, raw-data restoration, acceptance or fit is
authorized or executed by this document. Only dot operates the server. Do not
Stop or Terminate the Pod.

## The old container evidence does not identify the current runtime

The same Pod ID `52ivinpjwv947i` reportedly rebuilt its container at
`2026-10-14T14:59:11Z`, from `b5646c12356b` to `a7d3f0e408a4`. The reported
post-rebuild `/workspace` contains only `.cache`; the overlay allocation changed
from 30 to 50 GiB. These are incident observations supplied by the operator,
not a current preflight performed for this delivery. **50 GiB allocated does
not establish 50 GiB free, a durable volume, sufficient GPU memory, or a usable
Torch installation.** Do not delete `.cache` or assume it is disposable.

All paths in the preceding acceptance package and commands are historical:

- `/workspace/.venvs/paper2-gpu/bin/python`;
- `/workspace/paper1-diagnostic-runtime`;
- `/workspace/paper1-formal-numerics-review-97f1f42a`;
- `/workspace/paper1-source-diagnostic-c802`;
- `/workspace/paper1-readonly-probe/data` and its acceptance outputs;
- `/workspace/mi-eeg-cloud`, including its already-unobserved registration.

Do not execute old commands, reuse a former symlink target, infer an empty
checkpoint inventory, or register a replacement experiment because a directory
is absent. The verified historical CPU acceptance remains valid evidence for
the bytes it observed; it does not qualify this new container's training
runtime. Retain the original diagnostic and formal acceptance archives,
native failure, frozen hashes, original submissions and both papers' records.

The operator's existing 48-hour deadline is **2026-10-16 09:54 UTC**. Rebuilding
the container, restoring dependencies or waiting for review does not extend it.
The old paper1 eight-hour ledger started
`2026-10-14T07:07:45.290107Z` and expired
`2026-10-14T15:07:45.290107Z`; it must not be reset or replaced silently. The
48-hour authorization/deadline and any execution-budget amendment must be
recorded with their actual provenance rather than treated as a new launcher
clock. Existing scientific fit/update limits remain in force.

## Exact paper1 package requirements

The GPU dependency pair is:

| Package | Exact required build |
|---|---|
| CPython | `3.12.3` (the original paper1 runtime lock) |
| Torch | `2.8.0+cu128` |
| torchaudio | `2.8.0+cu128` |
| Torch compiled CUDA runtime | `12.8` |

The committed paper1 lightweight pins remain:

```text
braindecode==1.5.1
numpy==2.3.5
scipy==1.17.0
pandas==2.2.3
mne==1.13.2
scikit-learn==1.8.0
skorch==1.4.0
einops==0.8.2
h5py==3.16.0
joblib==1.5.3
threadpoolctl==3.6.0
boto3==1.40.61
pytest==9.1.1
```

The controlling source is
`research_runs/REDESIGN_CLOUD_20261013/requirements.txt`, not this duplicated
human-readable list. A future resolver must byte-bind that file from a fixed
reviewed checkout and produce an exact, hashed transitive wheel plan. Do not
guess NVIDIA or Triton versions: require the exact dependency pins declared
by the authenticated Torch `2.8.0+cu128` wheel METADATA. Every wheel must match
its reviewed SHA256, ABI/platform tags, metadata and package identity.

The public old-job `runtime_lock.json` was measured at
`2026-10-14T07:19:18.587714Z`, before source fits, and explicitly freezes
CPython `3.12.3` alongside the GPU/numerical package pair. The retrieved JSON's
SHA256 is `a18529ba66d7e73f47438981eafe1b2f7761d6b028998871d621a7656c7e1fa6`;
its source is the historical
`redesign/run-20261014T071918Z-exploratory-89b0c07d` branch under
`research_runs/REDESIGN_CLOUD_20261013/jobs/20261014T071918Z-exploratory-89b0c07d/runtime_lock.json`.
The same bytes were independently read back at immutable receipt commit
`d612f0cc2bcca045ff1304bc95a87df76bfd4a82`;
its old machine/GPU identifiers do not identify the current rebuilt container.

Public package references are the [PyTorch previous-version instructions](https://pytorch.org/get-started/previous-versions/)
and the [official CUDA 12.8 wheel index](https://download.pytorch.org/whl/cu128).
These links identify the intended provider; **no index or wheel has been
fetched for this container-rebuild plan**. An NVIDIA driver reporting a newer
CUDA capability does not establish the installed Torch/torchaudio build or
their actual library paths. Paper1 requires the original CPython `3.12.3`
runtime and its measured native ABI; accepting a generic supported 3.11/3.12
interpreter would silently change the frozen runtime contract.

The separately retrieved public paper2 first-fit receipt records CPython `3.11.16`,
Torch/torchaudio `2.8.0+cu128`, NumPy `2.2.6`, SciPy `1.15.3` and braindecode
`1.2.0`. Thus paper1 and paper2 use **different CPython ABIs** even though
their nominal Torch/CUDA versions agree. Whole Torch, torchaudio or Triton
package directories/extensions must not be shared from a `cp311` environment
into `cp312`, or conversely. The precise paper2 evidence pointer belongs in
the [parallel paper2 rebuild inventory](PAPER2_REBUILD_POINTERS.md): fixed
commit `f49a9779b53defbe38479d6ad7789b441cc4ad21`,
`research_logs/kumar_first_gpu_fit_20261014/fit_text_evidence/fit_result.json`,
SHA256 `5e3f6579f028193506dfd3d99c4df9d1c1e0ade781cdccf53d3443ee535158dd`.
Its GPU lock is `environments/gpu/uv.lock`, SHA256
`11682d951fe204e32859da12d9cc0ac73c6e63c1bce061d9834f8f68ebfe72e0`.
Neither public record measures the rebuilt container.

A venv cannot supply a missing interpreter version. If either frozen CPython
version is unavailable, restoration stops pending a separately reviewed image
or authenticated interpreter-distribution plan. Do not switch either paper's
Python version, upgrade global Python, or build a substitute interpreter
automatically to make a dependency resolver succeed.

## Two conditional construction routes, neither executable now

### A. A newly measured exact template can donate GPU components

Only after separately authorized current-container metadata observation may
an existing interpreter be considered. The old paper2 interpreter is not a
candidate by default. Require the current interpreter identity, prefix/base
prefix, exact CPython `3.12.3`, SOABI/cache tag, exact GPU metadata pair, all Torch-declared NVIDIA and
Triton pins, package paths, METADATA/RECORD hashes and critical module hashes.
Reject unrelated site roots, symlink chains of unknown origin, mixed CUDA
namespace majors or mismatched package metadata. Successful metadata inspection
is still not an actual trainer-import/source-input acceptance.

Create a fresh paper1 child venv without system-site/user-site inheritance.
Reuse only the reviewed GPU components and corresponding metadata, preserving
the donor unchanged. Install the frozen non-GPU wheel plan into the child.
Keep NumPy/SciPy and every other scientific dependency in the paper1 child;
never import them from a complete donor site through `.pth`/`PYTHONPATH`.

The current `isolated_training_runtime.py` implements this **donor-only**
route with a maximum 3 GiB newly allocated runtime/wheel-stage budget and a
10 GiB remaining-free-space floor. It rejects protected GPU installation;
it is **not a fresh-CUDA installer**. It must not be invoked using old paths
or a historical donor report after the rebuild.

### B. No exact donor: prepare ABI-specific GPU environments with reviewed storage

If no currently measured exact template exists, stop the donor-only route.
Do not trigger the old launcher's isolated-CUDA fallback: that launcher can
continue into job registration/execution and is not a restoration-only tool.

A separately reviewed fresh-environment implementation would:

1. Measure availability of CPython `3.12.3` for paper1 and `3.11.16` for paper2,
   their respective ABI tags, actual mount/free space, existing CUDA package
   allocation, operating-system/driver compatibility and concurrent paper2
   storage commitments. These observations are not performed by this plan.
2. Resolve the exact Torch `2.8.0+cu128` / torchaudio `2.8.0+cu128` pair for
   **each frozen CPython ABI**, including the correctly tagged Triton build
   and its pinned NVIDIA dependency closure. Use hashed binary wheels only;
   no source builds or unbounded caches. Different `cp311` and `cp312` Torch,
   torchaudio and Triton packages are required by the existing contracts and
   must not be collapsed into one donor package directory. Freeze compressed,
   expanded and transient bytes before installation. Do not mutate a new
   template's global Python.
3. Place the environments at new, current-container-qualified locations; do
   not recycle historical runtime paths. **NVIDIA-only** components may be
   candidates for one physical shared owner only if both authenticated wheel
   dependency closures require identical package versions/hashes and their
   actual `py3-none`/platform tags, namespace layout and loader paths permit
   reuse across the two Python versions. This is a conditional storage option,
   not a present implementation or verified compatibility. No manual patching
   of Torch/torchaudio binaries, private library paths or wheel RECORDs is
   allowed to force it. If this cannot be demonstrated, budget the complete
   isolated GPU closures honestly and seek review before allocating them.
4. Paper1 receives NumPy `2.3.5` / SciPy `1.17.0` and its committed pins.
   Paper2's previously reported NumPy `2.2.6` / SciPy `1.15.3` is **historical
   evidence**, not a measurement of the rebuilt container; restore paper2 from
   its own actual frozen runtime contract and import checks. Do not install
   paper1 scientific packages into paper2 or change Python version solely to
   enable sharing. Both existing contracts require the same nominal GPU pair,
   but their native Python extensions are still separate ABI-specific builds.
   Additional CUDA payload duplication, if required, needs a separately reviewed
   storage plan rather than an automatic fallback.
5. Bind GPU/component paths and hashes into each environment receipt. No whole-site
   inheritance. A pip plan must never install, uninstall or overwrite a
   borrowed GPU component, including via wheel `.data` paths or startup hooks.
   Validate actual module origins and donor bytes before and after imports.

This fresh-ABI route is **not implemented or approved for execution by the
donor-only helper**. Missing installation tooling or unavailable disk capacity
must be reported explicitly; do not turn a plan document into an unbounded pip
command or claim restoration is complete.

## Storage conditions: allocation is not free-space evidence

Use future measured bytes and the same filesystem that will hold the GPU components,
child environments, raw cache, arrays and recovery snapshots. If they occupy
different filesystems, enforce a separate budget for each. Monitor free space
throughout every permitted operation because paper2 may write concurrently.
Do not count symlinked CUDA payloads twice or ignore temporary wheel copies.

| Item | Bound or known frozen size | Meaning |
|---|---:|---|
| Existing donor-only route | 3 GiB maximum new bytes | Child, wheels, installation/evidence overhead; no CUDA copy |
| Proposed fresh-ABI GPU route | 20 GiB maximum peak new bytes | **Provisional hard ceiling**, not a measured wheel-size estimate; includes both required ABI-specific GPU/lightweight closures, retained wheels and transient install overhead; NVIDIA-only reuse must be demonstrated rather than assumed |
| Required remaining free-space floor | 10 GiB | Must remain available through preparation; not proof of future training capacity |
| 18 BNCI MAT files | 779873919 bytes | Frozen full raw source inventory, about 0.726 GiB |
| 174 Dreyer acquisition EDF files | 2515343396 bytes | Frozen full target acquisition inventory, about 2.343 GiB |
| Combined raw inventory | 3295217315 bytes | About 3.069 GiB; target restoration is still separately gated |
| Source plus target float32 three-band tensor payload | 685240320 bytes | Arithmetic bound from frozen 2592/6800 trials × 19 channels × 320 samples × 3 bands × 4 bytes; excludes container/archive/temp copies and metadata |
| Repository/metadata restoration allowance | 2 GiB provisional cap | Future actual checkout/download footprint must be measured |
| Checkpoints, backup staging and paper2 outputs | Not yet measured | Separate mandatory storage reservation; not zero because old paths are absent |

The 20 GiB fresh-route cap is a policy proposal for a future implementation.
It does not assert that current wheels fit it. Authenticate and sum actual
compressed/unpacked sizes and the installer peak first. Refuse any plan above
the cap; changing it requires a reviewed amendment, not an automatic expansion.

Before fresh-ABI environment creation, require at least `20 GiB + 10 GiB` free **plus all
unrestored raw/repository, prepared-array duplication, backup staging and paper2
commitments** that must coexist with the installation. Therefore 30 GiB free
alone is not complete-project capacity. The reported 50 GiB overlay may or
may not satisfy this condition after base image and existing allocations.
No deletion or Pod resize is authorized here. An exact template donor reduces
new allocation substantially, but it must first be measured rather than assumed.

The existing R2 importer separately requires missing raw bytes plus 6 GiB
reserve before GET; that guard does not substitute for the full concurrent
runtime/training storage ledger. Restore only missing verified files after
authorization; absence in a rebuilt container does not authorize raw-data
downloads in this preparation turn.

## Complete restoration gates before any future paper1 fit

All of the following must be resolved through actual evidence, in order; none
is marked passed by this file:

1. **Current container and access.** Preserve the rebuild incident. Establish
   the actual current writable mounts, Python, GPU/package inventory and disk
   commitments only after permission for that observation. Browser/HTTPS is
   the stated access route; no SSH-key, API-key or credential copying is needed
   for this plan. Do not invent a Jupyter URL or assume an old endpoint works.
2. **Fixed public source and private evidence.** Restore the reviewed fixed
   checkout and exact evidence archives to new paths. The original full-source
   package is 134436 bytes with SHA256
   `2871f422755bf5d0b939d0db59fc41547b192d6c939db1a6a13b97a91ba49ae9`;
   the formal CPU package is 12299 bytes with SHA256
   `a4c6c3f7beadf6ce0c927c6e4b9d20b6d37ff3bc2c033ad4b4fd836ca38a6b0d`.
   Their completed independent audits need not be repeated as scientific
   diagnostics. Verify restored archive bytes and code identities, not an
   assumed local cache. Binaries/raw EEG do not go into GitHub.
3. **Old execution, budget and backup reconciliation.** Recover authentic old
   registration/ledger/launch/checkpoint/update-intent evidence if available;
   record missingness explicitly. Retain the zero-fit failure evidence without
   treating inaccessible directories as newly proved absence. A committed,
   read-back-verified private recovery copy is review evidence, not resume
   authorization. Record the unchanged 48-hour deadline and the old eight-hour
   ledger, and require a reviewed transition implementation before execution.
   Paper2's completed-fit receipts also must be reconciled before dispatching
   its next fit; rebuilding must not cause duplicate fits in either paper.
4. **Source raw recovery and exact current runtime.** Restore the 18 source
   files through the reviewed identities and preserve all SHA gates. Use route
   A or a separately implemented/reviewed route B. Bind the actual isolated
   training consumer and the audited full package in one future read-only CPU
   source acceptance for the **new** runtime. Require all 18 files, 108 runs,
   2592 trials, three aggregate hashes and 7776 trial/band hashes unchanged.
   This is not a repeat of the prior diagnostic; it checks the actual runtime
   that would later consume training inputs. No target EEG or saved substitute
   arrays, and no fit or CUDA tensor operation in that acceptance.
5. **Dreyer mapping and target restoration.** Authentic object keys for all
   174 frozen Dreyer EDF files remain missing from the source-only R2 mapping.
   Obtain actual upload/object evidence through a separately authorized metadata
   operation; do not infer keys from filenames. Review the exact 192-file
   source+target mapping and byte/hash identities before any restoration. Then,
   only when authorized, restore missing objects and perform frozen raw/input
   checks. Retain A17/A41 provider exclusions, 85 retained participants, 6800
   events, the fixed 512 Hz numerical rule and all original target-input gates.
   Existing R2 objects/access are not proved by historical receipts alone.
6. **Execution freeze and recovery authorization.** Numerical review, real
   consumer imports, current-machine identity, explicit budget transition,
   backup ownership, full target restoration/mapping and all original scientific
   gates must be independently bound before one resumed/transitioned worker can
   fit. Preserve Broad/shared, fixed20/mean-loss/mean-rank, 19 channels, seeds,
   source-only selections and eval-only target BatchNorm. Dreyer prior exposure
   remains unknown; external evaluation remains exploratory. No new outcome-
   driven analysis or target fitting is authorized.

The current deliverable remains code/protocol preparation. Training
authorization is false, old clocks are unchanged, no raw data are read or
downloaded, and the Pod remains running under dot's sole control.
