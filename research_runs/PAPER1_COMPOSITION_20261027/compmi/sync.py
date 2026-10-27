"""Independent login-side reporting and automatic, resumable result publication.

No training runtime, raw data or model parameters are imported/read. GitHub
failures remain reporting failures. A finished archive is packed once and its
verified Git blobs are reused until the dedicated branch update succeeds.
"""
from __future__ import annotations

import argparse
import base64
from collections import defaultdict
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import signal
import tarfile
import tempfile
import time
import urllib.parse

from hpcmi.common import atomic_json, canonical_hash, utc_now
from hpcmi.github_sync import GitHubError, _api, _ensure_branch, _lock, _put_json, _read_token

PART_BYTES = 512 * 1024
os.environ.setdefault("PAPER1_GITHUB_TRANSPORT", "curl")


def _read(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except (FileNotFoundError, ValueError, OSError):
        return default


def _sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _child(root, relative):
    relative = Path(relative)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Result member must be relative")
    path = Path(root) / relative
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(Path(root).resolve()):
        raise ValueError("Missing or escaping result member")
    return path


def _tasks(project):
    tasks = _read(project / "tasks.json")
    if isinstance(tasks, dict):
        tasks = tasks["tasks"]
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("Frozen task plan is missing")
    ids = [task["id"] for task in tasks]
    if len(ids) != len(set(ids)) or any(not re.fullmatch(r"[A-Za-z0-9_.-]+", item) for item in ids):
        raise ValueError("Frozen task identities are invalid")
    return tasks


def _completed(project, task, expected_steps, expected_epochs):
    run = project / "outputs/runs" / task["id"]
    done = _read(run / "complete.json")
    if not isinstance(done, dict) or done.get("complete") is not True or done.get("status") != "complete":
        return None
    fields = ("family", "cell_id", "phase", "method", "seed", "fold", "train_trials_sha256")
    if done.get("task_id", done.get("id")) != task["id"] or any(done.get(key) != task.get(key) for key in fields):
        return None
    if task["family"] == "neural":
        if done.get("optimizer_updates") != expected_steps or done.get("global_step") != expected_steps or done.get("epochs_completed") != expected_epochs:
            return None
    elif done.get("classical_fits_completed") != 1:
        return None
    variant = "outer_fixed40" if task["phase"] == "development" else "fixed40"
    evaluations = done.get("evaluations")
    if not isinstance(evaluations, dict) or set(evaluations) != {variant}:
        return None
    try:
        summary = _read(_child(run, evaluations[variant]))
        if not summary or summary.get("model_sha256") != done.get("model_sha256"):
            return None
        if (len(summary["people"]) != len(task["test_ids"])
                or set(row["person_id"] for row in summary["people"]) != set(task["test_ids"])):
            return None
    except (KeyError, ValueError, TypeError):
        return None
    return {**done, "_summary": summary}


def _descriptive(groups):
    """Report a group estimate only after all its planned seeds/folds finish."""
    metrics = ("min_recall", "ba", "recall_left", "recall_right")
    result = []
    for key, group in sorted(groups.items()):
        family, phase, cell, method = key
        row = {"family": family, "phase": phase, "cell_id": cell, "method": method,
               "planned_tasks": group["planned"], "completed_tasks": len(group["completed"]),
               "status": "partial_pending_all_registered_folds_and_seeds"}
        if len(group["completed"]) == group["planned"]:
            by_person = defaultdict(dict)
            for task, done in group["completed"]:
                for person in done["_summary"]["people"]:
                    identity = person["person_id"]
                    if task["seed"] in by_person[identity]:
                        raise ValueError("Repeated held-out person/seed in a completed descriptive group")
                    by_person[identity][task["seed"]] = person
            people = []
            for identity, values in by_person.items():
                if set(values) != group["seeds"]:
                    raise ValueError("Completed descriptive group lacks a registered seed")
                datasets = {value["dataset"] for value in values.values()}
                if len(datasets) != 1:
                    raise ValueError("Held-out cohort changed across seeds")
                people.append({"person_id": identity, "dataset": next(iter(datasets)),
                               **{metric: sum(float(value[metric]) for value in values.values()) / len(values) for metric in metrics}})
            if not people:
                raise ValueError("Completed descriptive group has no participants")
            cohorts = sorted({person["dataset"] for person in people})
            means = {}
            for metric in metrics:
                if phase == "development":
                    means[metric] = sum(sum(person[metric] for person in people if person["dataset"] == cohort)
                                        / sum(person["dataset"] == cohort for person in people) for cohort in cohorts) / len(cohorts)
                else:
                    means[metric] = sum(person[metric] for person in people) / len(people)
            row.update(status="complete_descriptive", n_participants=len(people), n_seeds=len(group["seeds"]),
                       seed_aggregation="within-person arithmetic mean before participant aggregation",
                       aggregation="equal cohort then equal person" if phase == "development" else "equal person",
                       metrics=means, inference="none; frozen full analysis runs separately")
        result.append(row)
    return result


def collect_progress(project):
    project = Path(project)
    tasks = _tasks(project)
    study = _read(project / "config/study.json", {})
    epochs, updates = int(study["epochs"]), int(study["updates_per_epoch"])
    group = defaultdict(lambda: {"planned": 0, "completed": 0, "optimizer_updates": 0})
    descriptions = defaultdict(lambda: {"planned": 0, "seeds": set(), "completed": []})
    rows, completed = [], 0
    for task in tasks:
        status = _read(project / "outputs/runs" / task["id"] / "status.json", {})
        done = _completed(project, task, epochs * updates, epochs)
        count = int((done or status).get("optimizer_updates", (done or status).get("global_step", 0)) or 0)
        key = "/".join(str(task[name]) for name in ("family", "phase", "cell_id"))
        group[key]["planned"] += 1
        group[key]["completed"] += int(done is not None)
        group[key]["optimizer_updates"] += count
        descriptive_key = tuple(task[name] for name in ("family", "phase", "cell_id", "method"))
        descriptions[descriptive_key]["planned"] += 1
        descriptions[descriptive_key]["seeds"].add(task["seed"])
        if done:
            descriptions[descriptive_key]["completed"].append((task, done))
        completed += int(done is not None)
        rows.append({**{key: task.get(key) for key in ("id", "family", "phase", "cell_id", "method", "seed", "fold")},
                     "complete": done is not None, "optimizer_updates": count,
                     **{key: status[key] for key in ("stage", "epoch", "updated_at_utc", "processed_evaluation_samples") if key in status}})
    plan = _read(project / "state/plan.json", {})
    plan_matches = (plan.get("tasks_sha256") == canonical_hash(tasks)
                    and plan.get("task_counts", {}).get("total") == len(tasks))
    analysis = _read(project / "outputs/analysis/summary.json")
    analysis_complete = bool(analysis and analysis.get("status") == "complete" and not analysis.get("pending")
                             and analysis.get("plan_fingerprint") == plan.get("fingerprint"))
    report = {"schema_version": 1, "updated_at_utc": utc_now(), "counts": {"planned": len(tasks), "completed": completed,
              "remaining": len(tasks) - completed}, "by_family_phase_cell": dict(sorted(group.items())), "tasks": rows,
              "descriptive_statistics": _descriptive(descriptions),
              "plan_matches": plan_matches, "analysis_complete": analysis_complete,
              "ready_for_result_export": plan_matches and analysis_complete and completed == len(tasks),
              "observation_scope": "Saved steps and validated completion summaries; not proof of live GPU activity",
              "training_blocked": False}
    controller = _read(project / "state/controller_status.json")
    if isinstance(controller, dict):
        report["controller"] = {key: controller[key] for key in ("stage", "completed_tasks", "total_tasks", "active_children", "failed_this_invocation", "updated_at_utc") if key in controller}
    return report, analysis


def _atomic_bytes(path, content):
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _payloads(project, code_root):
    """Positive member list: predictions/results and contracts, never weights."""
    tasks = _tasks(project)
    selected = {}
    def add(root, relative, archive_path=None):
        source = _child(root, relative)
        archive_path = archive_path or str(relative)
        selected[archive_path] = {"path": archive_path, "source": str(source), "bytes": source.stat().st_size, "sha256": _sha(source)}
    for relative in ("tasks.json", "config/study.json", "config/paths.json", "state/plan.json"):
        add(project, relative)
    plan = _read(project / "state/plan.json")
    trialsets = {task["train_trials_file"]: task["train_trials_sha256"] for task in tasks}
    if trialsets != plan["trialsets_sha256"]:
        raise ValueError("Result export trialset mapping differs from the frozen plan")
    for relative, expected in sorted(trialsets.items()):
        add(project, relative)
        if selected[relative]["sha256"] != expected:
            raise ValueError("Result export trialset hash changed")
    for task in tasks:
        prefix = Path("outputs/runs") / task["id"]
        add(project, prefix / "complete.json")
        for path in sorted((project / prefix / "evaluations").rglob("*")):
            if path.is_file() and path.suffix in (".npz", ".json"):
                add(project, path.relative_to(project))
    for path in sorted((project / "outputs/analysis").rglob("*")):
        if path.is_file() and path.suffix in (".json", ".csv", ".png", ".svg", ".pdf"):
            add(project, path.relative_to(project))
    # Capture the actual executing implementation, including its frozen helpers.
    code_root = Path(code_root)
    for sub in ("compmi", "shared/hpcmi"):
        for path in sorted((code_root / sub).glob("*.py")):
            add(code_root, path.relative_to(code_root), "code/" + str(path.relative_to(code_root)))
    if (code_root / "shared/SOURCE_IDENTITY.json").is_file():
        add(code_root, "shared/SOURCE_IDENTITY.json", "code/shared/SOURCE_IDENTITY.json")
    return list(selected.values())


def _tar_add(archive, name, content):
    info = tarfile.TarInfo(name)
    info.size, info.mtime, info.mode = len(content), 0, 0o644
    archive.addfile(info, io.BytesIO(content))


def build_archive(project, code_root=None):
    project = Path(project)
    folder = project / "state/result_export"
    folder.mkdir(parents=True, exist_ok=True)
    receipt = folder / "bundle.json"
    if receipt.exists():
        value = _read(receipt)
        if (folder / value["archive"]["name"]).stat().st_size != value["archive"]["bytes"]:
            raise ValueError("Saved result archive size changed")
        return value
    report, _ = collect_progress(project)
    if not report["ready_for_result_export"]:
        return None
    index_path = folder / "payload_index.json"
    if index_path.exists():
        payloads = _read(index_path)["payloads"]
    else:
        payloads = _payloads(project, code_root or Path(__file__).resolve().parents[1])
        atomic_json(index_path, {"payloads": payloads})
    public_index = {"schema_version": 1, "task_count": report["counts"]["planned"],
                    "payloads": [{k: row[k] for k in ("path", "bytes", "sha256")} for row in payloads]}
    archive_path = folder / "results.tar.gz"
    if not archive_path.exists():
        fd, temporary = tempfile.mkstemp(prefix="results.", suffix=".tmp", dir=folder)
        try:
            with os.fdopen(fd, "wb") as raw:
                with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
                    with tarfile.open(fileobj=compressed, mode="w|") as archive:
                        for row in payloads:
                            content = Path(row["source"]).read_bytes()
                            if len(content) != row["bytes"] or hashlib.sha256(content).hexdigest() != row["sha256"]:
                                raise ValueError("Completed result payload changed during export")
                            _tar_add(archive, row["path"], content)
                        _tar_add(archive, "MANIFEST.json", (json.dumps(public_index, indent=2, sort_keys=True) + "\n").encode())
                raw.flush()
                os.fsync(raw.fileno())
            os.replace(temporary, archive_path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    parts = []
    with archive_path.open("rb") as stream:
        for index, content in enumerate(iter(lambda: stream.read(PART_BYTES), b"")):
            name = "part-%05d.bin" % index
            path = folder / name
            sha = hashlib.sha256(content).hexdigest()
            if path.exists():
                if path.stat().st_size != len(content) or _sha(path) != sha:
                    raise ValueError("Existing result part changed")
            else:
                _atomic_bytes(path, content)
            parts.append({"name": name, "bytes": len(content), "sha256": sha})
    value = {"schema_version": 1, "status": "PACKED_RESULTS_ONLY_NO_MODEL_PARAMETERS",
             "task_count": report["counts"]["planned"], "created_at_utc": utc_now(),
             "archive": {"name": archive_path.name, "bytes": archive_path.stat().st_size, "sha256": _sha(archive_path)},
             "parts": parts, "part_max_bytes": PART_BYTES, "payload_count": len(payloads),
             "contents": "Prediction shards, completion/evaluation/analysis summaries, frozen contracts and actual source code; no EEG or weights"}
    atomic_json(receipt, value)
    return value


def _verified_blob(repository, token, content):
    base = "/repos/" + repository
    result = _api("POST", base + "/git/blobs", token, {"encoding": "base64", "content": base64.b64encode(content).decode("ascii")})
    sha = result.get("sha", "")
    expected_git = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()
    if sha != expected_git:
        raise ValueError("GitHub blob identity differs from the uploaded bytes")
    observed = _api("GET", base + "/git/blobs/" + sha, token)
    if observed.get("encoding") != "base64":
        raise ValueError("GitHub blob readback encoding is invalid")
    decoded = base64.b64decode("".join(observed.get("content", "").split()), validate=True)
    if observed.get("size") != len(content) or hashlib.sha256(decoded).digest() != hashlib.sha256(content).digest():
        raise ValueError("GitHub blob strict SHA256 readback failed")
    return sha


def publish_archive(project, config, token, bundle):
    folder = Path(project) / "state/result_export"
    state_path = folder / "upload.json"
    repository, branch = config["repository"], config["branch"]
    identity = {"repository": repository, "branch": branch, "archive_sha256": bundle["archive"]["sha256"]}
    state = _read(state_path, {"verified_blobs": {}, **identity})
    if any(state.get(key) != value for key, value in identity.items()):
        raise ValueError("Saved upload belongs to different frozen results or destination")
    if state.get("status") == "PUBLISHED_AND_READBACK_VERIFIED":
        return state
    base = "/repos/" + repository
    remote = "research_runs/PAPER1_COMPOSITION_RESULTS_20261027/" + bundle["archive"]["sha256"][:16]
    entries = []
    members = [(row["name"], folder / row["name"], row) for row in bundle["parts"]]
    manifest_bytes = (json.dumps(bundle, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    members.append(("manifest.json", manifest_bytes, {"bytes": len(manifest_bytes), "sha256": hashlib.sha256(manifest_bytes).hexdigest()}))
    for name, source, metadata in members:
        content = source.read_bytes() if isinstance(source, Path) else source
        if len(content) != metadata["bytes"] or hashlib.sha256(content).hexdigest() != metadata["sha256"]:
            raise ValueError("Local result part hash differs from its frozen export receipt")
        stored = state["verified_blobs"].get(name)
        if not stored or stored["sha256"] != metadata["sha256"]:
            sha = _verified_blob(repository, token, content)
            state["verified_blobs"][name] = {"git_sha": sha, **metadata}
            atomic_json(state_path, state)
        else:
            sha = stored["git_sha"]
        entries.append({"path": remote + "/" + name, "mode": "100644", "type": "blob", "sha": sha})
    ref_path = base + "/git/ref/heads/" + urllib.parse.quote(branch, safe="")
    parent = _api("GET", ref_path, token)["object"]["sha"]
    commit = _api("GET", base + "/git/commits/" + parent, token)
    tree = _api("POST", base + "/git/trees", token, {"base_tree": commit["tree"]["sha"], "tree": entries})["sha"]
    created = _api("POST", base + "/git/commits", token,
                   {"message": "Publish complete composition experiment results", "tree": tree, "parents": [parent]})["sha"]
    _api("PATCH", base + "/git/refs/heads/" + urllib.parse.quote(branch, safe=""), token, {"sha": created, "force": False})
    if _api("GET", ref_path, token)["object"]["sha"] != created:
        raise ValueError("GitHub result branch commit readback differs")
    state.update(status="PUBLISHED_AND_READBACK_VERIFIED", commit=created, archive_sha256=bundle["archive"]["sha256"],
                 remote_path=remote, url="https://github.com/" + repository + "/tree/" + urllib.parse.quote(branch, safe="/") + "/" + remote,
                 completed_at_utc=utc_now())
    atomic_json(state_path, state)
    return state


def sync_once(project):
    project = Path(project)
    state = {"updated_at_utc": utc_now(), "training_blocked": False}
    try:
        with _lock(project / "state/sync_once.lock"):
            config = _read(project / "config/sync.json")
            config["repository"] = config.get("repository", config.get("repo"))
            if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", config["repository"]):
                raise ValueError("Invalid GitHub repository")
            if config["branch"] != "hpc/" + config["project_id"]:
                raise ValueError("Reporting branch must belong to this project")
            report, analysis = collect_progress(project)
            report["project_id"] = config["project_id"]
            bundle = build_archive(project) if report["ready_for_result_export"] else None
            token = _read_token(Path(config["token_file"]).expanduser())
            _ensure_branch(config["repository"], config["branch"], token)
            remote = "hpc_status/" + config["project_id"]
            commit = _put_json(config["repository"], config["branch"], remote + "/status.json", token, report)
            if analysis:
                _put_json(config["repository"], config["branch"], remote + "/statistics.json", token, analysis)
            state.update(status="SYNCED", commit=commit, counts=report["counts"])
            if bundle:
                result = publish_archive(project, config, token, bundle)
                state.update(status="COMPLETE_RESULT_PUBLISHED", result_commit=result["commit"], result_url=result["url"],
                             archive_sha256=result["archive_sha256"])
    except BlockingIOError:
        return {**state, "status": "OTHER_SYNC_ACTIVE"}
    except GitHubError as error:
        state.update(status="RETRY_PENDING", error_code=error.code, http_status=error.status)
    except Exception as error:
        # Arbitrary exception text can contain credentials. Only safe type/code
        # metadata is written; the training process never waits for this loop.
        state.update(status="RETRY_PENDING", error_code="sync_" + type(error).__name__)
    try:
        atomic_json(project / "state/sync_status.json", state)
    except OSError:
        state["local_status_write_failed"] = True
    return state


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--daemon", action="store_true")
    group.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=float, default=180)
    args = parser.parse_args(argv)
    if args.interval < 1:
        parser.error("interval must be positive")
    running = True
    def stop(number, frame):
        nonlocal running
        running = False
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        with _lock(args.project / "state/sync_daemon.lock"):
            while running:
                result = sync_once(args.project)
                print(json.dumps(result, sort_keys=True), flush=True)
                if not args.daemon or result["status"] == "COMPLETE_RESULT_PUBLISHED":
                    break
                deadline = time.monotonic() + args.interval
                while running and time.monotonic() < deadline:
                    time.sleep(min(1., max(0., deadline - time.monotonic())))
    except BlockingIOError:
        print(json.dumps({"status": "SYNC_DAEMON_ALREADY_RUNNING", "training_blocked": False}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
