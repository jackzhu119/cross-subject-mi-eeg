#!/usr/bin/env python3
"""Prepare existing eligible-v3 NPZ arrays for memory-mapped HPC training."""
import argparse
import json
import traceback

from hpcmi.data import prepare


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", required=True, help="Explicit input_sources.json")
    parser.add_argument("--output", required=True, help="Persistent prepared data directory")
    args = parser.parse_args()
    print(json.dumps({"stage": "python_data_import_started", "new_model_fits": 0}), flush=True)
    try:
        result = prepare(args.sources, args.output)
    except Exception:
        traceback.print_exc()
        return 1
    print(json.dumps({"stage": "prepared", "people": len(result["subjects"]),
                      "fingerprint": result["fingerprint"], "new_model_fits": 0}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
