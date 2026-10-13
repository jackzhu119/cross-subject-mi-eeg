#!/usr/bin/env python3
"""Register 2/2/2/3 source partitions without loading EEG or outcomes."""
from __future__ import annotations

import csv
import hashlib
import itertools
import json
import math
import random
from pathlib import Path


GROUPING_RNG = 20261017
PRIMARY = ((1, 2), (3, 4), (5, 6), (7, 8, 9))


def pairings(people: tuple[int, ...]):
    if not people:
        yield ()
        return
    first = people[0]
    for partner in people[1:]:
        remaining = tuple(p for p in people if p not in (first, partner))
        for rest in pairings(remaining):
            yield tuple(sorted(((first, partner),) + rest))


def register() -> list[tuple]:
    people = tuple(range(1, 10))
    partitions = []
    for triple in itertools.combinations(people, 3):
        remaining = tuple(p for p in people if p not in triple)
        partitions.extend(pairs + (triple,) for pairs in pairings(remaining))
    partitions = sorted(partitions)
    expected = math.factorial(9) // (math.factorial(2) ** 3 * math.factorial(3) ** 2)
    assert expected == 1260 == len(partitions) == len(set(partitions))
    for partition in partitions:
        assert tuple(map(len, partition)) == (2, 2, 2, 3)
        assert sorted(itertools.chain.from_iterable(partition)) == list(people)
    assert PRIMARY in partitions
    return partitions


def main() -> None:
    output = Path(__file__).resolve().parents[1] / "results"
    output.mkdir(parents=True, exist_ok=True)
    partitions = register()
    alternatives = random.Random(GROUPING_RNG).sample([p for p in partitions if p != PRIMARY], 5)
    selected = [PRIMARY] + alternatives
    partition_ids = {p: f"partition-{i:04d}" for i, p in enumerate(partitions, 1)}
    csv_path = output / "source_grouping_registry.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(("partition_id", "group_1", "group_2", "group_3", "group_4", "selected_variant"))
        for p in partitions:
            variant = f"G{selected.index(p)}" if p in selected else ""
            writer.writerow((partition_ids[p], *[";".join(map(str, group)) for group in p], variant))
    selection = {"schema_version": 1, "registry_seed": GROUPING_RNG,
                 "all_partition_count": len(partitions), "group_sizes": [2, 2, 2, 3],
                 "fold_weighting": "equal_fold", "source_cv_seed": 20261012,
                 "primary_variant": "G0", "optional_sensitivity_variants": [f"G{i}" for i in range(1, 6)],
                 "selection_uses_eeg_or_performance": False, "model_fits_started": 0,
                 "target_predictions_computed": False, "extension_execution_authorized_by_this_file": False,
                 "primary_inner_trajectories": 8, "optional_extra_inner_trajectories": 40,
                 "groupings": [{"variant": f"G{i}", "partition_id": partition_ids[p],
                                "validation_groups": [list(g) for g in p],
                                "role": "primary" if i == 0 else "optional_source_only_sensitivity"}
                               for i, p in enumerate(selected)],
                 "registry_csv_sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
                 "verification": {"complete_participant_assignment": True,
                                  "unique_partitions": True, "count_matches_combinatorics": True,
                                  "primary_included": True, "no_duplicate_selected_variant": len(set(selected)) == 6}}
    (output / "source_grouping_selection.json").write_text(json.dumps(selection, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"registered_partitions": len(partitions), "selected_variants": len(selected),
                      "eeg_data_read": False, "model_fits_started": 0,
                      "registry_csv_sha256": selection["registry_csv_sha256"]}))


if __name__ == "__main__":
    main()
