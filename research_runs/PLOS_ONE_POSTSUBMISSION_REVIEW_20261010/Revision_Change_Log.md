# Internal revision change log

Date: 11 October 2026. Candidate branch: `paper/plos-one-postsubmission-review-20261010`.

This is a candidate revision of the author-reported PLOS ONE submission **PONE-D-26-50597**, submitted 9 October 2026. The preserved `plos-one-submission-v1.1` package remains the record of the submitted files. No journal file was replaced; no email, withdrawal, resubmission or formal release was performed. The revised title below is a proposed candidate title, not a change made in the journal portal.

## A. Editorial, literature and presentation changes

1. **Title and comparison estimand.** Candidate title is *Source-only model selection and external evaluation of complete spectral-sharing pipelines in motor-imagery EEG decoding*. The abstract, introduction, methods interpretation, discussion, conclusion and cover draft consistently describe complete source-selected pipelines. They retain broad/shared 18/17 epochs for PhysioNet and 14/19 for Cho2017/Lee2019, and explicitly limit attribution because views, filtering, BatchNorm exposure and computation also differ.
2. **Abstract.** The source abstract is 206 words. It retains development balanced accuracy 33.72%→42.67%, S3/S8 contribution 87.57%, and the three external paired mean effects with person-bootstrap intervals. Abstract p-values are omitted consistently across cohorts; unchanged original tests remain in the main text. Physiology receives a limited descriptive statement.
3. **Contribution hierarchy.** Introduction ends with two scientific aims: selection reliability/participant heterogeneity and complete frozen-pipeline external transfer. Reproducibility is a transparency contribution; post-outcome BNCI physiology is auxiliary. Neither rank selection nor multibranch EEG is claimed as a first-ever algorithm.
4. **Semantic narrative and archive mapping.** Main-text project IDs have been replaced where unnecessary; supplementary Table S6 maps study names to original identifiers and existing file roots. Historical scientific files and scripts have not been renamed. Electrode labels remain intact.
5. **Literature and protocol context.** References increased from 28 to 36 by adding eight verified formal records listed below. Related Work and Discussion distinguish pooled-window, within-person, same-cohort session, subject-disjoint and external-cohort evaluation, and target fine-tuning/calibration or distribution matching. No numerical SOTA leaderboard was added. The nine requested studies were assessed; the accuracy-cost paper was evaluated but omitted as a main-text comparator.
6. **Equations and fixed-duration interpretation.** Explicit equation labels/references were added for selected epoch, shared prediction and balanced accuracy. Twenty epochs is described as a fixed development follow-up, not an optimum or an externally selected deployment recommendation. Original estimator equations and outcomes are unchanged.
7. **Figures and physiology.** Fig 6 and Fig S1 captions explain fixed scale and existing redundant marker/numeric encoding. Main TIFFs and SVG sources are byte-identical to v1.1; all graphical data, axes, colour scales and ±6-dB/±20-pp ranges are preserved. Physiology remains BNCI-only, nine-person, sensor-level, baseline-relative, post-outcome and nonmechanistic.
8. **Submitted-status materials.** Candidate README, cover draft, field/checklist and provenance documents distinguish the already submitted v1.1 from this internally reviewed candidate. New candidate approval is pending. Honest AI assistance, author-assessed ethics, sole-human contributions, funding/conflicts and raw-data redistribution limits are retained. The official human-participants form must be rebound to actual new Methods lines.
9. **Delivery structure.** Candidate structured source, clean exports, change diff, reference formats, issue matrix, provenance and delivery validation are maintained together in the new directory. The final validator and export receipts, rather than inherited historical pass records, establish current artifact readiness.

### Added formal references

| Candidate number | Reference | Reason and boundary |
|---|---|---|
| 23 | Roots, Muhammad and Muhammad (2020), *Computers*, “Fusion Convolutional Neural Network for Cross-Subject EEG Motor Imagery Classification,” DOI `10.3390/computers9030072` | Multibranch precedent. Original Methods uses pooled-window random splitting, so not treated as a matched held-out-person external comparator. |
| 24 | Luo et al. (2023), *BioData Mining*, “Overlapping filter bank convolutional neural network for multisubject multicategory motor imagery brain-computer interface,” DOI `10.1186/s13040-023-00336-y` | Independently trained overlapping-band branches and multisubject/session context; formal seven-author metadata used. |
| 25 | Smedemark-Margulies et al. (2024), *Journal of Neural Engineering*, “Improving subject transfer in EEG classification with divergence estimation,” DOI `10.1088/1741-2552/ad9777` | Formal journal title/year supersedes 2023 preprint shorthand. RSVP transfer/selection context, not motor imagery. Institutional postprint examined; direct publisher full text unavailable. This journal name is a bibliographic fact, not residual JNE submission targeting. |
| 26 | Zhang et al. (2021), *Neural Networks*, “Adaptive transfer learning for EEG motor imagery classification with deep Convolutional Neural Network,” DOI `10.1016/j.neunet.2020.12.013` | Requested identity confirmed from supplied review. Indexed original abstract supports target-subject fine-tuning; detailed calibration budget was not independently verified. |
| 27 | Wei et al. (2022), *PMLR* 176:205–219, “2021 BEETL Competition: Advancing Transfer Learning for Subject Independence and Heterogenous EEG Data Sets” | Cross-dataset context with labelled target calibration. Canonical publisher URL used; no DOI invented. |
| 28 | Cao et al. (2025), *PLOS ONE*, SMMTM, DOI `10.1371/journal.pone.0333805` | Learned multiscale branches and within-dataset LOSO context; incomplete reported validation detail is neither proof of leakage nor a certificate of a matched source-only budget. |
| 29 | Zhao et al. (2026), *PLOS ONE*, RMETNet, DOI `10.1371/journal.pone.0347671` | Source–target MMD/Riemannian alignment separates target-adapted evaluation from frozen source-only transfer; formal ten-author record used. |
| 30 | Sonntag et al. (2025), *Frontiers in Human Neuroscience*, “Neurophysiological predictors of deep learning based unilateral upper limb motor imagery classification,” DOI `10.3389/fnhum.2025.1617748` | Resting spectral associations in a different task/26-person within-person design; no validation of this paper's nine-person post-outcome mechanism. |

The original 28 references remain; later reference numbers move because of first-appearance ordering. Citation-number changes are editorial, not changes to source publications or scientific evidence. Bibliographic records and retrieval limits are in `evidence/literature_*.json/.md`.

## B. Added descriptive calculations from already saved predictions

The following are newly presented **post hoc saved-output summaries**, not new EEG fits, model predictions, statistical tests or zero-calibration performance improvements:

- Participant and trial-pooled CSP confusion counts, explicitly separated from equally weighted participant balanced accuracy.
- Trial-pooled predicted-left shares: Cho2017 **92.0722433460%**, Lee2019 **83.2129629630%**.
- Pooled medians of originally saved `p(left)`: **0.669354232975** and **0.632938736955**. These are not probability-calibration estimates.
- Supplemental Table S5 preserves both person-mean and pooled balanced accuracy, exposing the effect of unequal Cho trial counts.
- Binary prediction-complement arithmetic is disclosed only as a post hoc descriptive identity. No complement was selected or saved as a new primary predictor.
- The read-only evidence also records an explicitly defined near-threshold probability summary; no causal or calibrated-confidence claim is drawn from it.

Every original S1 Data member remains byte-identical. Five additions live under `postsubmission_diagnostics/`: `m1_csp_audit.json`, `new_report_csp_review.json`, `new_report_csp_per_person_confusion.csv`, `audit_archived_csp_outputs.py`, and `README.txt`. These additional audit members have a separate descriptive role and do not replace original results or the original archive manifest.

Methods, external CSP Results, Discussion and S1 Appendix S11 describe both what the audit establishes and what it cannot establish. Recorded mappings and successful historical replay do not prove all adapter assumptions or physical measurement calibration correct. Covariance/feature mismatch remains plausible, not demonstrated as a unique mechanism or a universal CSP failure.

## C. Report claims needing additional evidence or reconciliation

No important error in the submitted primary endpoints has been established by this revision audit. No primary effect, confidence interval, p-value, participant/trial count, selected epoch or physiology descriptor has been changed to improve the narrative. The following supplied-report assertions are **not upgraded into verified scientific results**:

1. Source training balanced accuracy **63.04%** requires source predictions/sample IDs and model/raw/epoch/scoring provenance. Even if authenticated it is resubstitution, not held-out generalization.
2. New source LOSO mean **61.65%** requires nine fold predictions, source exclusions, model manifests and runtime/code/hash records. Such an evaluation entails nine additional source fits, outside the original primary fit count; historical Q14/P-stage results cannot authenticate it.
3. New mean-centering scores **52.39% / 54.18%** require the exact transform, grouping, parameters, target information accessed, timing and output provenance. Target-input centering is target adaptation even without target labels; it cannot replace the frozen no-target-adaptation endpoint.
4. Report label-flip **47.22%** for Lee does not equal the complement of the authenticated originals, which rounds to **47.23%**. Cho **48.02%** is compatible with pooled-trial weighting, whereas the equal-person complement rounds to **48.01%**. This is a discrepancy in the supplementary report/its unspecified inputs, **not a mistake in the submitted primary balanced accuracy**.
5. The report's broad “implementation problems excluded” / cross-device explanation is narrowed. No physical error or unique device mechanism has been proved; lack of a detected mismatch is not proof that every possible error is absent.

Recover already produced diagnostic artifacts before deciding whether any report-only evidence can enter a future scientific revision. This task did not rerun those experiments. If later evidence establishes an important error in the submitted paper, the author should promptly and accurately inform PLOS ONE rather than wait for routine revision. No such communication has been sent.

## Frozen results explicitly retained

- Mean-rank development gain is exploratory and concentrated; S3/S8 contribute **87.57%**.
- Fixed-duration mean improvement does not imply a typical-person improvement; no corrected robustness gain is established.
- PhysioNet **+0.573 pp**, interval **[−0.097,+1.242]**, does not establish superiority.
- Cho2017 **−1.513 pp**, interval **[−2.249,−0.804]**, remains the adverse complete-pipeline contrast.
- Lee2019 **+0.204 pp**, interval **[−0.515,+0.969]**, remains uncertain and does not establish equivalence.
- Q16 negative signed laterality, all nine participants and all six descriptive correlations remain; no causal mechanism, clinical utility or prospective/online validation is claimed.

## Completion boundary

**Further Scientific Work Required.** The files are an author-review candidate, conditional on actual final delivery validation. M1's verified original-output component is strengthened; its source-refit and target-centering claims remain unverified. The author must approve this new candidate and obtain journal permission before replacing submitted files. `Editor_Inquiry_Draft.md` and the cover materials are drafts only. No formal v1.2 release is created.
