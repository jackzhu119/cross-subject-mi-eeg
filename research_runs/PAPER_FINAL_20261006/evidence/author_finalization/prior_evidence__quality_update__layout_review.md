# Independent final publication layout review

Status: **PASS, with documented rendering limits.**
Checked UTC: 2026-10-07T09:41:54.315815+00:00

The reviewed final exports comprise 25 main, 33 combined and 18 supplementary PDF pages (76 total). No scientific experiment, training, inference, frozen data or manuscript source was changed by this review.

## Findings

- All PDF text spans and images remain within page bounds; all embedded figure widths fit PDF printable width.
- All 18 DOCX images fit the section printable width. All 26 tables repeat their header, all 263 rows prevent splitting, and all 26 table-caption paragraphs keep with the next element. Body text is 11 pt; table runs are 9 pt. All DOCX footers include PAGE fields.
- All DOCX table-cell strings appear in PDF extraction. Every table is complete on its caption page in the reviewed PDFs; no clipping or lost text was observed in enlarged table reviews.
- Main/combined Table 2 stays on p6, Table 6 on p16 and Table 7 on p18. Supplementary Table S2 stays on p3 (combined p27).
- All figure captions and images stay on the same page. Figure 1 on p4 shows the requested baseline-relative μ/β-power and target-label boundary labels without overlap.
- Reference [28] shares the last reference page with refs9–27 in main/combined and refs12–27 in supplementary. It is not an isolated page.
- Current PDF/DOCX footers use neutral manuscript wording and contain no “Working manuscript” status.

## Documented limits

- DOCX results are OOXML structural checks; no Word or LibreOffice rendered-page claim is made.
- Native TeX compilation is not verified; the parent task reported unavailable handler support.
- Three DOCX hand-power table grids have a 1-twip (~0.018 mm) rounding excess over printable width; no visual clipping was observed. All figure widths have zero excess.
- PDF page size is 8.3 × 11.7 in; DOCX sections are A4.
- This is layout QA; independent numerical/scientific audit is separate.

## Visual evidence

Contact sheets and enlarged reviewed pages: `/workspace/paper-qa-20261007/final_review`.
Full-resolution samples reviewed: main p4,6,16,18,19,20,25; combined p26,27,29,31,32,33; supplementary p2,3,5,7,8,16,17,18.

## SHA256-bound latest inputs

| File | SHA256 |
|---|---|
| `manuscript_en.md` | `8a10c2ee5c089dd1456a521907d3e3721cdabd66440e51982be9d9b93594cd55` |
| `manuscript.tex` | `95455f299752352dabbce914df1a2d0f582868ec1373dc768356af8bd7c333f5` |
| `manuscript_content.json` | `2a779122b1b97f8a2d495f6572eda77470ff3d9dc3d602c6fb42ced83c856919` |
| `export_manuscript.py` | `8f5ebf7dced70fa66c0b800a146fa5686f156ef5e2c4a7a5718b72206bd7fe28` |
| `build_submission_variants.py` | `c641bda6975c7d1c35c848aac7e42df072f2e8673983652f0b10817a03c67501` |
| `figures/figure_workflow_zero_calibration.png` | `a6377c5cf3949f8eae60f8d91a965f68a735442bee841133bfae5a1da1c6f775` |
| `figures/figure_workflow_zero_calibration.svg` | `1085e64ac07c551884cee2e1b7aa4b010a62da83d9d6b24663aefbf16e50eb21` |
| `figures/figure_workflow_zero_calibration.pdf` | `2b620c9488a71bb280a95b9e1e9267b6fe82ff25d04e7f80872a583c953c1b90` |
| `manuscript_en.pdf` | `5e965ea4acee0a7ed7da9085ff200db9daa5efdea2d5efc2c99bb10cede3d014` |
| `manuscript_en.docx` | `b813d1de02d781e474a78ddf750d954f492bd58c589a5ad2b44467c878956463` |
| `manuscript_main_en.pdf` | `0200e5b1ed67b214447b3a3564db9a38cb13a2543ec22c7d81b79e545be9d8e0` |
| `manuscript_main_en.docx` | `b16da16289bf732bbc0b4b425d20af22e1f4103425381fdcc6c60e90e8ca3731` |
| `supplementary_materials.pdf` | `7c82cbe1db46810a2b31a7c09bf404b9ba5423b74a31fbc4f233174d3dc22d7f` |
| `supplementary_materials.docx` | `d5f1ba9fa5ccce1d076cb0214b2e4a051b5e4921dc4a982debe43f2615147f5c` |
