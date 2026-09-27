# Q15 prospective external-cohort amendment — metadata only

Status on 2026-09-27: **prepared, not trained, not externally scored, and not cleared for release**. This is a new prospective planning record. It does not edit the 2026-09-26 packet, Q14 checkpoints, predictions, validation, or failed-attempt history. Neither Lee2019_MI nor Cho2017 raw files have been audited for this amendment.

## Why a new source contract is needed

The frozen Q14 source model requires 22 ordered EEG channels, including `FCz` ([Q14 configuration](../Q14-E001/CONFIG.json)). The official [MOABB v1.7.2 Lee2019_MI source metadata](https://github.com/NeuroTechX/moabb/blob/v1.7.2/moabb/datasets/Lee2019.py#L297-L375) lists 62 EEG electrodes but no `FCz`. This is a **catalogue/loader metadata observation**, not a checksum-verified inspection of every Lee file. Under the existing fail-closed 22-channel rule, Q15-E001 (exact Q14 3-second model on Lee) and Q15-E004 (22-channel 2-second model on Lee) are blocked pending raw-file confirmation. Do not insert an interpolated channel, change model input shape, or silently remove `FCz` from a frozen checkpoint. If raw data unexpectedly contain `FCz`, document that in a versioned metadata audit before changing this block; no external scores may inform the decision.

The new, separately identified proposal below removes only `FCz` **from BNCI source training** before either new cohort is scored. Its output is not an unchanged Q14 checkpoint, and any result must be described as a new harmonized source model. This is a metadata-driven amendment made after Q14 PhysioNet outcomes were seen; it is prospective only with respect to Lee and Cho outcomes, not a retrospective preregistration of Q14.

## Predeclared branch and arithmetic

| ID | Dataset and action | New fits | Mandatory gate |
| --- | --- | ---: | --- |
| Q15-V001 | Lee2019_MI metadata-only audit: all subjects, both sessions, offline labeled MI runs | 0 | Raw hashes; actual 21-channel presence; cue origin; unit/reference; complete run inventory |
| Q15-V002 | Cho2017 metadata-only audit: all subjects and labeled MI runs | 0 | Same audit, including 3-second task-window coverage |
| Q15-E005 | BNCI2014_001 source-only 21-channel, cue-relative `[0.5,2.5)` s, 160 Hz source model | 14 deep + 1 CSP shallow | Both V001/V002 compatible and harmonization/code frozen **before** source fitting or external prediction |
| Q15-E006 | Cho zero-shot from exactly frozen E005 checkpoints | 0 target fits | E005 source-freeze receipt and Cho raw audit pass |
| Q15-E007 | Lee zero-shot from the **same** E005 checkpoints | 0 target fits | E005 source-freeze receipt and Lee raw audit pass |

E005 retains Q14's broadband EEGNet, shared μ/β EEGNet, and CSP4+LDA arms; 8–30, 8–13, 13–30 Hz bands; fourth-order zero-phase run-local filtering; all-source trials including artifact-flagged; four fixed source-only inner groups; fixed selection seed `20260923`; final seeds `20260924/25/26`; source-only epoch rule and training hyperparameters. Only the scientifically required input dimensions change to 21 channels and 320 samples. Two neural arms × (four inner fits + three final fits) = **14 deep fits**, plus **one** CSP+LDA source fit. This count excludes the separately proposed Q15-E002 22-channel Cho branch. Neither branch should be activated or chosen based on Cho/Lee balanced accuracy. No target subject supplies a fit, normalizer, selection signal, batch-normalization update, alignment statistic, or seed choice.

The primary external contrast is the equal-subject mean of `MU_BETA_SHARED − BROAD_EEGNET` balanced accuracy, averaging the same three frozen seeds within each subject first. Report both cohorts separately. Lee's two sessions are nested within each person, not 108 independent people. Subject bootstrap CIs and every subject's confusion/classes/seed variance accompany the effect; if claiming inference over the two prospective cohorts, apply the predeclared Holm correction. CSP is a contextual comparator. No binary score is directly comparable to the four-class BNCI BA.

## Stop rules and remaining work

1. Metadata-only V001/V002 must record a pinned provider/loader version, official or provider file hashes, expected-versus-observed subject/session/run inventory, ordered channel names, **native and loader-output physical units plus their deterministic conversion**, reference, cue-event origin, label definitions, in-task window coverage, and redistribution rights. Use Lee offline training runs only; its online MI test runs lack scored labels. Incomplete or corrupt files cause an explicit blocked receipt, never quiet exclusion. Metadata inspection may read label definitions/counts but no predictions or classification metrics.
2. Do **not** treat the MOABB channel catalogue as proof of raw compatibility. A raw-file audit may block E005/E006/E007; if that happens, retain the failure and create a new prospective amendment before any external outcomes rather than selecting a convenient channel intersection.
3. Freeze the V001/V002 inclusion table, source code and dependency versions, BNCI raw hashes, source checkpoint hashes, preprocessing, label map, epoch rule, and statistical script before first Lee/Cho prediction. A validator must independently reconstruct trial IDs and model predictions from checksum-verified raw files before a scientific `passed` receipt is issued. This packet's local validator checks only contract consistency and synthetic fail-closed logic.
4. Lee's [dataset record](https://ww2.nemar.org/dataset/nm000338) lists roughly 121 GB for its full converted release; Cho's [record](https://nemar.org/dataset/nm000245) lists roughly 16.7 GB. Verify the chosen original-MAT or converted-provider subset and disk needs before cloud deployment. The current plan does not authorize downloading everything or starting a GPU job.

The old [2026-09-26 external protocol](../PAPER_RELEASE_20260926/EXTERNAL_PROTOCOL.md) remains intact as historical context. Q14's independent portable validation and Q12's completed runs must be reported from their current result receipts, not the stale status text in that earlier planning packet.
