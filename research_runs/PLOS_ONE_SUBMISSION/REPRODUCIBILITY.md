# PLOS ONE editorial release reproducibility

Scientific experiments and frozen results are separate from manuscript export. This release does not retrain models, produce predictions, recalculate physiological powers or change statistical rules.

## Saved evidence

- Q15 validated result publication: `bc48b257eb44f412ad069f50d0f1a72a33c3c520`.
- Q15 scientific code: `271af288a2f3863430ab80e3145c2dee9bd5571d`.
- Q16 pre-power freeze: `050e01b028aaab8e3d745934b13b2d17e9bb0a7a`.
- Source manuscript and prior independent checks: `0c7146895dc46850e4fe7db38bd69d9aea2b41c3`.
- Active submission tag: `plos-one-submission-v1.0`.

The source scientific files retain their original paths and bytes. `evidence/source_protection_baseline.json` binds 16,417 of them. `SupportingInformation/S1_Data.zip` contains 66 frozen data/provenance files plus its README and manifest; raw EEG and model weights are excluded. Provider acquisition links and terms are in `PLOS_ONE_Data_Availability.md`.

## Read-only delivery validation

Clone the repository with its history, check out the release tag, install the editorial dependencies and run:

```bash
python research_runs/PLOS_ONE_SUBMISSION/validate_plos_package.py
```

The validator reads saved bytes, manuscript text, references, figure vectors, DOCX tables and PDFs. It also verifies the previous manuscript snapshot directly against immutable Git objects; obsolete submission files need not remain in the active tree. It writes a new local editorial validation report. It does not execute EEG/scientific experiments. Preserve the delivered reports before generating local replacements.

## Document export

`build_plos_package.py` reads the neutral scientific source under `research_runs/PAPER_FINAL_20261006/`, rearranges manuscript fields for PLOS ONE, writes DOCX/Markdown and copies frozen derived data. Existing verified figure bytes are retained. Use LibreOffice to export the main, cover letter and S1 Appendix DOCX files to PDF; name the main review PDF `PLOS_ONE_Manuscript_Review.pdf`. Recheck each new export; runtime and ZIP metadata may change file hashes without changing scientific content. After validation and visual inspection, run `package_submission.py` to make inventories, manifests and the full material archive.

Original raw/model replay instructions are preserved at [the immutable source revision](https://github.com/jackzhu119/cross-subject-mi-eeg/blob/0c7146895dc46850e4fe7db38bd69d9aea2b41c3/research_runs/PAPER_FINAL_20261006/reproducibility_readme.md). Those commands are for a separate scientific reproduction, and were not executed for this release. Do not overwrite frozen results or treat document preparation as new independent raw validation. See the original validation reports for their precise coverage and calibration limitations.

## Public delivery verification

SHA-256 and CRC checks validate archive delivery, not journal acceptance. The publication evidence outside this package records remote readback at the exact tagged artifact commit. Existing Git history and scientific tags are retained. No persistent archive DOI is claimed; licensing and any DOI deposit remain distinct author actions.
