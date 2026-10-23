# Paper1 inputs: download once, prepare once, then resume training

The school currently has no EEG data. Use the raw acquisition route below. The earlier eligible-v3 NPZ importer remains available when a verified cache already exists; it is not a requirement for a new machine.

## 1. Download on an approved data-transfer machine

Extract this complete package on a machine with internet access and enough storage, then run from its directory:

```bash
bash FETCH_DATA.sh --raw-dir /absolute/persistent/paper1-raw
```

The same command resumes incomplete transfers and skips completed file receipts. Set `PAPER1_FETCH_PYTHON=/path/to/python3` if needed. This stage needs Python 3.9+ standard library only, no Torch/SciPy, GitHub token or R2 credentials. Do not run a 68-GB archive extraction workload on `login1`; use an approved transfer machine. Training jobs never download raw data. Transfer the complete raw directory, including manifests and `.verified` records, to the school shared filesystem before launching compute jobs. Preserving timestamps avoids an unnecessary rehash on a later download resume; raw preprocessing always authenticates the files it consumes.

Reserve at least **100 GiB** for raw data, processed NPZ, memory-mapped NPY arrays, compressed transfer partials and normal working space. Source raw data total about 68.82 GB and external EDF about 2.52 GB. Model checkpoints/results require additional project storage.

| Dataset | Fixed native objects | Retained people / trials | Identity and download route |
|---|---:|---:|---|
| BNCI2014-001 | 18 MAT | 9 / 2,592 | Official BNCI URLs and their exact TU Graz MAT mirror, exact size/SHA256 |
| Yang2025 two-class v5 | 306 EEG/event BDF + 6 metadata | 51 / 30,591 | Official Figshare ZIP64 ranges, pinned directory and member layout; all 306 EEG/event files have frozen full SHA256; metadata have pinned CRC32 plus recorded full SHA256 |
| Dreyer2023 | 174 EDF | 85 / 6,800 | NEMAR nm000250 v1.0.5, exact size/SHA256; only canonical 302 to the exact hash-derived object at `nemar.s3.us-east-2.amazonaws.com` |

The Yang selected archive members are 68,044,344,823 uncompressed bytes; their compressed content is 43,981,251,776 bytes. The full 65.6-GB archive is not downloaded or claimed to have its published whole-archive MD5 verified. Each incomplete compressed member resumes by byte range; after decompression its exact size, CRC and frozen SHA are checked. Completed native files are not downloaded again. Dreyer excludes A17/A41 from analysis under the existing montage rule; its complete 174-object native inventory is retained. This is not a substitution of GDF or BIDS derivative BDF for the frozen EDF bytes.

Official sources: [BNCI](https://bnci-horizon-2020.eu/database/data-sets), [Yang v5](https://doi.org/10.25452/figshare.plus.22671172.v5), [NEMAR nm000250](https://nemar.org/dataexplorer/detail?dataset_id=nm000250). Yang is CC BY 4.0; retain provider attribution and original terms. The current official BNCI canonical URLs redirect to the same MAT basename at `https://lampx.tugraz.at/~bci/database/001-2014/`; this exact HTTPS mirror is allowed after public HEAD metadata verification. Acquisition uses public URLs, default TLS verification and existing network settings. Explicit HTTP denial and checksum errors stop that transfer with its files retained; no credentials, proxy bypass or unbounded retry is attempted.

All downloads ready: `raw/acquisition_status.json` has `ALL_RAW_DATASETS_READY`. The launcher's `hpcmi.acquire.quick_raw_ready(raw_dir)` checks manifest pins, file inventory and size only. It does not reread 71 GB on every submission. A one-dataset recovery is also available via `--dataset bnci`, `yang` or `dreyer`.

## 2. Preprocess offline in the allocated CPU job

The launcher uses the isolated preprocessing environment with NumPy **2.2.6** and SciPy **1.15.3**, not the environment used by another paper. The equivalent module command is:

```bash
/path/to/project/.venvs/preprocessing-cp312/bin/python -u -m hpcmi.raw_prepare --raw-dir /public/home/zhuziyuan/projects/paper1-hpc-methods/raw --cache-dir /public/home/zhuziyuan/projects/paper1-hpc-methods/cache --output /public/home/zhuziyuan/projects/paper1-hpc-methods/data
```

`vendor/eligible_v3` preserves the original preprocessing, eligibility and clock code byte for byte; `VENDORED.json` lists original paths/hashes. `config/hpc_filter_bank18.json` is a separately identified HPC numerical profile linked to the archived filter-bank SHA. Only the runtime/profile metadata changed. Every hexadecimal SOS/zi coefficient, channel, crop, sampling rate, event rule and normalization rule remains identical. New arrays are recorded under the new numerical profile; they are **not asserted to be bitwise identical** to arrays built using old NumPy 2.3.5 / SciPy 1.17.0.

The inherited rules use 18 genuine common channels, CAR18, broad 8–30 Hz / mu 8–13 Hz / beta 13–30 Hz views, frozen SOS/zi and odd padding 27, 160-Hz resampling and a 320-sample window. Each view/channel is temporally centered and divided by the same trial's broad-view RMS. No population normalization is fitted. Yang's established label-eligibility/clock handling and marker-relative [2,4)-second window are preserved; no labels, absent onsets or physiological timing are inferred. Dreyer is designated exploratory external evaluation.

Preparation saves one person at a time and emits a 30-second heartbeat. On interruption, rerun the same launch command: completed person receipts are checked by identity/stat and reused. A published NPZ without its final receipt is reverified, not recomputed blindly. The final NPZ-to-NPY conversion is similarly person-resumable. Files are published through same-directory temporary files, file `fsync` and `os.replace`; no hard links, `renameat2` or directory-fsync startup gate is used.

## 3. Existing eligible-v3 cache route (optional)

Copy `config/input_sources.example.json` and replace directories with actual NPZ locations; then run:

```bash
python -u prepare_data.py --sources /path/input_sources.json --output /path/paper1-data
```

The actual old NPZ keys are `X`, `y`, `metadata_json`, `audit_json`, and the `dataset`, `subject`, `session`, `run`, `trial_id` columns. `X` must be finite float32 `[trials,3,18,320]`; `y` must be integer binary labels. The old audit's array/metadata SHA, montage, rate, views and single-trial normalization are verified once per imported person. The importer never filters, selects extra trials or edits the old cache. Dataset roles are fixed explicitly: BNCI and Yang are source; Dreyer is external. Paper3 channels, trial limits, seeds and model files are not used.

## Prepared output and training interface

`data/manifest.json` contains schema version, preprocessing ID, shape/rate, scientific fingerprint and person entries. Each person has `X.npy`, `y.npy`, `trial_ids.json`, `sessions.json`, original metadata and audit. IDs are `bnci__BNCI001`, `yang__Yang2C001`, `dreyer__A01`, etc.; original physical trial IDs are retained. Evaluation shards use the original `session/run` identities. Registry construction reads only the manifest and file stats, not target EEG. Arrays open lazily when the corresponding person is requested.

```python
from hpcmi.data import Registry
registry = Registry('/path/paper1-data')
registry.ensure_source(registry.source_ids)
person = registry.load_person(registry.source_ids[0])
# person['X']: read-only float32 memory map [N,3,18,320]
# person['y']: read-only int64 memory map [N]
# person['trial_ids'], person['sessions'], person['dataset'], person['id'], person['role']
```

Completed import receipts bind original file stats and input SHA. Restart checks completed file sizes/mtimes; it does not repeat full-library hashing. Preserve prepared timestamps when copying a prepared directory. Modified input, output or configuration stops reuse and preserves the old version. Actual new hardware/library bitwise equivalence requires separate evidence; these tests verify the new execution path and retained numerical contract, not old-result equivalence.
