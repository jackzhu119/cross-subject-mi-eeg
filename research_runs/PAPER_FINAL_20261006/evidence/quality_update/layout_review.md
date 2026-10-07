# Independent final publication layout review

Status: **PASS, with documented rendering limits.**
Checked UTC: 2026-10-07T10:26:49.618005+00:00

The reviewed final exports comprise 26 main, 33 combined and 18 supplementary PDF pages (77 total). No scientific experiment, training, inference, frozen data or manuscript source was changed by this review.

## Findings

- All PDF text spans and images remain within page bounds; all embedded figure widths fit PDF printable width.
- All 18 DOCX images fit the section printable width. All 26 tables repeat their header, all 263 rows prevent splitting, and all 26 table-caption paragraphs keep with the next element. Body text is 11 pt; table runs are 9 pt. All DOCX footers include PAGE fields.
- All DOCX table-cell strings appear in PDF extraction. Every table is complete on its caption page in the reviewed PDFs; no clipping or lost text was observed in enlarged table reviews.
- Main/combined Table 2 stays on p6, Table 6 on p16 and Table 7 on p18. Supplementary Table S2 stays on p3 (combined p27).
- All figure captions and images stay on the same page. Figure 1 on p4 shows the requested baseline-relative μ/β-power and target-label boundary labels without overlap.
- Reference [28] shares its page with other references in all three PDFs. Current main p26 has references [26]–[28]; combined p33 has [9]–[28]; supplementary p18 has [12]–[28]. It is not an isolated reference.
- Current PDF/DOCX footers use neutral manuscript wording and contain no “Working manuscript” status.
- Title pages include the updated postal address ending Chongqing 401331, China without crop or overlap. Main/combined declaration pages contain the author contribution and ChatGPT (GPT-6, as reported by the author) / OpenAI Codex disclosure, kept readable on one page. This verifies artifact presence and layout, not the underlying author-reported activities.

## Documented limits

- DOCX results are OOXML structural checks; no Word or LibreOffice rendered-page claim is made.
- Native TeX compilation is not verified; the parent task reported unavailable handler support.
- Three DOCX hand-power table grids have a 1-twip (~0.018 mm) rounding excess over printable width; no visual clipping was observed. All figure widths have zero excess.
- PDF page size is 8.3 × 11.7 in; DOCX sections are A4.
- This is layout QA; independent numerical/scientific audit is separate. Contribution, approval and AI-use statements are checked for artifact presence/layout only; underlying author-reported actions and any all-code human-review process are not independently asserted.

## Visual evidence

Contact sheets and enlarged reviewed pages: `/workspace/paper-qa-20261007/final_review`.
Current enlarged visual samples reviewed: main p1,4,6,16,18,24,26; combined p24; supplementary p1. Other current table/figure layouts were reviewed in contact sheets and text extraction; the earlier enlarged review remains available outside the paper.

## SHA256-bound latest inputs

| File | SHA256 |
|---|---|
| `manuscript_en.md` | `83c039e6b9a05df15e7d28afae7761a23f01a5e9f7df00f86face10a85968c84` |
| `manuscript.tex` | `1654d1881a548c766f3f4523359d5d92ccd2174b2b6fb8926d004f69ede1e1c9` |
| `manuscript_content.json` | `d67e0c52e90ee84bbca96ecd3136ff5b476ed22e59d6d30bbcf46a6b1901ca7f` |
| `export_manuscript.py` | `526b1f7bb7c5c0fcf5bb67b188f324c36b92d45b3ac526db68019b219f7b9ff6` |
| `build_submission_variants.py` | `c641bda6975c7d1c35c848aac7e42df072f2e8673983652f0b10817a03c67501` |
| `figures/figure_workflow_zero_calibration.png` | `a6377c5cf3949f8eae60f8d91a965f68a735442bee841133bfae5a1da1c6f775` |
| `figures/figure_workflow_zero_calibration.svg` | `1085e64ac07c551884cee2e1b7aa4b010a62da83d9d6b24663aefbf16e50eb21` |
| `figures/figure_workflow_zero_calibration.pdf` | `2b620c9488a71bb280a95b9e1e9267b6fe82ff25d04e7f80872a583c953c1b90` |
| `manuscript_en.pdf` | `daedc7fe061e2185819aca97587c7c2fcaf47d478dbd780b536e0163fe8cd47b` |
| `manuscript_en.docx` | `54b45dec73dc64eea6f18f33b41a9848611e252bd7bc2224b62f27a1fa19ea77` |
| `manuscript_main_en.pdf` | `0292da85747e16369225aee3ed9ef6255b15eb033393611726624d89205ae393` |
| `manuscript_main_en.docx` | `1754b080aad1109a1fcfa2efb0d2808580d3d605d737f7cc3c2db3943d908e5d` |
| `supplementary_materials.pdf` | `478f6518a6a9d075615591a275d1d88a81a68c979098359fe70d9432cb192329` |
| `supplementary_materials.docx` | `539814f81a913544b005e71c9c0f993e21c5a5e06dc500259da7656b27a3c330` |
