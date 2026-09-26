# Isolated Linux CUDA 12.8 runtime for the paper-stage queue

This is a **new environment**, not a change to the frozen Q5–Q14 training
records or the legacy `.venv-cloud` / `setup_gpu.sh` recipe. The new host's
reported driver API is CUDA 12.8; the legacy environment contains a CUDA 13.2
PyTorch wheel and does not establish a working CUDA training runtime on this
host. The GPU's reported name is not assumed to be the same as the earlier
Q14 inference GPU.

From a clean project checkout on the Linux GPU host:

```bash
bash setup_paper_cu128.sh
./.venv-paper/bin/python check_gpu.py
./.venv-paper/bin/python -m pip check
```

The installer creates only `.venv-paper`. The default HTTPS Huawei PyPI mirror
supplies `torch==2.8.0` and `torchaudio==2.8.0` because the official cu128
endpoint transferred the large wheel too slowly on this particular host.
**The index or wheel filename is not treated as proof of CUDA compatibility.**
The independent check requires both runtime package versions 2.8.0, rejects
non-cu128 build suffixes, requires `torch.version.cuda == '12.8'`, imports
TorchAudio and EEGNet, and performs a real CUDA matrix operation. A CPU or
CUDA 13.x wheel fails closed. The script then installs pinned top-level
research packages from `requirements-paper-cu128.txt` and runs `pip check`.
If the mirror is unavailable, set `PAPER_INDEX_URL` to another trusted HTTPS
PyPI-compatible index and rerun; the same CUDA gate applies. This changes
the **download source only**, not the accepted scientific runtime.

Set `PAPER_PYTHON_BIN=/absolute/path/to/python3.12` only if the host does not
expose a suitable `python3.12` executable. The script records both the full
resolved inventory at `.venv-paper/pip-freeze.txt` and the package index URL
at `.venv-paper/package-index.txt`; retain both with run provenance. Transitive
packages are not fully locked by the top-level requirements alone.

PyTorch documents the matching 2.8.0 CUDA 12.8 wheel index in its
[previous-version installation instructions](https://pytorch.org/get-started/previous-versions/).
The TorchAudio binary ABI must match its PyTorch release, as explained in the
[TorchAudio installation guide](https://docs.pytorch.org/audio/main/installation.html).
The installer never falls back to CPU. A successful package installation is
**not** evidence of a working GPU; only the live CUDA check is.

Q14's original R2 run configuration also froze its **earlier** GPU name,
platform string, Python build, and package versions. A matching CUDA package
set on a different host cannot make its exact runtime equality check pass.
The separate, versioned Q14 validation-portability amendment must explicitly
record old and new runtime identities while preserving all frozen prediction
and EDF hashes. Do not spoof the GPU name, rewrite `run_config.json`, or
quietly skip the validator.

The scripts require no cloud account credentials. The project directory,
`.venv-paper`, and raw EEG data must reside on storage that survives closing
the browser or local computer; host termination, billing limits, or disk
exhaustion can still interrupt a detached queue.
