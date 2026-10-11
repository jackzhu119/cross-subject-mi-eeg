# Scientific integrity and provenance of the internal revision candidate

Candidate branch: `paper/plos-one-postsubmission-review-20261010`.

Candidate directory: `research_runs/PLOS_ONE_POSTSUBMISSION_REVIEW_20261010/`.

Prepared 11 October 2026 for Ziyuan Zhu's review. The author reports that PLOS ONE manuscript **PONE-D-26-50597** was submitted on **9 October 2026**. An authenticated journal portal was not accessed. This candidate has not been submitted, approved by the author, or accepted for replacement by the journal.

## Immutable baselines

| Record | Pinned identity / scope |
|---|---|
| Submitted package | Tag `plos-one-submission-v1.1`; artifact commit `1d4b0d1ef4d8bef19dd077a07e1a4ecdb1bde336` |
| Latest inspected baseline | `d9a11926076bd348696f6e690078955921dac3f8` |
| Submitted ZIP SHA-256 | `1b4a9f6d03bb8cfefc1c624b7ea96118cb0d5e4fd2d245ed9810004850779320` |
| Scientific manuscript source | `0c7146895dc46850e4fe7db38bd69d9aea2b41c3` |
| Q15 scientific execution code | `271af288a2f3863430ab80e3145c2dee9bd5571d` |
| Q15 independently validated frozen results | `bc48b257eb44f412ad069f50d0f1a72a33c3c520` |
| Q16 parameter freeze | `050e01b028aaab8e3d745934b13b2d17e9bb0a7a` |

The evidence manifests are `evidence/submitted_package_preservation.json` and `evidence/source_protection_baseline.json`. A direct read-only byte check during this review found **all 16,417 listed scientific files and all 73 listed submitted-package files unchanged**. All six main TIFFs and six SVG figure sources match their submitted-package counterparts. Every one of the original **68 S1 Data archive members** remains present and byte-identical; 66 are original scientific members and two are the original manifest and README. Candidate audit additions are separately named. These specific byte checks do not certify other unlisted files, prove all physical acquisition assumptions, or replace final document/package validation.

Original Q1–Q16 results, predictions, fitted models, training/analysis contracts, independent validations, paper numbers, manifests and hashes are protected. No scientific data were edited to increase significance or narrative appeal. The original main and supplementary numerical tables retain their frozen numerical content; titles and semantic labels may change editorially. The original v1.1 directory and tag are not overwritten.

## Scope of work actually performed

This revision performs source/literature review, saved-prediction aggregation, prose/caption/reference editing, candidate export and delivery validation. It performs **zero new model fits, zero new checkpoint-inference rows, zero new physiological experiments and zero target-statistic transformation fits**. No raw EEG or model object was loaded for the new CSP editorial audit. The actual frozen 9,365-byte CSP model was authenticated by byte hash and public readback, not deserialized or executed.

The supplied report **describes** nine new source-only CSP fits and target-input centering. Those actions are not actions executed in this revision and are not authenticated merely because the report names them. “No new fitting in this revision” must not be confused with “the report's proposed/new LOSO assessment requires no fitting.” A newly executed nine-fold source LOSO would involve new source models and must be reported separately from the original primary 15 source fits and zero target fits.

No paid GPU was started, no EEGNet was retrained, no hyperparameter or schedule was reselected, no external prediction comparison was rerun, no equivalence margin/test was added, and no physiology mechanism analysis was introduced. No other paper repository was modified.

## New report provenance and authority

Both reports were received from the author on 11 October 2026 and read completely. Their stated report date is 10 October 2026.

| Supplied document | Bytes | SHA-256 | Authority boundary |
|---|---:|---|---|
| `Q15_CSP崩溃_验证报告.md` | 5,596 | `ed7d49e6ae6c33590b89646621751dd951d725d951939ac9ee8cece957dc6b27` | No named author, new run ID, source scoring code/hash, fold manifests/predictions or centering execution parameters accompany the report; its named diagnostic image is not supplied. |
| `PLOS_ONE_投稿前评审报告.md` | 18,285 | See `evidence/author_supplied_reports/receipt.json` and `evidence/new_review_matrix.json` | Author-supplied technical review, not an authenticated PLOS editorial decision. Reviewer identity and whether it was automated are not established. Its literature table explicitly relies on search metadata, requiring primary-paper protocol verification. |

Copies and receipt are retained under `evidence/author_supplied_reports/`. Earlier audit files correctly stated the reports were missing at their own review time. `evidence/new_report_csp_review.json/.md` and `new_review_matrix.json/.md` supersede that availability status; they do not erase the earlier chronology or authenticate new report-only runs.

The review's pre-submission language is not adopted: this paper has already been submitted according to the author. Its suggested fixed-20-epoch external “inference-only” comparison is not implementable from the declared 14/19-epoch final weights. No matched final pair is fabricated, and the user-authorized editorial route is followed.

## CSP evidence hierarchy

1. **Original frozen external outputs, independently verified.** Primary CSP person-mean balanced accuracies remain 51.99% and 52.77%. Trial-pooled left shares, probability medians and confusion matrices are reconstructed from authenticated stored outputs, with pooling distinguished from the primary participant endpoint. The original validation artifact map covers 52 source-bound and 221 external-bound files, whose hashes still agree.
2. **Newly presented post hoc descriptions.** Table S5 and participant confusion records show severe class asymmetry. These add descriptive statistics from existing predictions; they do not add model performance experiments, confirmatory tests, calibrated probability claims or target-selected changes.
3. **Report-reported source resubstitution and source refitting.** The 63.04% resubstitution and 61.65% new nine-fold scores lack the required archived prediction/fold/execution provenance. They remain unverified and are not entered into scientific Results as authenticated evidence. Historical earlier binary CSP protocols have different inputs and cannot supply those missing results.
4. **Report-reported target centering.** The 52.39%/54.18% scores lack code, grouping, fitted transform/threshold parameters and output hashes. Even unlabelled target-input centering changes the target-information budget. It cannot replace the frozen no-target-adaptation result and cannot be treated as a deployment improvement chosen after seeing outcomes.
5. **Label-complement arithmetic.** Exhaustive binary complement gives `BA_complement = 1 − BA_original`; Cho weighting must be stated. The report's Lee47.22 discrepancy is not an error in the submitted primary endpoint. No complement was selected or new predictions created. Choosing a label flip from target scores would be target-driven tuning.

Original raw-to-prediction validation demonstrates reproducibility of declared processing and archived states within documented limits. It does not prove absence of every implementation error, physical voltage calibration, Cho payload channel identity, original acquisition reference or hardware cue timing. Cross-cohort covariance/feature mismatch is plausible but not isolated; no unique device cause, physiological mechanism or intrinsic CSP inferiority is established.

## Protected interpretation and physiology boundaries

The development selection improvement remains exploratory, repeatedly benchmarked and concentrated in S3/S8. Positive fixed-duration means do not imply a typical-person benefit. Corrected robustness superiority is not established. The external paired effects remain +0.573pp on PhysioNet, −1.513pp on Cho2017 and +0.204pp on Lee2019 with their original intervals/tests. PhysioNet does not establish superiority; Lee does not establish equivalence. Complete-pipeline comparisons cannot isolate spectral sharing, unequal selected schedules, preprocessing or computation.

Q16 remains BNCI-only, nine-person, post-decoder-outcome, baseline-relative sensor analysis. Thousands of trials are not thousands of independent participants. One baseline Welch segment versus three overlapping task segments and the different decoder window remain disclosed. Signed negative laterality is not absolute contralateral ERD; scalp interpolation is not cortical localization; a descriptive association is not learned decoder attribution. All six correlations, negative means, artifact flags and participant counterexamples remain. No physiological p-values, external physiology, biomarker, causal mechanism, clinical utility or real-time validation is claimed.

## Literature chain and access limits

The candidate's 36-reference source preserves the original 28 and adds eight formal records. Metadata and protocol review are bound in `evidence/literature_prior_methods.json`, `literature_transfer_physiology.json` and `literature_plos_comparators.json`, with their Markdown companions. DOI/author/year/title records are distinguished from experimental protocol facts.

- Roots and Luo are architectural precedents with nonmatching split/participant protocols, not source-only external leaderboard baselines.
- Smedemark-Margulies is cited by its formal 2024 JNE metadata; its institutional postprint supplies RSVP protocol evidence. Direct publisher full text was blocked and is not claimed retrieved.
- Zhang's identity is confirmed by the supplied review. Accessible indexed original abstract supports target fine-tuning; detailed calibration counts and full protocol were not independently checked.
- BEETL's formal2022 proceedings record describes labelled target calibration. No DOI is invented.
- SMMTM's published source-normalization details and incompletely specified selection budget are reported without inferring leakage. RMETNet's target distribution alignment is distinguished from source-only evaluation.
- Sonntag's task, 26-person cohort and resting/within-person associations do not validate this paper's nine-person descriptor.

No external paper's headline accuracy was used to rank the present balanced-accuracy endpoints. No prior method was re-executed. Primary PDFs used for verification are not republished as author-owned CC BY material.

## Human authorship, ethics and journal actions

Author facts remain author-reported: Ziyuan Zhu is the sole human and corresponding author; no research funding, no competing interests and no additional human acknowledgments. No original EEG collection contribution is attributed to him. Public dataset-provider terms remain applicable; raw EEG is not in this package. Original software and author-owned manuscript/derived outputs retain their stated licenses; third-party materials retain their own terms.

The current secondary-analysis ethics statement records the author's assessment and absence of formal approval/exemption documentation; it does not create an institutional determination. Original collection review/consent is a separate matter. Actual new Methods lines must be reflected in the official checklist/export receipt. Genuine AI assistance is disclosed; no fabricated model version or claim of absent AI assistance is made.

The prior submitted-version approval does not approve this candidate automatically. Earlier ORCID evidence found reversed Given/Family fields; account correction and portal association are author actions, not operations performed here. `Editor_Inquiry_Draft.md` and cover materials are drafts. No email, portal replacement, withdrawal, resubmission, formal v1.2 release or DOI registration has been performed. If an important submitted fact/result error is later established, timely correction should be discussed honestly with the editor.

## Delivery and unresolved status

Final technical checks must cover:

- protected-file and submitted-package byte preservation;
- original table cells and frozen numerical statements;
- actual citation numbering, usage and source/export agreement;
- unchanged figure data, intended physical type size and caption matching;
- clean manuscript, appendix, cover and official-form PDF/DOCX integrity and current line bindings;
- original S1 archive members plus explicitly separated audit additions;
- final file inventory, checksums and complete package readback;
- independent review of interpretation and layout where actually recorded.

Use `evidence/revision_validation.json/.md`, current export/form receipts, final inventory/checksums and independent review records for the **actual** executed outcomes. A prior v1.1 visual or numerical pass is historical evidence and cannot certify newly exported pages. Missing checks must remain marked pending or failed; this document does not manufacture a pass count or claim an unfinished export passed.

Scientific acceptance status: **Further Scientific Work Required**. The internally generated files can be an author-review work product after final technical delivery validation; they are not a declaration that the report-only source and centering evidence is scientifically cleared. M1 needs recovery of already produced artifacts. The author must review/approve this candidate and ask PLOS ONE whether revised files can be accepted before any replacement is made.
