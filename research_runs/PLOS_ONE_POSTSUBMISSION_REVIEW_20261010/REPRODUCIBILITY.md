# Post-submission candidate: reproducibility and evidence scope

## Version separation

The author reports that manuscript PONE-D-26-50597 was submitted to PLOS ONE on 9 October 2026. This directory contains an internal revision candidate, not a submitted revision. The submitted `plos-one-submission-v1.1` tag and `research_runs/PLOS_ONE_SUBMISSION/` remain unchanged. Candidate changes are confined to `paper/plos-one-postsubmission-review-20261010` and the new candidate directory.

Author approval of the submitted version does not approve this candidate. No journal portal files were replaced, no editor was contacted and no new journal release or archive DOI was created in this task.

## Immutable scientific sources

| Evidence | Frozen identifier |
|---|---|
| Verified scientific manuscript snapshot | `0c7146895dc46850e4fe7db38bd69d9aea2b41c3` |
| Q15 scientific code | `271af288a2f3863430ab80e3145c2dee9bd5571d` |
| Q15 independent validation/result publication | `bc48b257eb44f412ad069f50d0f1a72a33c3c520` |
| Q16 pre-power parameter freeze | `050e01b028aaab8e3d745934b13b2d17e9bb0a7a` |
| Submitted package | `plos-one-submission-v1.1` |

`evidence/source_protection_baseline.json` identifies protected scientific files. `evidence/submitted_package_preservation.json` binds the original submitted package files. Current candidate validation must compare the corresponding bytes; historical pass counts alone are insufficient. Experiment files, manifests, contracts, saved predictions, weights and result hashes are not renamed or edited to accommodate the revised prose.

## Three distinct levels of evidence

1. **Original frozen experiment evidence.** Source/external validation receipts document their own declared raw replay, model-state and statistics coverage. Use the actual final validation file rather than treating an earlier pending receipt as a current failure. These checks do not prove a particular physiological mechanism or exclude every possible acquisition and implementation issue.
2. **New read-only audit of archived outputs.** CSP class proportions, stored probabilities and confusion matrices can be reconstructed from existing prediction tables without fitting a model or generating predictions. Trial-pooled summaries and the paper's equal-participant mean balanced accuracy are different estimands. Binary label-complement arithmetic is a post hoc check using recorded ground truth; it is not a deployment correction, a new inference result or a replacement of primary scores.
3. **Report-only follow-up claims.** A source resubstitution score is not held-out generalization. A new nine-fold source LOSO study would require nine new source fits, even if it used no target fitting. Post hoc centering based on target statistics would constitute target adaptation. Claims in a report require the associated inputs, partitions, models, predictions, parameter records and receipts before being treated as independently verified. No missing artifact is manufactured for this candidate.

The manuscript retains only diagnostic statements supported at the stated audit depth. New audit tables and provenance, where included in S1 Data, must be separately identified and must not overwrite original scientific members. Primary zero-calibration comparisons continue to use the frozen predictions and source-selected durations. No new target-based threshold, label sign, preprocessing rule or model-selection decision was made.

## Editorial export and validation

Document building is separate from scientific execution. The candidate export reads revised text, verified references and preserved scientific inputs to generate DOCX, review PDF and supplementary exports. Candidate acceptance checks must cover the new exports, citation numbering, table numbers, figure captions, Methods line references, archive contents and byte preservation. Run `python research_runs/PLOS_ONE_POSTSUBMISSION_REVIEW_20261010/validate_revision.py` from the repository root for candidate acceptance. The candidate's `evidence/revision_validation.json` and `.md` record the checks actually run and any unresolved issues; copied v1.1 reports are historical evidence, not candidate validation.

Re-exporting a PDF or ZIP can change its file hash without changing scientific data. Recheck each delivered file and regenerate its inventory/checksums after the last export. The Human Participants Checklist is an administrative form: its references must point to the candidate's actual Methods lines and be reviewed again if the portal produces different line numbers.

No new EEGNet/CSP fit, checkpoint inference, physiology power calculation or external-performance experiment was executed to prepare this candidate. This statement describes this revision task; it does not deny that a separately reported LOSO diagnostic would involve new source fitting if its records were later supplied.

## Scientific reproduction and data rights

Original experiment commands remain at the [immutable scientific reproduction guide](https://github.com/jackzhu119/cross-subject-mi-eeg/blob/0c7146895dc46850e4fe7db38bd69d9aea2b41c3/research_runs/PAPER_FINAL_20261006/reproducibility_readme.md). They were not executed in this editorial task. Any separate future reproduction must respect the original scientific freezes and provider conditions; do not overwrite archived outputs.

Raw EEG is excluded from this package. Acquisition links, dated access evidence and dataset terms are in `PLOS_ONE_Data_Availability.md`. Original author-owned software uses MIT; original author-owned manuscript material and derived outputs use CC BY 4.0. Third-party EEG, software, fonts, published articles and official forms retain their existing rights. Checksums verify artifact delivery and preservation, not journal acceptance or proof that every possible scientific error has been excluded.
