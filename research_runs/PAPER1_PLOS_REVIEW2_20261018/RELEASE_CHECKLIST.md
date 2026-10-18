# Publication-release checklist

This is the release plan for the 18 October 2026 manuscript update. The original manuscript is author-reported as PONE-D-26-50597, submitted on 9 October 2026. This candidate has not been submitted or accepted for replacement by the journal; a new invitation, tagged release, DOI or complete public model archive is not inferred.

## Frozen scientific anchors

- Results: `040956085499ed788948de0d5a09cddd9eabca56`, `research_runs/ELIGIBLE_V3_RESULTS_20261018/`.
- Executed code content: `0539379578818b3d71f995192e5e8a81cf4d5aef`, with exact copies/locks in the result provenance.
- Original saved-result ZIP: 21,240,637 bytes; SHA256 `df8fdc4a43139acb4236ead749b74736a5bedaea6d8606c3bcc69234755fe02f`.
- Existing source, prediction, result, audit and freeze files stay unchanged. Preserve all null/adverse findings, fixed selectors and historical failures.

## Editorial release checks

- [x] New manuscript, supplement and figure captions agree with the current frozen experiment rather than the historical protocol draft.
- [x] All primary/secondary contrasts, denominators, confidence intervals, multiplicity and participant-level inference are retained and checked.
- [x] Numerical provenance and table/figure data are included; new descriptive summaries are identified as such.
- [x] References are cited, continuous and checked; author and third-party attribution are preserved.
- [x] Main DOCX has editable tables; figures and captions match numbering; PDF/DOCX exports open and layout has been inspected.
- [x] Each scientific supporting file is below 20 MB; compact S1 Data is separate from the >20 MB original archive.
- [x] Final delivery validation and SHA256 inventory describe the actual exported files.
- [x] No raw EEG, credentials or large neural checkpoint bundles are added to this editorial package.

The updated package passed 295 editorial delivery checks with zero failures, plus separate 448-check supplementary-inference and 602-check inventory reviews. Export and visual-review receipts bind the delivered artifacts. A checked box is not a substitute for personal author approval.

## Author and portal actions

- [ ] **AUTHOR ACTION REQUIRED:** approve this new main manuscript, supplement and figures.
- [ ] **AUTHOR ACTION REQUIRED:** confirm the actual portal state and permission/instructions for updating PONE-D-26-50597; do not create a concurrent duplicate submission.
- [ ] **AUTHOR ACTION REQUIRED:** check current ORCID name fields and link the iD.
- [ ] **AUTHOR ACTION REQUIRED:** check actual contributions, AI-use scope and the updated human-participants form. Current ethics text records the author's confirmation of the university research administration office's 17 October 2026 exemption covering BNCI/Yang/Dreyer under Article 32(1); the accompanying author statement is not an institutional-issued letter, and no identifier is invented.
- [ ] **AUTHOR ACTION REQUIRED:** inspect the portal-generated PDF and accept the publisher's actual declarations/terms personally.

## Tag, archive and default branch

1. Validate and commit the isolated `paper/p1-plos-review2-20261018` branch. Record the actual commit SHA in the delivery report.
2. Review the complete file inventory/checksums before creating an immutable manuscript tag. Use a new date/version-specific tag such as `paper1-plos-review2-20261018-v1.0` only if it is absent and this release is approved; do not overwrite an old tag.
3. A GitHub Release may attach the validated manuscript package and identify the frozen result/code commits. A DOI-ready archive can then be prepared if desired. State a DOI only after it is issued and actually resolves.
4. Do not force-push or replace `main`, old submission tags or Q1–Q16 history to publish this update. The current branch can be linked prominently without rewriting them.
5. Do not mark the nine large model bundles publicly archived or R2 independently retrievable until a real archive and full retrieval receipt exist. Saved-prediction arithmetic remains reproducible from the public result ZIP meanwhile.

No external submission, payment, resource creation or Pod operation is performed by this release checklist.
