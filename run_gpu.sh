#!/usr/bin/env bash
set -euo pipefail
export CUBLAS_WORKSPACE_CONFIG=:4096:8

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"
mkdir -p logs
exec > >(tee -a logs/q5_gpu.log) 2>&1

echo "[$(date --iso-8601=seconds)] Starting cloud setup and Q5 continuation."
if [[ ! -x "$PROJECT_ROOT/.venv-cloud/bin/python" ]]; then
  python3.12 -m venv "$PROJECT_ROOT/.venv-cloud"
fi
source "$PROJECT_ROOT/.venv-cloud/bin/activate"
bash setup_gpu.sh
python scripts/run_eegnet.py \
  --config configs/q5_e001_eegnet.json \
  --data-dir data/raw \
  --output-dir results/Q5-E001 \
  --device cuda \
  --resume
python scripts/validate_eegnet_run.py results/Q5-E001 --reference outputs/Q4-E001
echo "[$(date --iso-8601=seconds)] Q5 training and independent receipt validation finished."
