import argparse
import json
import sys

from .config import load


def main():
    parser = argparse.ArgumentParser(prog="lakematch")
    parser.add_argument("command", choices=["run", "train", "doctor", "bench"])
    parser.add_argument("--config", required=True)
    parser.add_argument("--probe", action="store_true", help="doctor: start a session to measure capabilities")
    args = parser.parse_args()
    try:
        config = load(args.config)
        print(json.dumps({"enabled_paid_features": config.enabled_paid}), file=sys.stderr)
        if args.command == "doctor":
            from .embeddings import availability
            report = {"runtime": config["runtime"], "methods": {n: config[n] for n in ("candidates", "features", "matcher", "decision", "cluster", "quality")},
                      "default_status": "starting hypotheses; no ZR-3 validation winners yet",
                      "enabled_paid_features": config.enabled_paid, "capabilities": "untested; use --probe",
                      "warnings": [reason] if (reason := availability(config)) else []}
            if args.probe:
                from .runtime import create_session, probe
                spark = create_session(config)
                try:
                    report["capabilities"] = probe(spark).to_dict()
                finally:
                    spark.stop()
        elif args.command == "bench":
            raise NotImplementedError("Benchmark campaign is ZR-3; use tools/experiment.py for ZR-1 verification")
        else:
            from .engine import execute
            report = execute(config, command=args.command)
        print(json.dumps(report, indent=2))
    except (ValueError, NotImplementedError, FileNotFoundError) as exc:
        parser.exit(2, f"lakematch: {exc}\n")


if __name__ == "__main__":
    main()
