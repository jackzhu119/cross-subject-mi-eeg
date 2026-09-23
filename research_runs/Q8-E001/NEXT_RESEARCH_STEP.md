# Research continuation after Q8-E001

First inspect:

1. `analysis/Q8_E001_FINAL_REPORT.md`
2. `analysis/Q5_vs_Q8_subject_comparison.csv`
3. `analysis/Q5_vs_Q8_paired_statistics.json`
4. `analysis/Q5_Q8_prediction_collapse_subject_means.csv`
5. `results/predeclared_selection.csv`
6. `analysis/validation_report.json`

Do not modify Q8-E001 after seeing target results.

Q8-E001 should be frozen after validation.

The next research decision depends on whether mean-rank:

- improves multiple held-out subjects;
- reduces very-early selected epochs;
- reduces class collapse;
- preserves strong Q5 subjects;
- or produces neutral/negative results.

Regardless of outcome, do not tune another source-selection rule on
Q8 target performance.

After interpreting Q8-E001, the project should normally transition
toward the predefined spatial-spectral representation stage, while
using a frozen training-duration protocol.
