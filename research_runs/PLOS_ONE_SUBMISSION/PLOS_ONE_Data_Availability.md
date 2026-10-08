# Data Availability — English submission text

Original EEG recordings are available from their third-party providers: BNCI2014_001/BCI Competition IV data set 2a (https://www.bbci.de/competition/iv/ and https://bnci-horizon-2020.eu/database/data-sets), PhysioNet EEG Motor Movement/Imagery Database version 1.0.0 (https://physionet.org/content/eegmmidb/1.0.0/; doi:10.13026/C28G6P), Cho2017 (doi:10.5524/100295; https://gigadb.org/dataset/100295), and Lee2019/OpenBMI (doi:10.5524/100542; https://gigadb.org/dataset/100542). Access is governed by the respective providers' terms; no raw EEG is redistributed in this submission package. De-identified derived summaries, saved Cho2017/Lee2019 predictions and validation evidence are provided in S1 Data; supplementary methods and inventories are provided in S1 Appendix. The complete code and archived result files are publicly accessible at https://github.com/jackzhu119/cross-subject-mi-eeg/tree/0c7146895dc46850e4fe7db38bd69d9aea2b41c3. The exact manuscript source snapshot is 0c7146895dc46850e4fe7db38bd69d9aea2b41c3; Q15 validated results are identified by bc48b257eb44f412ad069f50d0f1a72a33c3c520, and the Q16 pre-power freeze by 050e01b028aaab8e3d745934b13b2d17e9bb0a7a. The reproduction guide and source manifests identify the saved inputs underlying the figures and tables. No archive DOI is claimed.

## Access and rights boundaries

S1 Data contains byte copies of frozen outputs, with per-file SHA-256 and source paths. Saved internal and PhysioNet results remain accessible in the immutable full repository snapshot and its experiment inventories; they are not re-estimated here. The study uses no private participant identifiers. Public accessibility is not itself an open-data or software license: no repository-level LICENSE was found in the inspected snapshot. The author must confirm permissions and apply an appropriate explicit license to original code/derived outputs if required before depositing an archive. Third-party recordings retain their providers' terms. These access links do not imply that every provider has the same license.

## More stable archive plan — not executed

After the author confirms licensing, deposit the source revision, derived-output package, metadata and checksums with Zenodo or another appropriate repository. Inspect the deposited files and actual assigned DOI before substituting it in the statement. GitHub tags identify frozen source; a DOI has not been registered for this preparation package.

## Key result paths

- Saved Q15 predictions: `results/Q15-EXTERNAL/Q15-E006/predictions.csv` and `Q15-E007/predictions.csv`.
- Q16 derived data and validation: `research_runs/Q16-P001-BNCI-20261006/`.
- Internal/PhysioNet saved-run paths and grain: `research_runs/PAPER_FINAL_20261006/tables/completed_experiment_inventory.csv` and the source reproducibility guide.
- Source final numbers: `research_runs/PAPER_FINAL_20261006/paper_numbers.json`.
