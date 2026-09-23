# Q6 post-hoc target/source distribution analysis

This analysis reuses the exact Q6 preprocessing pipeline and the saved
source-only full-fold normalization receipts.

Important methodological boundary:

- Target-subject mean/std statistics in this analysis are POST-HOC diagnostics.
- They were not used to fit, select, normalize, or tune Q6.
- Q6 itself remains source-only.
- Applying the same affine source z-score to source and target does not
  mathematically eliminate target/source distribution shift.
- These statistics quantify how unusual each held-out target looks under its
  source-derived coordinate system.
- Associations use only nine subjects and are exploratory.
- S3 is a strong influential observation, so Pearson correlation must not be
  interpreted without the corresponding Spearman result and per-subject table.
