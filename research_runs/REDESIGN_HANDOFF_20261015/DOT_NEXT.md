# Historical metadata/runtime handoff — completed; do not rerun

**Superseded by [the actual source/runtime acceptance and original-job
continuity handoff](continuity_resume/DOT_CONTINUITY_NEXT.md).** The complete
actual acceptance package has now been independently verified. Do not execute
the preparation/diagnostic/acceptance commands below again. Financial
prerequisites are superseded-by-user; the historical wording below is retained
as evidence, not a current requirement. Paper2's remaining36 GPU items have
absolute priority; current P1 work is bounded metadata-only preparation by dot.

This file supplements, rather than erases, ec7ad35a/23bbe5e4 and all original
failure/acceptance evidence. Use the immutable execution commit and helper SHA
in `EXECUTION_PIN.md` accompanying this release. Do not mix versions. No path
below is asserted to exist on the rebuilt Pod. Obtain any approved code through
the existing HTTPS/browser route only; no SSH/key/security change or new secret.

**Current instruction remains preparation only. The following is a conditional
operator handoff, not an instruction to operate the Pod now.** Paper 2 always
has priority. Its fit7 is already complete per the author's separate audit;
do not re-run it or inspect its environment here. No Paper 1 GPU/fit is included.

## 1. Only the next small metadata observation

Dot first verifies a spare metadata window without affecting Paper 2 and
creates its own fresh scheduling record from
`runtime/paper2_priority_slot.PLAN_ONLY.json`, with `operation=metadata`.
It must contain actual timestamps, explicit Paper 2 reserve/rationale and the
granted status only after dot's check. The template is not a grant and this
handoff does not generate one. Do not invent current free bytes or reserve.

In the existing browser terminal, **later, when this operation is cleared**,
set four nonsecret paths/identities. `P1_REV` is copied from `EXECUTION_PIN.md`;
`P1_CODE` must be that exact reviewed checkout, not a guessed old directory.
`P1_OUT` is a new direct child of `/workspace`; `P1_SLOT` is dot's existing
metadata-slot file, outside both paper environments. No network is used by
the following metadata checks or helper.

```bash
(
set -eu
: "${P1_REV:?fixed forty-character execution SHA from EXECUTION_PIN.md}"
: "${P1_CODE:?actual reviewed fixed checkout path}"
: "${P1_SLOT:?dot-issued fresh metadata slot, not the PLAN_ONLY template}"
: "${P1_OUT:?NEW direct /workspace child for this metadata report}"
test "$(git -C "$P1_CODE" rev-parse HEAD)" = "$P1_REV"
test -z "$(git -C "$P1_CODE" status --porcelain)"

# Hold one immutable slot snapshot across the bounded metadata subprocess.
/usr/bin/python3 -I -B - "$P1_CODE" "$P1_SLOT" "$P1_OUT" <<'PY_METADATA'
from datetime import datetime, timezone
import hashlib, importlib.util, json, pathlib, shutil, subprocess, sys
root, slot, out = map(pathlib.Path, sys.argv[1:])
p = root / 'research_runs/REDESIGN_HANDOFF_20261015/runtime/priority_gate.py'
s = importlib.util.spec_from_file_location('paper1_metadata_priority', p)
m = importlib.util.module_from_spec(s); sys.modules[s.name] = m
s.loader.exec_module(m)
permit = m.validate_receipt(slot, expected_operation='metadata')
if (out.parent != pathlib.Path('/workspace') or out.exists() or out.is_symlink()
        or any(x.is_symlink() for x in out.parents)):
    raise ValueError('new_direct_workspace_metadata_directory_required')
if (permit.max_new_bytes < 2 * 1024**2
        or shutil.disk_usage(out.parent).free < permit.required_free_bytes + 2 * 1024**2):
    raise ValueError('metadata_space_and_paper2_reserve_required')
out.mkdir(exist_ok=False)
helper = root / 'research_runs/REDESIGN_HANDOFF_20261014/runtime_transition/donor_gpu_inventory.py'
# No numerical/GPU package import, environment dump or package modification.
with (out / 'gpu_donor_inventory.json').open('xb') as result, (out / 'worker.log').open('xb') as log:
    try:
        permit.assert_active()
        code = subprocess.run(['/usr/bin/python3', '-I', '-B', str(helper),
            '--expected-python', '/usr/bin/python3'], stdout=result, stderr=log,
            timeout=60, check=False).returncode
    except subprocess.TimeoutExpired:
        code = 124
(out / 'exit-code.txt').write_text(str(code) + '\n')
(out / 'observed-end-utc.txt').write_text(datetime.now(timezone.utc).isoformat() + '\n')
slot_error = None
try:
    permit.assert_active()  # Same instance: replacement, inode and byte drift fail.
except ValueError as exc:
    slot_error = str(exc)
(out / 'metadata_slot_check.json').write_text(json.dumps({
    'slot_sha256': permit.receipt_sha256, 'postcheck_error': slot_error,
    'continuous_mid_command_slot_monitor': False, 'training_authorization': False}, indent=2) + '\n')
files = sorted(out.iterdir())
(out / 'SHA256SUMS.txt').write_text(''.join(
    hashlib.sha256(f.read_bytes()).hexdigest() + '  ' + f.name + '\n' for f in files))
if code != 0 or slot_error:
    raise SystemExit('METADATA_INCOMPLETE_OR_SLOT_INVALID: preserve output; do not retry automatically')
print('DOT_METADATA_COMPLETE_SAME_SLOT_VERIFIED_NO_GPU_NO_EEG_NO_INSTALL')
PY_METADATA
/usr/bin/python3 -I -B \
  "$P1_CODE/research_runs/REDESIGN_HANDOFF_20261015/runtime/compare_donor_transcript.py" \
  --inventory "$P1_OUT/gpu_donor_inventory.json"
)
```

Return the small report/log/exit-code/checksum and actual fixed-code identity
through the existing authorised channel; do not return any secret or environment
dump. The scheduling check brackets this bounded metadata command rather than
continuously monitoring it; dot must allocate the full60-second window. A
nonzero exit, expired slot, missing ensurepip or changed metadata is retained
and reviewed, with no automatic retry or package installation.

A match means only
`COMPLETE_HELPER_METADATA_MATCHES_TRANSCRIBED_FIELDS_RUNTIME_STILL_PENDING`.
It does not verify the separately claimed2390-byte original JSON, every GPU
payload byte, venv viability, actual training imports, source hashes or GPU
arithmetic. Do not replace the original JSON with this new report.

## 2. Conditional minimal runtime plan — not installation this round

Only after the full helper output is independently reviewed, dot may reserve
a separate `runtime_preparation` slot when Paper 2 is unaffected. Use the same
fixed checkout and a NEW child path; the default below writes no environment.
`P1_SLOT` now names that separately granted slot, not the metadata slot.

```bash
/usr/bin/python3 -I -B \
  "$P1_CODE/research_runs/REDESIGN_HANDOFF_20261014/runtime_transition/isolated_training_runtime.py" \
  --code-revision "$P1_REV" --donor-python /usr/bin/python3 \
  --donor-report "$P1_OUT/gpu_donor_inventory.json" \
  --environment "${P1_ENV:?NEW reviewed direct /workspace child for Paper1}" \
  --priority-receipt "$P1_SLOT"
```

Expected status is `ISOLATED_RUNTIME_PLAN_ONLY_REVIEW_REQUIRED`, with
`training_authorization=false`. It checks the fresh donor again. All venv and
ensurepip tooling must already exist. No cp311/Paper 2 borrowing, apt, global
pip, full-site inheritance or CUDA duplication. The maximum new allocation is
3GiB, with10GiB plus dot's explicit Paper 2 reserve retained; the slot can
tighten these bounds. Actual free space must cover the cap plus that floor.

The existing helper's separate `--prepare --log NEW_LOG` operation is **not
authorised by this round**. There is intentionally no install invocation here.
Any later allowed install authenticates wheel bytes and origins, rejects GPU
replacement, monitors its own space/slot and preserves failure artifacts.

## 3. Later actual-runtime source acceptance — not run now

Prerequisites are an actually prepared/independently reviewed child; a separate
`source_cpu_acceptance` slot; the18 source originals restored against frozen
size/SHA; and the original full diagnostic archive restored/byte-verified. The
prior independent archive audit is reused, not redone as a scientific diagnostic.
Do not run the old full diagnostic or old diagnostic-runtime acceptance again.

```bash
timeout --signal=TERM --kill-after=10s 300s \
  "$P1_ENV/bin/python" -I -B \
  "$P1_CODE/research_runs/REDESIGN_HANDOFF_20261014/runtime_transition/accept_training_runtime_source.py" \
  --code-revision "$P1_REV" \
  --runtime-receipt "$P1_ENV/runtime_preparation.json" \
  --priority-receipt "${P1_ACCEPT_SLOT:?fresh separate dot source_cpu_acceptance slot}" \
  --data-dir "${P1_RAW_DATA:?actual reviewed restored source cache}" \
  --output-dir "${P1_ACCEPT_OUT:?NEW registered output directory}" \
  --old-work-root "${P1_OLD_REVIEW_ROOT:?actual restored historical review root or explicitly unobserved path}" \
  --diagnostic-package "${P1_FULL_ARCHIVE:?actual restored134436byte original full archive}"
```

Exact full archive:134436bytes/SHA256
`2871f422755bf5d0b939d0db59fc41547b192d6c939db1a6a13b97a91ba49ae9`.
Preserve the prior formal receipt archive too:12299bytes/SHA256
`a4c6c3f7beadf6ce0c927c6e4b9d20b6d37ff3bc2c033ad4b4fd836ca38a6b0d`.
No private evidence archive or raw EEG enters GitHub.

Success requires exit0, the original formal report plus
`runtime_bound_acceptance.json` with
`ACTUAL_TRAINING_RUNTIME_SOURCE_MATCH_REVIEW_AND_RECOVERY_PENDING`.
It checks actual training consumers, imports/origins and all18files/108runs/
2592trials/7776trial-band hashes, without arrays written, target read or a model
created. GPU arithmetic, old accounting and all training authority remain false.
Slot checks before/after the CPU work are not continuous cancellation; dot must
reserve the bounded CPU window without affecting Paper 2.

## 4. Required metadata recovery before execution can be designed

Use only already-authorised read-only metadata access. This release does not
retry the observed R2 401, add a credential, guess a target key, GET target EEG,
or operate the Pod. Return actual source records if an existing authorised route
can read them; missing local paths do not establish lost remote backups.

* Old task external `execution_registration.json`, `budget_origin.json`,
  `source/budget_ledger.json`, launch/config identity and unchanged counters.
* Full checkpoint/optimizer/RNG and update-intent inventory; authentic private
  COMMITTED/PENDING HEAD/manifest/object hashes. Do not deserialize checkpoints
  for this metadata request or fabricate a zero-state recovery.
* Current account/machine ownership, actual total hourly rate, cumulative spent
  amount and GPU hours/remaining $10 allowance with cost attribution. Public
  zero fits cannot answer these. No reset, new budget origin or renewed8h clock.
* Genuine upload/list/HEAD metadata linking **each** of174 frozen Dreyer rows
  in `metadata/dreyer_public_metadata_audit.json` to its actual R2 key/version,
  size and cryptographic SHA evidence. An S3 ETag is not automatically SHA256.
  Combine with18 authentic source mappings for the strict192-object gate.
  Preserve NEMAR EDF/version/license/creator attribution; do not substitute the
  original GDF ZIP or BIDS BDF as identical bytes.

The appended deadline record can be checked offline with:

```bash
/usr/bin/python3 -I -B \
  "$P1_CODE/research_runs/REDESIGN_HANDOFF_20261015/deadline_amendment/validate_deadline_amendment.py"
```

Its success never changes the old production budget gate or authorises a fit.
Only the calendar deadline is appended to2026-10-16 09:54UTC; $10 total,
8 cumulative GPU hours, fit/update counts and all original restrictions remain.

**Stop at the appropriate pending gate.** This package has no training launcher,
Pod-control command, target-EEG download or automatic budget transition. Once
the missing actual evidence is reviewed, a separate minimal, tested transition
can be developed without altering the scientific design or historical failure.
