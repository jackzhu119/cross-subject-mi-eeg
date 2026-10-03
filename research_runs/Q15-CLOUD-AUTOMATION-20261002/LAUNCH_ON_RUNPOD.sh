#!/usr/bin/env bash
# Current-Pod raw transport only: no model fitting before the scientific freeze.
set -euo pipefail
umask 077
q15_launch_dir=$(mktemp -d /tmp/q15-launch.XXXXXX)
trap 'rm -rf -- "$q15_launch_dir"' EXIT
cd "$q15_launch_dir"
curl -fSsL --retry 3 --connect-timeout 20 --max-time 180 https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/b2527a7e97300e6bf06b9ddc4e5dc2b5b2d203ce/scripts/q15_cloud/q15_cloud_bootstrap.py -o q15_cloud_bootstrap.py
curl -fSsL --retry 3 --connect-timeout 20 --max-time 180 https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/b2527a7e97300e6bf06b9ddc4e5dc2b5b2d203ce/scripts/q15_cloud/q15_cloud_job.py -o q15_cloud_job.py
printf '%s\n' '775f092c096f4f0fe077f1013ad6d2d2f343f5367c683650313556fce2ce31f4  q15_cloud_bootstrap.py' 'f4b9526b7a04d1f8d55bddac9b405f8d842e8a99ab800bfec1df34997604f8a2  q15_cloud_job.py' | sha256sum -c -
python "$q15_launch_dir/q15_cloud_bootstrap.py" "$@"
