"""Fixed broad-view, equal-cohort/person weighted CSP and regularized LDA.

This NumPy-only reference is separately specified from the historical
CSP-LDA(auto). It has no validation search, target adaptation, or Torch import.
Small source-statistic checkpoints and held-out session shards resume separately.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import sys
import tempfile
import time
import traceback

import numpy as np

from hpcmi.common import atomic_json, canonical_hash, exclusive_lock, utc_now
from hpcmi.data import Registry


PROTOCOL = "broad_weighted_csp_rlda_v1"


def atomic_npz(path, **arrays):
    """Same-directory file replacement; never serialize Python objects."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if any(np.asarray(value).dtype.hasobject for value in arrays.values()):
        raise ValueError("Object arrays are forbidden in numeric checkpoints")
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            np.savez(stream, **arrays)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def file_sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class RequestedStop(Exception):
    def __init__(self, code):
        self.code = code


class Signals:
    def __init__(self):
        self.code = None
        self.previous = {}

    def install(self):
        for name in ("SIGUSR1", "SIGTERM", "SIGINT"):
            if hasattr(signal, name):
                signum = getattr(signal, name)
                self.previous[signum] = signal.signal(signum, self._receive)

    def _receive(self, signum, _frame):
        # Explicit cancellation takes priority over a time-limit warning.
        code = 75 if signum == getattr(signal, "SIGUSR1", None) else 128 + signum
        if self.code is None or code != 75:
            self.code = code

    def check(self):
        if self.code is not None:
            raise RequestedStop(self.code)

    def restore(self):
        for signum, handler in self.previous.items():
            signal.signal(signum, handler)


class Progress:
    def __init__(self, run_dir, task, config):
        self.run_dir, self.task = run_dir, task
        self.interval = float(config.get("heartbeat_seconds", 30))
        self.last, self.processed = 0., 0

    def emit(self, stage, force=False, **extra):
        now = time.monotonic()
        if not force and now - self.last < self.interval:
            return
        self.last = now
        row = {"task_id": self.task["id"], "stage": stage, "pid": os.getpid(),
               "host": os.uname().nodename, "updated_at_utc": utc_now(),
               "family": "classical", "global_step": 0, "optimizer_updates": 0,
               "processed_evaluation_samples": self.processed, **extra}
        atomic_json(self.run_dir / "status.json", row)
        print(json.dumps(row, allow_nan=False), flush=True)


def _contract(config):
    settings = config.get("classical", {})
    if settings != {"method": "weighted_csp_rlda", "components": 4,
                    "csp_shrinkage": .1, "lda_shrinkage": .1}:
        raise ValueError("Classical settings differ from the fixed CSP/RLDA specification")
    if config.get("input_shape", [3, 18, 320]) != [3, 18, 320]:
        raise ValueError("Classical reference requires the common 18-channel input")
    return settings


def science_fingerprint(config, task, registry):
    fields = ("id", "family", "cell_id", "pool", "subset", "regime", "phase", "method",
              "seed", "fold", "train_ids", "validation_ids", "test_ids", "train_trials_sha256")
    return canonical_hash({"protocol": PROTOCOL, "science_version": config["science_version"],
                           "classical": _contract(config), "input_shape": [3, 18, 320],
                           "view": "broad", "weights": "equal_cohort_then_person_within_each_class",
                           "task": {key: task.get(key) for key in fields}, "data": registry.fingerprint})


def source_weights(registry, ids):
    registry.ensure_source(ids)
    cohorts = {}
    for person in ids:
        cohorts.setdefault(registry.by_id[person]["dataset"], []).append(person)
    if not cohorts:
        raise ValueError("Source cohort is empty")
    return {person: 1. / (len(cohorts) * len(people))
            for people in cohorts.values() for person in people}


def validate_whitelist(registry, ids, indices_by_person):
    registry.ensure_source(ids)
    if set(indices_by_person) != set(ids):
        raise ValueError("Training trial whitelist does not match source people")
    checked = {}
    for person in ids:
        values = list(indices_by_person[person])
        if not values or any(isinstance(x, (bool, np.bool_)) or not isinstance(x, (int, np.integer)) for x in values):
            raise ValueError("Whitelist must contain integer source trial indices")
        indices = np.asarray(values, dtype=np.int64)
        entry = registry.load_person(person)
        if len(set(values)) != len(values) or np.any(indices < 0) or np.any(indices >= len(entry["y"])):
            raise ValueError("Duplicate or out-of-range training trial")
        y = np.asarray(entry["y"])[indices]
        if set(np.unique(y).tolist()) != {0, 1}:
            raise ValueError("Each selected source person must contain both classes")
        checked[person] = indices
    return checked


def trial_covariance_sum(x):
    """Sum trace-normalized, temporally centered trial covariances."""
    x = np.asarray(x, dtype=np.float64)
    if x.ndim != 3 or x.shape[1] != 18 or not np.isfinite(x).all():
        raise ValueError("Expected finite broad-view trials with 18 channels")
    x = x - x.mean(axis=2, keepdims=True)
    cov = np.einsum("bct,bdt->bcd", x, x, optimize=True)
    trace = np.trace(cov, axis1=1, axis2=2)
    if np.any(trace <= 0):
        raise ValueError("Source trial has zero broad-view variance")
    return (cov / trace[:, None, None]).sum(axis=0)


def fit_csp(covariances):
    covariances = np.asarray(covariances, dtype=np.float64)
    if covariances.shape != (2, 18, 18) or not np.isfinite(covariances).all():
        raise ValueError("Invalid class covariance matrices")
    shrunk = .9 * covariances + .1 * np.eye(18)[None] / 18.
    values, vectors = np.linalg.eigh(shrunk.sum(axis=0))
    if np.any(values <= 0):
        raise ValueError("CSP composite covariance is not positive definite")
    whiten = (vectors / np.sqrt(values)[None, :]).T
    _, directions = np.linalg.eigh(whiten @ shrunk[1] @ whiten.T)
    filters = directions[:, [0, 1, 16, 17]].T @ whiten
    # Eigenvector signs do not affect variances; canonicalize for inspectability.
    for row in filters:
        if row[np.argmax(np.abs(row))] < 0:
            row *= -1
    return filters


def features(x, filters):
    x = np.asarray(x, dtype=np.float64)
    if x.ndim != 3 or x.shape[1] != 18 or not np.isfinite(x).all():
        raise ValueError("Invalid broad-view feature batch")
    projected = np.einsum("fc,bct->bft", filters, x, optimize=True)
    variance = projected.var(axis=2)
    total = variance.sum(axis=1, keepdims=True)
    if np.any(total <= 0):
        raise ValueError("CSP feature trial has zero projected variance")
    return np.log(np.maximum(variance / total, np.finfo(np.float64).tiny))


def fit_lda(means, second_moments):
    """Population moments under fixed class-conditional cohort/person weights."""
    covariance = np.mean(second_moments - np.einsum("ci,cj->cij", means, means), axis=0)
    covariance = (covariance + covariance.T) / 2.
    scale = float(np.trace(covariance) / 4.)
    if not np.isfinite(covariance).all() or scale <= 0:
        raise ValueError("LDA feature covariance has no positive finite scale")
    regularized = .9 * covariance + .1 * scale * np.eye(4)
    coef = np.linalg.solve(regularized, means[1] - means[0])
    intercept = -.5 * float((means[1] + means[0]) @ coef)
    return coef, intercept, regularized


def predict(model, x):
    score = features(x, model["filters"]) @ model["coef"] + float(model["intercept"])
    logits = np.column_stack((-.5 * score, .5 * score))
    if not np.isfinite(logits).all():
        raise FloatingPointError("Non-finite CSP/RLDA logits")
    return logits


def _stage(path, identity, shapes):
    if not path.exists():
        return {key: np.zeros(shape, dtype=np.float64) for key, shape in shapes.items()}
    with np.load(path, allow_pickle=False) as archive:
        if json.loads(archive["identity"].item()) != identity or set(archive.files) != set(shapes) | {"identity"}:
            raise ValueError("Source statistic checkpoint identity changed")
        arrays = {key: archive[key] for key in shapes}
    if any(value.shape != shapes[key] or not np.isfinite(value).all() for key, value in arrays.items()):
        raise ValueError("Invalid source statistic checkpoint")
    if not np.isin(arrays["done"], [0., 1.]).all():
        raise ValueError("Invalid source statistic completion flags")
    return arrays


def fit_model(registry, task, indices_by_person, run_dir, identity, config, signals, progress):
    """Source-only fit; checkpoint per-person moments, then save final model."""
    ids = task["train_ids"]
    indices = validate_whitelist(registry, ids, indices_by_person)
    weights = source_weights(registry, ids)
    batch_size = int(config.get("eval_batch_size", 128))
    if batch_size <= 0:
        raise ValueError("Batch size must be positive")
    n = len(ids)
    cov_path = run_dir / "source_covariances.npz"
    cov_identity = {**identity, "stage": "source_class_covariances"}
    state = _stage(cov_path, cov_identity, {"cov": (n, 2, 18, 18), "done": (n,)})
    for index, person in enumerate(ids):
        signals.check()
        if state["done"][index]:
            continue
        entry = registry.load_person(person)
        result = np.zeros((2, 18, 18))
        for label in (0, 1):
            selected = indices[person][np.asarray(entry["y"])[indices[person]] == label]
            for start in range(0, len(selected), batch_size):
                signals.check()
                batch = selected[start:start + batch_size]
                result[label] += trial_covariance_sum(entry["X"][batch, 0])
                progress.emit("classical_source_covariances", person_id=person)
            result[label] /= len(selected)
        state["cov"][index], state["done"][index] = result, 1.
        atomic_npz(cov_path, **state, identity=np.asarray(json.dumps(cov_identity, sort_keys=True)))
    covariance = sum(weights[person] * state["cov"][index] for index, person in enumerate(ids))
    filters = fit_csp(covariance)
    filter_hash = hashlib.sha256(filters.astype("<f8").tobytes()).hexdigest()
    moments_path = run_dir / "source_feature_moments.npz"
    moments_identity = {**identity, "stage": "source_class_feature_moments", "filters_sha256": filter_hash}
    moments = _stage(moments_path, moments_identity,
                     {"means": (n, 2, 4), "seconds": (n, 2, 4, 4), "done": (n,)})
    for index, person in enumerate(ids):
        signals.check()
        if moments["done"][index]:
            continue
        entry = registry.load_person(person)
        for label in (0, 1):
            selected = indices[person][np.asarray(entry["y"])[indices[person]] == label]
            first, second = np.zeros(4), np.zeros((4, 4))
            for start in range(0, len(selected), batch_size):
                signals.check()
                batch = selected[start:start + batch_size]
                f = features(entry["X"][batch, 0], filters)
                first += f.sum(axis=0)
                second += f.T @ f
                progress.emit("classical_source_features", person_id=person)
            moments["means"][index, label] = first / len(selected)
            moments["seconds"][index, label] = second / len(selected)
        moments["done"][index] = 1.
        atomic_npz(moments_path, **moments, identity=np.asarray(json.dumps(moments_identity, sort_keys=True)))
    means = sum(weights[p] * moments["means"][i] for i, p in enumerate(ids))
    seconds = sum(weights[p] * moments["seconds"][i] for i, p in enumerate(ids))
    coef, intercept, regularized = fit_lda(means, seconds)
    model = {"filters": filters, "coef": coef, "intercept": np.asarray(intercept),
             "class_means": means, "regularized_feature_covariance": regularized,
             "class_covariances": covariance}
    atomic_npz(run_dir / "model.npz", **model, identity=np.asarray(json.dumps(identity, sort_keys=True)))
    progress.emit("classical_model_saved", force=True, classical_fits_completed=1)
    return model


def load_model(path, identity):
    expected = {"filters": (4, 18), "coef": (4,), "intercept": (), "class_means": (2, 4),
                "regularized_feature_covariance": (4, 4), "class_covariances": (2, 18, 18)}
    with np.load(path, allow_pickle=False) as archive:
        if set(archive.files) != set(expected) | {"identity"} or json.loads(archive["identity"].item()) != identity:
            raise ValueError("Saved classical model identity changed")
        model = {key: archive[key] for key in expected}
    if any(value.shape != expected[key] or not np.isfinite(value).all() for key, value in model.items()):
        raise ValueError("Invalid saved classical numeric model")
    return model


def metric_row(y, logits):
    y = np.asarray(y)
    if len(y) == 0 or y.ndim != 1 or not np.isin(y, [0, 1]).all() or logits.shape != (len(y), 2) or not np.isfinite(logits).all():
        raise ValueError("Invalid held-out prediction shard")
    pred = logits.argmax(axis=1)
    z = logits.astype(np.float64)
    return {"n": len(y), "n_left": int((y == 0).sum()), "n_right": int((y == 1).sum()),
            "correct_left": int(((y == 0) & (pred == 0)).sum()),
            "correct_right": int(((y == 1) & (pred == 1)).sum()),
            "sum_ce": float(np.logaddexp(0, z[np.arange(len(y)), 1 - y] - z[np.arange(len(y)), y]).sum())}


def evaluate(model, model_path, registry, task, run_dir, variant, config, signals, progress):
    # A durable, identity-bound source model must precede any held-out array read.
    if not model_path.is_file():
        raise ValueError("Save source model before held-out evaluation")
    digest = file_sha(model_path)
    folder = run_dir / "evaluations" / variant / digest[:20]
    folder.mkdir(parents=True, exist_ok=True)
    people = []
    batch_size = int(config.get("eval_batch_size", 128))
    for person in task["test_ids"]:
        signals.check()
        entry = registry.load_person(person)
        y = np.asarray(entry["y"], dtype=np.int64)
        sessions = np.asarray(entry["sessions"], dtype=str)
        trial_ids = np.asarray(entry["trial_ids"], dtype=str)
        totals = {"n": 0, "n_left": 0, "n_right": 0, "correct_left": 0, "correct_right": 0, "sum_ce": 0.}
        for session in sorted(set(sessions.tolist())):
            signals.check()
            indices = np.flatnonzero(sessions == session)
            shard = folder / (canonical_hash({"person": person, "session": session})[:24] + ".npz")
            identity = {"model_sha256": digest, "person_id": person, "session": session,
                        "variant": variant, "seed": task["seed"]}
            if shard.exists():
                with np.load(shard, allow_pickle=False) as archive:
                    if set(archive.files) != {"logits", "y", "trial_ids", "identity"} or json.loads(archive["identity"].item()) != identity or not np.array_equal(archive["y"], y[indices]) or not np.array_equal(archive["trial_ids"], trial_ids[indices]):
                        raise ValueError("Held-out session shard identity changed")
                    logits = archive["logits"]
                progress.processed += len(indices)
            else:
                pieces = []
                for start in range(0, len(indices), batch_size):
                    signals.check()
                    batch = indices[start:start + batch_size]
                    pieces.append(predict(model, entry["X"][batch, 0]))
                    progress.processed += len(batch)
                    progress.emit("evaluating", evaluation_variant=variant, person_id=person, session=session)
                logits = np.concatenate(pieces)
                atomic_npz(shard, logits=logits, y=y[indices], trial_ids=trial_ids[indices],
                           identity=np.asarray(json.dumps(identity, sort_keys=True)))
            for key, value in metric_row(y[indices], logits).items():
                totals[key] += value
        if totals["n_left"] == 0 or totals["n_right"] == 0:
            raise ValueError("Held-out person lacks a class")
        left, right = totals["correct_left"] / totals["n_left"], totals["correct_right"] / totals["n_right"]
        people.append({"person_id": person, "dataset": entry["dataset"], "seed": task["seed"], "variant": variant,
                       **totals, "recall_left": left, "recall_right": right, "ba": (left + right) / 2,
                       "min_recall": min(left, right), "ce": totals["sum_ce"] / totals["n"]})
    if file_sha(model_path) != digest:
        raise RuntimeError("Held-out evaluation changed the source model")
    summary = {"variant": variant, "model_sha256": digest, "people": people, "completed_at_utc": utc_now()}
    atomic_json(folder / "summary.json", summary)
    return str((folder / "summary.json").relative_to(run_dir))


def _read_task(project, task_id):
    rows = json.loads((project / "tasks.json").read_text())
    rows = rows["tasks"] if isinstance(rows, dict) else rows
    selected = [row for row in rows if row["id"] == task_id]
    if len(selected) != 1 or not re.fullmatch(r"[A-Za-z0-9_.-]+", task_id):
        raise ValueError("Unknown or unsafe task ID")
    task = selected[0]
    if task.get("family") != "classical" or task.get("method") != "weighted_csp_rlda" or task.get("seed") != 0:
        raise ValueError("Expected the fixed deterministic classical reference task")
    return task


def run_task(project, task_id):
    project = Path(project).resolve()
    config = json.loads((project / "config/study.json").read_text())
    task = _read_task(project, task_id)
    run_dir = project / "outputs/runs" / task_id
    run_dir.mkdir(parents=True, exist_ok=True)
    progress = Progress(run_dir, task, config)
    with exclusive_lock(run_dir / "worker.lock"):
        signals = Signals()
        signals.install()
        try:
            paths = json.loads((project / "config/paths.json").read_text())
            registry = Registry(Path(paths["data_dir"]))
            from .plan import task_trialset
            indices = task_trialset(project, task, registry)
            fingerprint = science_fingerprint(config, task, registry)
            registry.ensure_source(task["train_ids"])
            test_ids = task["test_ids"]
            if task.get("validation_ids") or not test_ids or len(test_ids) != len(set(test_ids)) or set(task["train_ids"]) & set(test_ids):
                raise ValueError("Fixed train/test split is invalid or contains inner validation")
            if task["phase"] == "development":
                registry.ensure_source(test_ids)
                variant = "outer_fixed40"
            elif task["phase"] == "final" and all(registry.by_id[p]["role"] == "external" for p in test_ids):
                variant = "fixed40"
            else:
                raise ValueError("Unknown task phase or non-external final evaluation")
            identity = {"protocol": PROTOCOL, "fingerprint": fingerprint, "data_fingerprint": registry.fingerprint,
                        "train_trials_sha256": task["train_trials_sha256"], "source_person_ids": task["train_ids"]}
            model_path = run_dir / "model.npz"
            complete_path = run_dir / "complete.json"
            if complete_path.exists():
                complete = json.loads(complete_path.read_text())
                if complete["fingerprint"] != fingerprint or not model_path.is_file() or complete["model_sha256"] != file_sha(model_path):
                    raise ValueError("Completed classical task/model identity changed")
                if all((run_dir / name).is_file() for name in complete["evaluations"].values()):
                    progress.emit("already_complete", force=True, classical_fits_completed=1)
                    return 0
            signals.check()
            if model_path.exists():
                model = load_model(model_path, identity)
                progress.emit("classical_model_reused", force=True, classical_fits_completed=1)
            else:
                model = fit_model(registry, task, indices, run_dir, identity, config, signals, progress)
            evaluation = evaluate(model, model_path, registry, task, run_dir, variant, config, signals, progress)
            complete = {"status": "complete", "complete": True, "id": task_id, "task_id": task_id,
                        **{key: task.get(key) for key in ("family", "cell_id", "pool", "subset", "regime", "phase", "method", "seed", "fold")},
                        "train_trials_sha256": task["train_trials_sha256"], "fingerprint": fingerprint,
                        "model_sha256": file_sha(model_path), "classical_fits_completed": 1,
                        "global_step": 0, "optimizer_updates": 0, "epoch_selection": False,
                        "evaluations": {variant: evaluation}, "validation_history": [],
                        "runtime_history": [{"numpy": np.__version__, "python": sys.version.split()[0], "device": "cpu"}],
                        "completed_at_utc": utc_now()}
            atomic_json(complete_path, complete)
            progress.emit("complete", force=True, classical_fits_completed=1, evaluations=complete["evaluations"])
            return 0
        except RequestedStop as stop:
            progress.emit("checkpointed_for_resume" if stop.code == 75 else "cancelled_checkpointed", force=True,
                          requested_exit_code=stop.code, automatic_requeue_requested=False)
            return stop.code
        except Exception:
            failure = {"status": "failed", "task_id": task_id, "failed_at_utc": utc_now(),
                       "traceback": traceback.format_exc(), "optimizer_updates": 0}
            atomic_json(run_dir / "error.json", failure)
            atomic_json(run_dir / ("error-" + utc_now().replace(":", "").replace("+", "_") + ".json"), failure)
            print(failure["traceback"], file=sys.stderr, flush=True)
            progress.emit("failed", force=True, exit_code=1)
            return 1
        finally:
            signals.restore()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--task-id", required=True)
    args = parser.parse_args()
    try:
        code = run_task(args.project, args.task_id)
    except BlockingIOError:
        print(json.dumps({"status": "already_running", "task_id": args.task_id, "new_worker_started": False}), flush=True)
        code = 0
    except Exception:
        traceback.print_exc()
        code = 1
    raise SystemExit(code)


if __name__ == "__main__":
    main()
