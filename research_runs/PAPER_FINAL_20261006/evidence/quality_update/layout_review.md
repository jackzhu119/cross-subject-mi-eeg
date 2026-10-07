# Current publication layout review

Status: **PASS_WITH_DOCUMENTED_RENDERING_LIMITS**. Pass: **true**. Failed checks: **0**.
Checked UTC: 2026-10-07T15:36:15.868524+00:00

Reviewed current exports: main 26 pages, combined 33 pages, supplementary 18 pages and cover letter 2 pages (79 total). These values were derived from current PDFs, not prior reports.

## Findings

- No PDF text span or embedded image extends outside its physical page. Figures fit printable width; no replacement/null text glyphs were found.
- All 568 nonempty DOCX body paragraph strings and all current table-cell strings appear in PDF extraction after excluding page footers. Every table is complete on its caption page; every figure and caption share a page.
- All 18 DOCX images fit printable width. All 26 tables repeat headers, all 263 rows prevent splitting, all 26 table captions keep with the next element, and table text is explicitly 9 pt. Manuscript/supplementary DOCX footers carry PAGE fields; no Working manuscript wording remains.
- All 79 current PDF pages were visually inspected in 13 contact sheets. Enlarged samples covered title/contact details, Figure 1 information boundaries, Figure 6 physiology labels, long tables, Figure S3, contribution/AI declarations, reference ending, and both cover-letter pages. No clipped text, boxes, or missing scientific label was observed.
- Current reference endings are main p26 ([26]–[28]), combined p33 ([9]–[28]) and supplementary p18 ([18]–[28]); the final reference is not isolated.
- Ziyuan Zhu, the correspondence email and postal address ending Chongqing 401331, China appear in all PDF/DOCX variants. Main/combined p24 retain sole-author contribution, ChatGPT (GPT-6, as reported by the author), OpenAI Codex and author-responsibility wording. Presence/layout were checked; no underlying human-review activity is certified.
- The supplementary p8 Companion title has complete words and no literal Markdown asterisks after the final export repair.

## UK prose convention

Authored narrative uses labelled, favourable/favoured, behaviour and colour. Oxford -ize/-ization forms are valid British spellings and remain. No definite non-UK variant from the documented scan remains in the reviewed ordinary paragraph/caption/table-note fields or companion prose. Reference titles, identifiers, frozen figure image wording, table cells and protected declarations were excluded. The protected Data/code-availability declaration retains noun “licenses”; the frozen Table 2 cell retains “labeled”. These are documented preservation exceptions, not layout failures.

## Limits and observations

- DOCX results are OOXML checks and PDF text-presence checks; no Word/LibreOffice rendered-page or PAGE-field-refresh claim is made. Native TeX compilation was not tested.
- Three hand-power table grids have a 1-twip (~0.018 mm) rounding excess over printable width; no clipping was observed.
- A few Figure S3 participant IDs are tightly spaced for adjacent points; all nine IDs and scientific axes/panels remain visible. The cover-letter ethics sentence continues naturally over its page break.
- This assistant review does not independently validate scientific values and is not a human editorial proofread.
- Re-exporting any bound file invalidates the corresponding hash and requires refreshing this report.

## Current visual evidence

Renders are outside the paper tree: `/workspace/paper-qa-language-20261007`.
Enlarged current samples actually reviewed: manuscript_main_en.pdf: 1,4,8,18,20,24; manuscript_en.pdf: 32,33; supplementary_materials.pdf: 2,8,16; cover_letter_JNE.pdf: 1,2.

## Exact SHA256 bindings

| PAPER-relative file | SHA256 |
|---|---|
| `manuscript_en.md` | `14005a2115f4dc2fffa30c7047048b8b058a8e67888d77427c1974d98fe79556` |
| `manuscript.tex` | `a33e07de65f66358f3cadf9fadbadf5ea21a2a3bd8eee7a36ffcf988a34f094f` |
| `manuscript_content.json` | `29d4d2acb993fc66f790588d8fdab6b5bc6d9330328f835c30363c038bb1052d` |
| `export_manuscript.py` | `526b1f7bb7c5c0fcf5bb67b188f324c36b92d45b3ac526db68019b219f7b9ff6` |
| `build_submission_variants.py` | `75208440d3f15e014e51813f1efe7223e63a18d7dfade4fede8400ab2eb1045e` |
| `supplementary_methods.md` | `a8e979007246aa5de6ae6766e62c4d977aebff199502148f4cd441abf9fc4e3d` |
| `cover_letter_JNE_draft.md` | `b3269a8d2bed303a730b4ee95eba25633ac2062b610e9b79dd5f5d8ab7f38b5a` |
| `cover_letter_draft.md` | `a286162a4880a14b1160dbed11c10f6526f65617de379df4b934fd31652e5ec4` |
| `figures/figure_workflow_zero_calibration.png` | `a6377c5cf3949f8eae60f8d91a965f68a735442bee841133bfae5a1da1c6f775` |
| `figures/figure_workflow_zero_calibration.svg` | `1085e64ac07c551884cee2e1b7aa4b010a62da83d9d6b24663aefbf16e50eb21` |
| `figures/figure_workflow_zero_calibration.pdf` | `2b620c9488a71bb280a95b9e1e9267b6fe82ff25d04e7f80872a583c953c1b90` |
| `manuscript_main_en.pdf` | `e9726d6d2cab9fec1f75689a7236c59d87c62d462e1ed82ad9596c1b6688108d` |
| `manuscript_main_en.docx` | `b08aeb397d8f3dc5d82ca4391bedf9d8b04a6f7f3021cb42833c41a371287fda` |
| `manuscript_en.pdf` | `be556789234c8ff4cbd8f6fbc7a211d0de41aa7b04e2056d9bde0db88350683d` |
| `manuscript_en.docx` | `355fc95b55943955a3442e9e99a2912810b40ded856b673254dd1f97ae43b3e8` |
| `supplementary_materials.pdf` | `319cb29eab0c310ae018fba3b9271ee8a0c7830460beccd4235a8ee1c078f439` |
| `supplementary_materials.docx` | `040ac6b650aa9d722de8e5d9b49c57db02a2222ba376fb2bf95b153b6bf613ac` |
| `cover_letter_JNE.pdf` | `98e12f06fb0ceeb6a6e1d58667eedd79ca6e62fc52f79271ebc257528d0f5f23` |
| `cover_letter_JNE.docx` | `f32570677788c8f43aad9c6385ae718a1d6eeaec8b24dbce1ce0e637f0efda03` |
| `figures/figure1_selection_and_s3.png` | `86538328564c0062c1d9dabf21251071e1a02cc3ccde5a0d46d9884ee0eb733e` |
| `figures/figure1_selection_and_s3.svg` | `67e260ab97cce4831efda9fb5fd51a083dc35090c501a3af4eedca4eaeacdefb` |
| `figures/figure1_selection_and_s3.pdf` | `874c375cfaa87970a970bd2d64e22097d56945831dabf923fd3a5e1242dd9b64` |
| `figures/figure2_source_count_and_runtime.png` | `dcb1dc20e344a4110428d4eadbfb77634d7ba19d0cd1c9146c76e14818c15098` |
| `figures/figure2_source_count_and_runtime.svg` | `3a30c05065c2ba5b7acb6c069267da1581c25f833c8b1f77250311fbe7e0a7cc` |
| `figures/figure2_source_count_and_runtime.pdf` | `436e1f17c7bf84734de9f35ec69fdab6b84604e9b2b1fa941ffdabefa544a245` |
| `figures/figure3_external_primary.png` | `8ebc12054a9132b2661917bbf02b8965bb648c9bf09f16bff9e45d7a2202db40` |
| `figures/figure3_external_primary.svg` | `c81c087962ab7f3c29808740fa5a5328b6074a50757260dbe50bd81362f96acb` |
| `figures/figure3_external_primary.pdf` | `023149d604b03ca01901a602635a82876c1b5a7aac50f86edab458171cb87bf3` |
| `figures/figure4_q15_external_transfer.png` | `14ad3b5fa1a9eff99fd063d6d86872f3efd0550d3747e0b280122f59e8b04a80` |
| `figures/figure4_q15_external_transfer.svg` | `b2f41164e6d417cfbfc6209bf05b882fbce783a1eb4f17506efa848612db3f50` |
| `figures/figure4_q15_external_transfer.pdf` | `c4fddd82de9085711950a8a574aa73372cb4e84e9dc8e41607359c6f8a9df29f` |
| `figures/figure_q16_bnci_physiology.png` | `654db651727f7f0c73626a86abf4e1e9d69cf17a1f73dde324183d17a11fbeaf` |
| `figures/figure_q16_bnci_physiology.svg` | `9cdc59e7efb6dae6c1d2b367e28775a147aef7c0143bdc7f4756e57282c5720b` |
| `figures/figure_q16_bnci_physiology.pdf` | `aa06d80460a072237a184064557b9e62c948e495f1cbf9de3998b9275aa90e56` |
| `figures/figureS1_robustness_heterogeneity.png` | `aefbbe338c8440ed9eaee95b5a487ebb9e89c0091885f65aa7d08eea54760a51` |
| `figures/figureS1_robustness_heterogeneity.svg` | `b1a9c57d10b18d0641df65fc41577c0054baec13451212fc047ac43778490a8f` |
| `figures/figureS1_robustness_heterogeneity.pdf` | `1c2bc2544a434298fe5b211d8d7f3b275945553780f014795a8c81dcb426544d` |
| `figures/figureS2_q15_participant_heterogeneity.png` | `16c7535df988daf34ef6d08fc861e55d2b1d5ea8d8ee984a09e8831c5570c749` |
| `figures/figureS2_q15_participant_heterogeneity.svg` | `34fe69ad6830755935ff52bcb44bd5ce8709889de9e3001eb6c5574f966e006f` |
| `figures/figureS2_q15_participant_heterogeneity.pdf` | `c07251603556c28f4822522b7a8024b22a400a3779a86e323912d94cdb7a82a1` |
| `figures/figureS_q16_physiology_associations.png` | `3a6c45c05302195fe8af6cb59c7c2332d0c37d57cfb44c44e6df01135101018d` |
| `figures/figureS_q16_physiology_associations.svg` | `57b8165b6ea3023511686197100b162c34a0f962357e8b017d3ca8596ec9f81e` |
| `figures/figureS_q16_physiology_associations.pdf` | `da1a96996c47be79f450ba59c3a0a4424218841a03a0302d27ed275326fe9338` |
