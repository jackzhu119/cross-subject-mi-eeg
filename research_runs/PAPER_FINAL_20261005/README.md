# Completed scientific manuscript with Q15

This bundle extends the reviewed 2 October manuscript with the completed Cho2017/Lee2019 source-only evaluation. It preserves exploratory internal results, the earlier PhysioNet amendments, adverse transfer results, and acquisition-calibration limits. Author/corresponding author: Ziyuan Zhu; email: zzy2630816871@gmail.com.

## Read and edit

- `manuscript_en.pdf`: standalone, searchable ReportLab layout export.
- `manuscript_en.docx`: editable English manuscript, tables and six embedded figures.
- `manuscript_main_en.pdf/.docx` and `supplementary_materials.pdf/.docx`: separate submission-preparation versions (four main figures/five tables; two supplementary figures/three tables plus detailed methods).
- `manuscript_en.md` and `manuscript_content.json`: inspectable prose and structured source.
- `manuscript.tex`: standalone source, embedded numerical PGFPlots panels and references; the native compilation outcome is recorded separately, and the PDF above is not represented as a LaTeX-engine export.
- `中文说明.md`: Chinese abstract, results interpretation, scope and pending declarations.
- `supplementary_methods.md`, `supplementary_inventory.md`, `tables/`: full methodological and result evidence.
- `journal_strategy_zh.md`, `cover_letter_draft.md`, `author_information_template.md`, `submission_checklist_zh.md`: author review and submission preparation; no journal submission was performed.

## Reproduce the manuscript, without EEG fitting or inference

From this directory, with a checkout containing the archived controlling artifacts:

```bash
python audit_q15_numbers.py --repo ../.. --output .
python build_figures.py
python build_q15_figures.py
python build_content.py
python export_manuscript.py
python build_submission_variants.py
python validate_final_delivery.py
python package_final_delivery.py
```

See `reproducibility_readme.md` for audit arguments and data grains. Python dependencies are listed in `requirements-paper.txt`; no GPU or EEG model runtime is needed for manuscript reaggregation. The internal independent review is saved in `evidence/internal_review.json`; its reviewed raw prediction arithmetic and controlling hashes are independent of the table renderer. The previous reviewed manuscript source and evidence are preserved under `evidence/previous_draft/`.

## Evidence and interpretation

Q15 final results were read back at commit `bc48b257eb44f412ad069f50d0f1a72a33c3c520`, and subsequent completion/readback evidence is archived on `q15/run-20261005T050511Z-migration-from-r2-b82ad79b`. Paper preparation starts from `7af1a137e2676a018e1e880ab076de6cae4ce30b`. The new manuscript does not change experiments, source/inference contracts, checkpoints, or completed scientific reports.

`evidence/q15_numbers.json` independently verifies saved predictions, canonical audited events, frozen statistics and exact-commit publication bindings. The completed cloud scientific validator separately reports raw-to-prediction replay; the manuscript audit itself loads no raw EEG or checkpoints. Original Q15 source fits = 15; new migration source fits = 0; target fits = 0. Manuscript-preparation fits and checkpoint inference = 0. Current complete results have stated calibration limitations; publication readback does not establish physical server shutdown.

Author funding, competing interests, contributions and institutional secondary-analysis requirements remain pending confirmation. Affiliation verification distinguishes official Chinese institutional evidence from corroborated published English usage. No unverified official English translation, ethical exemption or journal acceptance is asserted.

`MANIFEST.sha256` and the ZIP receipt bind delivered files. Verification reports describe the actual checks and renderer limitations; a passed export check is not a new scientific experiment or an independent checkpoint replication.
