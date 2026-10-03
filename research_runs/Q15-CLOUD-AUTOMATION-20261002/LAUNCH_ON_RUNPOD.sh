#!/usr/bin/env bash
# Current-Pod raw transport only: no model fitting before the scientific freeze.
set -euo pipefail
umask 077
q15_launch_dir=$(mktemp -d /tmp/q15-launch.XXXXXX)
trap 'rm -rf -- "$q15_launch_dir"' EXIT
cd "$q15_launch_dir"
curl -fSsL --retry 3 --connect-timeout 20 --max-time 180 https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/08e20e92675f67cc4a4cb9e3bf020ec7101f99cf/scripts/q15_cloud/q15_cloud_bootstrap.py -o q15_cloud_bootstrap.py
curl -fSsL --retry 3 --connect-timeout 20 --max-time 180 https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/08e20e92675f67cc4a4cb9e3bf020ec7101f99cf/scripts/q15_cloud/q15_cloud_job.py -o q15_cloud_job.py
printf '%s\n' '44fe211995a9d363f317d6d80a056b731458c6296793d8573e6054925c2a74ab  q15_cloud_bootstrap.py' 'b969339a37b5409845015b8cfb3e33a975cc7d3cc7170ba59587c45a75c9917e  q15_cloud_job.py' | sha256sum -c -
python "$q15_launch_dir/q15_cloud_bootstrap.py" "$@"
