#!/usr/bin/env bash
# Start only Q13-E001/E004/E005 and Q13-E006; never starts Q15.
set -euo pipefail

usage() {
  echo 'Usage: bash scripts/run_q13_cloud.sh --execute --publish --python /abs/.venv-paper/bin/python --data-dir /abs/BNCI_MAT' >&2
  exit 2
}

execute=false
publish=false
python=''
data_dir=''
while (($#)); do
  case "$1" in
    --execute) execute=true; shift ;;
    --publish) publish=true; shift ;;
    --python) (($# >= 2)) || usage; python="$2"; shift 2 ;;
    --data-dir) (($# >= 2)) || usage; data_dir="$2"; shift 2 ;;
    *) usage ;;
  esac
done
[[ "$execute" == true && "$publish" == true && "$python" = /* && "$data_dir" = /* ]] || usage
[[ -x "$python" && -d "$data_dir" ]] || usage
command -v setsid >/dev/null || { echo 'setsid is required on this Linux host' >&2; exit 2; }

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
# MOABB may otherwise prefer its NEMAR mirror even when the frozen BNCI MAT
# files are present. This provider choice is inherited by every child process.
export MOABB_DOWNLOAD_PROVIDER=upstream
"$python" "$root/scripts/q13_cloud_chain.py" --check-only \
  --python "$python" --data-dir "$data_dir"

release="$root/results/Q13-RELEASE"
mkdir -p "$release"
pid_file="$release/supervisor.pid"
log_file="$release/launcher.log"
if [[ -f "$pid_file" ]]; then
  read -r old_pid < "$pid_file" || true
  if [[ "${old_pid:-}" =~ ^[0-9]+$ ]] && kill -0 "$old_pid" 2>/dev/null; then
    old_command="$(tr '\0' ' ' < "/proc/$old_pid/cmdline" 2>/dev/null || true)"
    if [[ "$old_command" == *"scripts/q13_cloud_chain.py"* ]]; then
      echo "An existing Q13 release chain is running (PID $old_pid)." >&2
      exit 1
    fi
  fi
fi

PYTHONUNBUFFERED=1 nohup setsid "$python" -u "$root/scripts/q13_cloud_chain.py" \
  --execute --publish --python "$python" --data-dir "$data_dir" \
  >> "$log_file" 2>&1 < /dev/null &
new_pid=$!
printf '%s\n' "$new_pid" > "$pid_file"
sleep 8
if ! kill -0 "$new_pid" 2>/dev/null; then
  echo "Q13 chain exited during startup; inspect $log_file and batch_status.json." >&2
  exit 1
fi
echo "Q13 chain detached with PID $new_pid"
echo "Status: $release/batch_status.json"
echo "Log: $log_file"
echo 'Closing SSH/laptop does not stop this process; stopping the cloud instance does.'
