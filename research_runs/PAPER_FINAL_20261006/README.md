# Source-only model selection and limits of fixed spectral-sharing pipelines in cross-subject motor-imagery EEG decoding

This revision integrates the completed Q15 external decoder evaluation with the BNCI component of the separate Q16 physiological analysis. It separates source-only decoder selection, fixed target inference, scoring and descriptive physiology. The 5 October paper remains an immutable historical delivery; its publication receipt does not verify the bytes of this revision.

Author and corresponding author: **Ziyuan Zhu (朱子元)**. Affiliation: **College of Artificial Intelligence Medicine, Chongqing Medical University, Chongqing, China**. Email: **zzy2630816871@gmail.com**. The author confirms the English college wording, also corroborated by published affiliations; this remains distinct from independent official college-page verification. Postal address: Jinyun Campus, Chongqing Medical University, No. 61, Daxuecheng Middle Road, Shapingba District, Chongqing 401331, China.

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
python validate_numeric_presentation.py
python validate_submission_revision.py
python validate_final_delivery.py
python package_final_delivery.py
```

These paper commands read saved numerical artifacts. They do not train a decoder or run a checkpoint. The saved-result rebuild requires neither GPU nor R2/RunPod credentials. Raw Q16 replay is described separately in `reproducibility_readme.md` and requires exact original files and the frozen recipe.

The author has confirmed that the research received no funding, that there are no competing interests, and that neither ethics approval nor an exemption was required for this public-data secondary analysis. The declaration source is retained in `evidence/author_declarations.json`; no committee decision, institutional policy or identifier has been invented. The author has confirmed a sole-author free-text contribution statement and final main/supplement/figure review and approval; actual journal submission remains separate. No journal submission, acceptance or physical Pod shutdown is inferred. `MANIFEST.sha256`, the archive checksum and the current publication receipt identify delivered bytes.

## Editorial and release revision — 7 October 2026

The title and complete-pipeline interpretation were refined, the four unequal source-validation groups are now an explicit limitation, and the main prose leads with semantic experiment names. Figure 1 separates event/class metadata from scoring ground truth and uses baseline-relative power rather than ERD/ERS as an estimator label. All quantitative figure data, tables, predictions, `paper_numbers.json`, source selections and Q15/Q16 frozen receipts are unchanged. Rounded main-table display retains the full-precision saved data.

Two directly relevant 2025 original DG papers were added after primary-source/registry checking; all 28 references are used. Official NeurIPS metadata and the proceedings PDF both print **Guagnyu Wang**, which is retained. Current IOP policy and remaining author actions are documented in `ai_disclosure_submission_draft.md`. The main manuscript omits draft/project-management title metadata; omission does not imply author approval or submission.

Word figures fit the printable width, tables repeat headers and prevent row splitting, and searchable PDF layouts keep short tables with their captions. `evidence/quality_update/` records the saved-data numeric review, protected scientific inputs, reference verification and layout review. Follow `release_plan.md` for publication-integrity gates. No repository archive DOI or journal acceptance is asserted.

The final delivery validator intentionally binds the reviewed export bytes. Freshly generated DOCX/PDF files can have different container timestamps or rendering bytes and need a new export/layout review before the exact delivery check passes. Rebuild in a separate checkout, retain the delivered archive, and use the saved-number checker to assess scientific display consistency. Do not overwrite reviewed receipts merely to make a rebuild pass.

## Author finalization — 7 October 2026

The author confirmed sole authorship, final review/approval, personal checking/revision, data-term checks, Github-only public history and no other-journal consideration. JNE is the target. ChatGPT (GPT-6) is author-reported; the actual Codex research/figure/drafting scope remains disclosed. See `author_information_template.md`, `ai_disclosure_submission_draft.md` and `evidence/author_finalization/`. No journal submission or DOI is claimed.

## Language refinement and contribution framing — 7 October 2026

The candidate `paper-v1.0.1` revises narrative prose, captions, supplementary text and cover letters. Its principal contributions are the source-only selection audit, participant-level interpretation of concentrated gains, and retained frozen external adverse/uncertain results. Class-specific recalls, conditional uncertainty and the distinction between computational validation and sensor physiology provide support. `contribution_evidence_zh.md` links these claims to existing evidence and states their limits.

`language_refinement.json` contains the accepted exact replacements; `apply_language_refinement.py` applies them after conventional citation numbering and checks every changed numeric/citation literal sequence. Table data, equations, references, figures, model selections and Q15/Q16 frozen results are unchanged. The prior author approval applies to the preceding scientific candidate; the newly revised wording needs the author's final read before submission. No AI-detector score, guaranteed acceptance, journal submission or new scientific experiment is claimed.
