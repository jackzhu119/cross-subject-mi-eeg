# Prespecified source selection and participant analysis

This is a prospective plan for a new experiment version. It contains no observed
EEG results. The prior Paper 1 results, including null and adverse comparisons,
remain historical evidence and are not overwritten by this package.

## Scientific comparison and task order

All five methods use the same architecture, eligible input arrays, source-person
partitions, class-balanced sampling schedule, number of optimizer updates, and
seed sets. The methods are `erm`, `groupdro`, `tail`, `consistency`, and
`tail_consistency`. The tail objective combines 0.5 times the mean group loss and
0.5 times the mean loss of the highest-loss half of the observed person/class
groups. It therefore keeps the loss scale comparable to the ERM baseline.
Consistency and the tail term are separately ablated. Source validation chooses
an epoch within the fixed training trajectory; it does not select a new
hyperparameter grid after examining held-out results.

The source registry contains nine BNCI and 51 Yang participants. Five outer
folds are constructed within each dataset using split seed 20261023. Each person
occurs in exactly one outer test fold. Within every outer training pool, a fixed
20% of people (rounded upward, separately within each dataset) form the inner
validation set. Each dataset retains at least two inner-training people.
Methods and seeds share the same person splits. A person's sessions never cross
these boundaries.

Five methods, five outer folds, and development seeds 20261031, 20261032, and
20261033 give 75 development fits. The inner criterion is weaker-class recall,
averaged first over people within each source dataset and then equally over
datasets. After all development fits and their saved outer evaluations finish,
the median of the 15 inner-selected epochs for each method is saved as its
source-selected final epoch. No outer score or target score enters that rule.

Fifteen final source fits use seeds 20261101, 20261102, and 20261103. These seed
values are distinct from the development seeds. All source people are used for
these fits. Every final fit runs the same 40-epoch trajectory. The final-epoch
checkpoint supplies the fixed-duration external comparison, and the already
selected epoch supplies a secondary source-selected comparison. These are two
checkpoints of the same fit, not two independently trained models. The Dreyer
participant list is the complete eligible external registry, expected to contain
85 people; missing eligible people require an explicit input correction rather
than silent filtering.

## Primary endpoint and statistical unit

For person *i* and seed *s*, define balanced accuracy as the mean of the left-
and right-hand class recalls. Define weaker-class recall W as the smaller of
those two recalls. Confusion counts from that person's sessions are combined
before computing each recall. W is calculated separately for each seed and then
averaged over the three seeds. Taking the minimum after seed averaging would be
a different endpoint and is not used.

The single primary comparison is `tail_consistency` minus `erm` on W in the
nested outer-source evaluations. The source estimand gives each dataset equal
weight and each person equal weight within that dataset, so Yang's larger
sample does not determine the overall result by participant count alone. All
60 source people contribute one held-out assessment per method and seed.

The fixed-40 Dreyer comparison on W is a registered exploratory external
evaluation. Prior use of Dreyer cannot be ruled out; the dataset is therefore
not represented as a new independent confirmatory cohort. Its participant
estimand uses equal person weights. The source-selected external checkpoint is
a secondary exploratory endpoint. Target labels are used only for scoring and
the documented event/class mapping, not for optimization, normalization fitting,
BatchNorm updates, epoch selection, or method selection.

## Uncertainty and multiplicity

The unit of paired inference is the person, after averaging that person's
seed-specific metric. Seeds do not multiply the sample size. The saved paired
differences receive a 95% percentile bootstrap interval using 10,000 replicates.
Source resampling is stratified by dataset and retains each dataset's observed
participant count, matching the equal-cohort estimand. External resampling is
over paired people. Intervals are conditional on the fitted models and observed
cohorts; they do not propagate all training-set uncertainty.

Two-sided paired sign-flip tests use complete enumeration for at most 16 people
and otherwise 100,000 Monte Carlo sign patterns with a plus-one correction.
These tests require exchangeable signs under the null. Dependence created by
shared training sets or cohort membership is not removed by a participant
bootstrap or sign flips. The resampling seed is 20261024 plus a deterministic
SHA256-derived domain/contrast offset, recorded in every output.

Within each reporting domain, the following fixed four secondary comparisons
form one Holm-adjusted family:

1. `tail_consistency` minus `groupdro` on W;
2. `tail_consistency` minus `tail` on W;
3. `tail_consistency` minus `consistency` on W;
4. `tail_consistency` minus `erm` on balanced accuracy.

The unique source primary test is reported separately. External families remain
exploratory, even when an adjusted p value is small. Source-selected and fixed-40
external results are not pooled into an inflated confirmatory family. The
software reports both effect direction and magnitude, pointwise confidence
intervals, raw p values, adjusted secondary p values, and counts of improved,
declined, and unchanged participants. It reports every method and every
prespecified comparison, including adverse and null results.

## Inputs, outputs, and resuming

Planning reads `config/study.json` and the prepared registry's metadata only.
`tasks.json` and `state/plan.json` record person splits and scientific identity
before any fit. Runtime-only heartbeat/checkpoint frequency changes do not
reset a scientific experiment. Changed input identities or scientific settings
require a separate experiment directory.

Source selection reads `outputs/runs/<task_id>/complete.json` and its
source-inner `best_epoch`. It saves `state/selection.json` and appends the 15
final tasks while preserving all 75 development task identities. Missing fits
leave the final phase pending; they do not trigger retraining of completed fits.

Statistical analysis reads saved per-person evaluation JSON only. It does not
open EEG, load model weights, perform inference, or start new fits. Each
reporting domain is calculated only when all registered methods, participants,
and seeds for that domain are complete. Its JSON and participant table are
saved under `outputs/analysis/`, together with input fingerprints. Unchanged
summaries are reused on later status ticks rather than rerunning resampling.
Evaluation failure is repaired from checkpoints and completed evaluation shards,
not by refitting a model. `outputs/analysis/summary.json` is the compact source
for the separate GitHub progress synchronizer.
