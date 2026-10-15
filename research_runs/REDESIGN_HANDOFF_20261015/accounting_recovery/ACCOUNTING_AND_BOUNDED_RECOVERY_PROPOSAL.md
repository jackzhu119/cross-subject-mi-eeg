# Paper 1 accounting recovery: review-only proposal

This document adds no authorization, registration, fit, installation, deadline,
funds, or GPU hours. It does not operate the Pod, access a provider or R2, inspect
checkpoint binaries, read EEG, or alter the production budget guard. Dot remains
the sole operator; Paper 2 has absolute priority. The author's latest report
states that Paper 2's 18/18 development fits were executed and exported, while
only seven are accepted. This document does not independently audit those fits
or equate execution/export with acceptance.

## Identity and unchanged ceilings

Retain job `20261014T071918Z-exploratory-89b0c07d`, original science revision
`05e683e91e2bb39b977970d04402221761e575d2`, original clock origin
`2026-10-14T07:07:45.290107+00:00`, and the original budget receipt SHA256
`fcb8de686bf53a419beccd00d833f0e253ff922824b3227683e9c1ae2c93e790`.
Retain the original native source-hash failure, every later recovery/diagnostic
record, and old machine identity exactly as historical evidence.

The sourced deadline-only amendment remains
`../deadline_amendment/deadline_only_amendment.json`: execution ends no later
than **2026-10-16 09:54 UTC**. The amendment does not reset the original
authorization origin, counters, spent dollars, cumulative GPU hours, or machine
identity. Ceilings remain $10 total, $2 reserved for non-GPU costs, eight
cumulative GPU hours, 26 source fits, 34,440 optimizer updates, and a total
server price no greater than $0.75/hour. Target fitting remains prohibited.
The old $0.34/hour quote is historical, not today's price.

The old production guard still rejects its expired eight-hour machine receipt.
Neither this proposal nor its calculator changes that guard or creates a new
receipt. A reviewed migration implementation is still necessary before any
execution transition.

## What the recovered public records establish

The seven byte-verified records at fixed commit
`d612f0cc2bcca045ff1304bc95a87df76bfd4a82` are indexed in
`../metadata/old_task_accounting_recovery.json`. They establish a historical
failed preparation, at its recorded timestamp, with zero fits/updates and no
target predictions. Published `r2_enabled=false`,
`completed_checkpoint_count=0`, and `backup_verified=false` describe that
snapshot only. They do not prove that later private state, checkpoints,
backups, charges, or additional execution never existed. Historical zero fits
cannot establish zero cost.

All present values for cumulative expenditure, GPU hours, remaining allowance,
and latest counters remain **unknown**. No inference of zero is made. Existing
401 observations are preserved; this proposal makes no new requests and does
not use inability to access R2 as evidence of absence.

## Minimum authentic evidence needed from existing records

Dot's parent can assemble the following through existing authorized read-only
paths. Return redacted metadata and hashes, never secrets. Do not rerun work to
manufacture historical records. One coherent signed-off index can reference
multiple existing records; duplicates are unnecessary.

| Evidence | Minimum content and review requirement |
|---|---|
| Original registration and clock | Byte copies or existing authenticated backup entries for `execution_registration.json`, `budget_origin.json`, old budget/launch/runtime/code records, with SHA256 and acquisition time. Preserve the old job/revision/origin. If a record is irrecoverable, mark it missing and explain the provenance of any reviewed append-only reconstruction; do not fabricate an original. |
| Provider chronology and charges | Existing provider account/resource identifiers, billable allocation start/end intervals, rates and rate changes, GPU count, storage/transfer charges, and debits/invoice or usage export covering the old job through the review cutoff, including container rebuild/migrations. Redact account identifiers for public GitHub while retaining the private evidence binding. Account balance, deposits, and screenshots of an idle GPU are not expenditure reconciliation. |
| Shared-Pod attribution | Timestamped Paper 1 and Paper 2 scheduling/controller evidence, linked to the same allocations and billing intervals. Record an explicit conservative attribution rule before computing the remaining allowance. Concurrent charges must not be discounted merely because Paper 2 is the priority task; allocations must not disappear from both ledgers or be treated as free. |
| Latest source ledger and fit state | Latest authenticated `source/budget_ledger.json`, all fit-receipt metadata, source/status receipts and publication/private-head chronology, with counters and timestamps. Reconcile started/completed/failed/active fits and optimizer updates monotonically against every available later record. A public zero snapshot is only a lower bound. |
| Checkpoint and in-flight update inventory | Metadata for `resume_state.pt`, model/optimizer/RNG checkpoints, fit identity, global updates, epoch/batch position, and any `update_intent.json`, PENDING/COMMITTED head or incomplete upload. Record bytes/SHA and the last consistent committed state. Do not deserialize a checkpoint merely to fill this metadata proposal. An authorized future resume review must independently validate the required state before use. |
| Backup binding | Existing off-host/R2 manifest and verification receipts for the latest consistent state: original job/revision, manifest/head SHA, member bytes/SHA, committed generation, read-back verification and cutoff. A backup receipt without a later-state chronology cannot prove there was no later state. |
| Current allocation and bounded future work | Real current total hourly price, GPU count, data/storage/transfer price bounds, a UTC review cutoff, remaining time before the approved deadline, a Paper 2 no-impact slot, and an explicit small proposed increment. A spot quote alone is not an upper bound on a changing rate; use a documented cap or recheck before each increment. |

Do not read target outcomes to resolve any of these records. Do not expose
provider credentials, full secret-bearing commands, signed URLs, or raw EEG in
the evidence index. Authentic source/package evidence already audited need not
be regenerated.

## Conservative bounded proposal for parent review

1. Establish a cutoff and a complete provider allocation/charge chronology.
   Keep all gaps explicit. If the full resource chronology is known but task
   attribution is ambiguous, assign the **entire ambiguous allocation** to
   Paper 1 for its financial/GPU-hour upper bound. An interval may be excluded
   only on authenticated evidence and an explicit reviewed allocation rule.
   If even the duration/rate/charges cannot be bounded, that interval has an
   unknown upper bound: the financial/GPU-hour gate cannot pass.
2. Preserve separate values for observed debits and conservative attributed
   upper bounds. Do not label an upper bound as an actual expense. Reconcile
   both to private evidence references and the review cutoff. Paid CPU-only
   preparation on a rented GPU Pod can still consume paid allocation; GPU
   utilization is not a billing clock. Retain the original cumulative
   allocation-hour interpretation; do not redefine it as GPU-active compute.
3. Use a small parent-reviewed interval `h`, bounded by the earliest of the
   approved calendar deadline, remaining cumulative allowance, and its reviewed
   Paper 2 scheduling slot. The calculator does not supply or grant a slot.
   Let `C_old_upper` be all potentially attributable past costs through cutoff;
   `H_old_upper` all potentially attributable GPU allocation hours;
   `r_upper` the authentic current capped total price; `C_extra_upper` additional
   costs for the proposed interval not included in `r_upper`. The deliberately
   stricter review envelope is:

   ```text
   C_old_upper + r_upper * h + C_extra_upper + 2 USD <= 10 USD
   H_old_upper + h <= 8 cumulative GPU hours
   source_fits_started + proposed_additional_fits <= 26
   optimizer_updates + proposed_additional_updates <= 34440
   0 < r_upper <= 0.75 USD/hour
   cutoff + proposed_interval <= 2026-10-16 09:54 UTC
   ```

   Keeping the full $2 reserve in addition to all counted historical costs is
   conservative even if some historical costs were non-GPU costs. It does not
   repurpose or replenish that reserve. Do not silently relax this envelope to
   obtain a positive interval. The total hourly quote must include the entire
   server charge relevant to the interval; do not multiply an incomplete GPU
   quote while ignoring additional hourly charges.
4. Counters must be authentically reconciled, not guessed. Unknown fit/update
   counters block any proposed fits regardless of financial headroom. A lost
   active checkpoint is not permission to repeat its fit without counting the
   prior started fit and consumed updates. An inconsistent/in-flight state
   requires a separately reviewed rollback/resume rule preserving prior costs
   and counters; no restart-from-zero shortcut is supplied here.
5. Append a **proposal**, not a replacement `budget_authorization.json` or new
   registration. Bind every authentic record, the preserved historical state,
   provenance of reviewed upper bounds, current machine/runtime, numeric input
   acceptance, backup ownership and target transport identity. Dot's parent
   reviews the proposal and every remaining scientific gate before any
   separately tested transition may run. Zero remaining safe allowance or
   unbounded missing evidence means **blocked**, not an automatic budget
   extension or request to spend more.

The new `bound_calculator.py` is a deterministic Decimal arithmetic aid. Its
template remains all unknown. It does not validate provider authenticity,
accounting completeness, checkpoint content, current runtime, targets or
backup access. Even a numerically feasible result always reports
`training_authorization=false` and `production_budget_gate_passed=false`.
It performs no network/Pod/EEG action and writes no file.
Numeric inputs support at most 12 fractional decimal places; fixed high
precision preserves the arithmetic without rounding a small excess below a
ceiling. The evidence index path/SHA are references, not authenticated by this
calculator.

```bash
python -I -B research_runs/REDESIGN_HANDOFF_20261015/accounting_recovery/bound_calculator.py \
  --proposal research_runs/REDESIGN_HANDOFF_20261015/accounting_recovery/bounded_recovery.PLAN_ONLY.json
```

Expected exit is 3 because original accounting remains unresolved. A future
reviewer may place authentic bounded inputs in a new evidence copy, without
changing the frozen template or historical records. The calculator's output
must remain a review artifact and must never be fed to the production trainer
as an authorization receipt.

## Latest platform-access boundary

The author reports that the latest platform-balance read did not obtain completed
site permission and was stopped. This task does not retry it, change route, or
request a new credential. The00:02 historical$2.51 observation is neither a
current balance nor an attributable Paper1 expense or remaining-budget proof.
All cost/hour/counter unknowns and the original$10/8hour ceilings remain as above.
