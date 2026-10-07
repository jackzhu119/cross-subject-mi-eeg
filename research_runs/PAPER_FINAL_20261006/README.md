# Zero-calibration MI EEG manuscript — Q15 and BNCI Q16 revision

This revision integrates the completed Q15 external decoder evaluation with the BNCI component of the separate Q16 physiological analysis. It separates source-only decoder selection, fixed target inference, scoring and descriptive physiology. The 5 October paper remains an immutable historical delivery; its publication receipt does not verify the bytes of this revision.

Author and corresponding author: **Ziyuan Zhu (朱子元)**. Affiliation: **College of Artificial Intelligence Medicine, Chongqing Medical University, Chongqing, China**. Email: **zzy2630816871@gmail.com**. The English college wording is corroborated by published affiliations; an accessible university-hosted official English naming page was not established.

## Read and edit

- `manuscript_en.pdf` and `manuscript_en.docx`: full English manuscript with in-document supplementary content.
- `manuscript_main_en.pdf/.docx` and `supplementary_materials.pdf/.docx`: separate main-paper and supplement exports.
- `manuscript_en.md`, `manuscript_content.json`, `manuscript.tex`: editable text, structured content and standalone TeX source.
- `figures/`, `tables/`, `supplementary_methods.md`, `supplementary_inventory.md`: numerical figures, supporting tables and detailed methods.
- `中文说明.md`: Chinese interpretation and remaining author decisions.
- `journal_strategy_zh.md`, both cover-letter drafts, `author_information_template.md` and `submission_checklist_zh.md`: submission preparation. Neither cover letter has been sent.

The PDF files are searchable ReportLab layout exports. Native LaTeX compilation is reported in `evidence/native_latex_check.json`; availability of a TeX source does not establish a successful TeX-engine export. Current figure/table counts and export checks belong to the current delivery reports, rather than the copied 5 October receipts.

## Evidence boundaries

Zero calibration means **no target-dependent parameter fitting or target-based model selection**. Labels may be used for documented metadata, eligibility, scoring and the separate descriptive physiological analysis. Fixed channel mapping, referencing and resampling are not target-fitted parameters. This definition does not assert label-free operation, online control or clinical effectiveness.

Q15 used 15 original source fits (14 neural and one shallow), with no new migration source fits and zero target fits. Its Cho2017 and Lee2019_MI outputs are preserved. Manuscript preparation and Q16 add zero decoder fits and zero checkpoint inference.

Q16-P001-BNCI-20261006 covers all 18 BNCI source MAT files: nine people, two sessions, 108 labeled runs and 5,184 four-class trials; the primary hand subset has 2,592 trials. Native 250-Hz, 22-channel EEG is processed with fixed cue-relative baseline [−1.5,−0.5) s and task [0.5,2.5) s, without additional digital filtering, CAR, resampling or decoder transforms. Trial-level log ratios and participant summaries are physiological descriptions. Their associations use already saved Q14 binary source-LOSO scores. External physiology was not computed; the BNCI component does not complete the proposed external physiological programme or establish what a decoder learned.

The protocol, passed metadata gate, committed freeze, executed manifest and independent validation are under `../Q16-P001-BNCI-20261006/`. A result is scientifically usable only with its executed output and verification receipt, not from protocol or freeze status alone.

## Rebuild the paper from saved results

From this directory in the delivered repository checkout:

```bash
python -m pip install -r requirements-paper.txt
python audit_q15_numbers.py --repo ../.. --output .
python build_figures.py
python build_q15_figures.py
python build_q16_figures.py --analysis ../Q16-P001-BNCI-20261006
python build_content.py
python build_bibliography.py
python export_manuscript.py
python build_submission_variants.py
python validate_final_delivery.py
python package_final_delivery.py
```

These paper commands read saved numerical artifacts. They do not train a decoder or run a checkpoint. The saved-result rebuild requires neither GPU nor R2/RunPod credentials. Raw Q16 replay is described separately in `reproducibility_readme.md` and requires exact original files and the frozen recipe.

Funding, competing interests, contributions, institutional secondary-use requirements and final author approval remain to be confirmed. No ethical exemption, journal submission, acceptance or physical Pod shutdown is inferred. `MANIFEST.sha256`, the archive checksum and the current publication receipt identify delivered bytes.
