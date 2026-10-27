"""Source-only plan, matched support and restart identity checks; no model fits."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "shared")]

from compmi.plan import create_plan, task_trialset
from hpcmi.common import atomic_json, read_json


class HeaderOnly(dict):
    def __getitem__(self, key):
        if key == "X":
            raise AssertionError("Planning must not access EEG arrays")
        return super().__getitem__(key)


class FakeRegistry:
    def __init__(self):
        self.fingerprint = "a" * 64
        self.entries = ([{"id": f"bnci-{i:02d}", "dataset": "bnci", "role": "source"} for i in range(9)]
                        + [{"id": f"yang-{i:02d}", "dataset": "yang", "role": "source"} for i in range(51)]
                        + [{"id": f"dreyer-{i:02d}", "dataset": "dreyer", "role": "external"} for i in range(85)])
        self.by_id = {entry["id"]: entry for entry in self.entries}
        self.source_ids = [entry["id"] for entry in self.entries if entry["role"] == "source"]
        self.external_ids = [entry["id"] for entry in self.entries if entry["role"] == "external"]
        self.loads = []
        self.metadata = {}
        for person in self.source_ids:
            n = 144 if self.by_id[person]["dataset"] == "bnci" else 300
            self.metadata[person] = HeaderOnly(y=np.repeat(np.arange(2, dtype=np.int64), n),
                                              trial_ids=[f"{person}/t{i:04d}" for i in range(n * 2)])

    def ensure_source(self, ids):
        if len(ids) != len(set(ids)) or any(self.by_id[p]["role"] != "source" for p in ids):
            raise ValueError("External participant in training whitelist")

    def load_person(self, person):
        if self.by_id[person]["role"] != "source":
            raise AssertionError("External EEG/labels must not be read")
        self.loads.append(person)
        return self.metadata[person]


def base_plan(registry):
    bnci = [p for p in registry.source_ids if p.startswith("bnci")]
    yang = [p for p in registry.source_ids if p.startswith("yang")]
    return {"fingerprint": "old-frozen-plan", "partitions": [
        {"fold": fold, "test_ids": list(b) + list(y)}
        for fold, (b, y) in enumerate(zip(np.array_split(bnci, 5), np.array_split(yang, 5)))]}


class CompositionPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.project = Path(cls.temp.name)
        (cls.project / "config").mkdir()
        shutil.copyfile(ROOT / "config/study.json", cls.project / "config/study.json")
        atomic_json(cls.project / "config/paths.json", {"data_dir": "/not-read", "base_project": "/not-read"})
        cls.registry = FakeRegistry()
        cls.base = base_plan(cls.registry)
        cls.plan = create_plan(cls.project, cls.registry, cls.base)
        cls.tasks = read_json(cls.project / "tasks.json")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_complete_task_grid_and_no_target_or_eeg_read(self):
        self.assertEqual(len(self.plan["cells"]), 15)
        self.assertEqual(len(self.tasks), 630)
        self.assertEqual(len(self.plan["trialsets_sha256"]), 90)
        self.assertEqual(self.plan["task_counts"], {
            "neural_development": 450, "neural_final": 90, "classical_development": 75,
            "classical_final": 15, "neural_total": 540, "classical_total": 90, "total": 630})
        self.assertEqual(set(self.registry.loads), set(self.registry.source_ids))
        self.assertEqual(len({task["id"] for task in self.tasks}), 630)
        for task in self.tasks:
            self.assertLess(len(task["id"]), 100)
            self.assertEqual(task["validation_ids"], [])
            self.assertFalse(set(task["train_ids"]) & set(task["test_ids"]))
            self.assertTrue(set(task["train_ids"]).issubset(self.registry.source_ids))
            if task["phase"] == "development":
                self.assertEqual(task["test_ids"], self.plan["outer_folds"][task["fold"]]["test_ids"])
            else:
                self.assertEqual(task["test_ids"], sorted(self.registry.external_ids))

    def test_s29_subsets_are_frozen_four_per_common_fold(self):
        selected = []
        for cell in self.plan["cells"]:
            if cell["pool"] != "S29" or cell["regime"] != "all":
                continue
            people = set(cell["pool_ids"])
            self.assertEqual(len(people), 29)
            self.assertEqual(sum(p.startswith("bnci") for p in people), 9)
            for fold in self.plan["outer_folds"]:
                self.assertEqual(sum(p.startswith("yang") for p in people & set(fold["test_ids"])), 4)
            selected.append(tuple(sorted(people)))
        self.assertEqual(len(set(selected)), 5)
        self.assertEqual(self.plan["s9_matched_alias"], "s9-all")
        self.assertFalse(any(task["cell_id"] == "s9-matched" for task in self.tasks))

    def test_matched_budgets_and_shared_support_across_methods_and_seeds(self):
        references = {}
        for relative in self.plan["trialsets_sha256"]:
            value = read_json(self.project / relative)
            cell = next(cell for cell in self.plan["cells"] if cell["cell_id"] == value["cell_id"])
            if cell["regime"] != "matched" and cell["pool"] != "S9":
                continue
            key = (value["phase"], value["fold"])
            references.setdefault(key, value["counts"]["class_total"])
            self.assertEqual(value["counts"]["class_total"], references[key])
            self.assertEqual(value["counts"]["class_total"], value["matched_reference_class_budget"])
            if cell["pool"] in ("S29", "S60"):
                self.assertEqual(value["counts"]["cohort_class_total"]["bnci"],
                                 value["counts"]["cohort_class_total"]["yang"])
            for people in value["indices_by_person"].values():
                self.assertEqual(people, sorted(set(people)))
        self.assertEqual(references[("final", None)], {"0": 1296, "1": 1296})
        for cell in self.plan["cells"]:
            for phase, fold in [("development", 0), ("final", None)]:
                tasks = [t for t in self.tasks if t["cell_id"] == cell["cell_id"]
                         and t["phase"] == phase and t["fold"] == fold]
                self.assertEqual(len(tasks), 7)
                self.assertEqual(len({(t["train_trials_file"], t["train_trials_sha256"]) for t in tasks}), 1)

    def test_restart_reuses_without_reloading_source_and_runtime_changes_are_allowed(self):
        config_path = self.project / "config/study.json"
        original = config_path.read_bytes()
        config = json.loads(original)
        config["checkpoint_seconds"] += 1
        config["resource_request"]["total_cpus"] = 20
        atomic_json(config_path, config)
        before = (self.project / "state/plan.json").read_bytes()
        loads = len(self.registry.loads)
        try:
            actual = create_plan(self.project, self.registry, self.base)
            self.assertTrue(actual["reused"])
            self.assertEqual(actual["fingerprint"], self.plan["fingerprint"])
            self.assertEqual(len(self.registry.loads), loads)
            self.assertEqual((self.project / "state/plan.json").read_bytes(), before)
        finally:
            config_path.write_bytes(original)

    def test_science_and_task_tampering_stop_without_reset(self):
        config_path = self.project / "config/study.json"
        original = config_path.read_bytes()
        config = json.loads(original)
        config["objective"]["tail_weight"] = .4
        atomic_json(config_path, config)
        try:
            with self.assertRaisesRegex(ValueError, "scientific plan differs"):
                create_plan(self.project, self.registry, self.base)
        finally:
            config_path.write_bytes(original)
        task_path = self.project / "tasks.json"
        original = task_path.read_bytes()
        tasks = json.loads(original)
        tasks[0]["seed"] = 1
        atomic_json(task_path, tasks)
        try:
            with self.assertRaisesRegex(ValueError, "task whitelist changed"):
                create_plan(self.project, self.registry, self.base)
            self.assertEqual(read_json(task_path)[0]["seed"], 1)
        finally:
            task_path.write_bytes(original)

    def test_worker_whitelist_validation_and_corruption_rejection(self):
        task = next(t for t in self.tasks if t["cell_id"] == "s60-matched")
        accepted = task_trialset(self.project, task, self.registry)
        self.assertEqual(set(accepted), set(task["train_ids"]))
        path = self.project / task["train_trials_file"]
        original = path.read_bytes()
        value = json.loads(original)
        person = task["train_ids"][0]
        value["trial_ids_by_person"][person][0] = "changed-trial"
        atomic_json(path, value)
        changed = {**task, "train_trials_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        try:
            with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
                task_trialset(self.project, task, self.registry)
            with self.assertRaisesRegex(ValueError, "trial identity changed"):
                task_trialset(self.project, changed, self.registry)
            with self.assertRaisesRegex(ValueError, "Frozen trialset changed"):
                create_plan(self.project, self.registry, self.base)
        finally:
            path.write_bytes(original)

    def test_invalid_common_folds_rejected(self):
        changed = copy.deepcopy(self.base)
        changed["partitions"][0]["test_ids"].append(changed["partitions"][1]["test_ids"][0])
        with self.assertRaisesRegex(ValueError, "partition all source"):
            create_plan(self.project, self.registry, changed)


if __name__ == "__main__":
    unittest.main()
