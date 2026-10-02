#!/usr/bin/env bash
# Run inside the RunPod Jupyter Terminal. This release downloads data only;
# science gates remain blocked, fits_started=0, then verified backup + Pod stop.
set -euo pipefail
mkdir -p /workspace/q15-launch
cd /workspace/q15-launch
curl -fSsL --retry 3 --connect-timeout 20 --max-time 180 https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/61a0204130da386a3b5b0a0e501a3f9fafb4b388/scripts/q15_cloud/q15_cloud_bootstrap.py -o q15_cloud_bootstrap.py
curl -fSsL --retry 3 --connect-timeout 20 --max-time 180 https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/61a0204130da386a3b5b0a0e501a3f9fafb4b388/scripts/q15_cloud/q15_cloud_job.py -o q15_cloud_job.py
printf '%s\n' '97216ebeaeed7e86793ded4d8c738115d5b986131d3fcaf59fde3251b1cf52bb  q15_cloud_bootstrap.py' '528047be63a1040355a9cbc679d991fd329e1aa764e89b34bd76c3affe80df96  q15_cloud_job.py' | sha256sum -c -
exec python /workspace/q15-launch/q15_cloud_bootstrap.py
