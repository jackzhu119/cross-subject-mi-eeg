# Proposed same-byte official EDF recovery transport

This amendment removes a transport dead end without changing any scientific
input identity. It is **proposed for dot parent review**, not permission to
transfer target data or start a fit. The current helper CLI is offline planning
only. No Pod, network, target EEG, installation, model, or old source diagnostic
was accessed or executed during this implementation.

## What is already established

The frozen acquisition manifest has **174 unique NEMAR `nm000250/v1.0.5`
`sourcedata` acquisition EDF paths, 2,515,343,396 bytes**, for R1/R2 of all 87
participants. Each exact HTTPS URL, byte length and SHA-256 is already frozen;
this amendment does not invent an R2 object key or substitute a different
dataset. The helper checks the pinned manifest against the archived provider
provenance, README/license and full expected roster before emitting the plan.

- Frozen acquisition manifest SHA-256:
  `2cfdf35aa7990df880826d1b84d1230e0bda3c9393c17d3ec6e27b7b311d2bf2`.
- Provider sourcedata provenance SHA-256:
  `0d45bdd3394555e33d8dd153ad1ff15f9340f6f867a99e7bd13cf1e3b582b274`.
- Frozen provider tree: `f77f8859a84df42bd775920d288261260b2236db`.
- Original acquisition-manifest provider SHA (a different file):
  `061a8e215093e1bb0db8f80f95b112c60266acfa640284d05f92c0c6a5ddc544`.

The provider declares these sourcedata EDF contents unchanged from the
MOABB/OSF distribution. That declaration and a future exact EDF SHA match do
not prove equivalence to the original Zenodo **GDF ZIP** or the root BIDS
**BDF** derivative. Neither is an allowed byte substitute. Current remote EDF
availability and current server object contents remain unobserved.

The archived provider evidence declares **CC BY 4.0**. Preserve creator
attribution, the dataset/provider and original-paper sources, the
[license link](https://creativecommons.org/licenses/by/4.0/), and an indication
of downstream processing changes. Relevant identifiers are
[NEMAR DOI](https://doi.org/10.82901/nemar.nm000250),
[original dataset DOI](https://doi.org/10.5281/zenodo.8089820), and
[original paper DOI](https://doi.org/10.1038/s41597-023-02445-z).
This is the previously archived license evidence, not a new license retrieval.

## Exact offline plan command

From an independently pinned, clean checkout containing this helper, the
following command reads only committed public metadata and prints a complete
174-row plan. It imports no numerical or GPU library and makes no request.

```bash
/usr/bin/python3 -I -B research_runs/REDESIGN_HANDOFF_20261015/official_edf_transport/official_edf_transport.py
```

An optional `--output /absolute/new/plan.json` writes only a new JSON path and
refuses an existing file. Do not use a live EEG cache path as the output. The
committed `frozen_official_edf_transport_plan.PROPOSED.json` is the reproducible
offline output; it is a transport mapping, not an observation of live bytes.

## Future transport implementation and controls

`transport_one()` is an isolated, synthetic-tested primitive, deliberately not
called by the CLI or the existing scientific worker. A later reviewed
coordinator must bind the complete fixed mapping, an approved amendment,
fresh transfer slot, actual budget/backup transition and exclusive cache
ownership before using it. The old metadata slot is consumed and cannot
authorize installation or transfer.

The existing `priority_gate.py` operations (`metadata`, `runtime_preparation`,
`source_cpu_acceptance`) **do not include target transport**. None of their
receipts authorizes this primitive. A separately reviewed transport-specific
coordinator/scope must protect the paper2 environment, global package roots,
code checkout and paper1 runtime against the destination root, and recheck
the complete-cohort cumulative network/disk quota. The per-object primitive
alone cannot establish those aggregate or path-isolation controls.

The primitive uses the exact `https://data.nemar.org/nm000250/v1.0.5/<path>`
URL only, normal certificate and hostname validation, and the inherited proxy
and CA configuration. It rejects **all redirects**, including same-origin
redirects. It requires status 200, exact `Content-Length`, identity content
encoding and a bounded full-body SHA-256 match. There is one serial object,
no automatic retry, no range/partial resume, no alternate hostname, no
insecure TLS fallback and no credentials. A redirect, TLS or byte failure is
an explicit stop, not permission to weaken the frozen gate.

An existing complete object is reused only after full size/SHA verification.
A symlink, corrupt existing file, or existing `.partial` stops and preserves
the evidence. New bytes go to an exclusive no-follow `.partial`; after full
size/SHA and a final control check they are published with atomic no-overwrite
`link()` followed by removal of the verified partial. A failed or interrupted
partial remains for manual review; it is never silently overwritten or
treated as complete. A fresh coordinator must inventory partials before
determining its remaining capacity and total-byte allowance. No two workers
may own the cache concurrently.

The full target payload is **2,515,343,396 bytes**, below 3 GiB. This is distinct
from the runtime preparation allowance (at most 3 GiB); those allowances do
not combine into a newly authorized total. Before transfer, real available
space must cover every missing EDF byte **plus at least 10 GiB plus the real
dot-issued paper2 reserve**. Per-object streaming rechecks the reserved floor
and a supplied live operation-control callback. A callback failure preserves
the partial and stops. The primitive cannot establish that paper2 is idle;
only dot may issue that new scheduling record. It cannot prove provider
charges, cumulative GPU time, backup state or historical checkpoints.

`verify_cached_manifest()` is a future byte-only local-cache receipt helper,
also not reachable from the offline CLI. A separately approved call hashes
all 174 complete EDFs and emits exact manifest bindings. This is an explicit
target raw-byte read, so it was **not run** in this task. Its receipt leaves
header/event/QC/per-event input hashes, runtime, accounting and training gates
false. It cannot be used as a scientific acceptance or fake R2 receipt.

## Production integration remains closed

The unchanged `prepare_data.py` currently calls the all-192-object R2 importer
unconditionally. Therefore placing official EDF files into its cache is **not
yet sufficient** and must not be reported as an R2 import success. This turn
does not change that worker or its source/target scientific gates.

After explicit approval, the minimal routing amendment would accept separate
authentic source-restoration and official-target-transport receipts, verify
their union against the same frozen 18-source/174-target identity inventory,
and then call the unchanged strict source reconstruction and target
header/event/QC/input-hash checks. It must retain the old R2 failures,
`r2_enabled=false` historical snapshot and missing private mapping evidence.
It must not manufacture `object_key`, `r2_enabled`, old job registration,
checkpoint or backup receipts. This requires independent review before
production integration; the current default CLI cannot bypass it.

Target status remains **exploratory**, with prior exposure unknown. The
frozen 19 channels, source selections/seeds, 85-person/6,800-event retained
roster, A17/A41 provider exclusions, native-context and all three-band input
hashes remain unchanged. No target fitting, normalization fitting, BatchNorm
updates, training-duration selection or outcome-driven rule changes are
authorized.

All actual-training runtime, strict source/target input, old task,
accounting/cumulative budget, checkpoint and backup gates remain required.
The deadline-only amendment ends at **2026-10-16 09:54 UTC**; this proposal
does not reset or expand the $10/cumulative-eight-GPU-hour/fit/update caps.
Unknown historical spend and GPU time stay unknown until supported by actual
records; zero newly observed fits is not zero cost.

## Targeted verification

The bounded suite uses synthetic byte strings and pinned public JSON/README
only. It checks exact URL/path identity, no redirects, TLS policy construction,
size/hash failures, corrupt/partial preservation, no-overwrite publication,
symlink rejection, resource floors, operation revocation and offline-only CLI.
It does not import CUDA, read an EDF, install a package, or rerun a diagnostic.

```bash
/workspace/mi-eeg-cloud-cpu28-tests/bin/python -B -m pytest -q \
  research_runs/REDESIGN_HANDOFF_20261015/official_edf_transport/test_official_edf_transport.py
```

The interpreter path above is the existing **local review environment**, not
a claim that the rebuilt Pod contains it. The helper itself is stdlib-only.
