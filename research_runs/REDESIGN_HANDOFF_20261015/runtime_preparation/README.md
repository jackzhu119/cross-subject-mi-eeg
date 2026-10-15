# Preparation-only controller after the actual run01 plan

The accepted plan has already run once. **Do not dispatch another standalone
plan/metadata task, old full-source diagnostic or CPU source acceptance here.**
The unchanged preparation helper still performs its required read-only donor
identity checks before and after its own preparation; those are not scientific
diagnostic reruns.
This directory supplies a later dot-operated preparation controller; it has not
been executed against the Pod. Paper 2 retains priority, its environment and
files are protected, and its fit/acceptance counts are not reinterpreted here.

## Bound inputs and unchanged inner helper

- Fixed inner checkout: `1efe9d1ba2ab8671ad1bf76c360e067fb63fd7ac`.
- Existing independently fetched checkout, reported by dot:
  `/workspace/paper1-metadata-code-1efe9d1`. The controller checks its actual HEAD,
  clean worktree, Git bytes and helper/slot/requirements SHA256; it never resets it.
- Inner `isolated_training_runtime.py` SHA256:
  `cdd8c2d47fb6e1653e8b5c2eb48de6483d4dd57a0af392f2c1495669e3c0cd9e`.
- Accepted plan stdout: exactly 25,128 bytes, SHA256
  `e4852d1e2517abc69464c22e69658c2618d8e3950184fa40eb4c8a2af6ce5a0c`.
- Complete donor report: exactly 22,450 bytes, SHA256
  `3a83a9cf93cca3e9813056645bc73f26a9429ee6f1f7bc06f2ae78a1c36471b1`.
- New environment, which must still be absent:
  `/workspace/paper1-training-runtime-cp312-run01`.

The inner helper is unchanged. It uses `/usr/bin/python3` 3.12.3/cp312 with existing
`venv`/`ensurepip`. Only enumerated GPU components and their distribution metadata
are linked from the reviewed same-ABI donor. The whole donor site is not inherited;
Paper 2's cp311 packages are never borrowed. Numerical dependencies and their
scientific requirements remain frozen. No apt, global pip, CUDA reinstallation,
source builds, alternate resolver indexes or numerical-thread changes are allowed.

## Required reviews and fresh slot

`dot_parent_review.PLAN_ONLY.json` is deliberately invalid. It does not grant an
operation. The parent must separately review the preparation policy and its cost
handling, retaining unknown historical spend and the original cumulative caps.
That reviewed record must bind the exact accepted plan, donor, helper and new
environment. It must explicitly acknowledge that the actual non-GPU wheel
resolver closure is **not yet observed**; policy review must not be presented as
prior approval of an actual unseen wheel closure.

Only after that review may dot issue a **new** `runtime_preparation` slot under
the fixed priority gate. Parent review must postdate the actual plan completion
at `2026-10-15T03:25:20.668962Z`; the new slot must be issued after that review and
expire within its validity. The old plan slot (SHA256
`17edfc14fc4b8a96591b07896b0f61ff3ab3bafa6bcf666901de759dae3ed23f`) is
explicitly rejected by comparison against the pinned accepted plan. The earlier
metadata slot is also rejected by operation and issue time. No slot is renewed
or manufactured by this controller. The existing overall deadline remains
`2026-10-16T09:54:00Z`.

New writes, including the child environment **and all outer evidence**, remain
within 3 GiB or the tighter fresh-slot cap. Remaining free space must remain at
least 10 GiB plus dot's reserve, with at least the accepted 5 GiB Paper 2 reserve.
Thus a full 3 GiB slot initially requires at least 18 GiB free. Capacity or an old
free-space observation is not a fresh measurement. No folders are deleted to
create space. Failed child environments/logs are retained; rerun/reuse is refused.

The maximum wall time is 20 minutes or the tighter parent bound, slot/review
expiry and existing authorization deadline. Slot, review identity, evidence sizes
and combined allocation/free-space limits are checked every 0.25 seconds and
after the helper returns. This is polling rather than an atomic filesystem quota
or a claim of continuous platform monitoring. The unchanged helper also checks
its own phases/downloads. On failure, the controller first interrupts its own
helper so the helper can clean its newly spawned installer sessions. Fallback
termination is limited to descendants whose PID/starttime was actually observed;
it never uses `pkill`, `killall`, process-name matching or reads process secrets.

## Exact invocation shape for the reviewed future step

The final delivery pins the controller's own commit/hash separately from the
unchanged inner-helper revision. Use the actual existing accepted-plan and donor
paths, not the original tarball or reconstructed JSON. All stdout, stderr and
inner install-log paths below must be **distinct, absent direct `/workspace`
children**. The dispatch receipt is a fourth new sibling formed from stdout's
name plus `.dispatch.json`. No output may overlap an input, Paper 2 or global paths.

```bash
/usr/bin/python3 -I -B /PATH/TO/PINNED/prepare_runtime_only.py \
  --code-dir /workspace/paper1-metadata-code-1efe9d1 \
  --donor-report /ACTUAL/PATH/gpu_donor_inventory.json \
  --accepted-plan /ACTUAL/PATH/plan.stdout.json \
  --review-record /ACTUAL/PATH/dot-parent-approved-review.json \
  --priority-receipt /ACTUAL/PATH/new-runtime-preparation-slot.json \
  --output /workspace/paper1-runtime-prepare-run01.stdout.json \
  --log /workspace/paper1-runtime-prepare-run01.stderr.log \
  --install-log /workspace/paper1-runtime-prepare-run01.install.log
```

There is no plan mode or retry mode here. The only helper child contains
`--prepare --log`, and cannot start before the independent review and new slot
have passed. Do not run this command merely because this README exists.

## Package-source and completion evidence

The inner helper's bounded dry resolver uses only `https://pypi.org/simple`,
binary wheels and exact frozen requirements/GPU constraints. Downloaded wheel
origins must be HTTPS `files.pythonhosted.org`; each needs an explicit SHA256,
bounded length and exact received bytes. It rejects GPU replacement, builds,
unsafe archive paths/startup hooks and writes into donated GPU components.
Installation uses only the retained authenticated wheels with `--no-index
--no-deps`, followed by `pip check`; no new resolver runs at install time.

The controller checks the resulting runtime receipt, donor before/after metadata,
requirements SHA, fresh slot binding, non-GPU resolver closure/wheel hashes,
GPU-component links and isolated venv configuration. It retains receipt and
closure SHA256 in the dispatch. The parent must then independently review those
actual outputs before scheduling later import/source acceptance.

Even successful preparation is **not** GPU import validation, strict source-input
acceptance, old-accounting reconciliation, target recovery, training permission,
a budget renewal, or completion of the scientific task. Source/target EEG reads
and all fits remain zero for this operation. Unknown old spend is not zero; a
platform balance is not Paper 1's attributed expense. No Pod operation occurs.
