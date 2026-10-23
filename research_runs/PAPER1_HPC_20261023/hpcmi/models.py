"""Compact EEGNet-style backbone; implemented directly with PyTorch.

This is a new version's implementation, not a claim of bitwise equivalence to
Braindecode EEGNet checkpoints from the earlier paper.
"""
import torch
from torch import nn


class CompactEEGNet(nn.Module):
    def __init__(self, channels=18, samples=320, F1=8, D=2, F2=16, kernel_length=64, dropout=0.25):
        super().__init__()
        # Explicit asymmetric padding preserves the time length for even kernels.
        self.features = nn.Sequential(
            nn.ZeroPad2d(((kernel_length - 1) // 2, kernel_length // 2, 0, 0)),
            nn.Conv2d(1, F1, (1, kernel_length), bias=False), nn.BatchNorm2d(F1),
            nn.Conv2d(F1, F1 * D, (channels, 1), groups=F1, bias=False),
            nn.BatchNorm2d(F1 * D), nn.ELU(), nn.AvgPool2d((1, 4)), nn.Dropout(dropout),
            nn.ZeroPad2d((7, 8, 0, 0)),
            nn.Conv2d(F1 * D, F1 * D, (1, 16), groups=F1 * D, bias=False),
            nn.Conv2d(F1 * D, F2, (1, 1), bias=False), nn.BatchNorm2d(F2),
            nn.ELU(), nn.AvgPool2d((1, 8)), nn.Dropout(dropout),
        )
        self.classifier = nn.Linear(F2 * (samples // 32), 2)

    def forward(self, x):
        if x.ndim != 3:
            raise ValueError("Backbone expects [batch, channel, time]")
        return self.classifier(self.features(x.unsqueeze(1)).flatten(1))


def build_model(config, device):
    shape = config.get("input_shape", [3, 18, 320])
    a = config.get("architecture", {})
    return CompactEEGNet(shape[1], shape[2],
        F1=a.get("F1", 8), D=a.get("D", 2), F2=a.get("F2", 16),
        kernel_length=a.get("kernel_length", 64),
        dropout=a.get("dropout", a.get("drop_prob", 0.25))).to(device)


def three_view_logits(model, x):
    if x.ndim != 4 or x.shape[1] != 3:
        raise ValueError("Three views in broad/mu/beta order required")
    n = len(x)
    z = model(torch.cat([x[:, 0], x[:, 1], x[:, 2]], dim=0))
    return z[:n], z[n:2*n], z[2*n:]
