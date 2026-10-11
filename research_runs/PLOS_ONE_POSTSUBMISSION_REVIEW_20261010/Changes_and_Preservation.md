# Post-submission revision changes and preservation

## Baseline and scope

The author reports that PLOS ONE manuscript PONE-D-26-50597 was submitted on 9 October 2026. The revision candidate is prepared on `paper/plos-one-postsubmission-review-20261010` in `research_runs/PLOS_ONE_POSTSUBMISSION_REVIEW_20261010/`. The submitted package remains at `research_runs/PLOS_ONE_SUBMISSION/` and the `plos-one-submission-v1.1` tag. Neither is replaced. Earlier administrative facts remain in history; candidate materials reflect the later author-reported submission.

The scientific baseline is snapshot `0c7146895dc46850e4fe7db38bd69d9aea2b41c3`, Q15 result publication `bc48b257eb44f412ad069f50d0f1a72a33c3c520` and Q16 parameter freeze `050e01b028aaab8e3d745934b13b2d17e9bb0a7a`. Preservation is checked against recorded file hashes, not inferred from unchanged headline numbers.

## A — Editorial clarification, literature and format

- Express broad/shared comparisons consistently as complete source-selected pipelines, including their unequal selected durations, view count, preprocessing, BatchNorm exposure and compute. Do not attribute the adverse Cho result to spectral sharing in isolation or call nonsignificance equivalence.
- Organize the Introduction around source-only selection reliability and external boundaries of the frozen pipelines. Reproducibility is a transparency contribution, not a newly invented algorithm. Mean-rank development findings remain exploratory.
- Replace unnecessary internal experiment IDs in the narrative with semantic study names while retaining mappings and historical paths in supplementary traceability. Electrode labels that resemble internal IDs are not removed.
- Revise the abstract, related work, terminology, captions and equation navigation without changing original scientific values. Compare target-data budgets and evaluation protocols rather than ranking unlike balanced-accuracy and accuracy scores.
- Retain Q16 as a post-outcome, BNCI-only nine-participant sensor-level baseline-relative description. It is not causal physiology, a decoder mechanism test, cortical localization or external physiological replication.
- Update candidate status, author materials, cover draft and editor inquiry. Previous approval applies to the submitted version; new candidate approval remains an author action.

These changes require current candidate export, citation and layout checks. Old v1.1 pass counts do not certify the new files.

## B — Added archived-output diagnostics

Only diagnostics reconstructible from original saved outputs and their provenance may be included. CSP prediction asymmetry, stored-probability summaries and confusion matrices are post hoc descriptive diagnostics. The paper's primary balanced accuracy is an equal-participant mean; a trial-pooled class proportion is separately identified. Binary label-complement arithmetic uses saved ground truth for scoring and is not a selected deployment correction.

New diagnostic evidence, if added to S1 Data, is labeled separately and leaves original scientific archive members intact. Neither target statistics nor outcomes are used to change frozen predictions, choose a model or improve the primary zero-calibration comparison. Diagnostic summaries do not establish the sole cause of limited transfer or prove that every possible mapping/acquisition/implementation error is absent.

## C — Potential substantive claims requiring additional records

The supplied CSP report mentions source resubstitution BA 63.04%, new nine-fold source LOSO BA 61.65% and post hoc mean-centering results. These are scientifically different from the original external model scores. A new LOSO diagnostic entails new source fitting; resubstitution is not independent generalization; a target-statistic centering intervention would be target adaptation. Without the corresponding run artifacts, these claims cannot be represented as independently validated results in the candidate.

A discrepancy between a report-level diagnostic and frozen-output arithmetic must be recorded with its estimand and provenance. It does not automatically show that the submitted primary score is wrong. If later evidence establishes an important submitted factual or method error, the author should promptly notify the editor with its specific consequences, rather than wait for a routine wording revision. No submitted primary result is changed to reconcile an unverified report.

## Protected content and exclusions

No original p value, confidence interval, participant/trial/epoch count, selected duration, physiology descriptor, saved prediction, model weight, scientific manifest, contract or frozen result hash is edited. Adverse and null findings remain visible: concentrated development gains, no corrected robustness benefit, uncertain PhysioNet/Lee results and the adverse Cho complete-pipeline result.

This revision task performs no new model fitting, prediction inference or EEG physiology experiment. That statement describes this task and does not deny the fitting required by any separately executed new source LOSO study. No paid GPU is started. The second paper repository is outside scope.

## Review and delivery boundary

`Revision_Change_Log.md`, `Revision_Issue_Matrix.md`, `Revision_Integrity_and_Provenance.md`, `Revision_Changes_Diff.html`, clean exports and `evidence/revision_validation.json` / `.md` must be read together. Use `validate_revision.py` for this candidate, not the copied v1.1 validator. Final readiness depends on checks actually completed and explicit unresolved issues. The candidate is not automatically sent to the journal, and its publication on a branch does not mean editorial permission or acceptance. No v1.2 Release or new DOI is created. `Editor_Inquiry_Draft.md` and the cover letter remain author-review drafts.
