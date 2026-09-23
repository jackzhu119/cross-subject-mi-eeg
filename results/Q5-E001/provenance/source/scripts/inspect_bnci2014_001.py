"""Inspect BNCI2014_001 metadata and, optionally, one subject's real recordings.

The default mode does not download EEG data. Use --load-data explicitly when
you are ready for MOABB to fetch and cache the selected subject.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject", type=int, default=1, choices=range(1, 10))
    parser.add_argument(
        "--load-data",
        action="store_true",
        help="Download/cache and inspect the selected subject's real data.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/P1-E001/data_audit.json"),
        help="JSON path used only when --load-data is supplied.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data/raw"),
        help="Local MOABB/BNCI cache root (only used with --load-data).",
    )
    return parser.parse_args()


def _json_safe(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "item"):
        return value.item()
    return str(value)


def summarize_raw(raw: Any, mne: Any) -> dict[str, Any]:
    channel_types = list(raw.get_channel_types())
    annotations = Counter(str(item) for item in raw.annotations.description)
    events = mne.find_events(raw, stim_channel="STI", shortest_event=1, verbose=False)
    event_counts = Counter(int(item) for item in events[:, 2])
    return {
        "n_channels": len(raw.ch_names),
        "n_times": int(raw.n_times),
        "duration_seconds": float(raw.times[-1]) if raw.n_times else 0.0,
        "sampling_rate_hz": float(raw.info["sfreq"]),
        "channel_names": list(raw.ch_names),
        "channel_type_counts": dict(sorted(Counter(channel_types).items())),
        "bad_channels": list(raw.info["bads"]),
        "annotation_counts": dict(sorted(annotations.items())),
        "event_counts": {str(key): count for key, count in sorted(event_counts.items())},
        "event_anchor": "MOABB MAT stim channel marks trial start; cue occurs 2 s later",
    }


def main() -> None:
    args = parse_args()

    try:
        import mne
        import moabb
        from moabb.datasets import BNCI2014_001
    except ImportError as exc:
        raise SystemExit(
            "Missing research dependencies. Create the project environment and run "
            '`python -m pip install -e ".[dev]"` before using this script. '
            f"Original error: {exc}"
        ) from exc

    dataset = BNCI2014_001(artifact_handling="annotate_bad")
    print(f"Dataset: {dataset.__class__.__name__}")
    print(f"Subjects: {dataset.subject_list}")
    print("Expected classes: left_hand, right_hand, feet, tongue")
    print(f"MOABB version: {moabb.__version__}")
    print(f"MNE version: {mne.__version__}")

    if not args.load_data:
        print("Metadata-only mode: no EEG data were downloaded or loaded.")
        print("Use --load-data --subject 1 when ready to inspect the real recordings.")
        return

    data_dir = args.data_dir.resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    os.environ["MNE_DATASETS_BNCI_PATH"] = str(data_dir)
    print(f"BNCI cache root: {data_dir}")
    nested_data = dataset.get_data(subjects=[args.subject])
    subject_data = nested_data[args.subject]

    audit: dict[str, Any] = {
        "created_at_utc": datetime.now(UTC).isoformat(),
        "dataset": dataset.__class__.__name__,
        "subject": args.subject,
        "software": {"moabb": moabb.__version__, "mne": mne.__version__},
        "artifact_handling": "annotate_bad",
        "data_cache_root": str(data_dir),
        "sessions": {},
    }

    for session_id, runs in subject_data.items():
        audit["sessions"][str(session_id)] = {}
        for run_id, raw in runs.items():
            summary = summarize_raw(raw, mne)
            audit["sessions"][str(session_id)][str(run_id)] = summary
            print(
                f"subject={args.subject} session={session_id} run={run_id} "
                f"shape=({summary['n_channels']}, {summary['n_times']}) "
                f"sfreq={summary['sampling_rate_hz']} Hz"
            )
            print(f"  channel types: {summary['channel_type_counts']}")
            print(f"  annotations: {summary['annotation_counts']}")
            print(f"  events: {summary['event_counts']}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as file:
        json.dump(audit, file, ensure_ascii=False, indent=2, default=_json_safe)
    print(f"Saved audit: {args.output.resolve()}")


if __name__ == "__main__":
    main()
