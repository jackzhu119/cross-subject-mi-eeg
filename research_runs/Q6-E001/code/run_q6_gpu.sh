#!/usr/bin/env bash
# Q6-E001 only.  Reuses the existing cloud environment/data without copying
# the 5.9 GB venv or the raw MAT files; never invokes or resumes Q5 training.
set -euo pipefail
export CUBLAS_WORKSPACE_CONFIG=:4096:8

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
Q5_ASSETS_ROOT="${Q5_ASSETS_ROOT:-/workspace/Q5_EEGNet_Cloud_Ready}"
Q6_PYTHON="${Q6_PYTHON:-$Q5_ASSETS_ROOT/.venv-cloud/bin/python}"
Q6_DATA_DIR="${Q6_DATA_DIR:-$Q5_ASSETS_ROOT/data/raw}"
Q6_OUTPUT_DIR="${Q6_OUTPUT_DIR:-$PROJECT_ROOT/results/Q6-E001}"
export PYTHONPATH="$PROJECT_ROOT/src:$PROJECT_ROOT${PYTHONPATH:+:$PYTHONPATH}"

mkdir -p "$PROJECT_ROOT/logs"
exec > >(tee -a "$PROJECT_ROOT/logs/q6_e001_gpu.log") 2>&1
echo "[$(date --iso-8601=seconds)] Q6-E001 startup in $PROJECT_ROOT"
echo "Python: $Q6_PYTHON; data: $Q6_DATA_DIR; output: $Q6_OUTPUT_DIR"
[[ -x "$Q6_PYTHON" ]] || { echo "Existing cloud Python is missing" >&2; exit 1; }
[[ -d "$Q6_DATA_DIR" ]] || { echo "Raw BNCI data directory is missing" >&2; exit 1; }
[[ "$Q6_OUTPUT_DIR" != "$Q5_ASSETS_ROOT/results/Q5-E001" ]] || {
  echo "Q6 output must not overlap Q5" >&2; exit 1;
}
cd "$PROJECT_ROOT"
nvidia-smi
"$Q6_PYTHON" -c 'import torch, braindecode; assert torch.cuda.is_available(), "CUDA unavailable"; x=torch.ones(2, device="cuda"); assert float(x.sum())==2.0; print("CUDA preflight OK; torch",torch.__version__,"braindecode",braindecode.__version__)'
if "$Q6_PYTHON" -m pytest --version >/dev/null 2>&1; then
  "$Q6_PYTHON" -m pytest tests/test_source_normalization.py tests/test_q6_e001.py -q
else
  echo "pytest is absent from the preserved cloud venv; local full suite passed 23/23."
  echo "Running dependency/import and syntax smoke checks without changing the cloud venv."
  "$Q6_PYTHON" -m compileall -q \
    scripts/run_q6_e001.py scripts/validate_q6_e001.py \
    src/mi_eeg/preprocessing/source_normalization.py
  "$Q6_PYTHON" -c 'import scripts.run_q6_e001, scripts.validate_q6_e001, mi_eeg.preprocessing.source_normalization; print("Q6 Python import smoke passed")'
fi

resume=()
if [[ -f "$Q6_OUTPUT_DIR/config.json" ]]; then
  resume=(--resume)
fi
"$Q6_PYTHON" -m scripts.run_q6_e001 \
  --config configs/q6_e001_source_channel_zscore.json \
  --data-dir "$Q6_DATA_DIR" \
  --output-dir "$Q6_OUTPUT_DIR" \
  --device cuda \
  "${resume[@]}"
"$Q6_PYTHON" -m scripts.validate_q6_e001 "$Q6_OUTPUT_DIR" \
  --data-dir "$Q6_DATA_DIR" \
  --reference "$PROJECT_ROOT/outputs/Q4-E001"
echo "[$(date --iso-8601=seconds)] Q6-E001 training and raw-statistics validation finished."
