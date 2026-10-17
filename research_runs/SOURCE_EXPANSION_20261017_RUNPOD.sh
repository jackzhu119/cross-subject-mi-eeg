#!/usr/bin/env bash
set -Eeuo pipefail
python3 - <<'PY'
import hashlib, os, subprocess, urllib.request

revision = "14bc7ad24c10cc72c9dc074816a63e0b246b0c68"
manifest_sha = "c73dde8be3e521e2c8b07dbf1ee508db1192510cabce8c9a9ead5be75af98564"
installer_sha = "6be61263bbcec2b4dac3e478f8d07bcc152df0940fd8d5af2398ca71ba1e60e5"
url = f"https://raw.githubusercontent.com/jackzhu119/cross-subject-mi-eeg/{revision}/research_runs/SOURCE_EXPANSION_20261017/fetch_bundle.py"
with urllib.request.urlopen(url, timeout=60) as response:
    payload = response.read(1_000_000)
if hashlib.sha256(payload).hexdigest() != installer_sha:
    raise SystemExit("Installer checksum mismatch; nothing was started.")
module = {"__name__": "paper1_verified_installer"}
exec(compile(payload, "fetch_bundle.py", "exec"), module)
code_dir, count = module["install"](revision, manifest_sha, "/workspace/paper1_expansion/code")
print(f"Verified {count} code and protocol files.")
subprocess.run(["bash", str(code_dir / "bootstrap.sh")], check=True,
               env=dict(os.environ, P1_ROOT="/workspace/paper1_expansion"))
PY
