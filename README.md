# Source-only model selection and limits of fixed spectral-sharing pipelines in cross-subject motor-imagery EEG decoding

**Ziyuan Zhu (朱子元)** · College of Artificial Intelligence Medicine, Chongqing Medical University, Chongqing, China · Correspondence: **zzy2630816871@gmail.com**

Updated **7 October 2026**. The completed decoder results and BNCI physiological characterization are preserved. The author approved the preceding scientific manuscript; this language-refined version is prepared for submission review. No journal submission, acceptance, clinical validation or archive DOI is claimed.

## Latest manuscript and frozen versions

- Paper branch: [`paper/zero-calibration-q16-20261006`](https://github.com/jackzhu119/cross-subject-mi-eeg/tree/paper/zero-calibration-q16-20261006).
- Paper archive: [`paper-v1.0.2`](https://github.com/jackzhu119/cross-subject-mi-eeg/releases/tag/paper-v1.0.2). This language-refined candidate retains the frozen results and prior author declarations; the revised wording requires an author read before journal submission.
- Manuscript directory: [`research_runs/PAPER_FINAL_20261006/`](https://github.com/jackzhu119/cross-subject-mi-eeg/tree/paper-v1.0.2/research_runs/PAPER_FINAL_20261006).
- Q15 scientific code: [`271af288a2f3863430ab80e3145c2dee9bd5571d`](https://github.com/jackzhu119/cross-subject-mi-eeg/commit/271af288a2f3863430ab80e3145c2dee9bd5571d).
- Q15 validated result publication: [`bc48b257eb44f412ad069f50d0f1a72a33c3c520`](https://github.com/jackzhu119/cross-subject-mi-eeg/commit/bc48b257eb44f412ad069f50d0f1a72a33c3c520).
- Q16 pre-power parameter freeze: [`050e01b028aaab8e3d745934b13b2d17e9bb0a7a`](https://github.com/jackzhu119/cross-subject-mi-eeg/commit/050e01b028aaab8e3d745934b13b2d17e9bb0a7a). Completed outputs and their hashes: [`Q16-P001-BNCI-20261006`](https://github.com/jackzhu119/cross-subject-mi-eeg/tree/paper-v1.0.2/research_runs/Q16-P001-BNCI-20261006).
- Artifact preservation evidence: [current publication receipts](https://github.com/jackzhu119/cross-subject-mi-eeg/tree/paper/zero-calibration-q16-20261006/research_runs/PAPER_FINAL_20261006-PUBLICATION). Each receipt applies to its exact immutable commit.

| Read / edit | File |
|---|---|
| Main manuscript | [PDF](https://github.com/jackzhu119/cross-subject-mi-eeg/blob/paper-v1.0.2/research_runs/PAPER_FINAL_20261006/manuscript_main_en.pdf) · [DOCX](https://github.com/jackzhu119/cross-subject-mi-eeg/blob/paper-v1.0.2/research_runs/PAPER_FINAL_20261006/manuscript_main_en.docx) |
| Supplement | [PDF](https://github.com/jackzhu119/cross-subject-mi-eeg/blob/paper-v1.0.2/research_runs/PAPER_FINAL_20261006/supplementary_materials.pdf) · [DOCX](https://github.com/jackzhu119/cross-subject-mi-eeg/blob/paper-v1.0.2/research_runs/PAPER_FINAL_20261006/supplementary_materials.docx) |
| Complete text and source | [Markdown](https://github.com/jackzhu119/cross-subject-mi-eeg/blob/paper-v1.0.2/research_runs/PAPER_FINAL_20261006/manuscript_en.md) · [TeX](https://github.com/jackzhu119/cross-subject-mi-eeg/blob/paper-v1.0.2/research_runs/PAPER_FINAL_20261006/manuscript.tex) |
| JNE submission files | [ZIP](https://github.com/jackzhu119/cross-subject-mi-eeg/blob/paper-v1.0.2/research_runs/PAPER_FINAL_20261006/JNE_submission_package.zip) · [Cover letter](https://github.com/jackzhu119/cross-subject-mi-eeg/blob/paper-v1.0.2/research_runs/PAPER_FINAL_20261006/cover_letter_JNE.pdf) |
| Contribution evidence | [中文贡献与证据](https://github.com/jackzhu119/cross-subject-mi-eeg/blob/paper-v1.0.2/research_runs/PAPER_FINAL_20261006/contribution_evidence_zh.md) |
| Complete archive | [ZIP](https://github.com/jackzhu119/cross-subject-mi-eeg/blob/paper-v1.0.2/research_runs/PAPER_FINAL_20261006/paper_bundle_zero_calibration_q16_20261006.zip) · [manifest](https://github.com/jackzhu119/cross-subject-mi-eeg/blob/paper-v1.0.2/research_runs/PAPER_FINAL_20261006/MANIFEST.sha256) |
| Reproduction and interpretation | [Reproducibility guide](https://github.com/jackzhu119/cross-subject-mi-eeg/blob/paper-v1.0.2/research_runs/PAPER_FINAL_20261006/reproducibility_readme.md) · [中文说明](https://github.com/jackzhu119/cross-subject-mi-eeg/blob/paper-v1.0.2/research_runs/PAPER_FINAL_20261006/%E4%B8%AD%E6%96%87%E8%AF%B4%E6%98%8E.md) |

## Results and interpretation

The following binary cohorts are evaluated separately. Balanced accuracy (BA) averages class recalls within each person; reported cohort means give each person equal weight, and the intervals resample people. These are complete frozen-pipeline contrasts with unequal source-selected durations, rather than isolated causal tests of sharing.

| Cohort | People / trials | Broad BA | Shared BA | Shared − broad (pp), 95% interval |
|---|---:|---:|---:|---|
| PhysioNet | 109 / 4,918 | 61.81% | 62.39% | +0.573 [−0.097, +1.242] |
| Cho2017 | 52 / 10,520 | 59.82% | 58.31% | −1.513 [−2.249, −0.804] |
| Lee2019 offline-training runs | 54 / 10,800 | 65.51% | 65.72% | +0.204 [−0.515, +0.969] |

Cho2017 retains the adverse shared-input result (two-cohort Holm p ≈ 0.000100). Lee2019 is uncertain (Holm p ≈ 0.604), without an equivalence conclusion; PhysioNet superiority is not established. No pooled cross-provider score or independently verified identity nonoverlap is asserted.

The internal nine-person mean-rank development gain remains exploratory: 33.72% → 42.67% BA, with S3/S8 supplying 87.57% of the aggregate gain. The matched-runtime fixed-duration mean gain did not represent typical-person improvement: four improved and five worsened. Corrected robustness gains were not established.

The BNCI-only physiological characterization retained 18 source files, nine people, two sessions and all 5,184 four-class trials; 2,592 hand trials supplied the hand summaries. Signed mean laterality was −0.250 dB in mu and −0.168 dB in beta. These post-decoder-outcome, baseline-relative sensor descriptions and six n=9 correlations have no physiological p-values, causal decoder attribution or external physiological replication. Negative signed laterality does not alone establish absolute contralateral ERD. Q16's BNCI component is complete; the proposed external physiological programme is not claimed complete.

## Information budget and verification

Zero calibration means **no target-dependent parameter fitting or target-based model selection**. Event/class metadata support documented eligibility and mapping; ground truth supplies scoring. The separate physiological analysis uses class metadata without decoder feedback. Fixed channel maps, reference operations and resampling are not target-fitted statistics. This does not establish universal label-free operation, calibrated physical voltage, online/real-time control or clinical utility.

Q15 used 15 original source fits (14 neural, one shallow), with zero new migration fits and zero target fits. The editorial revision and Q16 add no decoder fits or checkpoint inference. Source-duration validation groups contain 2/2/2/3 participants with equal fold weighting; grouping sensitivity was not evaluated prospectively.

The release contains saved-number audits, independent original scientific validators, current review bindings and layout reports. The editorial revision protected 16,417 scientific files and checked 261 displayed numeric cells against saved evidence. Raw/model scientific experiments were not rerun for manuscript editing. The TeX source is preserved; native compiler handlers were unavailable. The searchable PDFs are independently checked ReportLab exports.

## Reproduction and original data

Original EEG is **not included** in the repository or manuscript ZIP. Acquire it directly from the providers under their terms:

- [BCI Competition IV dataset 2a / BNCI](https://bnci-horizon-2020.eu/database/data-sets) and [original task description](https://www.bbci.de/competition/iv/desc_2a.pdf).
- [PhysioNet EEG Motor Movement/Imagery v1.0.0](https://physionet.org/content/eegmmidb/1.0.0/).
- [Cho2017 original dataset](https://doi.org/10.5524/100295).
- [Lee2019 / OpenBMI original dataset](https://doi.org/10.5524/100542).

Read the [reproducibility guide](https://github.com/jackzhu119/cross-subject-mi-eeg/blob/paper-v1.0.2/research_runs/PAPER_FINAL_20261006/reproducibility_readme.md) for frozen processing/model identities and validation coverage. Reading and checking manuscript numbers requires no GPU, R2 credentials or new training. Fresh document exports need their own review because container/rendering bytes may differ even when numeric results agree. Keep delivered receipts intact.

## Submission preparation

Funding, competing interests and the secondary-analysis ethics requirement reflect the author's confirmation: no funding, no competing interests, and neither approval nor exemption required for this secondary analysis. No committee decision or approval identifier is invented. The author confirms the college English wording. Official university sources confirm Jinyun Campus, Chongqing Medical University, No. 61 Daxuecheng Middle Road, Shapingba District, Chongqing 401331, China; the English street line is a translation.

The author confirmed sole authorship, personal checking/revision, final main/supplement/figure approval, data-term checks, Github-only publication history and no other-journal consideration. Journal of Neural Engineering is the confirmed target. ChatGPT (GPT-6) is author-reported; existing Codex code/figure/drafting uses are also disclosed. [Submission checklist](https://github.com/jackzhu119/cross-subject-mi-eeg/blob/paper-v1.0.2/research_runs/PAPER_FINAL_20261006/submission_checklist_zh.md) · [IOP AI disclosure](https://github.com/jackzhu119/cross-subject-mi-eeg/blob/paper-v1.0.2/research_runs/PAPER_FINAL_20261006/ai_disclosure_submission_draft.md). Actual submission requires the author's system declarations, original-reference verification, any required ORCID and final PDF check. No journal submission or DOI is claimed.

Historical experiment branches and results remain intact. Earlier drafts and development notes are historical records; the candidate paper and immutable publication receipts identify the current delivery.

The language refinement strengthens three empirical contributions: auditing source-only model selection, distinguishing aggregate gains from typical-participant outcomes, and retaining frozen adverse/uncertain external evidence. Class-recall diagnostics and separate computational/physiological evidence provide support. No new algorithm, cohort interaction, mechanistic biomarker or literature-wide priority claim is made. The prior `paper-v1.0` release remains intact.
