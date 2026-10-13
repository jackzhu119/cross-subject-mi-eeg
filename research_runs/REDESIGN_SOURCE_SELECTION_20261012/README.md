# Source-only selection reliability: research redesign work version

**Not submission-ready. No new independent target validation is claimed.**

Working title: *Reliability of source-only training-duration selection in motor-imagery EEG decoding*.

This branch, `research/source-selection-redesign-20261012`, preserves the original Q1–Q16 scientific artifacts and `plos-one-submission-v1.1`. It starts from historical revision `39ab4fe0492f4d2ab4c679c752634d3f74bb7bc8` and adds a separate research directory. It does not replace `main`, create a release/tag, submit a paper, or change the second research project.

## Current evidence

| Activity | Actually completed | What it does not establish |
| --- | --- | --- |
| Historical evidence audit | Byte/structured-file inventory; seven prediction reaggregations; schedule/statistic/Q16 arithmetic replay | Novel independent confirmation, universal absence of implementation error |
| Official source access | 18 BNCI files, 779,873,919 bytes, all original SHA-256 matches | Availability/authorization of R2: its read-only list returned Unauthorized |
| New source CSP | Public preanalysis; 9 LOSO + 1 all-source fits; 61.6512% LOSO BA, 63.0401% training resubstitution | New target validation or provenance recovery for an earlier unarchived diagnostic |
| Candidate target access | Three full files/48,295,882 bytes; one person's two acquisition runs, event/channel/unit pilot | Whole-cohort QC, original-GDF equivalence, no prior private use |
| New neural experiment | Config, gated source runner and software validation; inspect actual code receipts for tested scope | Completed scientific neural training: **0** new neural fits |
| New target performance | **0** predictions, **0** target fits | Confirmation, algorithm superiority, equality or physiology mechanism |

The current combined software run passed153tests without failures or skips; CPU tests do not certify a future GPU environment. The result of the technical delivery validation is scoped to the working package. Open scientific gates remain open even if file and software checks pass.

## Read the work

- [Main manuscript](REVISED_MANUSCRIPT.md), [editable DOCX](REVISED_MANUSCRIPT.docx), [review PDF](REVISED_MANUSCRIPT.pdf).
- [Supporting Information](SUPPORTING_INFORMATION.md), with [DOCX](SUPPORTING_INFORMATION.docx) and [PDF](SUPPORTING_INFORMATION.pdf).
- [Baseline audit](SCIENTIFIC_BASELINE_AUDIT.md), [literature/novelty review](LITERATURE_AND_NOVELTY_REVIEW.md), [hypotheses](RESEARCH_HYPOTHESES.md).
- [Locked conditional protocol](PROSPECTIVE_VALIDATION_PROTOCOL.md), [statistical plan](STATISTICAL_ANALYSIS_PLAN.md), [execution and cost plan](EXPERIMENT_EXECUTION_PLAN.md).
- [Dataset independence audit](DATASET_INDEPENDENCE_AUDIT.md), [transport preflight](DREYER_TRANSPORT_PREFLIGHT.md), [scientific validation](SCIENTIFIC_VALIDATION_REPORT.md).
- [Core differences](CORE_DIFFERENCES_FROM_SUBMITTED_V1_1.md), [change log](REVISION_CHANGELOG.md), [figures and numeric sources](figures/), [references](REFERENCES.md).

## Data and historical pointers

Raw EEG is not included. BNCI source: https://bnci-horizon-2020.eu/database/data-sets/001-2014/ and original description https://www.bbci.de/competition/iv/desc_2a.pdf. Familiar historical target providers: PhysioNet https://doi.org/10.13026/C28G6P, Cho2017 https://doi.org/10.5524/100295, Lee2019 https://doi.org/10.5524/100542.

Candidate Dreyer origin: https://doi.org/10.1038/s41597-023-02445-z and https://doi.org/10.5281/zenodo.8089820, CC BY 4.0. The separately qualified EDF/BDF route is NEMAR nm000250 v1.0.5; exact manifest, conversion evidence, licences and unresolved discrepancies are under `evidence/dataset_sources/`. Metadata checks are not proof of original raw-signal equivalence.

Original Q15 scientific result commit: `bc48b257eb44f412ad069f50d0f1a72a33c3c520`; scientific code `271af288a2f3863430ab80e3145c2dee9bd5571d`; original Q16 parameter freeze `050e01b028aaab8e3d745934b13b2d17e9bb0a7a` and result pointers remain in `SCIENTIFIC_BASELINE_AUDIT.md` and preserved original contracts. New CPU CSP preanalysis commit: `f35fb97a28d7ddeea6b87f92b4d0975a4a0ebece`; new run `cpu-csp-20261013T004218Z-2828deb4`. The working manuscript is not a substitute for those frozen scientific records.

## Reproduction and execution boundaries

From repository root, use a private Python environment and the recorded per-stage runtime versions. Source CSP raw files are cached outside the repository; downloaded raw data never passes through a Windows computer. Saved-output reviews need no raw download, model fit or prediction inference.

```
python research_runs/REDESIGN_SOURCE_SELECTION_20261012/scripts/cpu_csp_source_audit.py
python research_runs/REDESIGN_SOURCE_SELECTION_20261012/scripts/acquire_dreyer_runs.py
python research_runs/REDESIGN_SOURCE_SELECTION_20261012/scripts/train_source_selection_core.py
python research_runs/REDESIGN_SOURCE_SELECTION_20261012/scripts/infer_selection_core.py
python -m pytest research_runs/REDESIGN_SOURCE_SELECTION_20261012/tests -q
python research_runs/REDESIGN_SOURCE_SELECTION_20261012/scripts/build_work_artifacts.py
python research_runs/REDESIGN_SOURCE_SELECTION_20261012/scripts/validate_work_delivery.py
```

The first four commands are dry-run/blocked by default. Do **not** use `--execute` as a means to bypass missing data, source/code freeze, author exposure or funded-compute gates. No author declaration or payment authorization is fabricated. A source-only runner is not a complete target-inference or cloud-deployment automation. Read its actual dry-run requirements and the execution plan before provisioning.

The existing ten new CSP models and predictions are already archived; running its `--execute` again would create new source fits and is unnecessary for checking the present results. Model `.joblib` files belong to this explicitly recorded new run. Statistical tests use synthetic fixtures and saved scores, not target EEG fitting.

## Before proceeding

1. Author confirms whether Dreyer2023 has ever been used for model evaluation, including private work or the second project. A template with null/false values is supplied; silence is not confirmation.
2. Resolve complete target source/conversion/eligibility and duplication checks; freeze the final roster before target model outputs. If raw equivalence cannot be established, explicitly change the cohort claim to the qualified operational derivative before execution.
3. Complete independent code/runtime/source-input review and immutable public preanalysis readback. Keep actual fit and checkpoint counters separate from nominal cells.
4. Author explicitly approves a funded-compute ceiling after the source-only timing benchmark and live price are known. The proposed core ceiling is US$10; no spending has been authorized or incurred by this work.
5. Execute and independently validate the locked neural/target experiment; retain adverse/null outputs. Then revise the manuscript against actual results and obtain fresh author approval.
6. Select one journal only. PLOS ONE resubmission eligibility following the reported policy decision is unresolved. There is no newly created DOI, tag or release.
