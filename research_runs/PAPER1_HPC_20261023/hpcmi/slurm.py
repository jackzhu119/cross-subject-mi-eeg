"""Small Slurm 20.11 array adapter. No remote downloads or training happen here.

One active training array per project keeps concurrency <= max_parallel across
repeated launch commands. The caller decides phases and which failed tasks to
resume; this module never automatically resurrects a cancelled task.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import uuid


DEFAULT_CLUSTER = {
    "account": "zhuziyuan", "partition": "hpc_gpu1",
    "gres": "gpu:NVIDIAA100-SXM4-80GB:1", "cpus_per_task": 24,
    "mem": "128G", "max_parallel": 3, "exclude": ["gpu3"],
    "time_limit": "1-00:00:00", "signal_seconds": 180,
    "squeue_user": "zhuziyuan",
}
TERMINAL_STATES = {
    "CANCELLED", "COMPLETED", "FAILED", "TIMEOUT", "NODE_FAIL",
    "OUT_OF_MEMORY", "BOOT_FAIL", "DEADLINE", "REVOKED", "PREEMPTED",
}
TASK_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")


def _utc():
    return datetime.now(timezone.utc).isoformat()


def _atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def submission_lock(project):
    """Short local/shared-filesystem submission mutex; never delete its inode."""
    folder = Path(project).resolve() / "state"
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "submission.lock").open("a+") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Another launch is currently updating this project's submissions") from exc
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def slurm_options(project, cluster_config=None, job_name="paper1-hpc"):
    """Return portable sbatch options and create absolute log directories first."""
    c = dict(DEFAULT_CLUSTER)
    c.update(cluster_config or {})
    if int(c["max_parallel"]) < 1 or int(c["max_parallel"]) > 3:
        raise ValueError("max_parallel must be between 1 and 3 for this run")
    if int(c["cpus_per_task"]) < 1 or int(c["signal_seconds"]) < 30:
        raise ValueError("Invalid CPU or advance-signal allocation")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", job_name):
        raise ValueError("Invalid job name")
    log_dir = Path(project).resolve() / "logs" / "slurm"
    log_dir.mkdir(parents=True, exist_ok=True)
    result = ["--nodes=1", "--ntasks=1", "--account=" + str(c["account"]), "--partition=" + str(c["partition"]),
              "--gres=" + str(c["gres"]), "--cpus-per-task=" + str(c["cpus_per_task"]),
              "--mem=" + str(c["mem"]), "--time=" + str(c["time_limit"]),
              "--signal=B:USR1@" + str(c["signal_seconds"]), "--requeue",
              "--job-name=" + job_name, "--chdir=" + str(Path(project).resolve()),
              "--output=" + str(log_dir / (job_name + "_%A_%a.out")),
              "--error=" + str(log_dir / (job_name + "_%A_%a.err"))]
    exclude = c.get("exclude", [])
    if isinstance(exclude, str):
        exclude = [exclude] if exclude else []
    if exclude:
        if not all(re.fullmatch(r"[A-Za-z0-9_.-]+", node) for node in exclude):
            raise ValueError("exclude must contain plain node names")
        result.append("--exclude=" + ",".join(exclude))
    return result


class SlurmClient:
    def __init__(self, project, cluster_config=None, runner=None):
        self.project = Path(project).resolve()
        self.config = dict(DEFAULT_CLUSTER)
        self.config.update(cluster_config or {})
        self.runner = runner or subprocess.run
        self.ledger_path = self.project / "state" / "submissions.json"

    def _read(self):
        if not self.ledger_path.exists():
            return {"schema_version": 1, "submissions": []}
        value = json.loads(self.ledger_path.read_text())
        if value.get("schema_version") != 1 or not isinstance(value.get("submissions"), list):
            raise ValueError("Invalid submissions ledger; existing record retained")
        return value

    def _command(self, argv):
        return self.runner(argv, text=True, capture_output=True, timeout=30, check=False)

    def _queue(self):
        # %a is the account, not the array index. --array expands %i as job_index.
        result = self._command(["squeue", "--array", "-h", "-u", self.config["squeue_user"],
                                "-o", "%i|%j|%T"])
        if result.returncode:
            raise RuntimeError("squeue failed; no new submission attempted: " + result.stderr.strip()[:1000])
        rows = []
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            fields = [v.strip() for v in line.split("|")]
            if len(fields) != 3:
                raise RuntimeError("Unparseable squeue row; no new submission attempted")
            rows.append(tuple(fields))
        return rows

    def _reconcile_intents(self, ledger, queue):
        changed = False
        for item in ledger["submissions"]:
            if item.get("job_id") is not None or item["status"] not in {"SUBMITTING", "SUBMISSION_UNCERTAIN"}:
                continue
            observed = {token.split("_", 1)[0] for token, name, _ in queue if name == item["job_name"]}
            if len(observed) == 1 and next(iter(observed)).isdigit():
                item.update(job_id=next(iter(observed)), status="SUBMITTED_RECOVERED", recovered_at_utc=_utc())
                changed = True
            elif len(observed) > 1:
                raise RuntimeError("Multiple job IDs match one submission intent; inspect the retained ledger")
        if changed:
            _atomic_json(self.ledger_path, ledger)

    def _active(self, ledger, queue):
        tasks = set()
        for item in ledger["submissions"]:
            for token, name, state in queue:
                if name != item["job_name"] or state in TERMINAL_STATES:
                    continue
                match = re.fullmatch(r"(\d+)(?:_(\d+))?", token)
                if not match:
                    raise RuntimeError("Array queue was not expanded; cannot safely establish task identity")
                if item.get("job_id") and match.group(1) != str(item["job_id"]):
                    raise RuntimeError("Queue job name/ID disagree with the submission ledger")
                if match.group(2) is None:
                    tasks.update(item["tasks"])
                else:
                    index = int(match.group(2))
                    if index >= len(item["tasks"]):
                        raise RuntimeError("Queue array index exceeds retained submission map")
                    tasks.add(item["tasks"][index])
        return tasks

    def active_task_ids(self):
        with submission_lock(self.project):
            ledger, queue = self._read(), self._queue()
            self._reconcile_intents(ledger, queue)
            return self._active(ledger, queue)

    def task_scheduler_states(self):
        """Return latest registered scheduler states, including explicit CANCELLED.

        UNKNOWN stays unknown when accounting is unavailable; it does not mean
        an absent job completed or that an automatic retry is authorized.
        """
        with submission_lock(self.project):
            ledger, queue = self._read(), self._queue()
            self._reconcile_intents(ledger, queue)
            states = {}
            job_items = [x for x in ledger["submissions"] if x.get("job_id")]
            accounting = {}
            if job_items:
                ids = ",".join(dict.fromkeys(str(x["job_id"]) for x in job_items))
                try:
                    # JobID preserves array_job_task; JobIDRaw may expose the
                    # internal numeric task allocation instead of that mapping.
                    result = self._command(["sacct", "-n", "-P", "-j", ids, "-o", "JobID%64,State%32"])
                except (OSError, subprocess.TimeoutExpired):
                    result = None
                if result is not None and result.returncode == 0:
                    for line in result.stdout.splitlines():
                        fields = line.strip().split("|")
                        if len(fields) >= 2 and fields[1].strip() and re.fullmatch(r"\d+(?:_\d+)?", fields[0]):
                            accounting[fields[0]] = fields[1].split()[0].rstrip("+")
            for item in job_items:
                for index, task in enumerate(item["tasks"]):
                    token = str(item["job_id"]) + "_" + str(index)
                    state = accounting.get(token, accounting.get(str(item["job_id"]), "UNKNOWN"))
                    for queue_token, name, observed in queue:
                        if name == item["job_name"] and queue_token in {token, str(item["job_id"])}:
                            state = observed
                    states[task] = state
            return states

    def submit_task_array(self, task_ids, python_executable, code_root=None):
        task_ids = list(task_ids)
        if not task_ids or len(set(task_ids)) != len(task_ids) or not all(TASK_PATTERN.fullmatch(t) for t in task_ids):
            raise ValueError("Nonempty, unique safe task IDs are required")
        interpreter = Path(python_executable)
        if not interpreter.is_absolute() or not interpreter.is_file() or not os.access(interpreter, os.X_OK):
            raise ValueError("Prepared Python interpreter must be an absolute executable file")
        code_root = Path(code_root or Path(__file__).resolve().parents[1]).resolve()
        script = code_root / "slurm" / "train_array.sh"
        if not script.is_file():
            raise FileNotFoundError(script)
        with submission_lock(self.project):
            ledger, queue = self._read(), self._queue()
            self._reconcile_intents(ledger, queue)
            active = self._active(ledger, queue)
            if active:
                raise RuntimeError("ACTIVE_ARRAY_EXISTS: existing project tasks must finish before another array is submitted")
            if any(x["status"] in {"SUBMITTING", "SUBMISSION_UNCERTAIN"} and x.get("job_id") is None for x in ledger["submissions"]):
                raise RuntimeError("A previous sbatch outcome is uncertain; inspect the retained intent before retrying")
            nonce = uuid.uuid4().hex[:10]
            project_key = hashlib.sha256(str(self.project).encode()).hexdigest()[:8]
            name = "p1-" + project_key + "-" + nonce
            map_path = self.project / "state" / "submission_maps" / (nonce + ".json")
            mapping = {"schema_version": 1, "submission_id": nonce, "tasks": task_ids}
            _atomic_json(map_path, mapping)
            item = {**mapping, "created_at_utc": _utc(), "job_name": name, "job_id": None,
                    "status": "SUBMITTING", "map_path": str(map_path), "max_parallel": int(self.config["max_parallel"])}
            ledger["submissions"].append(item)
            _atomic_json(self.ledger_path, ledger)
            command = ["sbatch", "--parsable"] + slurm_options(self.project, self.config, name)
            command += ["--array=0-" + str(len(task_ids) - 1) + "%" + str(self.config["max_parallel"]),
                        str(script), str(self.project), str(interpreter), str(code_root), str(map_path)]
            try:
                result = self._command(command)
            except (OSError, subprocess.TimeoutExpired) as exc:
                item.update(status="SUBMISSION_UNCERTAIN", error_class=type(exc).__name__)
                _atomic_json(self.ledger_path, ledger)
                raise RuntimeError("sbatch outcome uncertain; retained job-name intent prevents duplicate submission") from exc
            answer = result.stdout.strip().split(";", 1)[0]
            if result.returncode or not answer.isdigit():
                item.update(status="SUBMISSION_FAILED" if result.returncode else "SUBMISSION_UNCERTAIN",
                            returncode=result.returncode, stderr=result.stderr.strip()[:2000],
                            stdout=result.stdout.strip()[:1000])
                _atomic_json(self.ledger_path, ledger)
                raise RuntimeError("sbatch failed; retained submission record: " + result.stderr.strip()[:1000])
            item.update(status="SUBMITTED", job_id=answer, submitted_at_utc=_utc())
            _atomic_json(self.ledger_path, ledger)
            return answer


def submit_task_array(project, task_ids, python_executable, cluster_config=None, code_root=None):
    return SlurmClient(project, cluster_config).submit_task_array(task_ids, python_executable, code_root)


def active_task_ids(project, cluster_config=None):
    return SlurmClient(project, cluster_config).active_task_ids()


def task_scheduler_states(project, cluster_config=None):
    return SlurmClient(project, cluster_config).task_scheduler_states()


def _aux_client(project, kind, cluster_config):
    if kind not in {"prep", "smoke"}:
        raise ValueError("Auxiliary kind must be prep or smoke")
    client = SlurmClient(project, cluster_config)
    client.ledger_path = client.project / "state" / ("aux_" + kind + ".json")
    return client


def _aux_state(client, ledger, queue):
    client._reconcile_intents(ledger, queue)
    if not ledger["submissions"]:
        return {"state": "NOT_SUBMITTED", "job_id": None, "record": None}
    item = ledger["submissions"][-1]
    for token, name, state in queue:
        if name == item["job_name"]:
            if not token.isdigit() or (item.get("job_id") and token != str(item["job_id"])):
                raise RuntimeError("Auxiliary scheduler identity disagrees with retained record")
            return {"state": state, "job_id": token, "record": item}
    state = "UNKNOWN"
    if item.get("job_id"):
        try:
            result = client._command(["sacct", "-n", "-P", "-j", str(item["job_id"]), "-o", "JobID%64,State%32"])
        except (OSError, subprocess.TimeoutExpired):
            result = None
        if result is not None and not result.returncode:
            for line in result.stdout.splitlines():
                fields = line.strip().split("|")
                if len(fields) >= 2 and fields[0] == str(item["job_id"]) and fields[1].strip():
                    state = fields[1].split()[0].rstrip("+")
    elif item["status"] == "SUBMISSION_FAILED":
        state = "SUBMISSION_FAILED"
    return {"state": state, "job_id": item.get("job_id"), "record": item}


def auxiliary_state(project, kind, cluster_config=None):
    """Inspect the latest preparation/smoke job; scheduler absence is UNKNOWN."""
    client = _aux_client(project, kind, cluster_config)
    with submission_lock(project):
        return _aux_state(client, client._read(), client._queue())


def submit_auxiliary(project, kind, python_executable, script_args=None,
                     cluster_config=None, explicit_resume=False, code_root=None):
    """Submit one preparation/smoke job, retaining all prior attempts.

    Existing active jobs are reused. Failed/cancelled/unknown attempts require
    a user-invoked resume; an unattended controller must pass False. Completion
    of the actual preparation/smoke receipt remains the caller's responsibility.
    """
    client = _aux_client(project, kind, cluster_config)
    interpreter = Path(python_executable)
    if not interpreter.is_absolute() or not interpreter.is_file() or not os.access(interpreter, os.X_OK):
        raise ValueError("Prepared Python interpreter must be an absolute executable file")
    code_root = Path(code_root or Path(__file__).resolve().parents[1]).resolve()
    script = code_root / "slurm" / ("prepare.sh" if kind == "prep" else "smoke.sh")
    if not script.is_file():
        raise FileNotFoundError(script)
    with submission_lock(project):
        ledger, queue = client._read(), client._queue()
        observed = _aux_state(client, ledger, queue)
        record, state = observed["record"], observed["state"]
        if record:
            if state not in TERMINAL_STATES | {"UNKNOWN", "SUBMISSION_FAILED"}:
                return str(observed["job_id"])
            if record.get("job_id") is None and record["status"] in {"SUBMITTING", "SUBMISSION_UNCERTAIN"}:
                raise RuntimeError("Auxiliary sbatch outcome uncertain; retained intent prevents duplicate submission")
            if state == "COMPLETED" and not explicit_resume:
                return str(observed["job_id"])
            if not explicit_resume:
                raise RuntimeError("AUXILIARY_REQUIRES_MANUAL_RESUME: " + kind + " " + state)
        nonce = uuid.uuid4().hex[:10]
        key = hashlib.sha256(str(client.project).encode()).hexdigest()[:8]
        name = "p1-" + kind + "-" + key + "-" + nonce
        item = {"created_at_utc": _utc(), "job_name": name, "job_id": None,
                "status": "SUBMITTING", "kind": kind}
        ledger["submissions"].append(item)
        _atomic_json(client.ledger_path, ledger)
        options = slurm_options(project, client.config, name)
        command = ["sbatch", "--parsable"] + options + [str(script), str(client.project),
                   str(interpreter), str(code_root)] + [str(x) for x in (script_args or [])]
        try:
            result = client._command(command)
        except (OSError, subprocess.TimeoutExpired) as exc:
            item.update(status="SUBMISSION_UNCERTAIN", error_class=type(exc).__name__)
            _atomic_json(client.ledger_path, ledger)
            raise RuntimeError("Auxiliary sbatch outcome uncertain; inspect retained intent") from exc
        answer = result.stdout.strip().split(";", 1)[0]
        if result.returncode or not answer.isdigit():
            item.update(status="SUBMISSION_FAILED" if result.returncode else "SUBMISSION_UNCERTAIN",
                        returncode=result.returncode, stderr=result.stderr.strip()[:2000],
                        stdout=result.stdout.strip()[:1000])
            _atomic_json(client.ledger_path, ledger)
            raise RuntimeError("Auxiliary sbatch failed: " + result.stderr.strip()[:1000])
        item.update(status="SUBMITTED", job_id=answer, submitted_at_utc=_utc())
        _atomic_json(client.ledger_path, ledger)
        return answer
