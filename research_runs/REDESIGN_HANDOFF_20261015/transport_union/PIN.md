# Fixed metadata bridge and immediate dot handoff

Code commit: **`cf8a8336daf71bafbb199448b190e09a8f0a2ad1`** on
`research/paper1-handoff-20261014`. All9 changed files passed immutable public
byte readback; see `PUBLIC_READBACK.json`. The81 focused synthetic tests passed;
`VALIDATION.json` and `TARGETED_TESTS.xml` retain the exact evidence.

| File | SHA256 |
|---|---|
| `transport_receipt_union.py` | `c4638ec15c1b2a2e4b87940df55b0006ac05cd553818eb458648a77785f13ace` |

The actual source-restoration/CPU-acceptance execution pin remains
**`709a213c04689f4c388ee40c7cfa24b4d4f45ab1`**. Follow
[the single dot execution handoff](../DOT_RUN_NEXT.md) and
[its exact small-bundle commands and SHAs](../repaired_acceptance/AUTHOR48_PIN.md).
Do not substitute this new metadata commit for that adapter's execution revision,
repeat repair/installation, or run the old training launcher directly.

## Optional off-host metadata check after actual receipts exist

From a reviewed checkout at the code commit above, the default command is
offline/public-metadata only:

```bash
/usr/bin/python3 -I -B \
  research_runs/REDESIGN_HANDOFF_20261015/transport_union/transport_receipt_union.py
```

After the real five receipts exist, externally verify each exact JSON SHA
before binding it. No placeholder receipt is generated here. The following
variables name existing metadata files and their independently checked hashes,
never credentials or raw data. This metadata review does not require waiting
before the already prepared source restoration/CPU acceptance can proceed.

```bash
(
set -eu
: "${P1U_SOURCE_JSON:?actual source restore receipt JSON}"
: "${P1U_SOURCE_SHA:?independently checked source receipt SHA256}"
: "${P1U_TARGET_JSON:?actual official target byte-only receipt JSON}"
: "${P1U_TARGET_SHA:?independently checked target receipt SHA256}"
: "${P1U_RUNTIME_JSON:?actual repaired-runtime bound acceptance JSON}"
: "${P1U_RUNTIME_SHA:?independently checked runtime receipt SHA256}"
: "${P1U_FORMAL_JSON:?actual formal source acceptance JSON}"
: "${P1U_FORMAL_SHA:?independently checked formal receipt SHA256}"
: "${P1U_ROUTE_JSON:?independently reviewed exact root and receipt binding JSON}"
: "${P1U_ROUTE_SHA:?independently checked route binding SHA256}"
/usr/bin/python3 -I -B \
  research_runs/REDESIGN_HANDOFF_20261015/transport_union/transport_receipt_union.py \
  --source-restore "$P1U_SOURCE_JSON" --source-restore-sha256 "$P1U_SOURCE_SHA" \
  --target-bytes "$P1U_TARGET_JSON" --target-bytes-sha256 "$P1U_TARGET_SHA" \
  --runtime-bound "$P1U_RUNTIME_JSON" --runtime-bound-sha256 "$P1U_RUNTIME_SHA" \
  --formal-source "$P1U_FORMAL_JSON" --formal-source-sha256 "$P1U_FORMAL_SHA" \
  --route-binding "$P1U_ROUTE_JSON" --route-binding-sha256 "$P1U_ROUTE_SHA"
)
```

Even a matching result is metadata-only: no raw bytes/cache presence observed,
no target scientific PASS, no production routing, no accounting/backup acceptance,
no fit. No Pod operation or dot message delivery was performed by this assistant.
The original scientific inputs, frozen hashes, failures and fit guards remain intact.
