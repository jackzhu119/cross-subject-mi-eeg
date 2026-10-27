# Source composition × training objective: frozen follow-up protocol

Scientific version: `paper1-composition-objective-v2-20261027`. Machine-readable settings are in `config/study.json`; generated participant and trial identities are frozen in the new project's `state/plan.json`, `tasks.json`, and `state/trialsets/` before fitting.

## Research question

Does the effect of a participant–class tail-risk objective change when the source cohort composition changes, under a fixed unique-trial budget and the same optimization schedule? The experiment also measures how the full available source data alter this relationship. This follow-up was designed after inspection of the earlier experiment; its hypotheses and contrasts are fixed before the new fits, and the earlier results remain available.

The design combines a source-composition factor, an available-versus-matched unique-trial factor, and two training objectives. A weighted CSP–regularized-LDA reference uses the same source-trial whitelists. The result can distinguish empirical patterns attributable to these controlled choices; it does not by itself identify a physiological mechanism or isolate participant count from provider identity.

## Data and common evaluation

Reuse the completed prepared registry from the original school project. It contains BNCI9 and Yang51 as sources, and Dreyer85 as external metadata. No preprocessing parameters are re-estimated. The common input has broad, mu and beta views with 18 channels and 320 samples per trial. Source labels and original trial IDs define all new training whitelists. External signals or labels are not consulted to construct pools, budgets, hyperparameters, seeds, stopping rules, or contrasts.

Reuse the original five outer `test_ids` groups, which partition all 60 source participants. Every condition evaluates the same outer-test people, including Yang people for S9-only training and BNCI people for Yang-only training. For each fold, training consists of its selected pool minus these common test people. There is no inner validation set and no epoch selection. After development, all prespecified final tasks train their full selected source pool and evaluate Dreyer85. Dreyer has prior project exposure, so this is an exploratory external evaluation rather than a new blind confirmation.

## Source conditions and trial budgets

| Pool | Global source membership | Trial-support regimes | Distinct cells |
| --- | --- | --- | ---: |
| S9 | 9 BNCI | all; matched is the identical explicit alias | 1 |
| Y51 | 51 Yang | all, matched | 2 |
| S60 | 9 BNCI + 51 Yang | all, matched | 2 |
| S29r01–r05 | 9 BNCI + 20 Yang, five frozen subsets | all, matched for each subset | 10 |
| Total | | | 15 |

Each S29 subset independently selects four Yang participants from each of the five common outer groups, giving 20 Yang globally and 16 Yang in any development training fold. Selection uses the five frozen `subset_seeds`, without scores or outcomes. Subsets may overlap; they are not independent replication cohorts. Pool membership is unchanged between all and matched regimes.

In the all regime, retain all eligible trials of each training participant. In the matched regime, define the class-specific unique-trial budget as the sum of available trials of that class among BNCI participants outside the common outer test fold. The prepared BNCI input provides 144 trials per class per participant. Final matched training therefore contains 1,296 trials per class, or 2,592 total unique trials.

For a mixed source pool, assign exactly half the class budget to each cohort; distribute each cohort's budget as evenly as possible among its selected people, with a frozen seeded remainder allocation. For a single-cohort pool, distribute the entire budget among that pool's people. Select unique physical trials without replacement using a stable seed derived from `trial_subset_seed`, phase, fold, cell, participant and class. Store selected indices and original IDs with their SHA256. All objectives and training seeds share the same cell/fold support. S9 all and matched are one identical input and fit identity, not two independent observations.

This matched design is **fixed-budget source-composition substitution**: adding Yang within the budget replaces some BNCI trials. It is not a pure augmentation with each original participant's trial count held fixed. Full-data cells separately measure the observed effect when additional available trials are retained.

## Neural models and fixed compute

Use the existing compact EEGNet implementation: `F1=8`, `D=2`, `F2=16`, temporal kernel 64, dropout 0.25. Adam learning rate is 0.001, weight decay 0; AMP is off. Each fit completes 40 epochs × 128 updates = 5,120 optimizer updates. The endpoint is fixed regardless of evaluation outcomes.

Each batch selects four distinct participants, two classes per participant and 16 trials per class: 128 physical trial samples and eight participant–class groups. Mixed pools select two participants from each cohort; single-cohort pools select four from that cohort. Trial draws are with replacement from each fixed participant–class whitelist, including when more than 16 trials are available. The unique-trial budget describes the eligible support, not the number of distinct draws in a batch. The shared implementation forwards all three source views in one batch, with broad-view logits supplying the supervised loss; source-view BatchNorm behavior is held constant between objectives. Evaluation uses the broad view, model evaluation mode, and unchanged weights/BatchNorm buffers.

Let the eight group-mean cross-entropies in a batch be \(\ell_g\). ERM minimizes their mean. TAIL minimizes

\[
L_{TAIL}=0.5\,\operatorname{mean}_{g=1}^{8}\ell_g
          +0.5\,\operatorname{mean}(\text{largest four }\ell_g).
\]

This is a batch-level tail objective over eight observed groups; it is not an estimator of population CVaR over every source participant–class group. It isolates the prespecified tail mixture from consistency or GroupDRO terms. Development seeds are 20261111–20261113; final seeds are 20261121–20261123. The participant-subset seeds, trial-subset seed and analysis seed are separately fixed in `study.json`.

## Classical reference and task totals

The deterministic broad-view reference uses trace-normalized trial covariance, four CSP components, fixed 0.1 covariance shrinkage and fixed 0.1 regularized LDA shrinkage. Cohort weights are equal, people are equally weighted within cohort, and classes are balanced. It shares each neural condition's source/trial whitelist, with no tuning on test people. It is a separately specified reference, not a claim of identity to the old CSP implementation or equal computational cost to neural fitting.

| Family | Development | Final | Total |
| --- | ---: | ---: | ---: |
| Neural: 15 cells × 2 objectives × 3 seeds | 450 across 5 folds | 90 | 540 |
| CSP–regularized LDA: 15 cells, deterministic seed 0 | 75 across 5 folds | 15 | 90 |
| All planned tasks | 525 | 105 | 630 |

All tasks are frozen upfront. Final model fitting does not use development scores to choose methods, cells or hyperparameters; the task list orders development before final fits within each family. A failed development task does not cancel independent final tasks; no final choice depends on development scores.

## Outcomes and prespecified contrasts

For each held-out participant, pool its session predictions and compute left recall, right recall, balanced accuracy \(BA=(R_L+R_R)/2\), weaker-class recall \(W=\min(R_L,R_R)\), and cross-entropy. Compute W per participant and seed before averaging seeds. For any S29 comparison, average the five subset-specific participant/seed outcomes first; five overlapping subsets do not multiply the evaluation sample size.

The primary source contrast is the matched-budget interaction

\[
I_i=[W_{i,S60,TAIL}-W_{i,S60,ERM}]
    -[W_{i,S9,TAIL}-W_{i,S9,ERM}].
\]

Average the three development seeds within participant, then average participant effects within BNCI and Yang and give these two cohort means equal weight. Positive I means the TAIL increment is greater under S60; negative I means it is smaller. Use a two-sided paired test and report the effect in percentage points with its interval.

The following nine source secondary comparisons form **one Holm-corrected family**:

1. Matched S60 − S9, ERM, W.
2. Matched TAIL − ERM, S60, W.
3. All-trial counterpart of the primary interaction, W.
4. S60/ERM all − matched, W.
5. Matched primary interaction using BA.
6. Matched mean-S29 − S9, ERM, W.
7. Matched S60 − mean-S29, ERM, W.
8. Matched Y51 − S9, ERM, W.
9. Matched S60 − Y51, ERM, W.

Evaluate the corresponding primary plus nine secondary contrasts on Dreyer as a separate **Holm-10 exploratory family**. Source significance does not license an uncorrected external significance search. All cells, both cohorts, five fold effects, five subset effects/ranges, and classical results remain available as planned descriptive analyses. No additional algorithm-superiority test family is inferred from the classical reference.

Use the fixed analysis seed, 10,000 participant-bootstrap replicates and 100,000 paired permutation replicates. Source bootstrap is stratified by cohort with equal-cohort aggregation; external aggregation is equal participant weight. These intervals/tests are conditional on the frozen pools, trial caps and fitted models. Shared training sets create dependence that participant resampling does not eliminate, and the five fold effects are also reported descriptively. An interval crossing zero is uncertainty about a difference, not evidence of equivalence or absence of effect. Preserve null, adverse and positive outcomes with their exact contrasts; no result-dependent omission or new contrast selection.

## Execution and evidence

One school Slurm job requests one node, two GPUs, 24 total CPU cores and 128G total memory in `hpc_gpu`. It schedules independent single-GPU fits using assigned `CUDA_VISIBLE_DEVICES`; it is not synchronous two-GPU DDP. Reuse the existing compatible GPU environment and prepared registry; do not download packages or data inside a GPU fit.

Checkpoints persist model, optimizer, objective/sampler state, epoch/step, random states and enabled AMP state. Periodic saves retain two generations on shared home storage. Completed tasks are skipped; unfinished tasks resume their existing checkpoints. Evaluation session shards are keyed by model identity and resume separately, so interrupted evaluation does not trigger retraining. USR1 requests a save and requeue where supported; explicit cancellation does not automatically resurrect a job. Transient GitHub synchronization failures retry independently of training. True data, numerical or identity errors remain visible with their original tracebacks and checkpoints.

The new experiment has independent outputs and preserves the old plan, results, failures and submission materials. The protocol, task/trial hashes, runtime records, predictions, complete records and statistical summaries together define its auditable output.
