# Operational update — 2026-10-15

Use [the new recovery supplement](../../REDESIGN_HANDOFF_20261015/README.md)
and [DOT_NEXT](../../REDESIGN_HANDOFF_20261015/DOT_NEXT.md) for current status,
fixed execution pin and the required operation-specific priority receipts. The
older text below is retained as history; do not infer current paths, Paper 2
fit state or accounting from it. No Pod/install/EEG/fit operation is authorised
by this preparation update.

# After the first formal source acceptance: runtime and recovery remain pending

## Latest steering: container rebuilt; old paths expired

The author reports a rebuild at 2026-10-14 14:59:11UTC on the same Pod 52ivinpjwv947i:
container b5646c12356b → a7d3f0e408a4; `/workspace` now contains only `.cache`, and
overlay capacity changed 30→50GiB. The cause and live filesystem have not been
independently observed here. dot reportedly issued no Stop/Restart and fit7 did
not execute. All pre-rebuild source/runtime/checkout paths below are historical,
**not available candidates**. No stale preflight or reuse command is authorized.

Use `CONTAINER_REBUILD_RECOVERY_GATES.md`, `CONTAINER_REBUILD_DEPENDENCIES.md`,
`PAPER2_REBUILD_POINTERS.md` and the fixed `DOT_RUNTIME_ACCEPTANCE.md` plan.
This round only delivers code/protocols: no Pod connection, install, R2 request,
target reads or training. Off-host/R2 backups are author-reported; actual
snapshot keys/manifests/blob readback remain separate verification gates.
The existing 48-hour authorization still ends 2026-10-16 09:54UTC; recovery cannot
extend it or overwrite the historic eight-hour ledger. Do not recreate SSH
keys, credentials or security settings. Only the existing HTTPS/browser route
may be used by dot after the separate recovery scope is cleared.

The author supplied the exact 12299-byte formal CPU acceptance archive. Its
SHA256, 16 manifest payloads + manifest, ten fixed97f execution identities,
archived source, command/log/report/exit3 and retained parsing correction were
independently verified. See
`../formal_numerical_execution/FORMAL_SOURCE_RECEIPT_INDEPENDENT_AUDIT.json`.
No diagnostic or source acceptance was rerun in this preparation.

The recorded source hash gate passed for 18 files / 108 runs / 2592 trials and all three
bands. This was the **diagnostic** runtime, not accepted training runtime.
Ten scheduling snapshots contain six GPU PID observations; five are non-zombie
paper2 GPU children and the last is zombie. Paper2's local fit-saved/backup-pending
receipt was observed, not independently scientifically or remotely audited here.
No receipt establishes the current live Pod state.

## Tools and their boundaries

| Tool | Allowed scope | What it never authorizes |
|---|---|---|
| `runtime_preflight.py` | Byte-bound donor metadata, existing private archive binding, historical accounting and target mapping metadata | Installation, source acceptance, restoration, fit or budget transition |
| `donor_gpu_inventory.py` | Exact torch 2.8.0+cu128/torchaudio 2.8.0+cu128, NVIDIA/triton pins, Python ABI, safe package paths, METADATA/RECORD and small module hashes | Actual GPU imports, exhaustive binary integrity or GPU computation |
| `isolated_training_runtime.py` | Plan by default; `--prepare` creates one new lightweight child after independent donor review | Job registration, core resume or training |
| `accept_training_runtime_source.py` | ONE separately registered CPU source acceptance via actual trainer's loader, bound to the prepared child and 134436-byte archive | Models, CUDA tensors, target access, review PASS or recovery |
| `transition_target_gate.py` | Frozen metadata and known non-secret old records; all unknown gates stay pending | New budget, identity equivalence, checkpoint absence or target restoration |

Detailed once-only commands are in `DOT_RUNTIME_ACCEPTANCE.md` in the subsequent
fixed handoff documentation commit. Historical `DOT_ACCEPTANCE.md` documents the
already completed diagnostic-role acceptance; **do not run it again**.

## Lightweight environment plan

The only pre-rebuild observed donor candidate was `/workspace/.venvs/paper2-gpu/bin/python`.
That path is now **expired** and its independently checked paper2 public lock
was Python 3.11.16, whereas paper1's original public runtime lock is Python 3.12.3.
The whole torch/torchaudio/triton donor scheme cannot cross these ABIs. The new
guard requires paper1's exact 3.12.3 before creating a child or source acceptance.
Any current template Python/CUDA component must
first be measured after recovery; this document does not prove one exists.
Its NumPy 2.2.6 / SciPy 1.15.3 do not satisfy paper1's fixed 2.3.5 / 1.17.0 and will not
be reused. The archive did not prove its torch/CUDA identities: inspect first.

Create a new no-inheritance venv using the measured donor base interpreter and
matching ABI. Reuse ONLY reviewed torch/torchgen/functorch/torchaudio/torio/triton/
nvidia directories and their distribution metadata as read-only symlink targets.
Do not add the donor's site-packages to sys.path, copy CUDA, alter paper2, force
OpenBLAS, or change numerical thread settings. Bytecode writes are disabled.

The resolver is constrained to the measured GPU versions; any protected package
installation aborts. Lightweight wheels are from PyPI, exact SHA-bound and
binary-only. Before installation, every wheel is checked for package/version,
size, safe paths and GPU destination collisions (including `.data` remapping),
startup hooks and symlinks. The sole startup-file exception is setuptools'
byte-exact local distutils shim (`2638ce9e…`), needed for torch on Python3.12;
modified content or the same file in another package blocks. It adds no foreign
package path. Install with `--no-deps --no-index` to prevent
uninstalling linked GPU distributions. Missing/unsupported wheels block; there
is no source-build or second-CUDA fallback.

Bound **new peak storage to 3 GiB** (retained wheels + twice expanded files + 256 MiB
overhead), require 13 GiB initially and retain at least 10 GiB. Child-owned TMPDIR
also covers ensurepip. Installation subprocesses and downloads monitor space
and abort their OWN process on a threshold or timeout. Paper2 can concurrently
change free space; these are measured abort guards, not an atomic filesystem
reservation or a promise that training will fit. Failed logs/partial environment
are retained; no automatic retry or deletion is implemented.

Later acceptance verifies actual numerical and GPU module origins/versions,
sys.path isolation and stable donor metadata before/after. It imports the actual
trainer/validator and calls the trainer's source loader once on CPU. No model or
CUDA tensor is created. All18original files, 108 runs, 2592 ordered unique trial IDs,
7776 trial-band hashes and three aggregate hashes retain the original strict gate.
The archived full diagnostic package must independently bind its exact SHA.
Even exit 0 remains **TRAINING_STILL_BLOCKED** until its review and other gates.

## Accounting and target gates

See `TRANSITION_AND_TARGET_GATES.md`, the PLAN_ONLY template and schema. The old
job/revision, native failure and original 07:07:45–15:07:45UTC eight-hour budget
remain immutable. Inaccessible old records stay unobserved; absence does not
establish zero counts/checkpoints or machine identity. Cross-machine/revision
resume is not implemented by these tools. A future independently reviewed
transition must reconcile counters/intents/checkpoints and verified private
backups and record a separate explicit funding/machine amendment. No clock is
renewed here, and no fit-cap/update-cap is removed.

The source-only R2 mapping still lacks all 174 Dreyer object keys. The target raw
inventory is 2515343396 bytes; full acquisition 174 EDF and fixed 85 participants /
6800 events after provider A17/A41 exclusions remain unchanged. Existing importer
requires 192 source+target mappings, verifies real bytes, downloads only missing
files and has no provider fallback. These tools only review metadata. The fixed
512Hz trial-band strict gate has not been tested on restored target EEG here.
No alternative numerical profile will be chosen from target failures/outcomes.
Unknown prior exposure keeps Dreyer exploratory.

dot remains the unique operator of bright_ivory_bear/52ivinpjwv947i. Keep the Pod
running for the two papers. This release never starts GPU fitting, changes
paper2, reads credentials, or issues Stop/Terminate. No manuscript/result,
historical submission, main or publication tag is changed.
