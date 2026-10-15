#!/usr/bin/env bash
# Fetch a small fixed source/metadata bundle only. Never install or run EEG work.
set -eu
P1_FETCH_REVISION=
P1_FETCH_MANIFEST_SHA=
P1_FETCH_DEST=/workspace/paper1-official-transition-code-run01
while [ "$#" -gt 0 ]; do
  case "$1" in
    --revision) P1_FETCH_REVISION=${2:?}; shift 2 ;;
    --manifest-sha256) P1_FETCH_MANIFEST_SHA=${2:?}; shift 2 ;;
    *) printf '%s\n' 'Unsupported option; no execution started.' >&2; exit 2 ;;
  esac
done
[[ "$P1_FETCH_REVISION" =~ ^[0-9a-f]{40}$ ]]
[[ "$P1_FETCH_MANIFEST_SHA" =~ ^[0-9a-f]{64}$ ]]
test ! -e "$P1_FETCH_DEST"
test ! -L "$P1_FETCH_DEST"
test -d /workspace
test ! -L /workspace
mkdir -m 700 -- "$P1_FETCH_DEST"
P1_FETCH_ORIGIN="https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/$P1_FETCH_REVISION"
P1_FETCH_MANIFEST="$P1_FETCH_DEST/EXECUTION_BUNDLE_SHA256SUMS.txt"
curl --fail --silent --show-error --proto '=https' --tlsv1.2 --retry 0 \
  --connect-timeout 10 --max-time 30 --max-filesize 16384 \
  "$P1_FETCH_ORIGIN/research_runs/REDESIGN_HANDOFF_20261015/target_restore/EXECUTION_BUNDLE_SHA256SUMS.txt" \
  -o "$P1_FETCH_MANIFEST"
printf '%s  %s\n' "$P1_FETCH_MANIFEST_SHA" "$P1_FETCH_MANIFEST" | sha256sum -c -
P1_FETCH_COUNT=0
while read -r P1_FETCH_FILE_SHA P1_FETCH_RELATIVE P1_FETCH_EXTRA; do
  [[ "$P1_FETCH_FILE_SHA" =~ ^[0-9a-f]{64}$ ]]
  test -z "$P1_FETCH_EXTRA"
  case "$P1_FETCH_RELATIVE" in
    research_runs/*) ;;
    *) printf '%s\n' 'Manifest path outside the reviewed source bundle.' >&2; exit 3 ;;
  esac
  [[ "$P1_FETCH_RELATIVE" =~ ^[a-zA-Z0-9_./-]+$ ]]
  case "/$P1_FETCH_RELATIVE/" in
    *'/../'*|*'/./'*|*'//'*) exit 3 ;;
  esac
  case "$P1_FETCH_RELATIVE" in *.py|*.json|*.txt|*.sh) ;; *) exit 3 ;; esac
  P1_FETCH_COUNT=$((P1_FETCH_COUNT + 1))
  test "$P1_FETCH_COUNT" -le 32
  mkdir -p -- "$P1_FETCH_DEST/$(dirname -- "$P1_FETCH_RELATIVE")"
  test ! -e "$P1_FETCH_DEST/$P1_FETCH_RELATIVE"
  curl --fail --silent --show-error --proto '=https' --tlsv1.2 --retry 0 \
    --connect-timeout 10 --max-time 30 --max-filesize 2097152 \
    "$P1_FETCH_ORIGIN/$P1_FETCH_RELATIVE" -o "$P1_FETCH_DEST/$P1_FETCH_RELATIVE"
  printf '%s  %s\n' "$P1_FETCH_FILE_SHA" "$P1_FETCH_DEST/$P1_FETCH_RELATIVE" | sha256sum -c -
done < "$P1_FETCH_MANIFEST"
test "$P1_FETCH_COUNT" -gt 0
(cd "$P1_FETCH_DEST" && sha256sum -c EXECUTION_BUNDLE_SHA256SUMS.txt)
printf '%s\n' 'FIXED_CODE_AND_PUBLIC_METADATA_FETCHED_NO_INSTALL_NO_EEG_NO_FIT'
printf '%s\n' "$P1_FETCH_DEST"
