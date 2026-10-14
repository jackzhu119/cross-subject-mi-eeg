# Explicit Python entrypoint detection: operational correction

## Observed issue and reproducible cause

The author's startup output at revision `05e683e91e2bb39b977970d04402221761e575d2` reported `LOCK_BUSY_NO_NEW_WORKER_STARTED`, scope `existing_cloud_supervisor`, owner PID 1125. No live access to that server or its PID was obtained. This report alone does not establish which remote process held that PID.

Independent local reproduction established a fault in the process scanner: it matched a scientific script name in any argument, including the launcher's own `python - budget_origin.json <stdin-fd> <python> <cloud_supervisor.py> launch` ancestor. The budget wrapper executes stdin code; the supervisor filename is an operand for a later subprocess. The old scanner incorrectly rejected that wrapper, and the reported local owner PID equalled its parent PID.

## Correction and preserved protections

`executed_python_script()` identifies the interpreter's file entrypoint after supported interpreter options. Stdin, command-string, module and shell wrappers are not classified as explicit-file workers. The scanner checks the entrypoint against the four actual worker filenames and resolves relative paths against that process's own working directory. It checks containment within the same canonical work root, so a sibling path sharing a string prefix does not cause a false conflict.

Real same-root explicit-file supervisor, training, inference and preparation processes still block duplicate launch. The local kernel locks, persistent execution registration, original eight-hour budget origin, runtime/machine checks, fit counters and source-before-target gates remain in force. No lock or registration was removed; no budget was renewed. Existing jobs still require their original revision and an explicit resume; this repair does not migrate or recover already fitted jobs automatically.

## Validation

The complete cloud software suite passed **309 tests**, including **37 process-detection regressions**. Tests include the exact live stdin-wrapper ancestor and live inert same-root worker processes, using absolute paths, relative paths and interpreter options. The before/after reproduction confirmed that only the former false positive was removed. Tests used fixtures and CPU software verification; no new EEG model fitting, real target prediction, cloud credential authentication or live GPU run was performed.

The evidence is recorded in `evidence/PROCESS_DETECTION_VALIDATION.json`. Historical Q1–Q16, manuscripts, frozen data/results/contracts and the cloud scientific configuration remain unchanged. This is an operational release, not a scientific result.

## New-server use

The command remains independent of provider account, Pod ID and IP address. The author supplied a new-server screenshot showing RTX 2000 Ada and US$0.24/hour; neither actual total billing nor that server's live runtime is certified by this local software check. Supply the actual total running quote at launch. The approved total budget and deadline are unchanged. No RunPod API is requested. Stop billable compute manually when completion, failure or deadline is reported.
