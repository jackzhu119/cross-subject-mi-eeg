# Paper-stage release gates (as of 2026-09-26)

This is a preparation checklist, not a claim that Q12–Q16 have been run. The
cloud is off. Local CPU/synthetic tests verify code paths but cannot replace
raw EEG, CUDA, checkpoint replay, or independent scientific validation.

| Gate | What must be checked before advancing | Current state |
| --- | --- | --- |
| G0 historical custody | Keep Q5–Q14 code, predictions, failed attempts, checkpoints, hashes, and negative results unchanged; publish a new amendment rather than rewriting history. | Historical results untouched in this preparation branch. |
| G_Q14_FULL_VALIDATOR | Confirm original `Q14-E002R2` 109-subject receipt and prediction hashes; run corrected `q14_r2_validate.py` on all 327 checksum-verified EDF files with the frozen runtime; require `passed=true`, 109 subjects, 34,426 rows, zero target fits, all metric/CI receipts and the new `Q14-R2FINAL` publication receipt. | **Pending cloud/raw EDF.** Offline aggregate and subject-file audit passes only. |
| G_Q12_Q13_SOURCE_ONLY | Commit reviewed protocol/code before GPU use; confirm Q8/Q5 and Q9 source-only provenance; check raw MAT hashes, 9-subject LOSO, all seeds, source-only selections, no target-fit transforms, CUDA and noninteractive Git write permission. | Local implementation/test stage; **not executed**. |
| G_Q12_INDEPENDENT_VALIDATION | Q12's 216 inner fits need hashes/curves/manifests and 162 final fits need exact held-out trial IDs, metrics and checkpoint replays from raw EEG. Preserve class collapse and failed arms. | **Pending new fits.** |
| G_Q13_INDEPENDENT_VALIDATION | Q13's 837 new fits, fixed-source subsets, source sessions, fit/epoch manifests, trial probabilities, all 837 checkpoint replays and subject-level tables must pass. | **Pending new fits.** |
| G_Q15_METADATA_AND_FREEZE | Before any Lee/Cho prediction: metadata-only eligibility table, cue origin/window, exact ordered channels, units, labels, subject/session inventory, raw hashes, license, full harmonization rule and source-model hash committed. Block incompatible arms rather than altering protocol after scores. | **Planned only**; no raw new-cohort audit. |
| G_Q15_INDEPENDENT_VALIDATION | Rebuild trial identities and predictions from each cohort's raw files; zero target fits; cohort-specific subject-level BA/CI/confusions and all exclusions/failures retained. Never call metadata-only audit a result. | **Not started.** |
| G_Q16_PHYSIOLOGY | Freeze pre-cue/task windows and μ/β bands before examining subject BA; inspect C3/Cz/C4 ERD/ERS and scalp maps for every eligible subject, with descriptive high/low performance comparisons that never feed model choice. | **Protocol planned only.** |
| G_PAPER_STATISTICS | Use subject—not trial/seed/subset/session—as inference unit; report effect sizes and CIs, Holm families where applicable, sensitivity and negative findings, plus clear exploratory/confirmatory labels. | Plan prepared; analysis awaits validated outputs. |

The release order is Q14 validator-only first, then Q12 and Q13 BNCI
exploratory mechanisms, then Q15 metadata/freeze before new external outcomes,
followed by Q16 and manuscript synthesis. A failed technical gate is a stop
for the corresponding scientific claim; it is not permission to change target
exclusions, select a better seed, or erase its logs. Q12/Q13 can be scheduled
sequentially on a later GPU host, but neither is allowed to rewrite Q14.

`validate_packet.py` checks the *planning packet* and fit arithmetic only. It
cannot turn any pending gate green. For Q14's later validation-only command,
see `research_runs/Q14-E002R2/VALIDATOR_ERRATUM_20260926.md`.
