# Fixed narrow transport patch — review only, no restoration command

| Artifact | SHA256 |
|---|---|
| `../nemar_single_hop.py` | `7a717fd63b4c0945e2a232c7560f475b5618c3c992c069cb9f451a569e5d4716` |
| `../test_nemar_single_hop.py` | `bc93515fa2121afb8f1f2f2e8162606e3e697536d0aa0a1c8df39728f8f2d603` |
| Unchanged `../official_edf_transport.py` | `1aa2da0b710b3ef109d00d19c75a00fda013a79f947e9aebbe3480c8e99b895f` |
| Official mechanism/provenance proof | `b840d408b8beeb51508002d0a2d4018ae1d976ccb32765b6c8170dbee11d252f` |

The Git commit identified in the delivery response fixes these files and
their metadata evidence. `PATCH_SHA256SUMS.txt` verifies the precise patch,
unchanged helper, frozen catalogue inputs and review records. It contains no
signed URL, raw EEG, credential or environment binary. No install or extra
package is needed; all adapter imports are standard-library/helper code.

The sole proposed protocol change is one302 from the frozen canonical URL
to one exact HTTPS storage host and content-addressed key. Inspect
`ADAPTATION.md`, `OFFICIAL_MECHANISM_PROOF.json` and
`NARROW_POLICY.PROPOSED.json` before any future integration. These are code
and policy-review records, not a genuine dot slot, parent grant or run03 claim.

## Offline verification

In an existing checkout of the fixed delivered commit, run only checksum
verification from `research_runs/REDESIGN_HANDOFF_20261015/official_edf_transport/http302_review_run01`:

```bash
sha256sum -c PATCH_SHA256SUMS.txt
```

The31 mocked tests already passed in the existing local test environment;
their exact command, actual UTC interval and output are in `TARGETED_TESTS.json`.
No Pod-side re-test or installation is necessary for this code-only handoff.
The tests use tiny synthetic bytes and synthetic signature sentinels, never
provider-signed URLs, EEG or target outcomes.

## Integration interface, not an execution dispatch

The reviewed adapter exports `frozen_plan`, `transport_one` and
`verify_cached_manifest`. `transport_one` retains the original arguments:

```python
transport_one(row, root, *, control_check, min_free_bytes,
              paper2_reserve_bytes, max_new_bytes)
```

There is no CLI, arbitrary-opener argument, alternate-host list, resume mode
or claim-management API. `control_check` must be the original approved
controller's live slot/review/time/global-allocation/free-space check. The
adapter calls it before each network step and during byte verification; it
does not independently issue or validate an operational slot. Preserve the
original1200-second ceiling,3GiB total allocation,10GiB free floor plus
Paper2 reserve>=5GiB and all remaining-write reservations in any later
controller. The single-hop primitive's typed resource checks are inherited
from the original primitive, not a replacement for those controller gates.

On failure, `ControlledTransportError.code` and `.safe_metadata` contain only
controlled code/status and allowed Location component classifications. The
public boundary rebuilds the exception without inner network traceback,
context or frames containing transient signed URLs. Log only those fields;
never introspect network objects, record raw response headers or persist the
transient URL. The one-hop response is checked against its actual final URL
in memory; it is never relabelled as a direct canonical response.

Run01/run02 remain failed with exclusive claims consumed. This patch has not
been injected into either spent entry or the production adapter. No recovery
command is supplied or authorized here. A future bounded execution must
first bind both failures and the reviewed adapter in a new explicit identity
with genuine fresh parent/dot resource records; retain every existing
scientific, source/runtime, continuity, byte/hash and training gate.
