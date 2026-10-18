# Reproducibility of this editorial revision

Original manuscript: `cac26b4f818907323863d03e65293efcb5a4b5e2/research_runs/PAPER1_PLOS_REVIEW2_20261018`. Frozen result commit: `040956085499ed788948de0d5a09cddd9eabca56`; executed training code: `0539379578818b3d71f995192e5e8a81cf4d5aef`. The earlier scientific paths are unchanged.

This revision recomputes metrics from the two saved prediction CSV.GZ files; it does not read raw EEG, deserialize weights, rerun a decoder, or introduce new hypothesis tests. `scripts/analyze_saved_predictions.py` accepts `--source` and `--out`; its complete output is in S4 Data and `evidence/additional_descriptives`. The original 68 aggregate differences and all 85 primary W/BA differences are checked.

The reusable editorial builder reads `scripts/revision_spec.json`, copies the immutable source package, applies the text revision, re-renders identical figure values, and exports documents. Changes to figure fonts and format do not change their data. EPS uses standard PostScript Times/Symbol fonts; raster previews are for author review. The main document excludes image objects and has continuous line/page numbers.

All payload checksums are recorded in MANIFEST.sha256. Checkpoint archives remain described by the original public reproducibility evidence; this author package does not redistribute third-party raw recordings or claim new external-cohort confirmation.
