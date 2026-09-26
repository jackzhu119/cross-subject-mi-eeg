#!/usr/bin/env bash
# Launch Q14 validation -> Q12 -> Q13 independently of SSH, terminal, or laptop.
set -euo pipefail

usage() {
  echo 'Usage: bash scripts/run_paper_cloud.sh --execute --publish --python /abs/venv/bin/python --data-dir /abs/BNCI-cache --physionet-dir /abs/EDF-cache' >&2
  exit 2
}

execute=false
publish=false
python=''
data_dir=''
physionet_dir=''
while (($#)); do
  case "$1" in
    --execute) execute=true; shift ;;
    --publish) publish=true; shift ;;
    --python) (($# >= 2)) || usage; python="$2"; shift 2 ;;
    --data-dir) (($# >= 2)) || usage; data_dir="$2"; shift 2 ;;
    --physionet-dir) (($# >= 2)) || usage; physionet_dir="$2"; shift 2 ;;
    *) usage ;;
  esac
done
[[ "$execute" == true && "$publish" == true && -x "$python" && -d "$data_dir" && -d "$physionet_dir" ]] || usage

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
batch="$root/results/Q12-BATCH"
mkdir -p "$batch"
pid_file="$batch/paper_cloud.pid"
log_file="$batch/paper_cloud_launch.log"
if [[ -f "$pid_file" ]]; then
  read -r previous_pid < "$pid_file" || true
  if [[ "${previous_pid:-}" =~ ^[0-9]+$ ]] && kill -0 "$previous_pid" 2>/dev/null; then
    previous_command="$(tr '\0' ' ' < "/proc/$previous_pid/cmdline" 2>/dev/null || true)"
    if [[ "$previous_command" == *"scripts/paper_cloud_queue.py"* ]]; then
      echo "Existing paper queue is still running (PID $previous_pid)." >&2
      exit 1
    fi
  fi
fi

command -v setsid >/dev/null || { echo 'setsid is required on the Linux host' >&2; exit 2; }
PYTHONUNBUFFERED=1 nohup setsid "$python" -u "$root/scripts/paper_cloud_queue.py" \
  --execute --publish --data-dir "$data_dir" --physionet-dir "$physionet_dir" \
  >> "$log_file" 2>&1 < /dev/null &
new_pid=$!
printf '%s\n' "$new_pid" > "$pid_file"
sleep 5
if ! kill -0 "$new_pid" 2>/dev/null; then
  echo "Queue exited during startup; inspect $log_file and paper_queue_status.json" >&2
  exit 1
fi
echo "Paper queue detached: PID $new_pid"
echo "Launch log: $log_file"
echo "Durable status: $batch/paper_queue_status.json"
echo 'Disconnecting SSH or closing the laptop will not stop this process; host shutdown will.'
