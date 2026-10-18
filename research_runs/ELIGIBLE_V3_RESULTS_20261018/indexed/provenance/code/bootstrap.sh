#!/usr/bin/env bash
# Start in the background; installs and outputs stay under the chosen task root.
set -Eeuo pipefail

P1_CODE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
P1_TASK_ROOT="${P1_ROOT:-/workspace/paper1_expansion}"
P1_WORKER_MODE="${1:-}"
mkdir -p "$P1_TASK_ROOT"
P1_TASK_ROOT="$(cd -- "$P1_TASK_ROOT" && pwd -P)"
export P1_ROOT="$P1_TASK_ROOT"

if [[ "$P1_WORKER_MODE" != "--worker" ]]; then
  command -v flock >/dev/null || { echo "This Linux image needs util-linux (flock)." >&2; exit 2; }
  if ! flock -n "$P1_TASK_ROOT/launch.lock" true; then
    echo "Paper1 is already running. Log: $P1_TASK_ROOT/run.log"
    exit 0
  fi
  nohup flock -n "$P1_TASK_ROOT/launch.lock" bash "$P1_CODE_DIR/bootstrap.sh" --worker \
    >> "$P1_TASK_ROOT/run.log" 2>&1 < /dev/null &
  P1_LAUNCH_PID=$!
  echo "Started Paper1 installer/trainer in the background (launcher PID $P1_LAUNCH_PID)."
  echo "Follow progress: tail -f $P1_TASK_ROOT/run.log"
  echo "Results: $P1_TASK_ROOT/runs/expansion18_v1/paper1_expansion_results.zip"
  exit 0
fi

trap 'P1_EXIT=$?; echo "Bootstrap stopped with exit $P1_EXIT. Inspect this log, then rerun the same command to resume." >&2; exit "$P1_EXIT"' ERR
export PYTHONUNBUFFERED=1
export CUBLAS_WORKSPACE_CONFIG=:4096:8
export UV_CACHE_DIR="$P1_TASK_ROOT/uv_cache"
export UV_PYTHON_INSTALL_DIR="$P1_TASK_ROOT/python"
export UV_PROJECT_ENVIRONMENT="$P1_TASK_ROOT/venv"
export UV_LINK_MODE=hardlink
export UV_HTTP_TIMEOUT=120
export UV_HTTP_RETRIES=5
export OMP_NUM_THREADS=8
export MKL_NUM_THREADS=8

command -v python3 >/dev/null || { echo "Choose a Linux RunPod image containing python3." >&2; exit 2; }
command -v nvidia-smi >/dev/null || { echo "An NVIDIA GPU Pod is required." >&2; exit 2; }
[[ "$(uname -m)" == "x86_64" ]] || { echo "The frozen environment targets Linux x86_64." >&2; exit 2; }
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv

mkdir -p "$P1_TASK_ROOT/tools"
python3 - "$P1_TASK_ROOT/tools/uv" <<'PY'
import hashlib, io, os, pathlib, sys, time, urllib.request, zipfile
path = pathlib.Path(sys.argv[1])
binary_sha = "0650696de7f403348e9dd617e1f65dc32147c106c40129138017efd8f0f01cc8"
wheel_sha = "b7e89798bd3df7dcc4b2b4ac4e2fc11d6b3ff4fe7d764aa3012d664c635e2922"
url = "https://files.pythonhosted.org/packages/38/16/a07593a040fe6403c36f3b0a99b309f295cbfe19a1074dbadb671d5d4ef7/uv-0.9.26-py3-none-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"
if not path.exists():
    last = None
    for attempt in range(5):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                data = r.read(23250202)
            if len(data) != 23250201 or hashlib.sha256(data).hexdigest() != wheel_sha:
                raise ValueError("Pinned uv wheel checksum mismatch")
            break
        except (OSError, ValueError) as e:
            last = e
            if attempt == 4:
                raise RuntimeError("Cannot fetch the fixed uv installer") from last
            time.sleep(min(2**attempt, 8))
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = [n for n in z.namelist() if n.endswith(".data/scripts/uv")]
        if len(names) != 1:
            raise ValueError("Unexpected uv wheel layout")
        binary = z.read(names[0])
    if hashlib.sha256(binary).hexdigest() != binary_sha:
        raise ValueError("Pinned uv binary checksum mismatch")
    temporary = path.with_suffix(".part")
    temporary.write_bytes(binary)
    temporary.chmod(0o755)
    os.replace(temporary, path)
if hashlib.sha256(path.read_bytes()).hexdigest() != binary_sha:
    raise ValueError("Installed uv differs from the pinned binary")
PY

"$P1_TASK_ROOT/tools/uv" --version
"$P1_TASK_ROOT/tools/uv" python install 3.12.12 --no-bin
cd "$P1_CODE_DIR"
"$P1_TASK_ROOT/tools/uv" sync --frozen --no-install-project --python 3.12.12
P1_PYTHON="$P1_TASK_ROOT/venv/bin/python"
"$P1_TASK_ROOT/tools/uv" pip check --python "$P1_PYTHON"

echo "Running numerical, scientific-contract and recovery checks before any training data transfer."
"$P1_PYTHON" selftest_data.py
"$P1_PYTHON" -m unittest discover -s tests -p 'test_*.py'
"$P1_PYTHON" selftest_training.py
"$P1_PYTHON" selftest_csp.py

echo "Starting the frozen source-expansion experiment."
exec "$P1_PYTHON" -u "$P1_CODE_DIR/p1_runner.py" --root "$P1_TASK_ROOT"
