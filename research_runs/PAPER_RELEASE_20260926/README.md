# Paper-stage execution packet (planning, not a result)

Status: `prepared_not_executed`. Based on `origin/main` commit `f99191b14b46589b058f3cb15d63b1f5f1b34639` as inspected on 2026-09-26. This packet does not change a frozen Q5–Q14 protocol, run an experiment, pass Q14 validation, or authorize a cloud batch. It is a release specification to review and freeze **before** new target outcomes are read. A validator of this packet checks internal consistency only; it is not a scientific validator of predictions.

## Evidence and decision order

1. Q14-E002R2 has a completion receipt for 109 external subjects, 4,918 unique trials, 34,426 prediction rows, 87 copied subjects, 22 newly inferred subjects, and zero target fits. The cloud supervisor nevertheless recorded `failed_stopped` because the independent validator compared twice-serialized probability CSVs with exact floating-point equality. The original failure and a numerical erratum remain public. The artifact-only audit's BA difference is provisional; it cannot be promoted to a validated external result until the full validator rereads all 327 checksum-verified EDF files in the matching runtime and passes. Do not retrain or repeat inference just to clear this gate.
2. Q12-E001/E002 and Q13-E001/E004/E005 are separate, post-hoc BNCI2014_001 mechanism studies. Their results must be called exploratory because existing BNCI target scores have been inspected. New conditions may not be chosen, stopped, or renamed from outer-target results. The runnable preparation matrix counts 378 Q12 deep fits and 837 Q13 deep fits. If 27 Q5-derived fits cannot be identity-verified for reuse, **Q13 stops**; a separately reviewed amendment could add 27 replacement fits (864), but the present runner must not silently do so.
3. Q15 is a **new prospective external-cohort family**. Audit Lee2019_MI and Cho2017 metadata, channels, cue timing, labels, licensing, files, and run inventory without scores. Freeze all branches and any new BNCI source model before a single new external prediction. Lee can test the exact Q14 3-second model only if the exact 22-channel/event/window contract is satisfied. Cho's documented 3-second task window cannot accommodate Q14's cue-relative `[0.5,3.5)` window as a like-for-like in-task test; a separate, shorter, metadata-driven `[0.5,2.5)` BNCI source freeze is specified. No model trained or selected using Lee/Cho data is part of zero-shot validation.
4. Q16 is a non-adaptive physiological plausibility analysis, not a model-selection stage. Use fixed pre-cue and task windows and all eligible subjects. Do not use target ERD/ERS, scalp topographies, or BA-defined groups to choose filters, exclusions, normalization, or models.
5. The [statistics plan](STATISTICAL_ANALYSIS_PLAN.md) defines subject-level inference, contrast families, effect sizes, uncertainty, and multiplicity. The [release gates](RELEASE_GATES.md) distinguish technical completion, independent validation, scientific interpretation, and Git publication.

## Incremental fit arithmetic

| Block | Mandatory new deep fits | Mandatory new shallow fits | Interpretation |
| --- | ---: | ---: | --- |
| Q14 R2 validator-only correction | 0 | 0 | Reuse 109 published subjects and all frozen checkpoints |
| Q12 source-only DG | 378 | 0 | Six conditions × (36 inner + 27 final) |
| Q13 heterogeneity | 837, or 864 if reuse fails | 0 | 81/108 selection + 648 source identity/quantity + 108 source session |
| Q15 Lee/Cho metadata audit and zero-shot inference | 0 | 0 | Inference has no target fitting |
| Q15 new 2-second BNCI source freeze, conditional on metadata | 14 | 1 | Two neural models × (4 source-only inner + 3 final); one CSP+LDA source fit |
| Q16 physiology and central statistics | 0 | 0 | Descriptive analysis, no classifier fit |

The already-prepared Q12+Q13 queue contains **1,215/1,242** new deep fits. If the prospective Q15 2-second source freeze is activated, the total is **1,229/1,256 deep + 1 shallow**. Optional strong baselines are Q11-A001 four-band CSP+LDA and affine-invariant tangent-space+LDA (**18 shallow CPU fits**) and only the ShallowFBCSPNet arm of Q11-E002 (**63 deep GPU fits**), not a model zoo. With both optional arms and the conditional Q15 freeze, the total is **1,292/1,319 deep + 19 shallow**. These are fit counts, not runtime or completed-work claims. Q14-E003 PhysioNet internal LOSO (conditionally `14N` deep + `N` shallow) is a distinct exploratory study and is **not** hidden in these totals.

## References

- [MOABB Lee2019_MI](https://moabb.neurotechx.com/docs/generated/moabb.datasets.Lee2019_MI.html): 54 participants, two sessions, 62 EEG channels at 1,000 Hz, left/right MI; its online MI test runs lack trial labels, so use labeled offline training runs only.
- [MOABB Cho2017](https://moabb.neurotechx.com/docs/generated/moabb.datasets.Cho2017.html): 52 participants, 64 EEG channels at 512 Hz, left/right MI with a 3-second task window.
- [PhysioNet EEG Motor Movement/Imagery v1.0.0](https://physionet.org/content/eegmmidb/1.0.0/); [MOABB PhysionetMI](https://moabb.neurotechx.com/docs/generated/moabb.datasets.PhysionetMI.html).

Dataset counts and timing above are documentation, **not local eligibility or electrode-intersection observations**. Any factual correction discovered in a metadata-only audit gets a dated, versioned amendment before outcomes; no silent edit to a frozen model or result.
