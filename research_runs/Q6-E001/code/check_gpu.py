"""Real CUDA availability and allocation check intended for the Linux cloud host."""

from __future__ import annotations

import sys

import torch


def main() -> int:
    print(f"Python: {sys.version.split()[0]}")
    print(f"PyTorch: {torch.__version__}")
    print(f"PyTorch CUDA runtime: {torch.version.cuda}")
    if not torch.cuda.is_available():
        print("ERROR: torch.cuda.is_available() is false; no CUDA training will start.")
        return 2
    for index in range(torch.cuda.device_count()):
        properties = torch.cuda.get_device_properties(index)
        print(
            f"GPU {index}: {properties.name}; compute capability "
            f"{properties.major}.{properties.minor}; "
            f"{properties.total_memory / 1024**3:.1f} GiB"
        )
    device = torch.device("cuda:0")
    left = torch.randn(256, 256, device=device)
    right = torch.randn(256, 256, device=device)
    product = left @ right
    torch.cuda.synchronize(device)
    if not torch.isfinite(product).all().item():
        print("ERROR: CUDA matrix operation returned non-finite values.")
        return 3
    print(f"CUDA allocation and matrix operation passed on {device}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
