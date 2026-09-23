"""Small deterministic EEGNet training helpers for source-only MI decoding."""

from __future__ import annotations

import random
from collections.abc import Iterable

import numpy as np
import torch
from braindecode.models import EEGNet


def seed_everything(seed: int, deterministic: bool = True) -> None:
    """Seed Python, NumPy and Torch before model initialization and shuffling."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(deterministic)


def build_eegnet(architecture: dict, device: torch.device) -> EEGNet:
    """Instantiate the configured Braindecode EEGNet and check its output shape."""
    model_parameters = {key: value for key, value in architecture.items() if key not in {"library", "model"}}
    model = EEGNet(**model_parameters).to(device)
    model.eval()
    with torch.inference_mode():
        probe = torch.zeros(2, architecture["n_chans"], architecture["n_times"], device=device)
        output = model(probe)
    if output.shape != (2, architecture["n_outputs"]):
        raise AssertionError(f"Unexpected EEGNet output shape: {tuple(output.shape)}")
    model.train()
    return model


def train_one_epoch(
    model: torch.nn.Module,
    optimizer: torch.optim.Optimizer,
    x: torch.Tensor,
    y: torch.Tensor,
    train_indices: torch.Tensor,
    batch_size: int,
) -> float:
    """Train on one supplied source-only index set; return trial-weighted CE."""
    if train_indices.numel() == 0:
        raise ValueError("Training indices cannot be empty")
    model.train()
    shuffled = train_indices[torch.randperm(len(train_indices), device=train_indices.device)]
    total_loss = 0.0
    for batch_indices in shuffled.split(batch_size):
        optimizer.zero_grad(set_to_none=True)
        logits = model(x[batch_indices])
        loss = torch.nn.functional.cross_entropy(logits, y[batch_indices])
        if not torch.isfinite(loss):
            raise FloatingPointError("Non-finite EEGNet training loss")
        loss.backward()
        optimizer.step()
        total_loss += float(loss.detach()) * len(batch_indices)
    return total_loss / len(train_indices)


def evaluate_cross_entropy(
    model: torch.nn.Module,
    x: torch.Tensor,
    y: torch.Tensor,
    indices: torch.Tensor,
    batch_size: int,
) -> float:
    """Evaluate on held-out source subjects without updating BatchNorm state."""
    if indices.numel() == 0:
        raise ValueError("Evaluation indices cannot be empty")
    model.eval()
    total_loss = 0.0
    with torch.inference_mode():
        for batch_indices in indices.split(batch_size):
            logits = model(x[batch_indices])
            losses = torch.nn.functional.cross_entropy(
                logits, y[batch_indices], reduction="sum"
            )
            if not torch.isfinite(losses):
                raise FloatingPointError("Non-finite EEGNet evaluation loss")
            total_loss += float(losses)
    return total_loss / len(indices)


def predict_probabilities(
    model: torch.nn.Module,
    x: torch.Tensor,
    indices: Iterable[int],
    batch_size: int,
) -> np.ndarray:
    """Return finite four-class probabilities for indices in input order."""
    ordered = torch.as_tensor(list(indices), dtype=torch.long, device=x.device)
    if ordered.numel() == 0:
        raise ValueError("Prediction indices cannot be empty")
    model.eval()
    parts = []
    with torch.inference_mode():
        for batch_indices in ordered.split(batch_size):
            probabilities = torch.softmax(model(x[batch_indices]), dim=1)
            if not torch.isfinite(probabilities).all():
                raise FloatingPointError("Non-finite EEGNet probabilities")
            parts.append(probabilities.cpu().numpy())
    result = np.concatenate(parts, axis=0)
    if not np.allclose(result.sum(axis=1), 1.0, rtol=1e-6, atol=1e-7):
        raise AssertionError("Predicted class probabilities do not sum to one")
    return result
