# Fixed supersession delivery for dot

> **Source run01 has now failed:** this authorization history remains valid, but do not rerun its source entry/claim. Use [SOURCE_RESTORE_REPAIR_PIN.md](SOURCE_RESTORE_REPAIR_PIN.md) for the new single repair and updated acceptance provenance. No Step B until actual18/18 and observed outer exit0.

Execution commit: **`0603c43fb082d7a63234ccbf5da849c5c2264687`** on `research/paper1-handoff-20261014`.
All15 changed files passed immutable public byte readback;84 focused gate tests passed.
Only the gate/template authorization changes. Both execution scripts and the original48-hour record retain their exact709a213c bytes.

Financial prerequisites are **superseded-by-user**, not passed. Do not wait for billing, balance or another money approval.
Historical accounts/unknowns/failures remain preserved. No install, Pod operation, target EEG read or fit was performed here.

## Deliver only the small fixed bundle

Dot performs this delivery under its existing technical/resource scheduling control. Use a new directory; retain the old709a213c bundle and all claims. No environment or scientific dependency is created or changed.

```bash
export P1_ACCEPT_REVISION=0603c43fb082d7a63234ccbf5da849c5c2264687
export P1_ACCEPT_DIR=/workspace/paper1-acceptance-code-0603c43f
(
set -eu
mkdir -m 700 "$P1_ACCEPT_DIR"
P1_ACCEPT_BASE="https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/$P1_ACCEPT_REVISION/research_runs/REDESIGN_HANDOFF_20261015/repaired_acceptance"
for P1_ACCEPT_FILE in acceptance_gate.py AUTHOR_CPU_RECOVERY_48H_20261015.json AUTHOR_FINANCIAL_SUPERSESSION_20261015.json restore_source_once.py accept_repaired_runtime_source.py source_restore_review.PLAN_ONLY.json source_restore_slot.PLAN_ONLY.json source_acceptance_review.PLAN_ONLY.json source_acceptance_slot.PLAN_ONLY.json; do
  curl -fSsL --proto '=https' --tlsv1.2 --max-time 30 \
    "$P1_ACCEPT_BASE/$P1_ACCEPT_FILE" -o "$P1_ACCEPT_DIR/$P1_ACCEPT_FILE"
done
cd "$P1_ACCEPT_DIR"
sha256sum -c <<'SHA256'
579067cf8eab2d3e6d20a00f54bc303f619796db04df9bd33eee4fdea066f528  acceptance_gate.py
ae0ee5135586a7c49bfd690946120455367b14d2c1426c5f7217347bedd12fb5  AUTHOR_CPU_RECOVERY_48H_20261015.json
d3a4e670332a9bf158da98abae0ab84702d092018c6043cbc36bf4f3f5fb7d90  AUTHOR_FINANCIAL_SUPERSESSION_20261015.json
2ee6355f51b29bbeedd30f8422c078af76615c26873e16826156ebc015d7f220  restore_source_once.py
83c30546f693511c7eee80d4520eb0cab70a945530e0321db575b7c75d25a7ca  accept_repaired_runtime_source.py
ed33d26e063fb1cf65e60160adaad2123c31967cf69424deab1a946a2ac0776b  source_restore_review.PLAN_ONLY.json
5a3db7b631aee759ac2c764bf1baab071812b6087be59c1a077674b7183e0d7e  source_restore_slot.PLAN_ONLY.json
e57ccf25702643a1edd9f250eb47f2d43bbf87920cd2133f742d4b5646fc257c  source_acceptance_review.PLAN_ONLY.json
6d79873e43d73ced4fb5b55b6f69133a945d9d331d85963f6aeb7bd810defa6a  source_acceptance_slot.PLAN_ONLY.json
SHA256
)
```

The gate SHA256 is `579067cf8eab2d3e6d20a00f54bc303f619796db04df9bd33eee4fdea066f528`.
The appended author record SHA256 is `d3a4e670332a9bf158da98abae0ab84702d092018c6043cbc36bf4f3f5fb7d90`.

## Bind technical records and execute the two original stages

The parent retains its actual technical GO but issues the correctly bound review for each operation. Use the new execution revision and gate SHA above. Remove `covered_dollar_upper_bound_reviewed`; bind `financial_preconditions_status="superseded-by-user"` and `financial_supersession_sha256` to the exact new author record. The templates themselves remain PLAN_ONLY and do not claim a real review or slot.

Dot supplies a fresh source_raw_restore slot, runs [Stage A](FINANCIAL_SUPERSESSION.md#stage-a--source-only-restoration-once), then binds the actual successful restore receipt in the source_cpu_acceptance technical review and issues its own fresh slot for [Stage B](FINANCIAL_SUPERSESSION.md#stage-b--actual-repaired-runtime-cpu-source-acceptance-once). The precise complete commands are in those two linked blocks; the exports above supply their immutable code/path variables. Already consumed or failed claims are not retried.

Keep1200s/300s,30-minute maximum single slots, the original48-hour CPU window and GPU deadline,3GiB ownership cap,10GiB floor plus real Paper2 reserve and all strict source SHA checks. The two recovered historical archives are reused at their real paths; no repeated retrieval or diagnosis is required.

A successful CPU acceptance still does not authorize a GPU fit, certify old costs/ledger unknowns, make a purchase, create a resource or operate the Pod from this assistant. This amendment changes no scientific protocol or training consumer.
