#!/usr/bin/env bash
# Compatibility entry: install a coherent current operations overlay, not one
# old submitter that could be incompatible with the login-side pipeline.
set -euo pipefail
BOOTSTRAP_BLOB="f60bc51c7de2acb65555b36736e0ab6f84cb81e0"
BOOTSTRAP_SHA="b44d67db6b783dc5cb20ae3131e4cd625773c057a7c6ff73b32517c9a5a5d2be"
BOOTSTRAP="$(mktemp /tmp/paper1-current-launch.XXXXXX)"
trap 'rm -f "$BOOTSTRAP"' EXIT
curl -4 -f --connect-timeout 8 --max-time 60 --retry 1 \
  -H 'Accept: application/vnd.github.raw+json' \
  "https://api.github.com/repos/jackzhu119/cross-subject-mi-eeg/git/blobs/$BOOTSTRAP_BLOB" -o "$BOOTSTRAP"
OBSERVED="$(sha256sum "$BOOTSTRAP")"
if [ "${OBSERVED%% *}" != "$BOOTSTRAP_SHA" ]; then
  printf 'Current launcher checksum differs; installed code and jobs retained.\n' >&2
  exit 2
fi
bash "$BOOTSTRAP" "$@"
