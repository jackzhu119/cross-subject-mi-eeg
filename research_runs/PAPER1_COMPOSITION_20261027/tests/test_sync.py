"""Synthetic publication contracts; no actual network, EEG or credentials."""
import base64
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from compmi import sync
from hpcmi.common import atomic_json, canonical_hash
from hpcmi.github_sync import GitHubError


class FakeGit:
    def __init__(self, fail_second_blob=False):
        self.head = "a" * 40
        self.blobs = {}
        self.posts = 0
        self.fail_second_blob = fail_second_blob

    def __call__(self, method, endpoint, token, payload=None):
        if method == "POST" and endpoint.endswith("/git/blobs"):
            self.posts += 1
            if self.fail_second_blob and self.posts == 2:
                raise GitHubError("github_network_unavailable")
            content = base64.b64decode(payload["content"])
            sha = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()
            self.blobs[sha] = content
            return {"sha": sha}
        if method == "GET" and "/git/blobs/" in endpoint:
            sha = endpoint.rsplit("/", 1)[1]
            content = self.blobs[sha]
            return {"sha": sha, "size": len(content), "encoding": "base64", "content": base64.b64encode(content).decode()}
        if method == "GET" and "/git/ref/heads/" in endpoint:
            return {"object": {"sha": self.head}}
        if method == "GET" and "/git/commits/" in endpoint:
            return {"tree": {"sha": "b" * 40}}
        if method == "POST" and endpoint.endswith("/git/trees"):
            self.tree = payload
            return {"sha": "d" * 40}
        if method == "POST" and endpoint.endswith("/git/commits"):
            return {"sha": "c" * 40}
        if method == "PATCH" and "/git/refs/heads/" in endpoint:
            if payload["force"] is not False:
                raise AssertionError("Result publication must not force branch history")
            self.head = payload["sha"]
            return {"object": {"sha": self.head}}
        raise AssertionError((method, endpoint))


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.project = self.root / "project"
        (self.project / "config").mkdir(parents=True)
        token = self.root / "private-token"
        token.write_text("SYNTHETIC_TOKEN_NEVER_EXPORT\n")
        os.chmod(token, 0o600)
        self.config = {"repository": "owner/repository", "project_id": "paper1-composition-v2",
                       "branch": "hpc/paper1-composition-v2", "token_file": str(token)}
        atomic_json(self.project / "config/sync.json", self.config)
        atomic_json(self.project / "config/study.json", {"epochs": 2, "updates_per_epoch": 3})
        atomic_json(self.project / "config/paths.json", {"data_dir": "/EEG/MUST/NEVER/BE/READ"})
        trialset = self.project / "state/trialsets/test.json"
        atomic_json(trialset, {"indices": {"source": [0, 1]}})
        trial_sha = hashlib.sha256(trialset.read_bytes()).hexdigest()
        self.tasks = []
        for family in ("neural", "classical"):
            task = {"id": "task-" + family, "family": family, "phase": "development", "cell_id": "s9-all",
                    "method": "erm" if family == "neural" else "weighted_csp_rlda", "seed": 123 if family == "neural" else 0,
                    "fold": 0, "test_ids": ["source-held-out"], "train_trials_file": "state/trialsets/test.json",
                    "train_trials_sha256": trial_sha}
            self.tasks.append(task)
            run = self.project / "outputs/runs" / task["id"]
            summary_path = "evaluations/outer_fixed40/hash/summary.json"
            atomic_json(run / summary_path, {"model_sha256": "e" * 64, "people": [{"person_id": "source-held-out", "dataset": "bnci",
                        "ba": .7, "min_recall": .6, "recall_left": .6, "recall_right": .8}]})
            (run / "evaluations/outer_fixed40/hash/predictions.npz").write_bytes(b"synthetic logits and labels")
            atomic_json(run / "complete.json", {**task, "task_id": task["id"], "status": "complete", "complete": True,
                        "model_sha256": "e" * 64, "global_step": 6 if family == "neural" else 0,
                        "optimizer_updates": 6 if family == "neural" else 0, "epochs_completed": 2,
                        "classical_fits_completed": 1 if family == "classical" else 0,
                        "evaluations": {"outer_fixed40": summary_path}})
            (run / "checkpoints").mkdir()
            (run / "checkpoints/latest.pt").write_bytes(b"MODEL_WEIGHTS_DO_NOT_EXPORT")
            (run / "model.npz").write_bytes(b"CLASSICAL_WEIGHTS_DO_NOT_EXPORT")
        atomic_json(self.project / "tasks.json", self.tasks)
        atomic_json(self.project / "state/plan.json", {"fingerprint": "f" * 64, "tasks_sha256": canonical_hash(self.tasks),
                    "task_counts": {"total": 2}, "trialsets_sha256": {"state/trialsets/test.json": trial_sha}})
        atomic_json(self.project / "outputs/analysis/summary.json", {"status": "complete", "pending": {}, "plan_fingerprint": "f" * 64})
        (self.project / "outputs/analysis/results.csv").write_text("metric,effect\nW,0.1\n")
        (self.project / "raw").mkdir()
        (self.project / "raw/EEG.edf").write_bytes(b"RAW_EEG_DO_NOT_EXPORT")
        self.code = self.root / "code"
        (self.code / "compmi").mkdir(parents=True)
        (self.code / "compmi/worker.py").write_text("# synthetic implementation identity\n")

    def tearDown(self):
        self.temp.cleanup()

    def test_archive_contains_all_predictions_and_contracts_but_no_parameters_or_token(self):
        bundle = sync.build_archive(self.project, self.code)
        folder = self.project / "state/result_export"
        archive = folder / bundle["archive"]["name"]
        with tarfile.open(archive, "r:gz") as stream:
            names = stream.getnames()
            combined = b"".join(stream.extractfile(name).read() for name in names)
            manifest = json.loads(stream.extractfile("MANIFEST.json").read())
        self.assertEqual(sum(name.endswith("predictions.npz") for name in names), 2)
        self.assertIn("tasks.json", names)
        self.assertIn("code/compmi/worker.py", names)
        self.assertIn("state/trialsets/test.json", names)
        self.assertEqual(manifest["task_count"], 2)
        self.assertFalse(any("checkpoints" in name or name.startswith("raw/") or name.endswith("model.npz") or name == "config/sync.json" for name in names))
        for secret in (b"SYNTHETIC_TOKEN_NEVER_EXPORT", b"MODEL_WEIGHTS_DO_NOT_EXPORT", b"RAW_EEG_DO_NOT_EXPORT"):
            self.assertNotIn(secret, combined)
        self.assertTrue(all(row["bytes"] <= 512 * 1024 for row in bundle["parts"]))
        timestamp = archive.stat().st_mtime_ns
        with patch.object(sync, "_payloads", side_effect=AssertionError("Completed archive packed twice")):
            self.assertEqual(sync.build_archive(self.project, self.code), bundle)
        self.assertEqual(archive.stat().st_mtime_ns, timestamp)

    def test_failed_blob_upload_resumes_verified_parts_and_commits_without_force(self):
        bundle = sync.build_archive(self.project, self.code)
        api = FakeGit(fail_second_blob=True)
        with patch.object(sync, "_api", api):
            with self.assertRaises(GitHubError):
                sync.publish_archive(self.project, self.config, "synthetic", bundle)
            saved = json.loads((self.project / "state/result_export/upload.json").read_text())
            self.assertEqual(len(saved["verified_blobs"]), 1)
            result = sync.publish_archive(self.project, self.config, "synthetic", bundle)
            self.assertEqual(result["status"], "PUBLISHED_AND_READBACK_VERIFIED")
            self.assertEqual(api.posts, len(bundle["parts"]) + 2)
            before = api.posts
            self.assertEqual(sync.publish_archive(self.project, self.config, "synthetic", bundle), result)
            self.assertEqual(api.posts, before)

    def test_network_failure_is_retry_pending_and_never_blocks_training(self):
        (self.project / "outputs/runs/task-classical/complete.json").unlink()
        with patch.object(sync, "_ensure_branch", side_effect=GitHubError("github_network_unavailable")):
            result = sync.sync_once(self.project)
        self.assertEqual(result["status"], "RETRY_PENDING")
        self.assertFalse(result["training_blocked"])
        self.assertFalse((self.project / "state/result_export/bundle.json").exists())

    def test_partial_or_wrong_update_count_never_exports_as_complete(self):
        complete = self.project / "outputs/runs/task-neural/complete.json"
        content = json.loads(complete.read_text())
        content["optimizer_updates"] = 5
        atomic_json(complete, content)
        progress, _ = sync.collect_progress(self.project)
        self.assertEqual(progress["counts"], {"planned": 2, "completed": 1, "remaining": 1})
        self.assertFalse(progress["ready_for_result_export"])
        self.assertIsNone(sync.build_archive(self.project, self.code))
        content["optimizer_updates"] = 6
        atomic_json(complete, content)
        atomic_json(self.project / "outputs/analysis/summary.json", {"status": "partial", "pending": {"external": 1}, "plan_fingerprint": "f" * 64})
        self.assertFalse(sync.collect_progress(self.project)[0]["ready_for_result_export"])

    def test_corrupt_github_readback_does_not_mark_result_published(self):
        api = FakeGit()
        def corrupt(method, endpoint, token, payload=None):
            result = api(method, endpoint, token, payload)
            if method == "GET" and "/git/blobs/" in endpoint:
                result["content"] = base64.b64encode(b"altered").decode()
            return result
        with patch.object(sync, "_api", corrupt):
            with self.assertRaisesRegex(ValueError, "SHA256"):
                sync._verified_blob("owner/repository", "synthetic", b"expected result bytes")
        self.assertFalse((self.project / "state/result_export/upload.json").exists())

    def test_descriptive_means_wait_for_all_seeds_then_weight_people_and_cohorts(self):
        completed = []
        for seed, offset in ((1, 0.), (2, .1)):
            people = []
            for person, cohort, value in (("B1", "bnci", .2), ("B2", "bnci", .4), ("Y1", "yang", .9)):
                people.append({"person_id": person, "dataset": cohort,
                               **{metric: value + offset for metric in ("min_recall", "ba", "recall_left", "recall_right")}})
            completed.append(({"seed": seed}, {"_summary": {"people": people}}))
        key = ("neural", "development", "s60-all", "erm")
        group = {"planned": 2, "seeds": {1, 2}, "completed": completed[:1]}
        partial = sync._descriptive({key: group})[0]
        self.assertEqual(partial["status"], "partial_pending_all_registered_folds_and_seeds")
        self.assertNotIn("metrics", partial)
        group["completed"] = completed
        full = sync._descriptive({key: group})[0]
        self.assertEqual(full["n_participants"], 3)
        self.assertEqual(full["n_seeds"], 2)
        self.assertAlmostEqual(full["metrics"]["min_recall"], .65)

    def test_daemon_exits_after_verified_result_publication(self):
        with patch.object(sync, "sync_once", return_value={"status": "COMPLETE_RESULT_PUBLISHED", "training_blocked": False}), \
                patch.object(sync.time, "sleep", side_effect=AssertionError("Finished uploader kept running")), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sync.main(["--project", str(self.project), "--daemon", "--interval", "180"]), 0)


if __name__ == "__main__":
    unittest.main()
