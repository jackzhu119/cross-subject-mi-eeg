# Cloud execution package: exploratory source-selection reliability

This package implements the locked 19-channel source-selection core on a **Dreyer2023 prior-exposure-unconfirmed exploratory cohort**. It is not a first-use independent confirmation. Historic Q1–Q16, submitted manuscripts, and earlier frozen data/code/results remain unchanged.

## Required server

Use a GPU Pod with **RunPod PyTorch 2.8.0 / CUDA 12.8**, Python3.11/3.12, one NVIDIA CUDA GPU, internet access and at least30GB usable working storage. RTX4000 Ada20GB is sufficient for the planned model/input dimensions; full GPU elapsed time has not been benchmarked here. Prefer a persistent `/workspace` volume so interrupted jobs retain state. The total running server quote (including billable resources) must be at mostUS$0.75/hour. The approved core budget is one totalUS$10 envelope, up to8hours from launcher entry, withUS$2 reserved. Installation, downloading, training, inference and backup share the wall-clock deadline. The program stops computation at the deadline; **it does not stop the Pod or its billing**. Stop the Pod manually in the provider console when completion/failure is reported, and keep the volume until backup is verified. Time spent running the server before entering the launcher or after worker exit is not measured by this program; stop any idle server promptly.

No RunPod API key is requested. No machine is purchased or launched by these scripts.

## Credentials

Only `GH_TOKEN` is mandatory for the default workflow. Create a GitHub fine-grained personal access token with access to `jackzhu119/cross-subject-mi-eeg` and **Contents: read and write**. It is entered at a hidden terminal prompt or provided as an existing environment binding. Never paste a token in chat or put its value into the command. Credentials are cached only in a private local filesystem with checked0700/0600 permissions, outside `/workspace`; they are not preserved when the container-local filesystem is lost. A shared RunPod volume that ignores chmod is not used for secrets.

Optional `--r2` prompts for `R2_BUCKET`, `R2_ENDPOINT`, `R2_ACCESS_KEY_ID`, and `R2_SECRET_ACCESS_KEY` and adds verified R2 evidence/checkpoint backup. It is not required to download the dataset. The default downloads the publicly pinned BNCI originals and NEMAR acquisition EDF mirror directly to the GPU server and validates hashes. Previously claimed R2 content or credentials are not assumed available. No Windows transfer is involved.

## Start

Use the immutable command in `RUN_INSTRUCTIONS_ZH.md`. It downloads this launcher at a fixed GitHub commit and passes the same revision with `--revision`. Enter the actual total hourly quote when asked, then the GitHub token; hidden input displays no characters. Once `DETACHED_WORKER_STARTED_NOT_SCIENTIFICALLY_COMPLETE` appears with job ID, the worker continues independently of the browser/local PC. This startup receipt does not mean training or scientific validation is complete.

Each job uses `research_runs/REDESIGN_CLOUD_20261013/jobs/<job-id>` inside the isolated checkout `/workspace/mi-eeg-cloud/code-<revision>`. Data/input arrays stay in `/workspace/mi-eeg-cloud/data`, outside Git. Results use a dedicated branch `redesign/run-<job-id>`; no main branch, old paper branch or old result is overwritten. The execution registration prevents repeated commands from silently launching a second budgeted job.

## Stage sequence and evidence

1. Verify actual CUDA arithmetic/runtime; verify code against immutable Git bytes; verify GitHub write and public byte readback before any fitting.
2. Fetch/reuse18 source originals and174 pinned EDF files; read all required real signals/events and reconstruct all frozen source/target inputs. Changes in hash, labels, eligibility or processed windows block execution. The roster remains85persons/6,800trials, A17/A41 excluded, no outcome-driven exclusions.
3. Publish the actual package/Python/CUDA/machine identity, runtime lock, budget and input/data receipts before fitting.
4. Train8 source-validation trajectories (40epochs), source-select mean-loss and mean-rank durations, then18 nominal final cells at three seeds. Identical architecture/seed/duration cells use declared owner checkpoints; actual fits can therefore be fewer than26. Extra40 grouping fits remain disabled. Source validation uses fixed2/2/2/3 groups and equal fold weights. Completed checkpoints/curves are periodically backed up; interrupted state remains local.
5. Separately reconstruct source splits/input identities, selector calculations, fit/update counts, checkpoint/alias hashes and final-epoch heldout-source CE. A failed audit blocks target inference. Freeze actual source models, roster and adapters at a public commit before inference.
6. Infer with fixed source models in eval mode, no target fitting, target-derived centering or BatchNorm updates. Score all18 nominal cells on the same locked trials and three seeds. Validate labels/coverage, raw logits, probabilities, argmax, checkpoint/state hashes and aliases separately, then compute the prespecified participant-level seed-averaged estimates and uncertainty. All adverse/null outcomes remain. Every result is exploratory; no confirmatory claim is opened by a small p-value.
7. Publish reports, per-trial model outputs, curves, models and receipts to GitHub and verify exact public bytes. Optional R2 performs full byte readback. Successful completion is reported only after scientific artifact validation and GitHub readback. API acceptance is not backup proof, and worker exit is not physical shutdown proof.

## Resume and failure

Use the same immutable launcher with `--resume <job-id>`, on the original machine and retained `/workspace`, within the original deadline. Completed fits are verified and reused. Active fits have batch state/RNG/optimizer counters; if an optimizer update may have happened without a committed state, automatic recovery blocks instead of silently repeating it. Resume does not allocate a new8-hour budget, change a seed or start another scientific job. A different Pod/UUID or missing private credentials requires review; this package does not claim automatic cross-account migration recovery.

`--reset-credentials` resets the private cache if the GitHub credential was rejected; combine with the printed job ID and `--resume`. Do not repeatedly start fresh jobs. Failure reports and local logs remain available. If repair will not be immediate, stop billable compute manually while retaining the volume.

## Validation limits

The delivered tests use mathematical fixtures for model/software behavior and authenticated real data for input reconstruction. The development environment has no CUDA GPU, so a full real-EEG CUDA fit, provider price/billing cutoff and live cloud-token authentication cannot be certified before the command runs on your server. Those are enforced/measured at launch. Software success is not a scientific experimental outcome. Original GDF equivalence, device calibration/electrode placement and cross-dataset person identity independence remain unverified; sham-display overlap remains a limitation. Earlier scientific conclusions are not upgraded by this package.
