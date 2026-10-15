# Paper 1 deadline-only operational amendment

This is an appended record of the author's current deadline-only instruction,
not an execution receipt, replacement budget, current machine authorization,
or training release. No Pod, environment, source/target array, accounting,
registration, security setting or model is changed by this record or validator.
Paper 2 has absolute priority; dot remains the sole Pod operator.

## Source and scope

The current author message explicitly asks to record the deadline-only change
already confirmed by dot's parent. It supplies the earlier proposal and two
author replies at `2026-10-15 00:01 UTC` (minute precision) and
`2026-10-15 00:48:15 UTC` (second precision). These are preserved verbatim in
[deadline_only_amendment.json](deadline_only_amendment.json), identified as
**author-supplied transcript**, not an independently retrieved conversation.
The present explicit instruction is the basis for recording this amendment;
the earlier short replies are not misrepresented as individually explicit
permission to bypass any gate.

The old job remains `20261014T071918Z-exploratory-89b0c07d`, scientific revision
`05e683e91e2bb39b977970d04402221761e575d2`. Its original budget start remains
`2026-10-14T07:07:45.290107+00:00`; its original eight-hour expiry remains
`2026-10-14T15:07:45.290107+00:00` in the original receipt. The appended absolute
**execution deadline is `2026-10-16T09:54:00+00:00`**. This does not extend the
previously authorized 48-hour operator window.

Unchanged ceilings are **US$10 total**, **US$2 non-GPU reserve**, **8 GPU hours**,
**26 neural fits**, **34,440 optimizer updates**, and **US$0.75/hour maximum**.
The original US$0.34/hour quote is historical evidence, not today's quote.
The GPU-hour limit is neither restarted nor enlarged by this calendar extension.
Any eligible transition must account for cumulative resource use; this record
does not reinterpret missing accounting as free time. Target fits and optional
grouping fits remain prohibited.

## Immutable old receipt

The original public receipt is at commit
`d612f0cc2bcca045ff1304bc95a87df76bfd4a82`, path
`research_runs/REDESIGN_CLOUD_20261013/jobs/20261014T071918Z-exploratory-89b0c07d/budget_authorization.json`.
Its exact historical snapshot is retained here as
[historical_budget_authorization_d612f0cc.json](historical_budget_authorization_d612f0cc.json):
**890 bytes**, SHA256
`fcb8de686bf53a419beccd00d833f0e253ff922824b3227683e9c1ae2c93e790`.
This file is a byte-identical copy of the prior public readback held in QA;
copying it does not represent a new remote lookup or current machine approval.
The original receipt, earlier failures and expired clock are not overwritten.

The old hostname/GPU UUID in that receipt apply only to the historical machine.
They do not establish the current account, container, machine, remaining credit,
spent amount, fit state, checkpoint existence or backup location.
**Zero newly started fits does not establish zero cost.** These quantities
remain unknown pending actual records. The container-rebuild fact is preserved;
no current path, package, security setting or SSH installation is inferred.

## Read-only verification

From a reviewed checkout, dot may verify these metadata files only:

```bash
/usr/bin/python3 research_runs/REDESIGN_HANDOFF_20261015/deadline_amendment/validate_deadline_amendment.py
```

The helper uses Python's standard library, reads two bounded JSON snapshots,
checks exact SHA256 and preserved ceilings, and writes only JSON to stdout.
It does not import CUDA, install packages, use network or credentials, read EEG,
resume a job or edit the old budget. A valid result is
`SOURCED_DEADLINE_ONLY_RECORD_VALID_EXECUTION_STILL_BLOCKED`, with
`training_authorization=false`. Expiration is explicitly reported; even before
the appended deadline, this output never authorizes execution.

## Mandatory remaining transition gates

The actual training runtime and source strict-hash acceptance, original task
identity and counters, cumulative spending and GPU-hour evidence, current
machine and total hourly rate, checkpoint and remote-backup identity, complete
frozen Dreyer mapping/license/restore gates, and reviewed execution transition
all remain separate prerequisites. Paper 2 scheduling clearance is required
before any Paper 1 workload could affect it.

The existing production budget validator still rejects expired or mismatched
machine receipts and couples the historical start/end to its original eight-hour
lifetime. It is deliberately unchanged here. This record cannot be renamed to
`budget_authorization.json`, copied over the old receipt, or consumed as a
training release. A future reviewed transition would need explicit enforcement
of the absolute deadline plus unchanged cumulative accounting and resource caps;
neither a reset origin nor an enlarged eight-hour allowance is permitted.

No scientific selection rule, source grouping, seed, preprocessing operation,
numerical thread setting, frozen hash, failure, target-fitting restriction or
interpretation is changed.
