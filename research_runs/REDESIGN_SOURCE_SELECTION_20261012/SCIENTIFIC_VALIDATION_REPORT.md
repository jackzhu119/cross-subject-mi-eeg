# Scientific validation report: evidence boundaries and redesign acceptance

Reviewed 13 October 2026. **Overall status: FURTHER SCIENTIFIC WORK REQUIRED — new independent neural confirmation and submission gate remain closed.** Technical checks below pass their stated scopes. They do not establish the new programme's H1 effect, participant independence or full-cohort preprocessing validity. This report is based on actual current artifacts, not planned experiment counts described as completed runs.

## 1. Executed scientific work versus planning

| Work | Actual state | Interpretation |
| --- | --- | --- |
| Historical prediction/selection/power arithmetic replay | Completed saved-output review | Retrospective reconstruction; primary historical outputs unchanged |
| Fresh traditional CSP source diagnostic | Ten completed source fits; nine LOSO plus one resubstitution | New retrospective source-only diagnostic; no independent target confirmation |
| Original frozen historical CSP model replay | SKIP; no old model deserialization/inference | New refit scores cannot be attributed to the historical model artifact |
| Dreyer access/parser preflight | Bounded three-file subset plus metadata; 12 replay checks | Partial transport/header/cue/pre-cue verification; full raw/provenance/QC gate not passed |
| Future statistical software | 37 invented-input tests, no failures/errors | Software correctness checks, not real EEG efficacy or independence evidence |
| Paired-t power planning | 72 assumed scenarios; 79 checks passed | CPU mathematics only; no target effect estimates |
| New 19-channel neural selection study | Zero new neural fits; zero new-target predictions | NOT EXECUTED |
| Optional alternative grouping study | Registry only; zero optional neural fits | NOT EXECUTED / disabled |
| New physiological experiment | None | Historical nine-person descriptions retained only |
| Paid GPU / new journal submission | Not executed by this work package | Separate authorization and completed evidence required |

The declared ten fresh CSP fits and zero new neural/target fits are distinct counters. Calling the entire upgrade “no new fitting” would be false. Conversely, completing the source diagnostic is not completing the 26-fit core neural design.

## 2. Verified historical numerical evidence

1. Historical development BA replay reproduces mean-loss 33.719136% and mean-rank 42.669753%, mean difference 8.950617 pp, median 1.851852 pp, and S3/S8 contribution 87.571839% of signed aggregate gain. Seven participants improve and two tie. The frozen nine-person tie-inclusive binomial sensitivity remains p=.179688; the seven-nonzero tie-excluding sign test and retrospective exhaustive sign-flip sensitivity give .015625 and do not replace it. These are exploratory observed-development results, not independent confirmation or proof that mean-rank is broadly superior.
2. The separate fixed20 follow-up has mean difference 10.063014 pp against its matched-runtime historical-loss replay, median −0.173611 pp and four improved/five worsened participants. The preserved sign-flip p=.125 is not replaced by a positive percentile bootstrap interval. No corrected robustness gain is established.
3. External complete-pipeline differences are PhysioNet +0.573296 pp [−0.096683,+1.241555], Cho2017 −1.513355 pp [−2.248958,−0.804487], and Lee2019 +0.203704 pp [−0.515432,+0.969136]. The adverse Cho result and uncertain PhysioNet/Lee outcomes remain. Lack of significance is not equivalence.
4. Historical PhysioNet's exact-zero sign procedure is retained (63/43/3; p=.064464). A newly labelled integer-count tolerance sensitivity (63/42/4; p=.050442) is not the frozen primary rule. Cho/Lee primary Monte Carlo sign-flip and Holm results are likewise not replaced by exploratory sign tests.
5. Historical CSP class bias is reconstructed from stored predictions: trial-pooled left shares 92.072243% and 83.212963%; median left probabilities .669354/.632939. Cho's person-mean left share differs from trial pooling. Label-complement arithmetic is post-outcome and changes no labels/predictions in the primary files.
6. Stored source curves reproduce loss/rank duration choices in nine outer folds/1,440 rows. Recorded Q15 source/external artifact bindings match the reviewed archived hashes. This supports the specific saved evidence chain, not all historical runtime or implementation claims.

Main pointers: `evidence/historical_reaggregation.json`, `results/historical_internal_paired.csv`, `results/historical_participant_metrics.csv`, `results/historical_participant_seed_cells.csv`, `results/historical_source_schedule_replay.csv`.

## 3. Fresh CSP source diagnostic: independently checked scope

Run `cpu-csp-20261013T004218Z-2828deb4` follows public preanalysis commit `f35fb97a28d7ddeea6b87f92b4d0975a4a0ebece`. The actual executor records 18 source originals, 108 runs, 2,592 binary trials, ten completed fits, zero neural fits and zero target fits/predictions. Raw-label/numeric replay validation passed; it shares the frozen transformation helper rather than independently reimplementing EEG preprocessing.

This report separately read all ten stored prediction CSVs, reconstructed class recalls/person BA with integer counts, verified prediction/partition/model byte hashes against fit receipts without deserialization, checked binary probability range/normalization/argmax, and verified the nine held-out files cover all 2,592 distinct source sample IDs exactly once. Both stored summary means agree: **61.651235% held-out source LOSO; 63.040123% fresh training resubstitution**. Full class confusion and bias quantities are in Supporting Information Tables S4–S7 and the machine-readable CSV. Each person has 144 trials/class.

The completed independent validator and 50-check stored-output review provide complementary provenance checks. These checks show an operational source pipeline whose mean BA descriptively exceeds 50% on nine already observed people under the new recorded runtime; they do not establish every implementation error absent, identify why CSP transfers poorly, certify physical device voltage calibration, or retroactively authenticate the previously unarchived audit run. The original historical model replay receipt is SKIP. Claimed posthoc target demeaning values remain unverified and are not inserted as actual results.

Pointers: `results/cpu-csp-20261013T004218Z-2828deb4/independent_validation.json`, `independent_validation_receipt.json`, `original_model_replay_receipt.json`, `participant_confusion_and_metrics.csv`, and `evidence/cpu_csp_execution_independent_review.json`.

## 4. Design consistency and implemented analysis safeguards

- The primary H1 is exactly Broad mean-rank−mean-loss, participant BA averaged over all three final seeds, two-sided paired t at α=.05. Every participant has equal inferential weight; trials, sessions and training seeds do not inflate n.
- The three prespecified secondary contrasts are fixed−loss, fixed−rank and shared-fixed−broad-fixed. Their Holm family only opens after the primary is rejected and scientific gates pass. All estimates are reported when closed. Ordinary 95% intervals are explicitly unadjusted; conservative 98.333% simultaneous intervals are separate.
- No noninferiority/equivalence hypothesis or data-chosen margin exists. Shared-fixed versus Broad-fixed matches duration but still contrasts entire pipelines, with differing views/filtering/BatchNorm/compute.
- Source groups are fixed 2/2/2/3 with equal fold weighting, one source-CV seed, and final seeds20261013/14/15. Optional grouping sensitivity is disabled. The single-CV-seed and arbitrary grouping limitations remain explicit.
- The core config's Broad/shared/fixed20 identifiers have a documented CSV alias map. Real scoring requires at least20 locked eligible trials/class/person and all conditions use the identical event inventory.
- Inputs are validated for complete person/condition/seed/event coverage, immutable truth/window fingerprints, duplicates, probabilities and checkpoint identities. Audit receipts must pass in their own JSON contents and match byte hashes/contract identity; real checkpoint bytes must match and predictions reference the correct condition/seed checkpoint. These are identity checks, not independent certification of truthful audit judgments.
- Synthetic nominal significance can never declare confirmation. Constant difference vectors are reported as degenerate, including float rounding residue from a repeated0.1 value, rather than returning an infinite t or p=0. Bootstrap resamples participants only.
- The current primary ceiling is85 after A17/A41 montage exclusions, not87 observed eligible participants. Five other provider flags remain pending raw-only QC. Power remains 72 assumed cases; n85, SD10 pp gives3.074038-pp primary MDE. Its independent normal/chi-square check is included in79 actual numerical checks.

Review corrections: the earlier statistics review JSON's63-case/69-check and n87-only planning metadata were stale. They are synchronized to the actual72-case/79-check, n85-inclusive artifacts without changing the saved72-scenario numerical values. This is metadata maintenance, not a changed primary hypothesis or observed result. The real-contract20-trials/class guard now matches the raw-QC protocol.

## 5. Physiological interpretation retained

Historical physiology is descriptive, sensor-level, BNCI-only, post-outcome, n=9 and without decoder feedback. Saved power arithmetic and six rank associations reproduce the record without new raw spectral computation. μ/β mean signed laterality remains −0.249685/−0.167875 dB. No p values are added; ρ=.6 is not confirmatory. One-baseline versus three-overlapping-task Welch segments, different physiology/decoder windows and no external replication prevent absolute unbiased ERD/ERS, biomarker, cortical localization or causal learned-mechanism claims.

## 6. Explicit unresolved scientific gates

1. **Author prior use/reuse confirmation:** metadata-only reading of second-project documents does not establish that Dreyer has never been model-evaluated by the author. No prior-exposure answer is inferred or invented. Published provider online-performance information was encountered during metadata/QC reading after conditional nomination, so completely unseen performance literature is not claimed; no new-model candidate scores were computed or used for design.
2. **Participant identity:** anonymized IDs/geography cannot prove no cross-provider overlap. Source/target acquisition duplication and participant-identity uncertainty require an explicit final judgment before confirmatory naming.
3. **Full raw/provenance/QC:** three-file access success does not clear174 acquisition files or authenticate original GDF/Zenodo conversion. The header/descriptor hardware-filter discrepancy and physical calibration limits remain. Full eligible event/channel/context/finite-signal/flatline audit is pending; n85/6,800 are ceilings, not final counts.
4. **Task transport:** sham visual feedback overlaps the planned crop. The design cannot claim purely cortical or feedback-free MI generalization. Any downgrade from original-input confirmation to operational derivative-cohort evaluation must be explicit before scores.
5. **Neural implementation and execution:** the common19 loader/trainer/adapter and exact frozen source checkpoints require complete executable review and authorized GPU execution. No matched-duration new-target result exists.
6. **Budget:** exact GPU runtime, peak memory and live price remain unmeasured. Paid deployment is not authorized by a planning estimate; optional extra40 fits remain disabled.
7. **Historical limitations:** original unarchived CSP audit provenance, original frozen-model source replay, target demeaning and full earlier mean-rank runtime identity remain unresolved. New numerical agreement does not repair their absence.
8. **Author/journal state:** preparing this work package neither withdraws nor replaces any manuscript. A new exclusive submission requires author review of actual completed evidence and confirmation of the current journal status; no false submission-ready declaration is issued.

## 7. Preservation and final delivery scope

The baseline audit reports that historical scientific outputs are unchanged. This independent review did not edit any historical result/model/contract or submitted-v1.1 file. The root's final preservation and delivery validator must still provide the complete final byte-level check and export/figure/package validation after all deliverables are generated. This report does not anticipate a future validator PASS or claim that a ZIP/PDF presently exists before it has been exported.

**Acceptance:** current saved numerical evidence, new retrospective source diagnostic, bounded metadata replay and synthetic statistical software pass their stated checks. **Scientific confirmation and submission readiness remain blocked.** The valid main story is developmental heterogeneity, failure-aware source-only selection auditing, and a falsifiable planned independent validation; an independent positive effect, SOTA performance, causal spectral-sharing mechanism or physiological validation cannot yet be written as a finding.

## 8. Subsequent real source-input software/data probe

The new common19 loader was exercised on all18 authenticated BNCI files after the diagnostic and document review. It extracted2,592 binary trials into three float32 arrays of shape[2592,19,320]; exact native-file, metadata and array hashes are in `evidence/core_source_input_probe.json`. Its measured CPU preprocessing elapsed24.06seconds, **not** GPU training time. No model fit or target recording/prediction was involved. This checks real source extraction/count/shape/finite-value guards, not physical device recalibration, full target adaptation, an independently designed filtering implementation or new neural efficacy. Live GPU runtime compatibility, complete target qualification and final source/inference publication gates remain unresolved.
