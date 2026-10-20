# Paper 1 — evidence-based review of supplied critique (20 October 2026)

**Basis:** The 18 October source-of-truth `main` commit `e53318846e4a3ce8604de2ffc8f12c7b58ff3953`; original editable manuscript `research_runs/PAPER1_SUBMISSION_CORRECTION_20261018/Main_Manuscript_REVISED.docx`, matching Markdown, S1 Appendix and saved-result records. The supplied critique is an external editorial assessment, **not** a PLOS ONE Academic Editor or referee decision.

## Dispositions

| Critique | Decision / source-based reason | Change |
|---|---|---|
| Exact UTC approval timestamp, operational contract language | Accept. File-level dates and approval sequence belong to research provenance, not narrative Methods | Removed exact seconds and process/contract prose in main text; archival dates preserved |
| “Independent” audit is not a human/third-party review | Accept. Source records describe separate scripted reconstructions, not a separate external reviewer | Main Results audit section replaced by selection-rule result; code/verification scope in S1; cover letter uses “automated” |
| Removal of all prior-target-exposure disclaimers | **Reject.** Earlier external exposure is not disproven; deleting it would overstate independence | One concise exploratory-design qualification retained |
| Post hoc contrasts and editor-revision meta-commentary | Accept stylistic correction, **retain post hoc status** | Rephrased Main Methods/Fig 6/S1 without new tests |
| Blanket global replacement of `frozen`, `contract` or experiment keys | **Reject blanket edit.** “Frozen” is legitimate for frozen model/analysis states; exact keys are needed for reproducibility | Limited inappropriate instances changed; BROAD and MU_BETA_SHARED are now introduced with ordinary names |
| Intro starts with results before the BCI task is framed | Partially accept (style preference, not scientific error) | Background and weaker-class problem now lead; principal positive numbers remain in the opening paragraph |
| Plain-text scaling expression | Accept | Trial RMS equation re-expressed with summation and index limits, preserving the same transform |
| S29→S60 marginal benefit; confounding of size, provider and 50:50 sampling | Accept scientific concern. Source pools and Table 2 confirm S60−S29 W=−0.549 pp (95% CI −2.1604 to +1.0624). Sample count and provider identity are not separately randomized | Expanded Discussion; no universal size-only or mechanistic plateau inference |
| Right-hand recall ↑ and left-hand recall ↓ | Accept data fact. 31.01%→59.64% right and 85.63%→68.71% left; hard-class changes alone do not distinguish separability from decision bias | Expanded class-asymmetry interpretation; no invented AUROC/logit recalibration |
| Unusual source-selected epochs | Accept observation. BROAD tail-recall selects 27/5/5 for S9/S29/S60; tail CE selects epoch 1 and tail BA epoch 39 for S29/S60 | Expanded scope discussion; no speculative cause presented as demonstrated |
| CSP–LDA exceeds EEGNet in mean BA | Accept descriptive fact. S60 CSP–LDA BA 65.3775%, broadband EEGNet BA 64.1716%; W differs in opposite direction | Stated explicitly; no unperformed between-decoder significance test |
| “8192 rows discards 75%” | **Reject as a literal description.** LDA uses 8192 **draws with replacement**, not a deterministic selection of 8192 unique trials; an exact weighted fit was not run | State stochastic sampling approximation and its limits, without inventing an experimental rationale |
| Missing Yang-only, target alignment/EA, logit calibration and Riemannian benchmarks | Accept as missing comparative evidence, **not** permission to fabricate training results | Clearly specified as unevaluated future work |
| Assert exact physiological-phase alignment from Yang marker+1.5 s | **Reject definitive claim.** Provider describes 1.5 s cue and 4 s MI, but dataset event marker interpretation and signal phase equivalence need not be identical across providers | Added transparent arithmetic of the crop relative to its computational anchor, retaining physiological uncertainty |
| Dreyer window includes visual-feedback interval | Accept. Provider's cue begins at t=3 s and feedback at t=4.25 s, so cue-relative [0.5,2.5) includes the later interval | Clarified possible feedback-related activity |
| `?V` is necessarily a lost `µV` glyph | **Reject.** The archived Yang native header is literally `?V`; replacing it with `µV` would invent a unit | Explicitly identify this as an ambiguous literal native unit string |
| Missing S in `S29`, malformed multiplication glyph, `F1=8.,`, missing period and uppercase after semicolon | Mixed: Markdown authoring source already contains `S29`, `2 ×`, `F1=8,`, and `p<0.001).`. A text-extraction artifact is not itself proof of bad PDF rendering. The semicolon-capitalization is an actual source typo | Fixed actual semicolon case, generated a source-matched abstract; automated PDF QA checks. Do not change scientifically valid symbols from unverified OCR alone |
| Results described as independent scientific confirmation based on 1,179 checks | Accept concern | Only S1 Appendix retains audit method/counts; they are labelled automated verification, not another external cohort |

## Invariants and boundaries

- No EEG preprocessing, model fit, target prediction, hypothesis-family addition or new statistical estimate was run.
- Tables 1–5 and S1 tables remain unchanged; external results, seed counts and the seven original standalone figures are preserved.
- Source files `PLOS_ONE_SUBMISSION`, `PAPER1_PLOS_FINAL_20261018` and `PAPER1_SUBMISSION_CORRECTION_20261018` remain intact.
- Ethics statement retains the author-confirmed regulatory basis without asserting an unverified institutional exemption document.
- The portal abstract is copied **verbatim** from the revised main manuscript; the live Editorial Manager metadata cannot be inspected from this repository.
- Before final resubmission, check the actual Editorial Manager latest manuscript matches the clean new DOCX and generate/upload a correctly based Track Changes file as directed by the journal.

**External provider evidence:** Yang et al., Scientific Data (2025), DOI: 10.1038/s41597-025-04826-y; Dreyer et al., Scientific Data (2023), DOI: 10.1038/s41597-023-02445-z; dataset implementations documented in the source bibliography.
