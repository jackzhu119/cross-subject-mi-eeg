# Q5 EEGNet cloud run

This bundle keeps the existing BNCI2014_001 source code, fixed Q5 configuration, historical Q1–Q4 outputs, Q5 startup failure receipt, and every completed Q5 fold checkpoint. Q5 has not yet trained a fold. The Q5 output directory is `results/Q5-E001`; new experiment outputs stay under `results/`. Older exploratory outputs remain in `outputs/` as historical inputs and comparison data.

## Fixed environment

- Linux x86_64, Python 3.12
- PyTorch 2.14.0 with CUDA 12.6 wheels
- Braindecode 1.5.1
- Scientific Python package versions are pinned in `requirements-cloud.txt`.

The provided cloud dashboard screenshot showed a CUDA 13.2 / PyTorch 2.13.0 / Python 3.12 image with a V100S device. That image's CUDA 13.2 build may not support V100's Volta compute capability. `setup_gpu.sh` therefore installs the official PyTorch 2.14.0 CUDA 12.6 wheel, matching the local PyTorch version and retaining V100 support while also supporting RTX 4090 class devices. Device availability is checked on the server before training. This bundle has not been GPU tested locally.

## Start on the cloud host

Extract the ZIP, enter the `Q5_EEGNet_Cloud_Ready` directory, then run:

```bash
bash run_gpu.sh
```

`run_gpu.sh` creates an isolated `.venv-cloud`, installs the pinned environment, runs `check_gpu.py` on the actual remote CUDA device, resumes Q5 from completed fold checkpoints, downloads BNCI2014_001 into `data/raw/` if needed, and runs the independent Q5 receipt validator when all folds finish. Full console output is appended to `logs/q5_gpu.log`.

The launcher sets `CUBLAS_WORKSPACE_CONFIG=:4096:8` before CUDA execution so the fixed deterministic training setting can use CUDA matrix operations.

`run_gpu.sh` runs the GPU check after installation and before training. To run that check directly after setup:

```bash
source .venv-cloud/bin/activate
python check_gpu.py
```

The check prints the CUDA runtime and GPU model, allocates tensors on the device, and executes a small matrix multiplication. Run it on the Linux cloud host only.

## Resume behavior and saved files

The fixed experiment is nine subject-wise outer LOSO folds. Each fold has four source-subject-only inner fits for epoch selection and three final seeds, using the exact Q5 config already saved in `configs/q5_e001_eegnet.json`. `--resume` skips completed folds and leaves prior checkpoints in place. If an interruption happens within one fold, that fold is restarted into a numbered retry directory; all prior partial files are preserved. Completed fold results are merged into `results/Q5-E001/` after each fold.

The runner does not change the model, preprocessing, split, seed, epoch-selection rule, or metrics on CUDA. The CUDA device affects numerical execution. The saved config and provenance record the installed library versions and actual device; compare final numbers with awareness that CPU and CUDA floating-point kernels can differ slightly.

Important outputs include `status.json`, `trial_metadata.csv`, `fit_manifest.csv`, `learning_curves.csv`, `selection.csv`, `predictions.csv`, `per_subject_metrics.csv`, `confusion_matrices.csv`, `summary_by_seed.csv`, `folds/`, and `validation_report.json`.

The raw dataset is excluded from the ZIP. The server needs internet access on first run to download the public MOABB dataset; the MAT file hashes are checked against the existing Q4 baseline.

## Official package references

- PyTorch 2.14 CUDA and GPU architecture matrix: https://github.com/pytorch/pytorch/blob/main/RELEASE.md
- Official PyTorch CUDA 12.6 wheel index for Python 3.12 Linux x86_64: https://download.pytorch.org/whl/cu126/torch/
- Braindecode 1.5.1 installation and model API: https://braindecode.org/stable/install/install.html and https://braindecode.org/stable/generated/braindecode.models.EEGNet.html
- NVIDIA Ada compatibility guide: https://docs.nvidia.com/cuda/archive/12.6.3/ada-compatibility-guide/index.html
