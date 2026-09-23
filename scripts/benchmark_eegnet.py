"""CPU-only EEGNet throughput smoke test on synthetic, shape-matched data.

This is a resource benchmark, never a classification experiment. No BNCI
labels or outer-test scores are read, so its result may inform a training cap.
"""

from __future__ import annotations

import argparse
import time

import torch
from braindecode.models import EEGNet


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--train-trials", type=int, default=3456)
    parser.add_argument("--validation-trials", type=int, default=1152)
    args = parser.parse_args()
    torch.manual_seed(20260923)
    torch.set_num_threads(args.threads)
    torch.set_num_interop_threads(1)
    model = EEGNet(
        n_chans=22, n_outputs=4, n_times=750, F1=8, D=2, F2=16,
        kernel_length=64, drop_prob=0.25,
    )
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    loss_fn = torch.nn.CrossEntropyLoss()
    x = torch.randn(args.train_trials + args.validation_trials, 22, 750)
    y = torch.randint(0, 4, (len(x),))
    start = time.perf_counter()
    model.train()
    for indices in torch.randperm(args.train_trials).split(args.batch_size):
        optimizer.zero_grad(set_to_none=True)
        loss = loss_fn(model(x[indices]), y[indices])
        loss.backward()
        optimizer.step()
    train_seconds = time.perf_counter() - start
    model.eval()
    start = time.perf_counter()
    with torch.inference_mode():
        for indices in torch.arange(args.train_trials, len(x)).split(args.batch_size):
            loss_fn(model(x[indices]), y[indices])
    validation_seconds = time.perf_counter() - start
    print({
        "device": "cpu",
        "torch": torch.__version__,
        "threads": args.threads,
        "batch_size": args.batch_size,
        "train_trials": args.train_trials,
        "validation_trials": args.validation_trials,
        "train_seconds": round(train_seconds, 3),
        "validation_seconds": round(validation_seconds, 3),
        "parameters": sum(p.numel() for p in model.parameters()),
        "loss_finite": bool(torch.isfinite(loss)),
    })


if __name__ == "__main__":
    main()
