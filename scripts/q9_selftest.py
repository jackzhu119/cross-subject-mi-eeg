"""Dependency-light tests for Q9 source-only splitting and epoch selection.

This does not train a model, download data, or inspect Q9 target outcomes.
It loads the exact functions from q9_neural.py via AST so a CPU-only local
Python without PyTorch/Braindecode can still verify the selection protocol.
The cloud runner itself still requires a real CUDA/PyTorch shape smoke test.
"""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts/q9_neural.py"


def load_function(name: str, namespace: dict) -> object:
    tree = ast.parse(RUNNER.read_text(encoding="utf-8"), filename=str(RUNNER))
    matching = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name]
    if len(matching) != 1:
        raise AssertionError(f"Expected one {name} function")
    module = ast.Module(body=matching, type_ignores=[])
    exec(compile(module, str(RUNNER), "exec"), namespace)
    return namespace[name]


def test_selection() -> None:
    select = load_function("select_mean_rank", {"np": np, "pd": pd, "MAX_EPOCHS": 40})
    curves = {}
    for fold in range(1, 5):
        values = np.arange(40, dtype=float)
        if fold == 1:
            # A large-scale fold prefers epoch 2. The other three source
            # folds prefer epoch 1; mean ranks, unlike mean raw CE, choose 1.
            values *= 1000.0
            values[0], values[1] = values[1], values[0]
        curves[fold] = [{"epoch": i, "val_ce": float(value)}
                        for i, value in enumerate(values, 1)]
    selected, detail = select(curves)
    assert selected == 1
    assert int(detail.selected.sum()) == 1
    tied = {fold: [{"epoch": epoch, "val_ce": 1.0} for epoch in range(1, 41)]
            for fold in range(1, 5)}
    assert select(tied)[0] == 1  # earliest tied epoch
    bad = {fold: rows for fold, rows in curves.items() if fold != 4}
    try:
        select(bad)
    except AssertionError:
        pass
    else:
        raise AssertionError("Incomplete source validation set was accepted")

    # Independently replay Q8's source-only learning curves and require its
    # published frozen nine-epoch selection; no Q9 target results are read.
    source = pd.read_csv(ROOT / "results/Q5-E001/learning_curves.csv")
    frozen = pd.read_csv(ROOT / "research_runs/Q8-E001/results/predeclared_selection.csv")
    for target in range(1, 10):
        frame = source.loc[(source.fold == f"loso_s{target}") & (source.stage == "inner")]
        from_curves = {}
        for inner in range(1, 5):
            one = frame.loc[frame.inner_fold == inner].sort_values("epoch")
            from_curves[inner] = one[["epoch", "val_ce"]].to_dict("records")
        selected, _ = select(from_curves)
        expected = int(frozen.loc[frozen.subject == target, "selected_epochs"].iloc[0])
        assert selected == expected, (target, selected, expected)


def test_partitions() -> None:
    partition = load_function("_source_partition", {"np": np})
    meta = pd.DataFrame({"subject": np.repeat(np.arange(1, 10), 576)})
    for target in range(1, 10):
        validations = set()
        for inner in range(1, 5):
            trains, vals, train_idx, val_idx = partition(meta, target, inner)
            assert target not in trains and target not in vals
            assert len(trains) == 6 and len(vals) == 2
            assert len(train_idx) == 3456 and len(val_idx) == 1152
            assert not np.intersect1d(train_idx, val_idx).size
            validations.update(vals)
        assert validations == set(range(1, 10)) - {target}


def test_source_clean_and_normalization() -> None:
    clean = load_function("source_training_indices", {"np": np})
    meta = pd.DataFrame({"subject": np.repeat(np.arange(1, 10), 576),
                         "artifact_flagged": np.tile(np.arange(576) % 10 == 0, 9)})
    target = 9
    candidates = np.flatnonzero((meta.subject != target).to_numpy())
    test = np.flatnonzero((meta.subject == target).to_numpy())
    filtered = clean(meta, candidates, exclude_flagged=True)
    assert len(filtered) < len(candidates)
    assert not meta.iloc[filtered].artifact_flagged.any()
    assert np.array_equal(clean(meta, candidates, exclude_flagged=False), candidates)
    assert len(test) == 576 and meta.iloc[test].artifact_flagged.any()
    # Inner source validation stays complete even when training is cleaned.
    partition = load_function("_source_partition", {"np": np})
    _, _, inner_train, validation = partition(meta, target, 1)
    assert len(validation) == 1152 and meta.iloc[validation].artifact_flagged.any()
    assert len(clean(meta, inner_train, exclude_flagged=True)) < 3456

    namespace = {"np": np, "hashlib": hashlib}
    load_function("_sample_ids_hash", namespace)
    fit = load_function("fit_source_band_standardizer", namespace)
    rng = np.random.default_rng(20260924)
    short_meta = pd.DataFrame({"subject": np.repeat(np.arange(1, 10), 2),
                               "sample_id": [f"s{s}_t{i}" for s in range(1, 10) for i in range(2)]})
    signal = rng.normal(size=(18, 2, 22, 750)).astype(np.float32)
    signal[:, 0] += 10.0
    signal[:, 1] *= 3.0
    source_subjects = list(range(1, 7))
    source_idx = np.flatnonzero(short_meta.subject.isin(source_subjects).to_numpy())
    first = fit(signal, short_meta, source_idx, source_subjects)
    changed = signal.copy()
    changed[short_meta.subject.isin([7, 8, 9]).to_numpy()] += 100000.0
    again = fit(changed, short_meta, source_idx, source_subjects)
    assert first == again  # validation/target perturbation cannot alter fitted statistics
    assert len(first["channel_mean_microvolts"]) == 2
    assert len(first["channel_mean_microvolts"][0]) == 22
    assert first["channel_mean_microvolts"][0][0] > 8.0
    assert first["channel_mean_microvolts"][1][0] < 3.0
    mean = np.asarray(first["channel_mean_microvolts"])
    std = np.asarray(first["channel_std_microvolts"])
    normalized_source = (signal[source_idx] - mean[None, :, :, None]) / std[None, :, :, None]
    np.testing.assert_allclose(normalized_source.mean(axis=(0, 3)), 0, atol=1e-5)
    np.testing.assert_allclose(normalized_source.std(axis=(0, 3)), 1, atol=1e-5)
    try:
        fit(signal, short_meta, source_idx[:-1], source_subjects)
    except ValueError:
        pass
    else:
        raise AssertionError("Partial source population was accepted for normalization")


if __name__ == "__main__":
    test_selection()
    test_partitions()
    test_source_clean_and_normalization()
    print("Q9 source-only selection, split, artifact, and normalization self-tests passed; no Q9 training was run.")
