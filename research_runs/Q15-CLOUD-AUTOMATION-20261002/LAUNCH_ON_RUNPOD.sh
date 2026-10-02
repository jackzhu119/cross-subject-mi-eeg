#!/usr/bin/env bash
# Execute in the current RunPod Jupyter Terminal. Credentials remain hidden.
# Transport only: fits_started=0, verified backup, then stop this current Pod.
set -euo pipefail
mkdir -p /workspace/q15-launch
cd /workspace/q15-launch
curl -fSsL --retry 3 --connect-timeout 20 --max-time 180 https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/5e86353017ef9465866a49508f5b75d2a29fa52f/scripts/q15_cloud/q15_cloud_bootstrap.py -o q15_cloud_bootstrap.py
curl -fSsL --retry 3 --connect-timeout 20 --max-time 180 https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/5e86353017ef9465866a49508f5b75d2a29fa52f/scripts/q15_cloud/q15_cloud_job.py -o q15_cloud_job.py
printf '%s\n' '7d17c01b607bd4def05d00546898bce208c2327a08efee4039211a4fb2f3f975  q15_cloud_bootstrap.py' '3556b8dbf2d1753b41866842f68ced1ee3cb98ae4dd763fccbc9b7a36c539c42  q15_cloud_job.py' | sha256sum -c -
exec python /workspace/q15-launch/q15_cloud_bootstrap.py
