# Independent narrative, methods and presentation audit

Read-only review of `/workspace/cross-subject-mi-eeg` / `plos-one-submission-v1.1`. No repository edits, fits, inference or physiology computations.

## M2

Status: `existing_boundaries_correct_targeted_clarity_recommended`.

- Q15 durations broad14/shared19 and Q14 broad18/shared17 already disclosed.
- Complete-pipeline rather than isolated spectral-sharing causal effect is already stated.
- Two views/shared BatchNorm/forward compute differences are disclosed.
- Within-cohort band-design differences and between-protocol montage/window/reference/preprocessing differences must remain separate.
- Cho -1.513 pp adverse retained; PhysioNet +0.573 and Lee +0.204 remain uncertain; Lee does not establish equivalence.

## M3

Status: `rewrite_introduction_contribution_paragraph`.

- Existing end of Introduction combines selection, external transfer, transparency and physiology without explicit two-primary-contribution hierarchy.
- Use two empirical contributions; Q16 supplementary/descriptive, evidence chain transparency contribution, no original algorithm or selection-rule priority claim.

## M4

Status: `semantic_replacements_and_SI_crosswalk_required`.

- Internal Q/P IDs still occur in main headings, paragraphs, captions and table labels.
- Replace main narrative IDs with scientific names; preserve all archive filenames and establish semantic-name-to-ID-to-path SI table.
- Montage channel labels P1/P2 are real electrodes and must not be replaced as project IDs.

## Q16

Status: `existing_scientific_boundaries_correct_preserve`.

- BNCI only, nine people, post-decoder-outcome, no p-values, no external physiology and no decoder feedback already stated.
- 1-s baseline one Welch segment / 2-s task three overlapping segments and log-power bias disclosed.
- Signed laterality is contra minus ipsi, not absolute contralateral ERD; S2 counterexample retained.
- rho +0.600 is descriptive and higher BA with less-negative laterality, not evidence of stronger suppression.
- All sensors/profiles/trials/artifact flags and negative means must remain; sensor interpolation does not locate cortical sources.

## MINOR_FIGURE2

Status: `no_font_failure_found_at_recorded_output_size`.

- Every observed text element corresponds to approximately 8.000 pt at the TIFF physical width 19.05 cm; SVG nominal 13.142708 is not the delivered point size.
- Figure is legible in direct preview; legends have no visible overlap.
- Keep output width or increase fonts if journal reduces width; do not assert future typesetter scale verified.

## MINOR_CVD

Status: `existing_redundant_encoding_present_caption_strengthening_and_simulation_optional`.

- Fig6 scalp color map RdBu_r, negative blue/positive red, fixed +/-6dB. Profile left/right already use circle/triangle and blue-green/brown.
- FigS1 robustness heatmap RdBu, fixed +/-20pp, every cell has signed numeric annotation.
- Do not equate RdBu with red-green-only palette and do not rescale ranges to make near-zero signals visually stronger.
- Add caption descriptions of color direction and shape/numeric redundancy; if CVD simulation is performed, retain it as display review and not mathematical guarantee for all viewers.

## MINOR_FIXED20

Status: `clarifying_sentence_recommended`.

- Already described as later matched-runtime sensitivity control, four improve/five worsen, negative median and no universal optimum.
- Clarify fixed20 provides a common-duration control and is not an external-outcome-selected deployment rule; no new justification from favourable average.

## MINOR_EQUATIONS

Status: `definitions_and_explicit_crossreferences_recommended`.

- Rank and shared-logit equations exist without numeric labels. Balanced accuracy equation lacks explicit TP/FN/C definitions in its adjacent prose.
- Add editorial equation labels/references and define symbols, keeping algorithms/bounds unchanged.
- Power ratio and signed laterality may remain inline with explicit symbols defined; no estimator changes.

## Suggested surgical replacements

- 6 `text` (M3): We make two empirical contributions. First, we audit the reliability of source-only training-duration selection in cross-subject EEGNet, examining short selected schedules, heterogeneous source-validation trajectories and gains concentrated in a few participants. This is an exploratory analysis within a repeatedly used development benchmark, not independent confirmation of a new selection algorithm. Second, we evaluate complete, frozen broad and shared-input pipelines on external binary motor-imagery cohorts, retaining adverse and uncertain results at the participant level. A separate post-outcome BNCI sensor analysis provides descriptive context rather than a third mechanistic contribution. Open code, saved predictions and linked validation evidence make these analyses auditable [11].
- 128 `text` (M2): The external schedules are part of the pipeline contrast: broad/shared fits used 18/17 epochs for PhysioNet and 14/19 for Cho2017 and Lee2019. Within each cohort, the paired contrast therefore combines selected duration with one-view versus two-view input, band filtering, shared BatchNorm exposure and forward-pass computation. Across the two external protocols, montage, crop, reference, filtering scope and source checkpoints also differ. These comparisons do not identify the causal contribution of parameter sharing or band decomposition alone.
- 37 `text_append` (MINOR_FIXED20): The fixed 20-epoch condition is a common-duration sensitivity control, not a prospectively validated stopping rule or a recommendation selected from external outcomes.
- 118 `caption_append` (MINOR_CVD): The signed colour scale uses blue for negative and red for positive values. Hand profiles are additionally distinguished by circle and triangle markers.
- appendix 4 `caption_append` (MINOR_CVD): Signed numerical cell labels provide an interpretation independent of the blue–red colour encoding.

## Block indexing and traceability

Full original/edited block mapping and every main Q/P occurrence are in the JSON. Do not treat P1/P2 electrode names as internal experiment IDs. Main numeric table cells remain unchanged; semantic row labels may be edited with an explicit SI crosswalk.

## Frozen checkpoint inventory

Read the six declared Q15 final neural manifests and verified each checkpoint SHA-256. Broad models are all 14 epochs; shared models are all 19 epochs. No matched-duration all-nine-source final pair was found in these declared artifacts. Inner checkpoints have different source populations and cannot be substituted. No checkpoint was deserialized or executed; no inference or training occurred.
