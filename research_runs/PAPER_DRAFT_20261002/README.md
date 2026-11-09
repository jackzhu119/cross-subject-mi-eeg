# Paper author-review bundle — 2 October 2026

English working manuscript with a Chinese companion, based on completed research before Q15. No new model fit, EEG preprocessing, checkpoint inference, publication, submission, or GitHub push was performed.

Start with `manuscript_en.pdf` for reading or `manuscript_en.docx` for editing. `中文说明.md` explains the claims and limitations in Chinese. `manuscript_en.md` contains the same prose, tables, and figure captions. `manuscript_content.json` is the shared document content used by the exporters.

The manuscript has approximately 5,000 English prose words, four figures, seven tables, and eleven source-verified references. The complete inventory contains 61 Q4–Q14 condition records and 34 early binary QC endpoints; reuse, n=1 diagnostics, calibration, target populations, validation depth, failures, and unrun branches are identified explicitly. Row counts are not counts of independent replications or cumulative model fits.

## Evidence and interpretation

GitHub main was checked at `adb2d406b4300e2c8e4d5112969291c0331f3ed5`. The local checkout and each figure/table source are identified in `evidence/source_snapshot.json`. Older project progress notes are superseded where later completed results exist. The connected research project named 科研 was located; its historical-chat tool did not return during bounded attempts, so this bundle does not claim access to those chats.

The nine-person four-class analysis is exploratory. Training-duration effects and participant heterogeneity motivate the paper, while internal representation/robustness results and the 109-person binary external primary contrast do not establish general superiority. Four-class and binary scores are reported separately. Runtime differences, bootstrap seeds and counts, sign-test tie conventions, external sampling-rate amendments, CSV precision failure, portability limits, and newline conversion custody are disclosed.

`evidence/q4_q11_review.*`, `q12_q14_review.*`, and `independent_numbers.*` retain independent numerical/method reviews and source hashes. `methods_and_references.*` records implemented protocols and verified literature. Current arithmetic audits are distinct from historical scientific checkpoint replay. Passing batch orchestration is not automatically a scientific validator. Raw EEG and large checkpoints are not copied into this bundle.

## Reproduction

Run from a checkout containing the recorded source artifacts, with Python and pandas, NumPy, SciPy, Matplotlib, python-docx, ReportLab, and DejaVu fonts available. The scripts read archived tables and receipts; they do not call experiment runners or models.

```bash
python research_runs/PAPER_DRAFT_20261002/build_figures.py
python research_runs/PAPER_DRAFT_20261002/build_inventory.py
python research_runs/PAPER_DRAFT_20261002/build_manuscript.py
```

The standalone `manuscript.tex` embeds all chart panels as numerical PGFPlots/TikZ figures and uses inline references. Its source does not need additional project files. Native editor open and compilation requests timed out; successful LaTeX compilation is **unverified**. `evidence/latex_editor_status.json` records the result. Do not describe the ReportLab PDF as a successfully compiled LaTeX PDF.

`figures/` contains PNG, vector PDF, and SVG outputs. `tables/` provides participant-level values and complete condition/QC inventories. `supplementary_completed_experiment_inventory.md` includes technical and analysis-only history.

## Author review and release status

This is a substantive working draft, not a journal-ready submitted manuscript. Authors/affiliations, corresponding author, funding, contributions, competing interests, secondary-analysis ethics requirements, target-journal requirements, and any required AI-assistance disclosure need author confirmation. No declaration or approval identifier is invented. Confirm the public availability of referenced large artifacts before submission.

`evidence/delivery_validation.json` records final checks; `MANIFEST.sha256` hashes the packaged files. `paper_bundle_20261002.zip` packages the deliverables and evidence, without raw EEG, login credentials, Q15 files, or preview images. This task leaves Q15 training untouched: `fits_started = 0` during paper preparation.
