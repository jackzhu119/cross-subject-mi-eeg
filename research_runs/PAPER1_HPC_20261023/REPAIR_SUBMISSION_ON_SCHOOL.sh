#!/usr/bin/env bash
# Compatibility entry: install a coherent current operations overlay, not one
# old submitter that could be incompatible with the login-side pipeline.
set -euo pipefail
BOOTSTRAP_BLOB="18886a6939b378071af2f5d919368904b76dc614"
BOOTSTRAP_SHA="f79782cbb15a24e2454676da6ffb82fc27d1a1336bc1e445e95a70d01a551bc5"
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
