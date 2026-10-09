# Source-only model selection and limits of fixed spectral-sharing pipelines in cross-subject motor-imagery EEG decoding

**Ziyuan Zhu (朱子元)** · College of Artificial Intelligence Medicine, Chongqing Medical University, Chongqing, China · Correspondence: **zzy2630816871@gmail.com**

The current manuscript and submission materials are prepared for **PLOS ONE**. The completed Q1–Q16 results remain frozen. This editorial release changes the journal presentation and submission materials; it adds no model fitting, prediction inference or physiological experiment. Publication in a journal, acceptance and an archive DOI are not claimed.

## Current manuscript and submission files

- Current editorial branch: [`paper/plos-one-author-finalization-20261009`](https://github.com/jackzhu119/cross-subject-mi-eeg/tree/paper/plos-one-author-finalization-20261009).
- Publication tag: [`plos-one-submission-v1.1`](https://github.com/jackzhu119/cross-subject-mi-eeg/releases/tag/plos-one-submission-v1.1).
- Manuscript directory: [`research_runs/PLOS_ONE_SUBMISSION/`](research_runs/PLOS_ONE_SUBMISSION/).
- Delivery and preservation evidence: [`research_runs/PLOS_ONE_AUTHOR_FINAL_PUBLICATION_20261009/`](research_runs/PLOS_ONE_AUTHOR_FINAL_PUBLICATION_20261009/).

| Purpose | File |
|---|---|
| Complete PLOS ONE submission-material archive | [ZIP](research_runs/PLOS_ONE_SUBMISSION/PLOS_ONE_Submission_Package.zip) · [SHA-256](research_runs/PLOS_ONE_SUBMISSION/PLOS_ONE_Submission_Package.zip.sha256) |
| Main manuscript for upload | [DOCX](research_runs/PLOS_ONE_SUBMISSION/PLOS_ONE_Manuscript.docx) · [PDF for reading](research_runs/PLOS_ONE_SUBMISSION/PLOS_ONE_Manuscript_Review.pdf) · [Markdown source](research_runs/PLOS_ONE_SUBMISSION/PLOS_ONE_Manuscript.md) |
| Cover letter | [DOCX](research_runs/PLOS_ONE_SUBMISSION/PLOS_ONE_Cover_Letter.docx) · [PDF](research_runs/PLOS_ONE_SUBMISSION/PLOS_ONE_Cover_Letter.pdf) |
| Six standalone figures | [TIFF files](research_runs/PLOS_ONE_SUBMISSION/Figures/) · [Figure quality report](research_runs/PLOS_ONE_SUBMISSION/Figure_Quality_Report.md) |
| Supporting information | [S1 Appendix PDF](research_runs/PLOS_ONE_SUBMISSION/SupportingInformation/S1_Appendix.pdf) · [S1 Appendix DOCX](research_runs/PLOS_ONE_SUBMISSION/SupportingInformation/S1_Appendix.docx) · [S1 Data ZIP](research_runs/PLOS_ONE_SUBMISSION/SupportingInformation/S1_Data.zip) |
| Submission metadata | [Title and keywords](research_runs/PLOS_ONE_SUBMISSION/PLOS_ONE_Title_and_Keywords.md) · [Abstract](research_runs/PLOS_ONE_SUBMISSION/PLOS_ONE_Abstract.txt) · [Submission fields](research_runs/PLOS_ONE_SUBMISSION/PLOS_ONE_Submission_Fields.md) · [Data availability](research_runs/PLOS_ONE_SUBMISSION/PLOS_ONE_Data_Availability.md) |
| Author checklist and fees | [中文投稿检查表](research_runs/PLOS_ONE_SUBMISSION/PLOS_ONE_Submission_Checklist_zh.md) · [费用与资助说明](research_runs/PLOS_ONE_SUBMISSION/PLOS_ONE_APC_Assistance_Guide_zh.md) |
| Evidence and integrity | [Numerical validation](research_runs/PLOS_ONE_SUBMISSION/Numerical_Validation_Report.md) · [Checksums](research_runs/PLOS_ONE_SUBMISSION/MANIFEST.sha256) · [Package guide](research_runs/PLOS_ONE_SUBMISSION/README.md) |

The package guide identifies which files to upload separately. The main review PDF is a reading copy; PLOS ONE accepts the Word manuscript. Funding and competing-interest statements are supplied through the submission fields. The author has approved the current materials, supplied ORCID 0009-0005-1153-4926, confirmed sole authorship and authorized the stated original-output licenses. The public ORCID given/family-name fields require correction to Ziyuan/Zhu; the author must link the iD and check the portal-generated PDF and final declarations before submitting. No submission is performed by this repository.

## Frozen scientific identities

- Q15 scientific code: [`271af288a2f3863430ab80e3145c2dee9bd5571d`](https://github.com/jackzhu119/cross-subject-mi-eeg/commit/271af288a2f3863430ab80e3145c2dee9bd5571d).
- Q15 independently validated result publication: [`bc48b257eb44f412ad069f50d0f1a72a33c3c520`](https://github.com/jackzhu119/cross-subject-mi-eeg/commit/bc48b257eb44f412ad069f50d0f1a72a33c3c520).
- Q16 pre-power parameter freeze: [`050e01b028aaab8e3d745934b13b2d17e9bb0a7a`](https://github.com/jackzhu119/cross-subject-mi-eeg/commit/050e01b028aaab8e3d745934b13b2d17e9bb0a7a).
- Q16 completed outputs and independent checks: [`research_runs/Q16-P001-BNCI-20261006/`](research_runs/Q16-P001-BNCI-20261006/).
- Frozen manuscript number authority: [`paper_numbers.json`](research_runs/PAPER_FINAL_20261006/paper_numbers.json).
- Preserved scientific tables and audit inputs: [`research_runs/PAPER_FINAL_20261006/`](research_runs/PAPER_FINAL_20261006/). This is a scientific-source collection, not a second submission package.

Q15 used 15 original source fits: 14 neural fits and one shallow fit. Migration added zero source fits, and target fitting remained zero. The source-duration validation groups contain 2/2/2/3 participants with equal fold weighting; prospective grouping sensitivity was not evaluated. Historical Git commits and immutable tags retain earlier editorial versions without presenting them as the current submission.

## Results and interpretation

Balanced accuracy (BA) averages class recalls within each person. Cohort means weight participants equally; confidence intervals resample participants. The broad/shared comparisons are complete frozen-pipeline contrasts with unequal source-selected durations, rather than isolated causal tests of spectral sharing.

| Cohort | Participants / trials | Broad BA | Shared BA | Shared − broad (pp), 95% interval |
|---|---:|---:|---:|---|
| PhysioNet | 109 / 4,918 | 61.81% | 62.39% | +0.573 [−0.097, +1.242] |
| Cho2017 | 52 / 10,520 | 59.82% | 58.31% | −1.513 [−2.249, −0.804] |
| Lee2019 offline-training runs | 54 / 10,800 | 65.51% | 65.72% | +0.204 [−0.515, +0.969] |

Cho2017 retains the adverse shared-input result. Lee2019 remains uncertain, without an equivalence conclusion; PhysioNet superiority is not established. No pooled cross-provider score or independently verified participant-identity nonoverlap is asserted.

The nine-person internal mean-rank development gain remains exploratory: 33.72% → 42.67% BA, with S3/S8 supplying 87.57% of the aggregate gain. The matched-runtime fixed-duration mean gain did not represent typical-person improvement: four participants improved and five worsened. Corrected robustness gains were not established.

The BNCI-only physiological characterization retained 18 source files, nine participants, two sessions and all 5,184 four-class trials; 2,592 hand trials supplied the hand summaries. Signed mean laterality was −0.250 dB in mu and −0.168 dB in beta. These post-decoder-outcome, baseline-relative sensor descriptions and six n=9 correlations have no physiological p-values, causal decoder attribution or external physiological replication. Negative signed laterality does not alone establish absolute contralateral ERD.

Zero calibration means no target-dependent parameter fitting or target-based model selection. Event/class metadata support documented eligibility and mapping; ground-truth labels supply scoring. The separate physiological analysis uses class metadata without decoder feedback. This work establishes no universal label-free operation, online/real-time control, clinical utility, mechanistic biomarker or superiority over existing domain-generalization methods.

## Reproduction and original data

Raw EEG is **not included** in the repository or submission package. Obtain it from the original providers and comply with their terms:

- [BCI Competition IV dataset 2a / BNCI](https://bnci-horizon-2020.eu/database/data-sets) and [original task description](https://www.bbci.de/competition/iv/desc_2a.pdf).
- [PhysioNet EEG Motor Movement/Imagery v1.0.0](https://physionet.org/content/eegmmidb/1.0.0/).
- [Cho2017 original dataset](https://doi.org/10.5524/100295).
- [Lee2019 / OpenBMI original dataset](https://doi.org/10.5524/100542).

[Release reproducibility guide](research_runs/PLOS_ONE_SUBMISSION/REPRODUCIBILITY.md) and [S1 Appendix](research_runs/PLOS_ONE_SUBMISSION/SupportingInformation/S1_Appendix.pdf) describe the frozen preprocessing and model identities. [S1 Data](research_runs/PLOS_ONE_SUBMISSION/SupportingInformation/S1_Data.zip) contains saved derived tables, predictions and audit inputs, with byte-level provenance. Reading and checking the manuscript numbers requires no GPU, cloud credentials or model training.

The following command checks the existing editorial artifacts against their frozen inputs. It does not fit models, recompute predictions or run physiological experiments:

```bash
python research_runs/PLOS_ONE_SUBMISSION/validate_plos_package.py
```

Install the editorial dependencies listed in [`requirements-editorial.txt`](research_runs/PLOS_ONE_SUBMISSION/requirements-editorial.txt) if necessary. The package checksums and publication receipts bind exact delivered bytes; re-exporting a document requires a new layout review and checksum record.

## Author and disclosure information

The author reports no research funding, no competing interests and no additional acknowledgments. The statement that neither approval nor exemption was required for this secondary analysis is the author's confirmation; no institutional determination or committee identifier is invented. Original collection approvals are distinct from the requirements for this secondary analysis.

ChatGPT (GPT-6, author reported) and OpenAI Codex assistance are disclosed according to their actual recorded scope. The author reports personal checking and revision of the scientific content. The current author checklist records approval, sole-author contribution roles, original-output licensing, self-payment of the publication charge if accepted and no opposed reviewers. No formal secondary-analysis ethics document exists. The official human-data form has been prepared against Methods lines 470–487; portal checks and any journal-requested explanation remain personal author actions.


## Recorded research access and permissions

Historical GitHub/cloud research receipts document BNCI2014_001 access during 21 September–6 October 2026, PhysioNet access on 25 September 2026, and Cho2017/Lee2019 raw auditing and external evaluation during 3–5 October 2026. These are retained-record access intervals, not proven first-ever downloads or dates inferred from backups. See the [audited evidence](research_runs/PLOS_ONE_SUBMISSION/evidence/research_access_dates.md) and [completed official human-data checklist](research_runs/PLOS_ONE_SUBMISSION/AuthorForms/PLOS_Human_Participants_Checklist_2026_completed.pdf).

Original author-owned software is licensed under [MIT](LICENSE); original author-owned manuscript and derived outputs use [CC BY 4.0](LICENSE-DATA.md). [Scope and exclusions](LICENSING.md) preserve original third-party terms for raw EEG, incorporated software, fonts, provider materials and official forms. No third-party rights are re-granted.
