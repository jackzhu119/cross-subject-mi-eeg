"""One synthetic forward/backward/checkpoint/resume test in an allocation."""
import argparse
import copy
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile

from .common import atomic_json, read_json, canonical_hash, utc_now


def check(project, device="cuda"):
    import numpy as np
    import torch
    from .models import build_model, three_view_logits
    from .worker import configure, seed_all, capture_rng, restore_rng
    project = Path(project)
    config = read_json(project / "config/study.json")
    configure(config, device)
    if device == "cuda" and not os.environ.get("SLURM_JOB_ID"):
        raise RuntimeError("GPU smoke requires an allocated compute job")
    identity = {"python": platform.python_version(), "torch": torch.__version__,
                "numpy": np.__version__, "cuda_build": torch.version.cuda,
                "architecture": config["architecture"], "input_shape": config["input_shape"],
                "device_type": device}
    if device == "cuda":
        identity["capability"] = list(torch.cuda.get_device_capability(0))
        identity["device_name"] = torch.cuda.get_device_name(0)
        try:
            identity["driver"] = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
                text=True, timeout=10).splitlines()[0].strip()
        except (OSError, subprocess.SubprocessError):
            identity["driver"] = "not_observed"
    fingerprint = canonical_hash(identity)
    receipt = project / "state" / ("gpu_smoke.json" if device == "cuda" else "cpu_smoke_test.json")
    if receipt.exists() and read_json(receipt).get("fingerprint") == fingerprint:
        return {**read_json(receipt), "reused": True}
    seed_all(20261023)
    model = build_model(config, device)
    opt = torch.optim.Adam(model.parameters(), lr=.001)
    x = torch.randn(8, *config["input_shape"], device=device)
    y = torch.arange(8, device=device) % 2

    def update(m, optimizer):
        optimizer.zero_grad(set_to_none=True)
        broad, _, _ = three_view_logits(m, x)
        loss = torch.nn.functional.cross_entropy(broad, y)
        if not torch.isfinite(loss):
            raise ValueError("Nonfinite synthetic smoke loss")
        loss.backward()
        optimizer.step()
        return float(loss.detach().cpu())

    before = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
    first_loss = update(model, opt)
    payload = {"model": copy.deepcopy(model.state_dict()), "optimizer": copy.deepcopy(opt.state_dict()),
               "rng": capture_rng(), "step": 1}
    with tempfile.TemporaryDirectory(prefix="smoke-", dir=project / "state") as tmp:
        path = Path(tmp) / "checkpoint.pt"
        with path.open("wb") as stream:
            torch.save(payload, stream)
            stream.flush()
            os.fsync(stream.fileno())
        update(model, opt)
        expected = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        restored = build_model(config, device)
        restored_opt = torch.optim.Adam(restored.parameters(), lr=.001)
        saved = torch.load(path, map_location=device, weights_only=False)
        restored.load_state_dict(saved["model"])
        restored_opt.load_state_dict(saved["optimizer"])
        restore_rng(saved["rng"])
        second_loss = update(restored, restored_opt)
        if not all(torch.equal(expected[k], v.detach().cpu()) for k, v in restored.state_dict().items()):
            raise RuntimeError("Synthetic uninterrupted/resumed model differs in this runtime")
        if all(torch.equal(before[k], expected[k]) for k in before):
            raise RuntimeError("Synthetic model did not update")
    result = {"status": "passed", "synthetic_only": True, "new_scientific_fits": 0,
              "identity": identity, "fingerprint": fingerprint, "updated_at_utc": utc_now(),
              "first_loss": first_loss, "resumed_loss": second_loss,
              "forward_backward_save_restore": True, "gpu_verified": device == "cuda"}
    atomic_json(receipt, result)
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--project", required=True)
    p.add_argument("--device", choices=["cuda", "cpu"], default="cuda")
    args = p.parse_args()
    print(json.dumps(check(args.project, args.device)), flush=True)


if __name__ == "__main__":
    main()
