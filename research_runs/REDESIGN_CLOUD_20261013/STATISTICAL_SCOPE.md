# Exploratory statistical execution scope

Prepared14October2026 before any new source neural fit or target model output. This additive implementation follows the numerical source/participant estimation decisions in the preserved source-selection statistical plan. Author prior exposure to Dreyer2023 remains unknown; **all analyses here are exploratory and every independent-confirmation flag remains false**. This changes evidential qualification, not the source design or observed eligibility. The old first-use gate is not bypassed and no never-used declaration is fabricated.

## Fixed design

Source:9BNCI people, both sessions,2,592 binary hand trials, provider flags included. Common genuine19sensors, CAR19, native six-second contexts, fixed8–30/8–13/13–30Hz views,160Hz,0.5–2.5s crop. Four source validation groups S1–S2/S3–S4/S5–S6/S7–S9 have2/2/2/3participants and equal fold weights. One selection seed20261012, epochs1–40, earliest minimum/tie. Final all-source seeds20261013/20261014/20261015. Adam0.001, batch64, no drop_last. Broad and shared-input complete pipelines; shared views concatenate through one backbone and average logits before cross entropy. The two pipelines have different normalization exposure/input/compute; no isolated spectral-sharing causal effect is identified.

Actual target roster:85Dreyer people, two acquisition runs each,6,800events,3,400per class. Known provider hard exclusions A17/A41 remain; five other provider flags retained. Eligibility/input fingerprint inventory is fixed before model outputs. Labels enter eligibility/mapping and final scoring only. No target fitting, target-derived centering, target BatchNorm updates, model/epoch/seed selection, threshold rescue or performance exclusion.

## Estimation

Per person/cell/seed, balanced accuracy is the equally weighted mean of left/right recall. Average the three seed-wise single-model BAs within each person, then give each of85persons equal weight. This is not ensemble accuracy, trial-pooled accuracy or85×3independent samples. Primary planned contrast: Broad mean-rank minus Broad mean-loss, in percentage points. Planned secondary contrasts: Broad fixed20 minus mean-loss; Broad fixed20 minus mean-rank; Shared fixed20 minus Broad fixed20. Retain estimates in either direction and null outcomes.

Paired-t intervals and two-sided p-values use participant difference vectors (df84), conditional on these source models and fixed source group. Report ordinary95% t intervals,20,000participant percentile bootstrap resamples (seed20261016), and three-contrast Holm p-values plus conservative98.333% secondary simultaneous intervals. These are exploratory summaries, not independent-cohort confirmation or equivalence/noninferiority tests. Zero-variance identical pipelines are handled explicitly. Do not switch tests or choose a favourable seed/interval based on results.

Shared rank-minus-loss, selected-duration Shared-minus-Broad and architecture-by-rule interactions are descriptive/exploratory; they cannot replace the planned primary contrast. Per-seed/class predictions, mean-seed dominance≥0.95, below-chance scores and participant tails remain visible; failures never justify removing a person.

## Acceptance

Training counters, source folds, raw/input identities, selected durations, checkpoint owners/aliases and actual optimizer updates must pass separate source reconstruction before inference. Source weights/adapter/roster/runtime are publicly frozen before any target model output. All122,400nominal prediction rows (6,800events×18cells), immutable logits, labels, probabilities/argmax and unchanged model state are checked separately before statistics. Numeric verification describes different-code-path reconstruction, not third-party human review. Final artifacts include hashes, all cell/person results and explicit unknown-prior-exposure limitations. A runtime/GitHub write/readback failure blocks success; no frozen outcome is edited to improve publication claims.
