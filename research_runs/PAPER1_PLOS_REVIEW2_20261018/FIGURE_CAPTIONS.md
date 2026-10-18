# Figure captions

## Fig 1. Frozen source-expansion design and evidence flow.

**A**, The nested source configurations contain nine BNCI2014-001 participants (S9), BNCI plus a fixed set of 20 Yang participants (S29), or BNCI plus all 51 eligible Yang participants (S60): 2,592, 14,590 and 33,183 eligible trials, respectively. **B**, One 18-channel processing recipe produces dimensionless spectral inputs using each trial's broadband root-mean-square amplitude. **C**, Five whole-participant validation folds and three seeds yield 90 trajectories and 48 source-only checkpoint choices. **D**, Three final seeds yield 18 complete trajectories at 5,120 updates each; S29/S60 assign half the training-sampling mass to each source cohort. The 144 selected outputs reuse 99 distinct checkpoints. **E**, Exploratory external scoring covers 85 Dreyer participants and 6,800 unique trials; event/class metadata determine eligibility and mapping, and ground-truth labels support scoring only. **F**, Source-integrity, selector-binding and saved-prediction arithmetic checks establish the archived evidence links; raw-signal reconstruction and checkpoint-forward replay fall outside this audit. Source data: `figure_data/Fig1_source_configurations.csv`; provenance: `figure_data/SOURCE_PROVENANCE.json`.

## Fig 2. All four frozen participant-paired external contrasts.

The primary contrast (filled circle) shows the 21.17-percentage-point increase in weaker-class recall from S9 to S60 under BROAD/tail-weaker-class-recall selection. Open squares show all three frozen secondary contrasts, including selector and S60–S29 comparisons. Points average 85 participant-paired differences after within-participant averaging over three seeds. Horizontal bars are pointwise, unadjusted 95% *t* confidence intervals conditional on the fitted trajectories. The primary *p* value is unadjusted; the three secondary *p* values form one Holm-adjusted family. Source data: `figure_data/neural_recomputed_comparisons.csv`.

## Fig 3. Participant-level improvement in weaker-class recall.

Weaker-class recall increases for 72 of 85 Dreyer participants under the S60 versus S9 BROAD comparison. Bars display every paired change in ascending order, including 10 declines and three unchanged observations (squares). The dashed line marks the frozen mean increase of 21.17 percentage points. Metrics are calculated within seed and then averaged across three seeds for each participant. This descriptive display retains original participant identifiers and plot order in `figure_data/Fig3_primary_participant_changes.csv`.

## Fig 4. External class coverage and balanced accuracy across source configurations.

**A**, Balanced accuracy; **B**, weaker-class recall; **C**, mean absolute left–right recall gap. BROAD and shared μ/β use source-only tail-weaker-class-recall selection; CSP with shrinkage LDA uses its fixed configuration. A/B show participant means and stored pointwise 95% *t* intervals (*n* = 85). Source expansion raises weaker-class recall while reducing recall imbalance: for BROAD, the mean gap falls from 62.01 percentage points at S9 to 31.38 at S60, with similar means at S29 and S60. Panel C is a post hoc descriptive decomposition, `2 × (balanced accuracy − weaker-class recall)`, calculated within seed and preserved by averaging; no extra interval or test is introduced. The comparison retains all three pipelines and concerns complete source configurations, including their selected checkpoints. Lines guide the eye. Source data: `figure_data/Fig4_descriptive_endpoints.csv` and `figure_data/Fig4_posthoc_absolute_recall_gap.csv`.

## Fig 5. All 48 frozen source-only checkpoint selections.

The matrix retains all eight selection rules across three source configurations and two pipelines. Numbers and shading encode source-selected epoch; the same epoch is applied to the three final seeds. The primary BROAD rule selects epochs 27, 5 and 5 for S9, S29 and S60 (outlined cells). Each complete trajectory used 40 epochs × 128 updates = 5,120 optimizer updates; evaluation uses the rule-specific checkpoint duration. Source data: `figure_data/Fig5_selected_epochs.csv`, matched to the frozen `selection_freeze.json`.

## Fig 6. Source-expansion gains in the additional paired analyses.

The additional S29–S9 BROAD comparison shows increases of 21.72 percentage points in weaker-class recall and 5.79 points in balanced accuracy. Within CSP with shrinkage LDA, S60–S9 gains are 13.82 and 5.25 points, respectively. These four comparisons were defined for this post hoc review after the original outcomes were known, then calculated together without changing selection rules or fitted models. Each contrast uses the same 85 participants and three-seed within-participant averages. Horizontal bars are pointwise, unadjusted 95% *t* intervals conditional on the fitted models; the four displayed *p* values form a separate Holm-adjusted family. The original frozen primary and secondary comparisons remain unchanged. Source data: `figure_data/Fig6_review2_posthoc_comparisons.csv`.

## Fig 7. Source-expansion gains at a common 20-epoch checkpoint.

At the fixed20 checkpoint, every displayed source expansion improves both balanced accuracy (**A**) and weaker-class recall (**B**) relative to S9. Bars show the three-seed mean paired difference for S29–S9 and S60–S9 under both BROAD and shared μ/β; numerical labels give the bar heights in percentage points. The 24 overlaid points show all three seed-specific cohort-mean differences, using the same 85 participants. All compared checkpoints represent 20 epochs and 2,560 optimizer updates, providing a common-duration descriptive control alongside source-selected comparisons. This post hoc display includes all eight fixed20 condition/endpoint combinations, rather than selecting the best checkpoint or seed; no additional interval or hypothesis test is introduced. Seed consistency is conditional on the same cohort and does not represent independent replication. The complete 68-row source-expansion inventory, including other selectors and negative differences, remains available in `figure_data/Fig7_complete_source_expansion_inventory.csv`; seed data: `figure_data/Fig7_fixed20_seed_differences.csv`.

## Figure-preparation assistance

ChatGPT assisted plotting-code development and revision of labels and captions. Figures were rendered from archived, audited numerical tables; Fig 4C is explicitly identified as a descriptive algebraic decomposition. The author is responsible for verification and final approval.
