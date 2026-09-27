# Q12 and Q14 evidence audit (snapshot: 2026-09-27)

This note records results already present on GitHub `main` at
`e70a07690646561135aa4b22d0bd9335a44c7412`. It is an analysis note,
not a new experiment, revised endpoint, or authorization to retrain.
Values below were checked against the committed subject-level tables and,
for Q14, independently recomputed from the committed trial predictions.
The unit of inference is the held-out person, **not** a seed or EEG trial.

## Completion and provenance

| Item | Evidence-backed status | Controlling records |
| --- | --- | --- |
| Q12-E001/E002 | Six source-only conditions complete; 216 inner and 162 final deep fits. Orchestration and scientific validation passed; the latter replayed all 162 final checkpoint predictions and checked 63 source-only transform receipts. Git publication receipt records commit `3bb54f4351088f3693b1b1d7f55f0771abf0f83f`. | `results/Q12-BATCH/batch_status.json`, `orchestration_validation.json`, `scientific_validation.json`, `publish_status.json` |
| Q14-E002R2 external inference | All 109 subjects were inferred under the **post-freeze, metadata-triggered R2 sampling-rate amendment**: 4,918 unique trials and 34,426 prediction rows (three seeds for each of two deep models plus one CSP arm); 87 prior subject outputs copied byte-for-byte, 22 newly inferred, 3 resampled, zero target fits. | `results/Q14-E002R2/external/completion_receipt.json`, `research_runs/Q14-E002R2/PROTOCOL.md` |
| Original Q14-R2 validator attempt | **Failed/stopped**, although inference had completed. It rejected second-serialized aggregate probabilities under an inappropriate exact-float comparison; this receipt is retained and must not be relabelled as a successful original run. | `results/Q14-R2BATCH/batch_status.json`, `research_runs/Q14-E002R2/VALIDATOR_ERRATUM_20260926.md` |
| Q14-E002R2V1 independent validation | **Passed** as a versioned, validation-only, cross-host portability attempt. It verified the 327 official EDF files and existing predictions, reconstructed the subject metrics, and added zero fits/inference rows. The validation GPU/packages were recorded separately from the frozen inference runtime. Git publication receipt records commit `215f4dea54488b364dc9a2bb50906c53c3ca7075`. | `results/Q14-E002R2V1/validation_report.json`, `results/Q14-R2PORT/batch_status.json`, `results/Q14-R2PORT/publish_status.json`, `research_runs/Q14-E002R2/VALIDATION_PORTABILITY_AMENDMENT_20260926.md` |

An earlier paper queue attempt also failed and remains visible at
`results/Q12-BATCH/paper_queue_status.json`; it does not supersede the later
complete Q12 batch and Q14 portable validation receipts. Do not infer that
every stage of that historical queue succeeded.

## Q12: source-only domain generalization on BNCI2014_001

All Q12 comparisons use the frozen four-class Q8-E001 broad EEGNet as the
reference, except GroupDRO, whose mandatory matched-batching control is
source-balanced ERM. The Q8 reference mean is **0.426698** subject-level
balanced accuracy (BA), recomputed from
`research_runs/Q8-E001/results/per_subject_metrics.csv` with `stratum=all`.
Q12 uses nine LOSO target subjects and three fixed final seeds per condition.
The table shows equal-subject means; paired differences average the three
seeds **within each person first**. All Q12 contrasts are exploratory because
BNCI2014_001 had been examined in prior stages.

| Q12 condition | Mean BA | Paired contrast | Mean Δ BA | Subject bootstrap 95% CI for Δ | Within-family Holm-adjusted exploratory p |
| --- | ---: | --- | ---: | --- | ---: |
| Source-pooled whitening | 0.443351 | vs Q8 | +0.016654 | [−0.003922, +0.036651] | 0.3594 |
| Source-balanced ERM | 0.431842 | vs Q8 | +0.005144 | [−0.007073, +0.017747] | 0.4766 |
| Source GroupDRO | 0.367348 | vs balanced ERM | −0.064493 | [−0.114712, −0.017876] | 0.1406 |
| Channel dropout | 0.410044 | vs Q8 | −0.016654 | [−0.045076, +0.006366] | 0.7617 |
| Gain perturbation | 0.434221 | vs Q8 | +0.007523 | [−0.003408, +0.018583] | 0.7617 |
| Channel dropout + gain | 0.409208 | vs Q8 | −0.017490 | [−0.050540, +0.009131] | 0.7617 |

The saved paired-difference file uses an exact two-sided sign-flip test and
subject bootstrap; the p-values above are corrected within the
source-only-DG and augmentation families. GroupDRO's unadjusted sign-flip
`p=0.046875` and unadjusted bootstrap interval suggest a potentially
harmful effect, but the family-adjusted `p=0.140625` does **not** establish
a family-wise 5% finding. The largest GroupDRO-minus-balanced-ERM losses
were S8 (−0.1979), S9 (−0.1493), and S1 (−0.1059); the direction is
heterogeneous, so this is a mechanism lead rather than proof that robust
optimization generally fails. Whitening and gain perturbation have positive
point estimates but intervals spanning zero. No Q12 condition has a
demonstrated corrected improvement over its declared control.

Seed variability is reported rather than choosing a favorable run. Across
the three fixed seeds, the equal-subject BA ranges from 0.4298 to 0.4608 for
whitening, 0.3588 to 0.3794 for GroupDRO, and 0.4248 to 0.4416 for gain
perturbation. The SD across the nine subject-level three-seed means is
0.1638 for whitening and 0.0903 for GroupDRO. At least one zero-recall
class occurs in 5/27 whitening subject-seed cells and 2/27 GroupDRO cells;
these descriptive counts are not a post hoc exclusion rule.

The numeric table was rechecked directly from
`results/Q12-BATCH/subject_level_metrics.csv` and the frozen Q8 table;
recomputed mean deltas match
`results/Q12-BATCH/paired_subject_contrasts.json` to floating-point
precision. Per-seed BA, class recall, zero-recall classes, and dominant
prediction shares are in
`results/Q12-BATCH/subject_seed_metrics.csv`. The unchanged protocol,
fixed source-only split/selection rule, and the pre-fit loader-key correction
are documented in `research_runs/Q12-PREP-20260926/PROTOCOL.md` and
`EXECUTION_AMENDMENT_BANDS_20260926.md`; that correction occurred before
any Q12 checkpoint or target prediction.

The descriptive [fixed-order subject heatmap](figures/q12_subject_delta_heatmap.png)
shows all nine paired effects for all six conditions, including harms and
near-zero effects. It is generated by
`scripts/paper_q12_heterogeneity_figure.py` from the saved paired contrasts;
its color and annotation units are BA percentage points. The GroupDRO row
uses balanced ERM as its comparator; the other rows use Q8. This figure is
not a multiple-testing or causal-mechanism result.

## Q14: frozen binary BNCI-to-PhysioNet transfer

The Q14 external population is PhysioNet EEG Motor Movement/Imagery Database
v1.0.0, all 109 subjects and imagery runs 4, 8, and 12. The binary task is
left versus right hand. The source models, contrast, seeds, epoch and channel
rules were frozen before external access; the R2 **rate harmonization** was
nevertheless amended after partial R1 external execution and must be
disclosed. Q14's binary BA cannot be directly compared numerically with
Q8/Q12's four-class BA.

| Frozen external model | Mean subject BA | SD across subjects | Median subject BA |
| --- | ---: | ---: | ---: |
| Broad EEGNet | 0.618146 | 0.125649 | 0.582345 |
| Shared μ/β EEGNet | 0.623879 | 0.129217 | 0.587286 |
| CSP4 + LDA | 0.544617 | 0.078985 | 0.520751 |

The **predeclared primary** shared-μ/β-minus-broad contrast is
**+0.005733 BA** (+0.573 percentage points). Its 20,000-resample
subject-bootstrap percentile 95% CI is **[−0.000967, +0.012416]**;
63 people favor shared μ/β, 43 favor broad, and three tie; the two-sided
exact sign-test `p=0.06446` excludes ties. The interval crosses zero and
the sign test does not reject at 0.05. The defensible conclusion is a
small positive point estimate **without established external superiority**.
For context only, broad and shared μ/β exceed CSP by +0.07353 and +0.07926
mean subject BA respectively; those comparisons are not Q14's primary
confirmatory contrast and should not replace it in the abstract.

Subject heterogeneity is substantial: shared μ/β BA ranges from 0.3933
(S36) to 0.9707 (S85), with median 0.5873. As an **exploratory diagnostic**
using a 10%/90% predicted-left-share threshold, 42/327 shared-model
subject-seed cells, 53/327 broad-model cells, and 46/109 CSP cells show
near single-class predictions. This threshold was not a frozen endpoint.
No single subject reverses the sign of the average primary contrast when
omitted (leave-one-subject-out mean Δ range +0.00486 to +0.00666), but
deleting the five most favorable subjects lowers the mean to +0.00199;
neither post hoc deletion is a replacement for the frozen analysis.

Across the three fixed deep-model seeds, broad's 109-subject mean BA is
0.6182/0.6131/0.6231 and shared μ/β's is 0.6231/0.6199/0.6286 in seed
order 20260924/25/26. Mean *within-subject* seed SD is 0.0416 for broad and
0.0375 for shared μ/β. All three seeds remain in the primary contrast; these
descriptive summaries cannot justify selecting the best seed.

The sampling-rate sensitivity is descriptive: S088, S092, and S100 were
native 128 Hz and deterministically resampled 5/4 after native-Hz
filtering/epoching; their mean primary Δ is +0.005139, versus +0.005750
for 106 native-160-Hz subjects. With only three rate-anomalous people,
this is not a powered subgroup conclusion. The Q14-E001 BNCI matched-binary
development stage had broad/shared/CSP mean BA 0.68210/0.67348/0.61535
across nine source subjects, but its sample, training set and acquisition
context differ; do not treat the numeric source-to-external gap as an
isolated causal effect of dataset shift.

The Q14 validator's saved outputs are
`results/Q14-E002R2V1/external/subject_seed_metrics.csv`,
`subject_metrics.csv`, `subject_primary_contrast.csv`,
`pooled_confusion_by_model_seed.csv`, and
`native_rate_sensitivity.json`. The immutable trial predictions are
`results/Q14-E002R2/external/predictions.csv`. An independent recomputation
from those predictions found exactly 34,426 rows, 4,918 trial IDs, 109
subjects, and all 763 subject/model/seed BA cells; maximum absolute
cell difference from the validator table was `1.11e-16`. Recomputing the
frozen subject bootstrap and sign test reproduced the report's primary
interval and p-value.

## Paper-safe interpretation and limits

1. Q12 supplies **exploratory, same-cohort** evidence that the tested
   source-only robustness interventions did not establish a corrected
   gain over their controls; GroupDRO has a notable adverse signal requiring
   independent follow-up. Negative results and all nine person-level
   contrasts must remain visible.
2. Q14 supplies a **passed, independent-dataset, zero-target-fit** external
   audit of already-frozen binary models, but not a positive primary
   superiority result. The R2 metadata-triggered amendment and later
   cross-host validation-only portability exception must accompany every
   strong external-validation claim. Neither is permission to change
   predictions or select a method using PhysioNet outcomes.
3. Four-class BNCI Q12 and binary PhysioNet Q14 address related
   generalization questions under different tasks, acquisition/reference
   conditions and class baselines. Their raw BA values must not be pooled,
   ranked as if interchangeable, or used to infer which single mechanism
   explains transfer.
