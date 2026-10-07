# Reproducibility guide — Q15 results and BNCI Q16 physiology

The paper has three verification layers: saved decoder-result arithmetic, original EEG/model replay already documented for Q15, and newly computed descriptive BNCI physiology. They are distinct forms of verification.

## Immutable inputs

| Role | Snapshot or artifact |
|---|---|
| Inspected final Q15 results | `7af1a137e2676a018e1e880ab076de6cae4ce30b`, `q15/run-20261005T050511Z-migration-from-r2-b82ad79b` |
| Verified Q15 scientific publication | `bc48b257eb44f412ad069f50d0f1a72a33c3c520` |
| Q15 scientific code | `271af288a2f3863430ab80e3145c2dee9bd5571d` |
| Q15 source-artifact base | `782d2d0070a50c37d13c8e9f1cab3b3b81bac4fc` |
| Q15 pre-fit freeze | `fc0e7d54006076bec7701064e1045034c02d06a4` |
| Q15 inference/statistics freeze | `2ad479f5bccb4f92cd6c77bc78a8ba9b620604c1` |
| Earlier paper delivery | `ac75a339c8db2861ff8e7d072e50690c79c602c4` |
| Reviewed 5 October paper assets | `e4d0303c39ab7104a99556cac23ae6175f03e091`; receipt committed at `124e1b02895b13657b11365d8360c2515800792b` |
| Current Q16 protocol, raw receipt and metadata gate | `research_runs/Q16-P001-BNCI-20261006/PROTOCOL.md`, `raw_source_receipt.json`, `metadata_audit.json` |
| Q16 pre-power freeze | `research_runs/Q16-P001-BNCI-20261006/preprocessing_freeze.json`; the commit is bound by `run_manifest.json` |
| Q16 outputs and independent validation | `research_runs/Q16-P001-BNCI-20261006/`; inspect actual executed manifest and verification coverage |
| Current paper branch | `paper/zero-calibration-q16-20261006`; the publication receipt fixes its delivered commit |

Q15's terminal scientific status is `completed_with_calibration_limitations`. Original source fits=15, migration new source fits=0 and target fits=0. The paper/Q16 stage performs no new decoder fitting or checkpoint inference. Publication readback establishes stored bytes; it does not establish physical server shutdown.

## Saved decoder arithmetic and paper exports

Retain the exact delivered revision and install the paper dependencies in a Python environment:

```bash
git clone https://github.com/jackzhu119/cross-subject-mi-eeg.git mi-eeg-paper
cd mi-eeg-paper
git checkout paper/zero-calibration-q16-20261006
cd research_runs/PAPER_FINAL_20261006
python -m pip install -r requirements-paper.txt
python audit_q15_numbers.py --repo ../.. --output .
python build_figures.py
python build_q15_figures.py
python build_q16_figures.py --analysis ../Q16-P001-BNCI-20261006
python build_content.py
python build_bibliography.py
python export_manuscript.py
python build_submission_variants.py
python validate_final_delivery.py
python package_final_delivery.py
```

For an immutable rerun, replace the branch name with the current publication receipt's exact paper commit. Preserve the delivered evidence and compare regenerated values with it before changing the archive. The final delivery report describes actual export checks. The ReportLab PDF is distinct from native TeX compilation.

The Q15 audit reaggregates `results/Q15-EXTERNAL/Q15-E006/predictions.csv` and `Q15-E007/predictions.csv`. Confirm 10,520/10,800 unique trials, 73,640/75,600 prediction rows, three-seed within-person averaging, Lee session pooling, equal-person cohort means, paired contrasts and the frozen two-cohort Holm correction. Rows, random seeds and sessions do not enlarge the participant sample size. This arithmetic audit reads no EEG/checkpoint and is narrower than original-data inference replay.

## Independent raw Q16 replay

Acquire the 18 official BNCI2014_001 MAT originals under the provider's terms. Use the file identifiers, byte counts and digests in `raw_source_receipt.json`. Private R2 copies were transport copies, not a new public source. The metadata auditor compares bytes with the previously persisted Q15 original-file receipt; it does not independently authenticate the official provider's checksum publication anew. Original EEG is not included in the manuscript archive.

From the repository root, use a separate output directory so the delivered power table and evidence remain intact. Replace the illustrative paths with real paths containing the exact originals:

```bash
python scripts/q16_metadata_audit.py \
  --data-dir /path/to/bnci-raw \
  --output /path/to/q16-recheck/metadata_audit.json

Q16_FREEZE_COMMIT=$(python - <<'PYQ16'
import json
from pathlib import Path
p=Path('research_runs/Q16-P001-BNCI-20261006/run_manifest.json')
print(json.loads(p.read_text())['freeze']['git_commit'])
PYQ16
)

python scripts/q16_bnci_analysis.py \
  --execute \
  --data-dir /path/to/bnci-raw \
  --freeze-commit "$Q16_FREEZE_COMMIT" \
  --output-dir /path/to/q16-recheck/power
```

The committed metadata gate remains the default power-execution gate. The replay verifies that bound code, protocol, metadata and original-file bytes match the pre-power freeze, and refuses to overwrite an existing `trial_power.csv.gz`. Read the delivered manifest's runtime versions when creating the replay environment. Unpinned paper-rendering dependencies do not establish bitwise equivalence across environments.

The power table has grain trial × EEG channel × frequency band: 5,184 × 22 × 2 = 228,096 rows. Eligibility distinguishes missing/invalid power from genuine zero dB change. Provider artifact flags remain annotations: the all-trial description is primary and the unflagged table is a sensitivity description. Four-class summaries include feet/tongue; hand maps/laterality and saved-score associations use 2,592 left/right trials.

Check `PROTOCOL.md`: zero-based MATLAB trial onset, cue=trial start+500 samples, baseline offsets [125,375), task offsets [625,1125), periodic Hann, 250-point FFT/segment, 125 overlap, linear detrending, density scaling, inclusive 8–13/13–30 Hz bins and trapezoidal integration. Average trial dB within session/hand, then weight the two sessions equally per person. Do not substitute log of mean powers. Laterality requires paired eligible C3/C4 trials and includes constituent absolute channel values. Native-numeric squared units and dB ratios do not establish new physical voltage calibration.

The independent verification report documents manually implemented FFT replay of all 31,104 C3/Cz/C4 trial-band pairs, complete saved-row/aggregation checks and six association checks. It does not claim independent raw-power replay for all 22 channels. From the repository root, run `python scripts/validate_q16_independent.py --execute --data-dir /path/to/bnci-raw --freeze-commit "$Q16_FREEZE_COMMIT" --run-dir /path/to/q16-recheck/power` after the separate-output replay above; the separate run directory preserves the original verification receipt. Baseline/task Welch estimates use one versus three correlated segments, so log-estimation bias remains a stated limitation. Descriptive Spearman values use n=9 saved Q14 binary source-LOSO scores; no p-values, favourable participant selection or decoder tuning were added. These saved decoder scores used three-second windows; Q16 uses two seconds.

## Original Q15 model replay

Official sources are [BNCI/BCI Competition IV 2a](https://www.bbci.de/competition/iv/desc_2a.pdf), [PhysioNet EEG Motor Movement/Imagery v1.0.0](https://physionet.org/content/eegmmidb/1.0.0/), [Cho2017](https://doi.org/10.5524/100295) and [Lee2019/OpenBMI](https://doi.org/10.5524/100542). Each source has separate terms and acquisition documentation.

Use the Q15 frozen scientific revision and `requirements-q15-runtime.txt` for decoder replay. It includes metadata audit, six-second context construction, fixed 21-channel CAR, native-rate filters, polyphase resampling, 320-sample crops, checkpoint inference and independent validation. The Q15 validator uses probability tolerances atol=10⁻⁷, rtol=10⁻⁶ and exact argmax agreement. Q16's unfiltered native sensor analysis is a separate representation.

Do not substitute Q14's 22×480 tensors, Lee `EEG_MI_test`/`smt`, changed event conventions, target-fitted normalization or continuous filtering through Cho class-concatenated chunks. Q14 and Q15 use separately frozen pipelines. Their comparative neural arms have differing selected durations; they are complete-pipeline contrasts, not isolated tests of weight sharing.

## Interpretation, licensing and archives

Q16 covers BNCI only. It does not establish external sensor-level physiology, cortical localization, a learned decoder mechanism, behavioral compliance or neural recovery during a nominal pre-cue baseline. Constant-gain invariance of a dB ratio does not solve reference, montage or cue-timing differences. Q15 voltage calibration, Cho acquisition reference and hardware cue latency remain unverified.

Use public result tables, protocols, code and receipts under the repository's actual LICENSE. Check each provider's current terms and citations separately; do not infer a common license or redistribute private transport copies. A DOI archive can be added after author, metadata and licensing review. No archive DOI or journal submission is claimed here.

## Editorial release verification without scientific reruns

The 7 October revision changes manuscript wording, reference metadata, schematic Figure 1 labels and export layout only. Run `validate_numeric_presentation.py` and `validate_final_delivery.py` in the paper directory to check saved numerical evidence and artifacts. `evidence/quality_update/protected_scientific_inputs.json` binds the prior scientific files. Do not execute the raw/model replay commands above merely to regenerate the manuscript.

The external duration designs use fixed source-validation groups S1–S2, S3–S4, S5–S6 and S7–S9 with equal fold weighting despite group sizes 2/2/2/3. No new grouping-sensitivity experiment is introduced. `release_plan.md` describes candidate-tag, archive and GitHub readback gates; source data are linked at their original providers and are not redistributed. Submission approval and a DOI remain separate author/deposit actions.

## Author confirmation and institutional correspondence

Final author review/approval, sole-author contribution, personal checking/revision, data-term checks and Github-only/no-other-journal history are author-confirmed. Correspondence: Jinyun Campus, Chongqing Medical University, No. 61, Daxuecheng Middle Road, Shapingba District, Chongqing 401331, China. Official university/campus/postcode evidence and the current IOP AI policy are in `evidence/author_finalization/`. ChatGPT/GPT-6 is author-reported; Codex code/figure/drafting uses are retained. No scientific result changes, new model execution, journal submission or DOI creation accompany these metadata updates.
