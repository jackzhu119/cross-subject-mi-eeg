# Delivery verification — 23 October 2026

This is a code/protocol verification record, not a result from the proposed EEG experiment.

| Check | Actual outcome |
|---|---|
| Integrated unit/behavior suite | 82 tests passed, 3.684 seconds; `unit_tests.txt` |
| Native-rate preprocessing tests | 3 tests passed, 0.057 seconds; `preprocessing_tests.txt` |
| Synthetic end-to-end execution | 1 test passed, 1.110 seconds; 25 development + 5 final tiny CPU jobs, one update each; `end_to_end.json` |
| Synthetic forward/backward/save/restore smoke | Passed on CPU; no GPU verification claimed |
| Isolated preprocessing installation | Actual offline installation of the two pinned official wheels succeeded; repeat setup reused its receipt |
| Official download endpoints | HEAD: BNCI302→TU Graz200; NEMAR200. Yang range metadata: 407,291 bytes in two Range requests, all 312 selected members and pinned central-directory SHA matched. No EEG member body downloaded. See `public_download_metadata.json` and `yang_live_metadata.json` |
| Final resource-allocation adjustment | Two targeted scheduler tests passed after giving preprocessing the known one-GPU partition allocation; no scientific code change |
| Shell syntax | Bash syntax check of all package shell entry points passed |
| Frozen original preprocessing | Vendored original file SHA values checked; separate HPC filter profile preserves all numerical coefficients and scientific rules |

The training tests used Python **3.12.14**, PyTorch **2.5.1+cpu**, NumPy **2.2.6** in an isolated local QA environment. The preprocessing tests used Python **3.12.14**, NumPy **2.2.6**, SciPy **1.15.3** in a different isolated CPU environment. These are not the school's Python3.12.3/CUDA execution environment.

The integrated suite covers atomic two-generation checkpoints, full optimizer/RNG/sampler restoration, all five loss functions, signal forwarding, cancellation precedence, denied requeue, duplicate submissions, failed-task isolation, source/target role separation, frozen source-only selection, complete evaluation references, all result directions, dependency isolation, download partials/hash rejection, and GitHub failure isolation.

The end-to-end test uses deterministic synthetic arrays and a deliberately tiny test-only model/configuration. It exercises actual CPU gradient updates and the production stage interfaces. Its 30 mini updates are QA activity, not EEG fits, evidence of scientific improvement, or additions to a historical task ledger. The formal configuration remains 75 development +15 final tasks.

No school SSH/Slurm session was available. No A100 execution, driver compatibility, queue availability, school network download completion, or GPU timing was observed. The package schedules one synthetic GPU forward/backward/save/restore check after allocation and reuses a matching successful receipt. The first real data acquisition still must authenticate each complete input against its published/pinned inventory. No target EEG or prior model results were read for selecting this algorithm's coefficients.

The existing manuscript and Q1–Q16/frozen eligible-v3 outputs were not modified. New arrays explicitly carry a new NumPy/SciPy numerical-profile identity; old array hashes and failure evidence were not replaced or relaxed.
