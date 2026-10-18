# Reproducibility and frozen evidence

## Versions and scope

This manuscript update uses the completed `paper1_source_expansion_18ch_dimensionless_eligible_v3_20261018` experiment. The immutable result snapshot is commit `040956085499ed788948de0d5a09cddd9eabca56`, directory `research_runs/ELIGIBLE_V3_RESULTS_20261018`. Executed code content corresponds to public commit `0539379578818b3d71f995192e5e8a81cf4d5aef`; the result directory also contains byte-identical executed code, locks, configuration and registries under `indexed/provenance/`.

The current manuscript branch is `paper/p1-plos-evidence-update-20261018`. An immutable manuscript commit or tag should be cited from the actual final Git record after validation and publication; no unpublished tag or DOI is implied. Historical 19-channel analyses and earlier submissions remain separate. This 18-channel dimensionless experiment is not a continuation of their numerical table rows.

## Inspect the public frozen inputs to this manuscript

From the repository root, verify the original saved-result archive without importing study modules, loading model files or accessing EEG:

```bash
python3 - <<'PY'
from pathlib import Path
import hashlib
import zipfile
p = Path('research_runs/ELIGIBLE_V3_RESULTS_20261018/evidence/paper1_expansion_results.zip')
assert p.stat().st_size == 21240637
assert hashlib.sha256(p.read_bytes()).hexdigest() == 'df8fdc4a43139acb4236ead749b74736a5bedaea6d8606c3bcc69234755fe02f'
with zipfile.ZipFile(p) as z:
    assert len(z.infolist()) == 57
    assert z.testzip() is None
    for name in ('results/comparisons.csv', 'results/condition_summaries.csv',
                 'results/per_subject_metrics.csv', 'results/selection_freeze.json',
                 'provenance/study.json'):
        assert name in z.namelist()
print('PASS: frozen saved-result archive size, SHA256, member count and CRC')
PY
```

The indexed provenance and frozen ZIP are retained byte-for-byte. The compact S1 Data supplies the table and figure data used by the new manuscript. Figure/table presentation and manuscript export are editorial operations; no result is selected or recalculated by retraining a decoder.

## Saved-result reproduction layers

1. **Study design and identity:** inspect `indexed/provenance/study.json`, `source_registry.json`, `execution_identity.json`, the code manifest, eligibility manifest and input provenance. The eligible counts are S9: 2,592; S29: 14,590; S60: 33,183 distinct trials. The external roster comprises 85 participants with 80 trials each.
2. **Source-only checkpoint choice:** inspect `results/source_validation_curves.csv` and `results/selection_freeze.json` in the archive. There are 23,520 validation rows and 48 frozen selectors (3 levels × 2 pipelines × 8 rules). Selected epochs are part of the saved source-only decision record, not chosen from external scores.
3. **Participant-level endpoints:** `external_predictions.csv.gz` contains 979,200 neural rows; `csp_external_predictions.csv.gz` contains 61,200 conventional-model rows. Calculate both class recalls within each participant and final seed, then balanced accuracy and the smaller class recall. Average the seed-specific metrics over the three final seeds. Taking the minimum after averaging recalls or treating seeds as independent participants changes the estimand.
4. **Prespecified comparisons:** `comparisons.csv` and `paired_subject_differences.csv` report the primary comparison and all three secondary comparisons. Participant-paired t intervals use n=85 and df=84; 10,000 paired bootstrap resamples use seed 20261016. The secondary p values form a single three-test Holm family. Confidence intervals are pointwise.
5. **Independent numerical evidence:** `audits/external/audit_results.json` and `audit_external.py` document 1,179 checks and zero failures. The separate integrity/source-selection audit and 108-trajectory off-Pod verification document archived payload hashes, source aggregation and selector choices.

The archived external-audit script preserves its original absolute evidence paths. It is supplied as an audit record, not falsely advertised as a turnkey relative-path command. To rerun it in a new workspace, a reviewer must reproduce its documented `inputs/results`, `inputs/provenance` and evidence-package layout, and make any path-only adaptation explicitly in a separate copy. The original audit script and its recorded hash remain unchanged. Saved-result arithmetic does not require model loading or raw EEG.

## Full scientific reproduction is a distinct operation

The archived project requires Python 3.12 and the executed `uv.lock` / `pyproject.toml`, including PyTorch 2.8.0+cu128, torchaudio 2.8.0+cu128, Braindecode 1.5.1, NumPy 2.3.5, SciPy 1.17.0, pandas 2.2.3 and scikit-learn 1.8.0. Read the locked executed configuration rather than substituting a current library release. The data manifests identify the exact BNCI and Dreyer bytes and the Yang v5 archive/member identities. Provider licensing and access conditions apply. The GPU runtime, numerical backend and hardware identity also matter; version labels alone do not establish bitwise equivalence.

Full model reproduction additionally requires lawful provider data retrieval, the pinned processing and eligibility rules, participant folds, 90 validation plus 18 final trajectories, and the independently stored checkpoints. No training command is launched by this editorial package. Its publication-preparation scripts must not be treated as authorization to download EEG, start new scientific work or replace frozen results.

## Audit and archival boundaries

The 144 neural condition-by-seed evaluation outputs reuse 99 distinct selected checkpoints from 18 final trajectories; they are not 144 independent training runs. The 108 neural trajectories have 4,320 saved epoch checkpoints. Nine large checkpoint archives have off-Pod integrity reports but are not embedded in GitHub. The repository includes the nine conventional-model checkpoint files; reviewing their hashes does not require unsafe deserialization.

The audits distinguish archive/code integrity, source-selection arithmetic and saved-prediction arithmetic. They did not reprocess raw EEG, rerun checkpoint inference, inspect optimizer internals, conduct signal-level duplicate detection or establish every historical target-access event. The evaluation cohort is exploratory because prior exposure is uncertain. An independently verified model archive and full R2 retrieval remain separate operational tasks; neither a GitHub copy nor an audit report is a fabricated completion receipt for those tasks.

Raw recordings are not redistributed. Provider/version links and data/code licensing boundaries appear in `submission/Data_Availability.md`. Author-owned manuscript/derived outputs follow CC BY 4.0 and original software MIT, subject to the existing repository notices and third-party rights.

## Rebuild and validate the editorial delivery

Run from the repository root in an existing editorial environment with Matplotlib, NumPy, pandas, Pillow, python-docx and PyMuPDF. The document renderer also requires the existing LibreOffice executable named in its source; do not substitute these packages for the locked scientific runtime. These commands read saved result tables, never EEG or model checkpoints:

```bash
python3 research_runs/PAPER1_PLOS_REVISION_20261018/scripts/build_figures.py
python3 research_runs/PAPER1_PLOS_REVISION_20261018/scripts/export_manuscript.py
python3 research_runs/PAPER1_PLOS_REVISION_20261018/scripts/build_data_bundle.py
python3 research_runs/PAPER1_PLOS_REVISION_20261018/scripts/validate_delivery.py
python3 research_runs/PAPER1_PLOS_REVISION_20261018/scripts/package_delivery.py
```

The included S1 Data is an exact-copy small-table bundle with its own manifest. Its builder copies saved tables without a model operation. After any editorial source change, rebuild affected exports, rerun validation and regenerate the checksum/package inventory. A new export need not have the same DOCX/PDF hash because container metadata and timestamps can change; the recorded content and validation receipts bind the delivered artifacts.
