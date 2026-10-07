# Independent saved-evidence numerical review

passed_saved_evidence_numeric_review

Checked 261 displayed numerical cells and 422 named checks across 12 tables and 9 figures. Found 0 numerical discrepancies.

Recomputed PhysioNet person means/SDs/medians, Q15 seed-to-person means/recalls and participant SDs, Q16 signed hand descriptors and all six nine-person average-rank correlations. All match the manuscript within its displayed rounding. All 31 S1 rows, 16 S3 rows and 11 S2 contrasts match saved source tables.

Raw spectral replay was not performed in this second review; its existing validation covers 31,104 C3/Cz/C4 trial-band pairs. No new fits or inference occurred.

- Table 8 and Table S4: Displayed rounding alone determines tolerance; full source values remain in CSV/JSON. No n=9 descriptor uncertainty is inferred from decimal precision.
- Numerical reconstruction: Saved numeric arithmetic and audit receipt checks do not rerun model fitting, checkpoint inference, raw EEG spectral analysis, or new statistical hypotheses.
