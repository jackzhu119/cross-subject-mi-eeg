# NEMAR file GET302: narrow transport correction, no recovery dispatch

## Actual failure and metadata diagnosis

The run02 original archive is14244 bytes, SHA256
`6f9bbb8e6070bf0df1a0ffdcd57b484184e9b6d244c82b08bc3285fa0e1bf176`.
Its24 payloads plus manifest passed independent full length/SHA verification.
Actual execution was2026-10-15 09:03:57.420562–09:03:58.718980 UTC,
PID26987, exit3, HTTP302 on the first canonical file, with Location present
but withheld. No verified EDF, success summary or partial was in the archived
postflight. Both consumed claims and all original failure records remain
unchanged. Run01's missing HTTP status is still unknown.

One separately authorized GET-header diagnosis from the Codex executor ran
2026-10-15 09:13:46.186894–09:13:47.015579 UTC. It used the original
secure opener, default TLS/CA/proxy and Accept-Encoding identity. Result:

```json
{
  "http_status": 302,
  "location_components": {
    "scheme": "https",
    "hostname": "nemar.s3.us-east-2.amazonaws.com",
    "port": null,
    "query_present": true,
    "fragment_present": false
  }
}
```

It followed nothing and made zero application response-body read calls. The
diagnostic did not retain the storage path, complete Location, query values,
signature or credentials. It is not a retrospective capture of run02's
withheld Location. No storage-object request or restoration retry occurred.

## Official mechanism and exact-host proof

[NEMAR's Data API](https://docs.nemar.org/platform/data-api/) describes
canonical versioned file resolution and backing annex storage. Its
[agent guide](https://docs.nemar.org/platform/for-agents/#downloading-datanemarorg)
explains why HEAD200 and GET302 are compatible. The original reject-all
redirect gate therefore blocked an expected download step; HEAD200 never
established that a GET could complete under that gate.

The exact host is supported by fixed official implementation/configuration,
not by a guessed mirror or suffix allowlist:

- [`data-router.ts:254`](https://github.com/nemarOrg/nemar-cli/blob/e77013a858f8242783d91bdef2f6e832781b9506/backend/src/services/data-router.ts#L254): plain annex storage uses dataset ID plus the manifest's content key.
- [`s3.ts:132`](https://github.com/nemarOrg/nemar-cli/blob/e77013a858f8242783d91bdef2f6e832781b9506/backend/src/services/s3.ts#L132): the backing GET is signed for the configured bucket/region.
- [`wrangler-sccn.toml:225`](https://github.com/nemarOrg/nemar-cli/blob/e77013a858f8242783d91bdef2f6e832781b9506/backend/wrangler-sccn.toml#L225): production bucket `nemar`, region `us-east-2`.

`OFFICIAL_MECHANISM_PROOF.json` records exact source hashes, line ranges,
limitations and the frozen first-object pointer. In the original frozen tree
`f77f8859a84df42bd775920d288261260b2236db`, its103-byte Git blob is
`5f67d2a5f58592c8ff4ffcbf790ead40922b135e`, encoding the size14805604
and the already frozen SHA256. The fresh tag tree differs and is not used
to replace the frozen tree or manifest. Only the first pointer was read in
this investigation; no claim of174 independently observed live storage
paths is made. The public source pin is not proof of the live deployment's
complete code identity.

## Minimal proposed amendment

Keep the original174 canonical URLs, version, license, sizes and SHA256
unchanged. The proposed adapter allows at most one302 from the exact
canonical row to HTTPS on **only** `nemar.s3.us-east-2.amazonaws.com`, with
no port override, userinfo or fragment. In memory, require the storage path
to equal `/nm000250/objects/SHA256E-s<row.bytes>--<row.sha256>.edf` exactly.
The strict derived-key condition is an additional transport acceptance rule;
an actually different key/path stops, rather than changing scientific input.

The provider query is transient delivery data. It is used unchanged only for
that one allowed-host GET and is never persisted, printed or put in an
exception/receipt. Start every object from its canonical frozen URL; never
cache or construct a signature, create credentials or use a storage URL as
the dataset identity. Forward no Cookie, Authorization or arbitrary origin
headers. Preserve default proxy/CA and hostname/certificate verification.

Reject all further redirects. A401/403, unknown host, different key, invalid
Location, expired signature or any other failure stops without auth refresh,
fallback, range resume or automatic retry. Direct canonical200 remains
subject to the same full-object verification. Require actual final200,
exact Content-Length, identity encoding, full byte count and SHA256 before
the unchanged atomic publication. Preserve partials and every disk, resource,
control callback and time limit. A normal two-request canonical-to-storage
chain is one download attempt; it is not a retry.

Diagnostics expose only controlled error code/status and parsed Location
scheme, hostname, port and query/fragment booleans. No full storage URL,
path, query value, signature, response body or header dump belongs in logs,
chat or Git. The controlled exception metadata is for a later reviewed
controller integration; no spent controller is silently modified.

## Delivery boundary

`nemar_single_hop.py` is a small transport-only adapter using the original
verified helper and inherited full-object verifier. It does not install,
enumerate targets remotely, launch restoration, issue a slot/claim, fit a
model, alter scientific processing or change deadlines. Original transport,
run01/run02 controllers, claims, manifests and production gate stay fixed.

This delivery includes offline mocked tests and metadata/source evidence
only. A later single recovery execution needs its own explicit failure-bound
identity and fresh genuine dot review/resource slot. This correction does
not revive run01/run02, issue run03 authority, or turn an untested storage
path into an accepted input. After actual174/174 byte verification, scientific
input preparation, old-task continuity and training authorization remain
separate. Dot remains the sole Pod operator; Paper2 priority is unchanged.
