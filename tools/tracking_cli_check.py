#!/usr/bin/env python3
"""Exercise train -> accepted pointer -> fresh CLI scoring on synthetic data."""
import csv
import json
from pathlib import Path
import subprocess
import sys

import yaml

from offline_run import assert_offline


def main():
    assert_offline()
    root = Path("data/tracking-cli").resolve()
    root.mkdir(parents=True, exist_ok=True)
    for side, prefix in (("left", "a"), ("right", "b")):
        with (root / f"{side}.csv").open("w") as stream:
            writer = csv.writer(stream)
            writer.writerow(["rec_id", "name", "code"])
            writer.writerows([(f"{prefix}{i}", f"canary person {i}", str(i)) for i in range(8)])
    for name, ids in (("train", range(4)), ("validation", range(4, 8))):
        with (root / f"{name}.csv").open("w") as stream:
            writer = csv.writer(stream)
            writer.writerow(["a_id", "b_id", "label"])
            writer.writerows([(f"a{i}", f"b{j}", int(i == j)) for i in ids for j in ids])
    cfg = {"entity": {"name": "cli_contract", "fields": {"name": {"type": "person_name"}, "code": {"type": "code"}}},
           "features": {"multi_token": ["idf_token_cosine"], "embeddings": {"provider": "none"}},
           "candidates": {"q": 2, "k": 8, "max_pairs": 100, "max_join_rows": 10000},
           "matcher": {"max_iter": 3, "max_depth": 2}, "decision": {"threshold": .5},
           "input": {"left": str(root / "left.csv"), "right": str(root / "right.csv"),
                     "labels": str(root / "train.csv"), "validation_labels": str(root / "validation.csv")},
           "mlflow": {"tracking_uri": f"sqlite:///{root}/mlflow.db", "acceptance_f1": 1.},
           "model": {"path": str(root / "scratch_model"), "pointer": str(root / "models/current.json")},
           "output": {"root": str(root / "train_output")}}
    report = {"status": "running", "commands": [], "confirmation_scored": False}
    for mode in ("train", "run"):
        if mode == "run":
            cfg["input"]["labels"] = cfg["input"]["validation_labels"] = None
            cfg["output"]["root"] = str(root / "score_output")
        config_path = root / f"{mode}.yaml"
        config_path.write_text(yaml.safe_dump(cfg))
        command = [sys.executable, "-m", "lakematch.cli", mode, "--config", str(config_path)]
        report["commands"].append(command)
        subprocess.run(command, check=True, timeout=120)
        report[mode] = json.loads((Path(cfg["output"]["root"]) / "metrics.json").read_text())
    assert report["train"]["model"]["accepted"]
    assert report["train"]["links"] == report["run"]["links"] == 8
    assert report["train"]["model"]["model_uri"] == report["run"]["model"]["model_uri"]
    import pandas as pd
    trained = pd.read_parquet(root / "train_output/links").sort_values(["a_id", "b_id"]).reset_index(drop=True)
    scored = pd.read_parquet(root / "score_output/links").sort_values(["a_id", "b_id"]).reset_index(drop=True)
    assert trained[["a_id", "b_id"]].equals(scored[["a_id", "b_id"]])
    assert float((trained.p - scored.p).abs().max()) < 1e-12
    report.update(status="completed", cleanup="succeeded", fresh_cli_prediction_equivalence=True)
    (root / "report.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
