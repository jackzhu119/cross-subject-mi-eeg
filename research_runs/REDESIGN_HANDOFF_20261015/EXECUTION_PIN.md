# Current continuation pin

Source restoration and actual-runtime CPU acceptance are now complete and
independently audited. Use the [original-job metadata continuation pin](continuity_resume/EXECUTION_PIN.md)
(`6710cf4e14c6182896668320fe96dfd3efa1e901`) for the next operation. The earlier
pin and commands below are preserved historical metadata/runtime preparation
evidence, not instructions to repeat completed work.

---

# Immutable Paper 1 preparation pin

**Execution code:** `1efe9d1ba2ab8671ad1bf76c360e067fb63fd7ac`.
Branch: `research/paper1-handoff-20261014`.
This is the minimal operational patch on handoff ec7ad35a/code23bbe5e4;
the numerical/scientific execution and frozen results are unchanged.

The later documentation commit adds this pin and the actual public readback
receipt. It is not a different runtime version. All future helper calls require
an actual reviewed checkout whose HEAD is the execution SHA above, not merely
the latest branch head. No old rebuilt-container path is assumed to exist.
Do not reset a worktree or delete evidence to obtain that checkout.

## Exact identities

| Execution file | SHA256 |
|---|---|
| `REDESIGN_HANDOFF_20261014/runtime_transition/donor_gpu_inventory.py` | `33d50cdc2ad09c23fa4aa93526a0edb065611d52d51eb233215f217610aa07e1` |
| `REDESIGN_HANDOFF_20261015/runtime/priority_gate.py` | `eb88b6c75381a714bd91d9b0bb0acb4fd82edf295b73a25abed4f0236c054fff` |
| `REDESIGN_HANDOFF_20261014/runtime_transition/isolated_training_runtime.py` | `cdd8c2d47fb6e1653e8b5c2eb48de6483d4dd57a0af392f2c1495669e3c0cd9e` |
| `REDESIGN_HANDOFF_20261014/runtime_transition/accept_training_runtime_source.py` | `7e78279b513e7301cf499c2cacba7f48884fb08d11888f5ff866b2b7fde90ac0` |

Paths in the table are relative to `research_runs/`.
Every changed execution/evidence/document file in this commit was fetched
from its immutable public GitHub raw URL and compared with exact committed
bytes. The detailed30-file result is
[PUBLIC_EXECUTION_READBACK.json](PUBLIC_EXECUTION_READBACK.json).
This is GitHub publication verification, not a Pod/runtime/data acceptance.

## dot's exact next operation

Current scope is still **no Pod operation or installation by this assistant**.
Dot remains the only operator, with Paper 2 first. When a fresh metadata-only
window is separately cleared, use the first block in
[DOT_NEXT.md](DOT_NEXT.md) with:

```bash
P1_REV=1efe9d1ba2ab8671ad1bf76c360e067fb63fd7ac
# Set P1_CODE to the ACTUAL reviewed checkout at this exact SHA.
# Set P1_SLOT to dot's fresh metadata scheduling receipt.
# Set P1_OUT to a NEW direct /workspace child for metadata evidence.
# These paths are deliberately not supplied as alleged current observations.
```

It only reads cp312 package metadata and small entry files; no package install,
Torch import, target EEG, model, fit or new credential. Its report is a new
observation, not a reconstruction of the author's2390-byte JSON. Return that
small report before any environment construction. The default runtime-plan
and later actual-runtime CPU-source command are also in DOT_NEXT, explicitly
conditional; this release includes no training or installation invocation.

## Remaining hard gates

The17 transcribed GPU versions are a metadata candidate, not all environment
bytes or actual imports. The isolated route is cp312-only, capped at3GiB new
allocation with at least10GiB **plus dot's Paper 2 reserve** remaining; require
the full cap plus floor before creating a child. Paper 2 cp311/global packages
remain protected. No numerical thread setting changes.

Seven historical public task records are verified, but original cumulative
accounting/checkpoints/private backup and174 actual target R2 keys remain
unresolved; the existing R2 metadata identity returned401. Unknown costs are
not zero. Preserve the old job, failures and caps; append only the authorised
calendar deadline2026-10-16 09:54UTC, without extending the operator window or
resetting $10/8GPUhours/fit/update counters. The unchanged production budget
gate still blocks. All source strict hashes, real-runtime acceptance, old
accounting and complete target mapping/restoration gates must pass before any
separately reviewed Paper 1 execution transition can be considered.
