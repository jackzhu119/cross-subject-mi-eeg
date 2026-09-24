# Research log — Q8 freeze and Q9 batch design

| Date | Question / action | Parameters and inputs | Result or issue | Next step |
|---|---|---|---|---|
| 2026-09-24 | Verify historical Q8 before planning spatial-spectral work | Public `main` commit `13421ef`; Q5/Q8 prediction rows; Q8 34-file SHA256 manifest | Independent recomputation agrees with Q5/Q8 mean BA and paired difference. S3+S8 account for 87.57% of total gain; S5 still has two zero-recall classes. Q8 report's sign-test denominator includes two ties; conventional tie-excluded p=0.015625. Q8 files remain untouched. | Keep Q8 frozen; cite the interpretation caveat. |
| 2026-09-24 | Design one-server Q9 batch | Same BNCI2014_001 LOSO subjects, seeds, source-only mean-rank selection rule, 40-epoch cap; proposed fixed mu/beta, source-fitted CSP/PCA, PSD, artifact and normalization controls | `PROTOCOL.md` and `Q9_BATCH_MATRIX.json` specify 558 deep and 18 shallow *planned* fits. No Q9 training, target prediction, or cloud GPU validation has occurred. | Implement resumable runner/validator, run source-only smoke test, freeze code/config hashes, then rent/run GPU instance. |

Q9 outcome fields intentionally remain blank until genuine computation and independent validation. The batch plan does not establish a publishable result by itself.
