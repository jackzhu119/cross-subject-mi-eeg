# Dreyer transport and parser preflight

Checked on 13 October 2026. **PARTIAL_SOURCE_ROUTE_VERIFIED_NO_TARGET_PERFORMANCE.** This is a transport, header, annotation and unit-conversion preflight. It is not the new independent scientific evaluation and does not release its gate. No target model output, decoder score or task-signal feature was computed. This audit started no model fits; source-only CPU fitting elsewhere in this research project is a separate operation.

## What was actually acquired and checked

The versioned [NEMAR nm000250 v1.0.5](https://data.nemar.org/nm000250/v1.0.5/) manifest and nontruncated Git tree `f77f8859a84df42bd775920d288261260b2236db` name individual files with content SHA-256 hashes. For the fixed subset below, Git-annex pointer blobs were independently authenticated with Git blob SHA-1, their content keys were checked against manifest size/SHA-256, and full downloaded file bytes were checked against those keys. Seven small provider metadata files were authenticated using their manifest Git blob hashes.

| Fixed subset | Bytes | Full SHA-256 |
|---|---:|---|
| `sourcedata/sub-01/eeg/sub-01_task-R1acquisition_eeg.edf` | 14,805,604 | `a678fe6d37e0496eb381dcac6b877b047d02dfffc659ae4cfc38226f4850e185` |
| `sourcedata/sub-01/eeg/sub-01_task-R2acquisition_eeg.edf` | 14,805,604 | `e956c7f68aca5912c2cb9dbd75ea76bdfff6e2cca0ba1071ae70f08aa4aab5bf` |
| `sub-1/ses-0/eeg/sub-1_ses-0_task-imagery_acq-R1acquisition_run-0_eeg.bdf` | 18,684,674 | `9f0bf9b7947d803847f7b5633c4c9b1c26fd306e4872cd249b3c5cc71021491a` |

The subset totals **48,295,882 bytes** and stays outside Git at `/workspace/mi-eeg-redesign-data/dreyer_subset/`. Only the first two acquisition runs of person 1 and a format-conversion counterpart were downloaded. No other person's signal file was acquired in this preflight. Original provider and collection-performance tables were not read for target selection.

## Counts, labels, units and event mapping

Both EDFs have 450 one-second records at 512 Hz. Their 33 signals comprise 27 EEG, three EOG, two EMG and an EDF annotation signal. The BDF counterpart contains the same 27 EEG labels plus annotations; the auxiliary EOG/EMG channels are absent. Header physical units for the EEG are `uV`; physical minima/maxima and digital calibration coefficients were explicitly parsed to SI volts rather than assuming that native integers were volts. BIDS `channels.tsv` uses `V`, a reader-level convention rather than an independent acquisition calibration certificate.

All 19 proposed shared real electrodes are present exactly once: `Fz, FC3, FC1, FCz, FC2, FC4, C5, C3, C1, Cz, C2, C4, C6, CP3, CP1, CPz, CP2, CP4, Pz`. Matching these names does not prove the physical acquisition order is correct for the documented A17/A41 faults, and those exclusions remain unchanged.

Each of the two EDF acquisition runs has 20 `769` left-hand cue annotations and 20 `770` right-hand cue annotations. For the first run, EDF events map to BDF `left_hand`/`right_hand` annotations and TSV `value=1/2` with matching order and class counts. The maximum observed onset difference is **0.000047 seconds**, below the declared half-source-sample tolerance **0.0009765625 seconds**. This reflects decimal/sample encoding agreement, not verification of hardware-to-display latency.

For signal calibration conversion, only the first one-second prefix was interpreted, ending before the earliest class cue (7.998 seconds for EDF R1, 8 seconds for EDF R2 and 7.998047 seconds for the BDF counterpart). All 19 EDF-to-BDF physical signal differences stayed within one BDF quantization step, approximately **1.00653 × 10⁻⁹ V**. The largest observed prefix difference was approximately **5.031 × 10⁻¹⁰ V**. These are file-format scale checks on a precue prefix; no task features, class-amplitude comparison, fitted transformation, model inference or decoder efficacy was evaluated. They do not establish instrument calibration or correctness of all task samples.

## The 520-versus-522 manifest issue is localized

The source EDF mirror declares 87 people and 520 runs. The only missing run identifiers are `sub-59` R5online and R6online. All **174 R1/R2 acquisition files (2 × 87)** are declared. The pinned MOABB adapter independently documents the same person-59 exception. Therefore the missing later online runs do not remove a file from the proposed first-two-run cohort. A file manifest is not proof that all 174 files have been downloaded, hash-checked or passed signal QC.

The complete acquisition-only EDF manifest totals **2,515,343,396 bytes** (about 2.343 GiB), providing a feasible selective transport route without the full original 27.5 GB archive. The final new primary population remains only an upper bound of 85 people / 6,800 expected trials after the predeclared A17/A41 exclusions, pending whole-cohort QC and author prior-use confirmation. This preflight does not change those objective rules.

## Provenance and unresolved boundaries

The NEMAR root BIDS dataset is explicitly described as a derivative generated using MOABB. Its `sourcedata/README.md` separately claims that the mirrored EDF contents are unchanged relative to files retrieved by MOABB from its upstream source; the matched source-provenance entries and file hashes were checked. Thus it is precise to say **an authenticated upstream EDF mirror subset and its BDF counterpart were checked**. It is not precise to say **original Zenodo GDF acquisition bytes were checked**. The original Zenodo archive/GDF route remains unverified, and the GDF-to-EDF equivalence is not demonstrated by the EDF-to-BDF prefix comparison.

The upstream OSF manifest, README, dataset description and channel list were also fetched as small metadata documents. The OSF description uses BIDS `DatasetType=raw`; that denotes data-stage organization and does not prove byte identity to the original GDF distribution. Its channel list classifies auxiliary EOG/EMG names as EEG. The preflight therefore uses authenticated names and explicit auxiliary exclusions, rather than trusting that generic type field. Original-person demographics were not established: the NEMAR participant table repeats age 29 for every row, consistent with an aggregate mean placeholder rather than independently verified individual ages.

The derivative EEG sidecar records a 5–35 Hz Butterworth `HardwareFilters` field, while the descriptor and MOABB acquisition metadata state that raw signals had no hardware filters and describe the participant-specific online filter separately. This conflict remains recorded. Neither the file header nor the one-second roundtrip establishes whether original samples had online processing applied. The proposed primary runs include side-specific sham feedback, rather than a feedback-free physiology window. Reference metadata says left earlobe; this is not a physical re-reference certificate.

The following gates remain closed: authentication/equivalence to original GDF signals; full-cohort hash/header/event/units and signal-only QC; trial/person duplicate audit; raw-run-specific quality-flag handling; author confirmation of no earlier Dreyer analysis/model-result use; and commitment of all source-selection/target-inference rules before target decoder outcomes are examined. Public provider metadata cannot substitute for the author's prior-use confirmation. These documents must not be cited as a completed confirmatory replication.

## Reproduction and evidence

Run the bounded preflight with:

```bash
python research_runs/REDESIGN_SOURCE_SELECTION_20261012/scripts/check_dreyer_metadata.py --download-subset
```

Without `--download-subset`, the script checks saved metadata and any already cached subset; it does not acquire missing raw files or recheck live Git-annex pointers. The online receipt is [evidence/dreyer_access_metadata_receipt.json](evidence/dreyer_access_metadata_receipt.json). The separate `scripts/validate_dreyer_metadata_preflight.py` replays byte hashes, reparses headers and precue physical samples, checks event correspondence and rejects a truncated record file. It passed 12 checks, with zero failures, recorded in [evidence/dreyer_metadata_replay_validation.json](evidence/dreyer_metadata_replay_validation.json). Raw signals are excluded from the repository.

The upstream adapter was saved at exact MOABB revision `7819d70e3b40d7c7311f60d2084a3182e622de49`, recorded alongside the source URL and SHA-256. Its upstream BSD 3-Clause license and copyright notice are retained beside the snapshot; these third-party bytes are not relicensed as author-owned code. OSF metadata retrieval has a separate receipt; the original upstream source identity and preprocessing boundaries must not be strengthened beyond the documents actually inspected.

## Future complete acquisition-mirror transport

The new `scripts/acquire_dreyer_runs.py` has been run **only in its default metadata dry-run mode**. That run verifies the fixed 174-file plan without opening absent signals, downloading data or starting a worker. Its receipt is `evidence/dreyer_acquisition_dry_run.json`. A separate 12-case gate test suite checked refusal of an altered manifest, reordered channels, an unconfirmed author template, absent author evidence, an abbreviated/unmatched registration commit and numeric `0` substituted for a confirmed Boolean. The default CLI and blocked-download path were tested with network/raw access forbidden. No real author confirmation was created by those software tests.

Future download instructions, **only after the author has truthfully completed the prior-use declaration and the access plan is committed**, are:

```bash
python research_runs/REDESIGN_SOURCE_SELECTION_20261012/scripts/acquire_dreyer_runs.py \
  --download \
  --author-declaration /path/to/actual-author-prior-use-declaration.json \
  --registration-commit FULL_40_CHARACTER_COMMIT_SHA \
  --receipt /workspace/mi-eeg-redesign-data/dreyer_acquisition_audit.json
```

`AUTHOR_DREYER_PRIOR_USE_TEMPLATE.json` contains unresolved `null` values and `AUTHOR_ACTION_REQUIRED`; it cannot pass as a confirmation. The code verifies that the actual declaration matches the pinned manifest and explicitly distinguishes the documented metadata/precue preflight from earlier scientific use or decoder-result inspection. It also verifies that `DREYER_DATA_ACCESS_PLAN.json` is byte-identical to the supplied Git commit. It does not authenticate the author's identity or turn their declaration into proof of participant uniqueness.

Explicit future `--audit-cache` follows the same gates but reads existing cached files rather than downloading. Both modes hash-check every file and parse headers, class events and a precue unit prefix; a failure stops the audit rather than silently discarding a difficult person or overwriting a corrupted file. Even a successful 174-file metadata audit leaves `full_cohort_signal_qc_complete`, `original_gdf_equivalence_verified` and `confirmatory_model_evaluation_authorized` false. It does not train or predict, and does not inspect task-signal features. Retaining/excluding trials still requires a separately frozen signal-only QC contract.

For later source/target parser integration, EDF digital calibration yields **physical µV** in the exact common19 order; conversion to SI volts is `×10⁻⁶`, not native integers treated as volts. The planned `core_source_inputs.transform_context19` interface expects physical µV. Cue `769/770` maps to labels `1/2`; cue sample indices derive from the authenticated 512 Hz annotation convention and require the full-cohort annotation/sample agreement gate. Filtering, reference, resampling, epoch extraction and model inference are not implemented by this transport launcher and must use their separately committed scientific contract.
