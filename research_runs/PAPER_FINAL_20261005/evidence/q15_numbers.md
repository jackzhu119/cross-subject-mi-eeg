# Independent reconstruction of Q15 paper numbers

The audit reads immutable Git blobs and saved probabilities. It performs no model fitting, checkpoint inference, checkpoint deserialization, or raw EEG loading.

Results branch head: `7af1a137e2676a018e1e880ab076de6cae4ce30b`. Verified scientific results commit: `bc48b257eb44f412ad069f50d0f1a72a33c3c520`.

| Cohort | Persons | Unique trials | Broad BA | Shared BA | CSP BA | Shared − broad, pp (95% CI) | Holm p |
|---|---:|---:|---:|---:|---:|---|---:|
| Cho2017 | 52 | 10,520 | 59.8237% | 58.3104% | 51.9904% | -1.5134 (-2.2490, -0.8045) | 9.9995e-05 |
| Lee2019_MI | 54 | 10,800 | 65.5123% | 65.7160% | 52.7685% | +0.2037 (-0.5154, +0.9691) | 0.60366982 |

Balanced accuracy is calculated after pooling declared sessions within a person, separately for each seed; deep-model seed means then receive equal person weighting. The primary paired contrast and all archived person confusion matrices, 20,000 bootstrap draws, sign-flip p values, and the two-cohort Holm correction reproduce within 1e-12.

The audit confirms 223 publication digest bindings at the verified result commit, 221 validator artifact bindings, 52 source artifact bindings and 10 frozen source artifact bindings. The publication snapshot of job_status.json is checked at its committed revision rather than incorrectly compared with the later final job status.

The archived cloud validator reports independent raw metadata, raw-to-epoch and frozen checkpoint prediction replays. Those operations are not repeated in this paper audit.

Original source fitting comprised eight inner deep fits, six final deep fits, and one CSP–LDA fit. Migration reused those 15 fits; it added no source fit and performed no target fit. Broad/shared selected training durations were 14/19 epochs.

Cho2017 comprises 10,520 retained trials: most persons have 200, but persons 7, 9 and 46 have 240. Seven model/seed variants per trial are repeated predictions rather than independent observations. Lee2019_MI comprises 10,800 trials in 108 sessions.

The complete benchmark is an adapter evaluation with calibration limitations. Raw physical voltage calibration, the original Cho hardware reference and hardware cue latency remain unverified. Completion does not establish physical Pod shutdown.

Person standard deviations, mean seed dispersion, class-specific recalls and sign counts are descriptive additions. They are not new predeclared confirmatory tests. Individual 95% bootstrap confidence intervals are not simultaneous intervals.
