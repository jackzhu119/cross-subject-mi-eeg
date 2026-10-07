# Independent Q16 validation

Status: **independent_raw_and_saved_evidence_validation_passed**

No decoder fitting or new checkpoint inference was performed.

All 18 original files matched their frozen SHA-256 and byte counts. All 5,184 four-class trial identities and 228,096 channel-band rows were checked. The independent FFT calculation replayed all 31,104 C3/Cz/C4 trial-band pairs.

Maximum relative power difference: 1.85e-15; maximum absolute dB difference: 7.11e-15 dB. Tolerances were fixed at 1e-10 relative power and 1e-10 absolute dB to accommodate float64 detrending/FFT round-off; no fitted tolerance or arbitrary power epsilon was used.

All session, equal-session person, paired-channel laterality, artifact-stratum, and six descriptive correlation tables were recomputed. All 63 Q14 saved prediction files, 18,144 prediction rows, and 135 source-only fit manifests were checked without loading models or recomputing predictions.

This validation supports the fixed descriptive BNCI estimator and its output arithmetic. It does not prove absolute voltage calibration, resting-state recovery, an external physiological replication, a cortical mechanism, decoder causality, or inferential significance of nine-person correlations.
