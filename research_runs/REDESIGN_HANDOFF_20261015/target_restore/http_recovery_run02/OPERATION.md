# Run02: one explicitly approved attempt after the first HTTP failure

This is a narrow operational derivative of the original raw-only coordinator,
not a new scientific project or general resume/retry framework. The original
`target_restore_once.py`, its immutable run01 execution bundle, transport
helper, scientific files and production adapter are unchanged. The exact
derivative is inspectable in `DERIVATIVE_PATCH.diff`; helper loading, slot
validation, allocated-byte scanning, atomic writes, journal writes and the
live resource/time/control check are unchanged.

The user supplied a same-Pod HEAD observation,564 bytes, SHA256
`a1d19255b427122f9f961cde33873693f35c0db3773112fdaebaa17ae8629ebe`.
It records2026-10-15 08:50:56.723734–08:50:57.160548 UTC,200, no
Location,14805604 bytes, frozen SHA ETag, default TLS/proxy, no body read,
redirect or retry. The original attachment is retained byte-for-byte under
`evidence/`. Its Pod attribution comes from the user's supplied provenance;
this JSON has no independent machine-identity attestation. HEAD200 does not
identify the earlier GET failure's HTTP status or reason.

## Exact scope and failure ancestry

Parent has agreed to one explicitly bounded additional raw-restoration
attempt. A new genuine parent review and fresh dot `target_raw_restore` slot
are still required; the template is not an approval. The new review binds
the new code SHA/revision, `recovery_identity`, original failure archive,
exact old claim/journal/outer hashes, same-Pod HEAD SHA and
`one_additional_bounded_attempt_authorized=true`. The old three cache records,
old actual exit3 receipt, original controller and HEAD are SHA-checked before
the new claim and rechecked throughout and after completion. The original
failure archive is64961 bytes, SHA256
`599a690184f657da06d2dcf35fd519fd6c8d4999115bc763396bf220d4242e43`.

Reuse only `/workspace/paper1-target-recovery-run01`. Fresh inspection must
find its exact old claim/journal/log and allowed frozen empty directories;
any EDF, partial, unknown member, modified/missing old record, old success
receipt or new run02 marker stops before GET and is preserved. No old record
is overwritten or removed. This entry does not resume a partial run02.

The new exclusive identity is `target_raw_restore_run02_after_first_HTTPError`:

```text
target_restore_run02.claim.json
target_restore_run02.journal.jsonl
target_restore_run02.log
target_restore_run02.json
```

The byte-only success receipt remains `target_bytes_receipt.json`, absent in
the failed run01. Success requires all174 exact files/2515343396 bytes,
an actual exit0 and mutually bound summary/byte receipt. A success-looking
summary before a late control failure is insufficient.

## HTTP recording without weakening transport

GET still uses the identical frozen URLs, original secure opener,
Accept-Encoding identity, verified TLS/hostname, no redirects, no retries,
exact Content-Length and whole-file SHA256. The first new HTTPError stops
the run02 loop. A401/403 is recorded and stops; no alternative endpoint or
authentication bypass is attempted. Unknown partials/hash failures stop.

HTTPError logging adds only bounded integer `http_status`, actual
`location_present`, `public_location`, `unsafe_location_omitted`, no body
read/redirect and no automatic retry. A Location is emitted only if it is
an exact public HTTPS frozen dataset/version acquisition-object URL for
participants01–87 with no query, fragment, credentials, port or other path.
Every other Location is withheld completely. No error-body, header dump,
arbitrary exception text or credentials are logged. Successful network
objects have status200 established by the unchanged helper; Location was
not inspected on that success path and is recorded as null, not absent.
New HTTP observations never backfill the unknown run01 status/reason.

## Gates retained

Reuse the accepted97-package runtime and18 source files without installing,
parsing EEG, re-running acceptance or changing metadata. The raw entry uses
`/usr/bin/python3 -I -B`, with original source/runtime metadata bindings.
Preserve1200-second outer and parent wall limits, individual30-second
network timeout,3GiB total target allocation including old/new logs,
10GiB free floor plus fresh dot Paper2 reserve>=5GiB and all remaining
writes, single sequential transport, fresh slot/review rechecks and the
unchanged deadline. Dot alone checks actual resources and operates the Pod.
No fee/balance prerequisite is reintroduced.

No fitting, inference, target scientific processing, new resource, credential
or lifecycle operation is authorized. Old task counters/checkpoints and
backup continuity remain unknown, not zero. Paper2 retains priority.

The separate production adapter still pins original raw code SHA655073… .
It will correctly reject this new run02 summary rather than accept a forged
run01 SHA. After genuine run02 success and observed outer0, review only the
necessary production receipt-binding amendment; do not bypass it now.

Use `EXECUTION_PIN.md` for the immutable source fetch and exact single
command. Record the real start/end, argv, source SHA, new review/slot SHA,
stdout/stderr and actual exit in a fresh run02 dispatch directory, keeping
the old dispatch unchanged. A failure leaves the new claim consumed and
does not authorize another attempt.
