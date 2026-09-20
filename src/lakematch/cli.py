import argparse
import json
import sys

from .config import load


def main(argv=None):
    parser = argparse.ArgumentParser(prog="lakematch")
    parser.add_argument("command", choices=["run", "train", "cluster", "doctor", "bench"])
    parser.add_argument("--config", help="Required for run, train, cluster and doctor")
    parser.add_argument("--all", action="store_true", help="bench: execute every declared benchmark corpus")
    parser.add_argument("--plan", action="store_true", help="bench: print the finite campaign without executing it")
    parser.add_argument("--project-root", default=".", help="bench: prepared lakematch checkout")
    parser.add_argument("--probe", action="store_true", help="doctor: start a session to measure capabilities")
    parser.add_argument("--batch-id", help="cluster: stable request ID for atomic publication and retries")
    parser.add_argument("--model-uri", help="cluster: immutable composite MLflow model URI")
    parser.add_argument("--pair-metadata", choices=["gram_cosine"],
                        help="cluster: explicitly declare the model's self-dedupe cos/rank/gap contract")
    parser.add_argument("--save-scores", action="store_true", help="run/train: preserve candidate probabilities for audit")
    args = parser.parse_args(argv)
    if args.command == 'bench':
        if not args.all:
            parser.error('bench requires --all')
    elif not args.config:
        parser.error('--config is required for ' + args.command)
    elif args.all or args.plan or args.project_root != '.':
        parser.error('--all, --plan and --project-root apply only to bench')
    try:
        if args.command == 'bench':
            from .benchmark.campaign import execute
            report = execute(project_root=args.project_root, plan=args.plan)
            print(json.dumps(report, indent=2))
            return
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
        elif args.command == "cluster":
            from .cluster_job import execute
            report = execute(config, model_uri=args.model_uri, batch_id=args.batch_id, pair_metadata=args.pair_metadata)
        else:
            from .engine import execute
            report = execute(config, command=args.command, save_scores=args.save_scores)
        print(json.dumps(report, indent=2))
    except (ValueError, NotImplementedError, FileNotFoundError) as exc:
        parser.exit(2, f"lakematch: {exc}\n")


if __name__ == "__main__":
    main()
