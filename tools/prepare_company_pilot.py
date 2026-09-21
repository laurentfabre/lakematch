#!/usr/bin/env python3
"""Prepare the approved development/validation corpus without confirmation rows."""
import argparse
import json
from pathlib import Path

from lakematch.benchmark.company_pilot import prepare


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    if args.manifest.exists():
        parser.error("Use a fresh manifest path")
    manifest = prepare(args.output)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"generator": manifest["generator"], "source_rows_materialized": 32000,
                      "confirmation_materialized": False, "files": len(manifest["files"])}))


if __name__ == "__main__":
    main()
