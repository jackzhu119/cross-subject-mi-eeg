#!/usr/bin/env bash
# Current-Pod raw transport only: no model fitting before the scientific freeze.
set -euo pipefail
umask 077
q15_launch_dir=$(mktemp -d /tmp/q15-launch.XXXXXX)
trap 'rm -rf -- "$q15_launch_dir"' EXIT
cd "$q15_launch_dir"
curl -fSsL --retry 3 --connect-timeout 20 --max-time 180 https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/40c93ebd80589637cdbfe936fd27687f5175673f/scripts/q15_cloud/q15_cloud_bootstrap.py -o q15_cloud_bootstrap.py
curl -fSsL --retry 3 --connect-timeout 20 --max-time 180 https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/40c93ebd80589637cdbfe936fd27687f5175673f/scripts/q15_cloud/q15_cloud_job.py -o q15_cloud_job.py
printf '%s\n' '827ca023cd442a1ac116e28ac3f979978b66e26d3bcd3589e07de6509cd1229f  q15_cloud_bootstrap.py' 'f3c313cb37e73b9d2030cc467645bd2aa83d8db87169ad91f5f300b73cd2989d  q15_cloud_job.py' | sha256sum -c -
python "$q15_launch_dir/q15_cloud_bootstrap.py" "$@"
