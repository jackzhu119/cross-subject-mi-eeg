# Conservative recovery accounting proposal: 04:49–04:51 UTC observation

**Status: proposal for parent review, not an approved budget or a passed execution gate.**
This is an append-only accounting proposal. It does not modify the old job,
receipt, costs, hours, checkpoints, fit/update counters, or production budget
validator. No Pod/provider/payment operation was performed for this proposal.
All observation times below are explicitly UTC, as in the supplied evidence.

## Actual evidence and its limits

The user supplied dot's normal read-only official RunPod console/Billing
observation for **2026-10-15 04:49–04:51 UTC**. It reports one current Pod,
`bright_ivory_bear / 52ivinpjwv947i`, RTX A4500 ×1, uptime display `19h29m`,
and total current price **$0.257/hour** ($0.25 GPU + $0.007 for 50 GB disk).
Displayed account balance is **$1.27**, estimated time left **5 hours**,
Auto-Pay Disabled. No payment, configuration change, or Stop was made. These
are author-supplied fields, not an independently acquired billing export here.

The visible Billing explorer covers 1–14 October UTC and declares one-hour
lag. On 14 October, account total is $4.268 = GPU $4.169 + storage $0.099.
Displayed GPU subtotals are A4500 $3.802, RTX 2000 Ada $0.366, and RTX 4000 Ada
$0, rounded. Their rounded sum does not reconstruct the parent GPU subtotal;
**use the account total once, never add its GPU/storage breakdown again**.
The $0 display is not proof of zero usage. The 15 October account total is not
visible. Other dates, including 5 October $2.824 and 2 October $0.613, are
account history, not automatically Paper1 expenses.

The current Pod, the account daily bill, and the old Paper1 job are different
accounting grains. A current balance is neither cumulative spending nor a
Paper1 allocation. The estimated five hours is a display, not a paid-through
guarantee. At the quoted rate, $1.27/$0.257 is approximately 4.942 hours before
other costs or later changes. The user's promise to replenish later is not an
observed credit. The instruction to keep the Pod running is preserved; this
proposal does not Stop it or assume a future top-up already arrived.

## A concrete conditional dollar envelope

Let `t` be a new execution cutoff, in hours after 15 October 00:00 UTC. Let
`U14` be a valid final upper bound for the **whole account's 14 October total**;
`r15` a verified ceiling on the **sum of all relevant account resources** for
all of `[00:00, t]`; and `Uextra` a documented upper bound for uncovered time,
resources/accounts, late entries, and display uncertainty. Then:

```
C_upper(t) = U14 + r15*t + Uextra
C_upper(t) + future_window_cost + $2 protected reserve <= $10
```

Using an entire account's daily cost for Paper1 is deliberately conservative
and can cover Paper2 costs too. It is **an upper-bound charge for decision
making, not a claim about actual Paper1 spend**. It is valid only if all
Paper1 consumption since the old authorization is contained in that scope.
No historical cost is subtracted because the job performed no new fits.

At the illustrative evidence cutoff **04:51 UTC**, `t = 4.85 hours`:

| Conditional rate ceiling for 15 October | Missing-day increment | 14 October + increment | Plus 30 minutes at $0.257/h + $2 reserve |
|---|---:|---:|---:|
| $0.257/h throughout the entire interval | $1.24645 | $5.51445 | $7.64295 |
| $0.75/h throughout the entire interval | $3.6375 | $7.9055 | $10.0340 |

Both rows omit `Uextra` solely to expose the arithmetic; neither is a certified
bound yet. The second row exceeds $10 even before uncertainty. The old
approved maximum quote of $0.75/hour is not evidence that all actual account
resources or parallel allocations stayed below it. The first row leaves
$2.35705 of **conditional** headroom for all uncertainty and uncovered items,
not demonstrated remaining Paper1 funds. A current rate proves neither row's
historical premise. There is no guessed precision or arbitrary $0.01 pad
masquerading as a proven bound. Refresh `t` at the actual later execution;
04:51 arithmetic cannot fund an unlimited delay or the rest of the day.

There is a finite smaller alternative if the $0.75 historical-rate scenario
is the tightest justified bound. At that same 04:51 cutoff it leaves only
`$10 - $2 - $7.9055 = $0.0945` for additional work and uncertainty. With zero
uncertainty that is approximately **22.0623 minutes** at $0.257/hour. A
**10-minute** window costs exactly $0.257/6 = $0.0428333…; rounding its charge
**up** to six decimal places gives $0.042834 and a total envelope of
**$9.948334**, including the $2 reserve. Thus at most **$0.051666** of further
uncertainty can fit that illustrative envelope. Neither maximum is a live
quote: later cutoff time reduces headroom and any unbounded historical item
invalidates the envelope. A ten-minute window may be too short to complete
source recovery; preserve incomplete evidence instead of extending it.

The following real premises must be recorded before converting the first row
into an admissible dollar bound:

1. The 14 October account total is final or a documented `U14` covers billing
   lag and rounding; scope includes the original authorization at
   **2026-10-14 07:07:45.290107 UTC**. Including that day's earlier spending is
   conservative, not a deduction. Charges on other accounts, if any, need an
   additional bound; the current account cannot cover them by assertion.
2. For every portion of 15 October through the new cutoff, the number, types,
   and prices of allocated Pods, volumes/storage and other billed resources
   are known sufficiently to bound their **sum**. The current sole Pod and
   current price do not prove no other earlier resource existed or changed.
3. Late entries, taxes/fees if applicable, price precision and any uncovered
   period have a defensible finite allowance. If a component remains
   unbounded, the total remains pending rather than replacing it with zero.
4. At execution, a fresh finite window has a verified all-inclusive price
   ceiling and parent-reviewed dollar inequality. The account can actually
   finance that window without assuming a pending payment completed.

Read-only platform history, user-confirmed historical allocation facts, and
existing original records can establish these premises; no new credentials
or alternate access route is required by this proposal. If the premises
cannot be established, the calculations remain useful conditional scenarios
and do not pass the budget gate.

## GPU allocation hours cannot be replaced by fit hours

The original job remains `20261014T071918Z-exploratory-89b0c07d`, original
scientific revision `05e683e91e2bb39b977970d04402221761e575d2`, with **$10 total,
$2 reserve, 8 cumulative GPU hours, 26 neural fits and 34,440 optimizer
updates**. Only its calendar execution deadline was extended, to
**2026-10-16 09:54 UTC**. Original costs, counters, checkpoint and machine
transition remain unknown; a historical public snapshot is not the latest
private ledger. The recovery work does not reset any of these quantities.

Maintain separate fields for (a) allocated/billed GPU hours, including idle
GPU allocation during CPU recovery, and (b) GPU time actually used for model
fits. GPU idle, empty `nvidia-smi`, CPU-only work and zero new fits do **not**
make (a) zero. This single Pod's displayed uptime alone is already **19h29m**,
which exceeds eight hours if charged as one allocated GPU throughout; it
cannot be represented as passing the old cap. Whether that uptime is fully
attributable to Paper1 is unknown. A Paper2-priority allocation must not be
silently assigned zero marginal cost or zero allocated hours to Paper1.

The calendar interval from the old origin to 04:51 is approximately
21.720753 hours. This is only an hour *upper bound* if a real record proves
at most one allocated GPU at any instant, all allocations began no earlier
than the origin, and all relevant accounts/resources are covered. Without
that proof it is neither total GPU hours nor a recovered checkpoint. Do not
use the daily-dollar envelope to infer GPU hours from rounded SKU charges.

Minimal records to recover, or explicitly mark unavailable, are:

- Original registration/authorization and integrity-linked task ID, source
  revision, machine/account transition and last known controller status.
- Original ledger entries with allocation intervals, rates/charges and scope;
  actual fit start/stop/update records maintained separately.
- The latest durable checkpoint manifest/object identifiers, sizes/hashes,
  completed/started fit counters, optimizer updates and backup/readback
  receipt. Unknown checkpoint state is not `completed_checkpoint_count=0`.
- An overlapping-allocations/account-scope statement sufficient for a finite
  hour bound if a cumulative ceiling is to be revised. No old machine
  identity, lost local directory or post-snapshot record is invented.

## Smallest concrete operational amendment to consider

An eight-hour ceiling that may already be consumed cannot be passed by
renaming recovery as a new job. Therefore, if further billed allocation is
required, **explicit author approval of a finite hour exception/amendment is
necessary**, in addition to the existing calendar-only extension. This file
records a proposed decision, not that approval.

Propose **one Paper1 CPU-only import/source acceptance window of at most
30 minutes on the already running Pod**, after a new parent review and dot
slot. At a newly verified all-inclusive rate ceiling $0.257/hour, its maximum
increment is **$0.1285**. Source transfer, if needed, must be in the same time
bound or separately costed; the proposal does not promise that downloading
779,873,919 source bytes plus acceptance will finish within 30 minutes.
Expiry closes the Paper1 worker, preserves evidence and keeps the shared Pod
running. There is no new fit, target EEG access, GPU computation, purchase,
second Pod or automatic retry authorization. Paper2 remains independent.

The amendment must explicitly say that this **additional <=0.5 allocated
GPU-hour recovery window** may proceed despite the old eight-hour limit
being unverified/possibly exceeded. It must retain the old eight-hour cap as
historical policy and its breach/uncertainty, rather than certify compliance
or reset its origin. The maximum cumulative total remains unknown until
actual history is bounded. If a global cumulative limit is required, obtain
`H_upper` from actual allocation records and authorize the finite ceiling
`H_upper + 0.5` hours; do not fill `H_upper` from uptime alone. The exception
is limited to this recovery attempt and confers **no additional fit hours**.
Do not change a production validator until its exact amendment is reviewed.

The dollar ceiling and reserve are unchanged: the new window is permitted
only if the refreshed, fully covered `C_upper + $0.1285 + $2 <= $10` passes.
If the higher-rate scenario is the best available bound, 30 minutes cannot
be authorized under the unchanged dollars; use the above ten-minute
alternative with explicit review if its *refreshed* inequality still holds,
or obtain better bounded evidence. Do not silently add budget. A 30-minute
amendment is one aggregate recovery allocation, not 30 minutes for each
stage: separately reviewed source-restore and acceptance slots remain
distinct, and their total charged Paper1 recovery duration must stay within
the single approved cap. A new slot is not a new budget or a new half-hour.

A minimal author decision, once the parent has established the dollar bound:

> 是否同意在不增加10美元总额、不动用2美元预留、不重置旧账本和计数的前提下，另批准一次最多30分钟、增量费用最多0.1285美元的论文1 CPU恢复验收窗口；明确允许该窗口增加最多0.5个已分配GPU小时，承认原8小时上限可能已经耗尽或超出且不声称旧门通过？本次仍不授权训练，超时仅结束论文1工作进程，Pod保持运行。

If only the smaller envelope is supportable at the real cutoff, replace
“30分钟 / 0.1285美元 / 0.5小时” with “10分钟 / 0.042834美元（向上取整） /
1/6小时”. The parent must select and record one actual finite cap before
author approval; this is not permission to switch or extend it afterward.

The user's 04:51 keep-running/top-up-later instruction is not recorded as an
answer to this explicit cap-amendment question. The parent may present the
question when a real bounded dollar proposal is available. Metadata/code
preparation can continue without representing this decision as already made.

## Exact new-operation review bindings

The prepared `acceptance_gate.py` requires new parent records for
`source_raw_restore` and `source_cpu_acceptance`. Each must explicitly set
`bounded_cpu_recovery_exception_authorized=true` and
`covered_dollar_upper_bound_reviewed=true`, bind the real author exception
provenance as `cpu_recovery_grant_sha256`, and use the **same**
`cpu_recovery_window_start_utc` / `cpu_recovery_window_end_utc` for both stages.
The gate bounds this absolute window to at most 30 minutes; a ten-minute
author grant requires the correspondingly shorter actual window. Both new
reviews and distinct dot operation slots must fall inside that one window.
Parent review must check the actual approval source behind the SHA and the
fully covered, refreshed dollar bound; a syntactically valid hash is not
proof of approval or of recovered spending. Templates remain false/pending.
These fields authorize only the bounded CPU recovery exception and do not
pass or modify the original fit budget validator. Actual cumulative
allocation hours remain fully counted and unknown until independently
bounded; future GPU fits require a separately reconciled, finite revision.

## Deterministic verification

`compute_bill_bound.py` uses exact decimal inputs, explicit UTC arithmetic,
and no network or provider calls. Its JSON is an arithmetic proposal with
`budget_gate_passed=false`, `training_authorization=false`, actual costs and
hours `null`, even when a conditional numerical scenario fits $10. It never
writes or replaces the production authorization. Focused tests verify the
$5.51445/$7.9055 scenarios, reserve accounting, uncertainty, invalid decimal
inputs and the distinction between calendar/uptime and actual GPU accounting.
