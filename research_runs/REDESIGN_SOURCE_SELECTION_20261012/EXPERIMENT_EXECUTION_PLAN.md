# Execution plan and bounded GPU budget proposal

Prepared13October2026. Current environment:3CPU workers,8GiB memory limit, no NVIDIA device/nvidia-smi/PyTorch GPU runtime. No free authenticated GPU is attached. CPU source provenance, mathematical planning, saved-prediction review and the new10-fit traditional-source diagnostic are authorized and executed separately. No cloud instance has been bought or started.

## Core experiment cost accounting

Nominal26neural fits:8source-CV40-epoch trajectories +18final all-source fits for2architectures×3rules×3seeds. G0 has three7-person source fits and one6-person fit per architecture:2016/1728source trials, batch64,32/27updates per epoch. Thus CV uses9,840 optimizer updates. Final fixed20 contributes4,920updates; four selected schedules in[1,40] add492–19,680updates across3seeds. Core total is **15,252–34,440 optimizer updates**, conditional on ordinary ceil batches and no repeated technical failures. Two-view shared updates cost more than one broad update; update count is not FLOP equality.

Five optional grouping variants add40inner trajectories /49,200updates and are disabled. They are not included in the core funding request. No hidden target-performance search, hyperparameter sweep, physiological model or foundation-model pretraining is budgeted.

## Resource estimate and approval boundary

A single NVIDIA card with16–24GB VRAM is a conservative practical choice (for example RTX4000Ada20GB/RTX409024GB); actual peak training memory and epoch time are unmeasured for this new19-channel implementation and must be benchmarked using source data only. The historical source completion timestamp is not an authenticated isolated per-fit speed benchmark for this new runtime. No exact timing is claimed. A planning envelope is **2–8billable GPU hours including setup, source training and target preparation**, subject to a bounded source-only benchmark, early cost cutoff and successful data audit. This is an estimate, not a measured completion promise.

Proposed hard ceiling for the core: **US$10 total**, with no more than8GPU hours at an approved hourly rate≤US$0.75, plus at mostUS$2 for disk/transfer/contingency (US$8 planned bound, US$10overall cap). Rates are budget assumptions/caps, not a live provider quote; confirm the exact instance/disk quote at the time of purchase. Optional grouping sensitivity needs a separate budget and is not automatically enabled. Obtain explicit author authorization before any paid instance, storage purchase or deployment. A worker time/cost guard stops computation, not cloud billing: before provisioning, configure a verified provider-side lifetime/billing cutoff or agree on supervised manual stopping within the approved ceiling. Neither a worker exit nor an API acknowledgement proves physical Pod shutdown. If no authorization arrives, produce the research work package and keep neural execution blocked.

## Disk and raw-access routes

All18BNCIoriginals total779,873,919bytes. The Dreyer original singleZIP is27,475,466,178bytes and currently had timed-out raw-content probes; unpacking plus containers/caches would warrant100–150GB disk. The checksum-addressed acquisition-only EDF route is much smaller; its pinned174-file manifest declares2,515,343,396bytes (2.343GiB), not the full27.5GB archive. If this route qualifies,30–50GB available working disk is a conservative envelope for raw source/target, three input views, environments/checkpoints and temporary copies; a20–30GB container disk may be separate, so verify what the provider total includes. Exact expected raw bytes plus tensor/cache/temp/environment margins must set a per-job free-space guard before any purchase; do not buy a second persistent archive merely because R2 is separate object storage. Raw input tensors and all temporary/cache bytes stay out of Git. Models, configurations, predictions and receipts are retained in versioned scientific outputs.

R2 variables are configured, but the actual S3 list returned Unauthorized. No credentials were printed, changed or reprompted. Official BNCI download was used and authenticated against frozen hashes; R2 setup readiness is not proof of API authorization. Do not promise automatic cloud backup until an actual write/read-back check succeeds under a separately authorized execution.

## Execution sequence

1. Commit/read back CPU source protocol; hash18source originals; run10fresh CSP fits and independent saved-output/raw-label validation.
2. Confirm author prior exposure of the candidate, complete full cohort provenance/QC/event/montage/duplicate audit and lock final roster. Bounded metadata/header success is not full-cohort clearance.
3. Complete19-channel neural loader/trainer/adapter implementation, meaningful synthetic/source-only tests and independent code review; bind this final code to the design before fitting. Current design JSON is an explicit specification, not a falsely advertised ready launcher.
4. Obtain paid GPU approval for the concrete quoted instance within the hard cap; benchmark the locked source job and refine timing/cost without consulting targets.
5. Execute all core cells; log attempts, curves, checkpoints, selected epochs and actual resource cost. Freeze source/inference state before score release.
6. Compute paired participant endpoints only after all gate receipts/checkpoint/prediction hashes pass; run an independent reconstruction and keep adverse/null/failed outputs.
7. Reorganize the final Results and assess a single exclusive journal submission only if evidence supports it.

Current delivery is a **non-submission-ready research work package**. No claim of actual matched-duration external results, independent target confirmation, affordability at a particular live rate, automatic server shutdown or new manuscript acceptance is made.
