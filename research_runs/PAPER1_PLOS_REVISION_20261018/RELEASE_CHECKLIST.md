# Publication-release checklist

This is the release plan for the 18 October 2026 manuscript update, not a claim that a journal submission, tagged release, DOI or full model archive already exists.

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

Completed technical checks belong in the generated validation report. A box here is not a substitute for a machine receipt or personal author declaration.

## Author and portal actions

- [ ] **AUTHOR ACTION REQUIRED:** approve this new main manuscript, supplement and figures.
- [ ] **AUTHOR ACTION REQUIRED:** confirm real-time exclusive-submission status and the correct new-submission/update/invited-revision route.
- [ ] **AUTHOR ACTION REQUIRED:** check current ORCID name fields and link the iD.
- [ ] **AUTHOR ACTION REQUIRED:** check actual contributions, AI-use scope, ethical-use explanation and any required updated human-participants form. No formal secondary-analysis ethics determination is invented.
- [ ] **AUTHOR ACTION REQUIRED:** inspect the portal-generated PDF and accept the publisher's actual declarations/terms personally.

## Tag, archive and default branch

1. Validate and commit the isolated `paper/p1-plos-evidence-update-20261018` branch. Record the actual commit SHA in the delivery report.
2. Review the complete file inventory/checksums before creating an immutable manuscript tag. Use a new date/version-specific tag such as `paper1-plos-20261018-v1.0` only if it is absent and this release is approved; do not overwrite an old tag.
3. A GitHub Release may attach the validated manuscript package and identify the frozen result/code commits. A DOI-ready archive can then be prepared if desired. State a DOI only after it is issued and actually resolves.
4. Do not force-push or replace `main`, old submission tags or Q1–Q16 history to publish this update. The current branch can be linked prominently without rewriting them.
5. Do not mark the nine large model bundles publicly archived or R2 independently retrievable until a real archive and full retrieval receipt exist. Saved-prediction arithmetic remains reproducible from the public result ZIP meanwhile.

No external submission, payment, resource creation or Pod operation is performed by this release checklist.
