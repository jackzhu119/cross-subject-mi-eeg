# Actual raw-restoration failure and one authorized HEAD

## Evidence reviewed

The off-host archive `paper1-target-restore-failure-evidence-run01.tar.gz`
is64961 bytes, SHA256
`599a690184f657da06d2dcf35fd519fd6c8d4999115bc763396bf220d4242e43`.
The independent audit accompanies this note. The original archive remains
outside Git; no raw EEG, credentials or archive binary was added.

The actual attempt ran2026-10-15 08:41:48.388294–08:41:49.744257 UTC
and exited3. Its consumed claim binds raw code revision
`5e58526918169a15080cc79e3c44d8024e24f911`, script SHA256
`65507374bc7640d4c6b2b7d9b609d86b809a11d61a1aa55d61e6527ced4e5190`,
and original task `20261014T071918Z-exploratory-89b0c07d`.
The journal identifies `HTTPError` on the first frozen EDF basename; it
contains no HTTP status or Location. The archived postflight inventory has
only directories, claim and logs, with zero verified objects and no success
summary. This is a failed attempt; its old claim is not reusable.

The exact request URL follows from the pinned manifest, sorted execution
order, fixed source code and affected basename. It was not captured as an
HTTP wire trace. Neither a redirect nor an authorization denial can be
inferred from the old error class alone.

## One HEAD actually performed

At2026-10-15 08:49:15.825958–08:49:16.611013 UTC, the current Codex
executor made exactly one HEAD request to:

```text
https://data.nemar.org/nm000250/v1.0.5/sourcedata/sub-01/eeg/sub-01_task-R1acquisition_eeg.edf
```

The response was HTTP200 with no `Location`, Content-Length14805604 and
ETag `"sha256:a678fe6d37e0496eb381dcac6b877b047d02dfffc659ae4cfc38226f4850e185"`.
The length and server-declared ETag agree with the frozen first-object
metadata. No EDF response body was read; there was no redirect or retry.
Default proxy/CA configuration, certificate verification and hostname
verification were retained. The response's `Server` field was `envoy`;
this observation is not an independent origin-server identity proof.

The official directory/version in the frozen URL remains
`nm000250/v1.0.5`, with archived metadata tree
`f77f8859a84df42bd775920d288261260b2236db`. No directory listing or newer
version was fetched. This HEAD says nothing about the other173 URLs.

`head_observation.json` records the actual metadata. `executed_one_head.py.txt`
is an archival copy of the exact script that ran, not a new command to run.
No additional HEAD, GET or alternate endpoint was attempted. No Pod access,
installation, EEG processing or fitting occurred.

## Decision and next boundary

This current-executor HEAD200 is not the missing status of the earlier Pod
GET. Differences between execution environments, HTTP methods and observation
times remain unresolved. A HEAD response/ETag is not a full downloaded-byte
SHA256 verification and does not establish174-object restoration success.

There is no observed redirect to justify a redirect-policy amendment and no
observed denial to bypass. **Keep all redirects rejected and TLS/hash checks
unchanged.** Do not rerun restoration, clear/reissue its claim, delete cache
members or start production input preparation on this evidence. A future
Pod-side metadata observation would need its own explicit, bounded dot
authorization; this delivery does not issue it or claim it happened.

The independent production adapter remains separately pinned at
`ebd024aee8eca2f5655c8ddcd9d51cbc94c5b693`; it is not authorized to execute
without the actual successful raw-summary/outer-exit prerequisites. Original
task counters/checkpoints/backup continuity remain unknown, not zero. The
financial prerequisites remain superseded by the user's instruction; this
HTTP investigation introduces none.
