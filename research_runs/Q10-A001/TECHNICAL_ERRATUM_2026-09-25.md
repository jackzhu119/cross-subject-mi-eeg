# Q10-A001 technical erratum: Q8 metadata line endings

Q10-A001 did not produce a model or target prediction in its first cloud attempt.
The 2026-09-24 14:21 UTC `q10_geometry` stage stopped before output initialization
because the matrix's frozen Q8 `trial_metadata.csv` SHA256 was calculated on a
Windows CRLF working tree (`6f507d27460279e0fab65acd2ff6e75e19085e5902c2cca320c00b8e6c9a338b`),
whereas Git stores and checks out the same CSV on Linux with LF bytes
(`3fdf0cb8e7dc86112bf7abc56f007dfdcc09f47de2d69362eb8a857bb8392214`).

The repair canonicalizes **only CRLF/LF representation** to the matrix's CRLF
form before checking the declared hash. It still rejects unexpected carriage
returns, requires the same SHA256 after canonicalization, checks the exact
5,184 trial identities against newly loaded BNCI metadata, and checks all 18
raw MAT file hashes. It does not change data, features, labels, folds, seeds,
models, metrics, the predeclared matrix, or any Q10-E001 result. A new unit
test confirms identical LF/CRLF content passes while altered values fail.

The failed cloud receipt and log remain in `results/Q10-QUEUE/`; they must not
be rewritten. This code-only repair is recorded before the first Q10-A001
target prediction. Q10-A001 remains **not run** until a new cloud attempt
completes and its independent validator passes.
