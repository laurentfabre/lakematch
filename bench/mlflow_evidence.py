#!/usr/bin/env python3
"""ZR-5 evidence: the laptop run (tracking only, resolved by run id) and the fourth-pat run (Unity Catalog, @champion)
of the same FEBRL4 example, read back from their stores. -> bench/results/mlflow.json

    lakematch run --config examples/febrl4.yaml                                   # writes models/current.json
    lakematch run --config examples/febrl4_uc.yaml --root data/runs/febrl4_uc     # registers, moves @champion
    python bench/mlflow_evidence.py

Everything recorded here is re-read from the stores, not copied from the run summaries: the laptop model is loaded
by runs:/<id>/model from the SQLite store, the UC model by the version @champion names, and both score the same
pairs (they were trained on the same label set, so their scores must agree).
"""
from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lakematch import tracking  # noqa: E402
from lakematch.config import load  # noqa: E402


def side(config: str, summary: Path) -> dict:
    import mlflow
    cfg = load(ROOT / config)
    run = json.loads(summary.read_text())["mlflow"]
    model, uri = tracking.load_current(cfg)
    client = mlflow.MlflowClient()
    r = client.get_run(model.metadata.run_id)
    contexts = sorted(t.value for i in r.inputs.dataset_inputs for t in i.tags if t.key == "mlflow.data.context")
    out = {"config": config, "tracking_uri": tracking.tracking_uri(cfg), "resolved_uri": uri,
           "run_id": model.metadata.run_id, "signature_inputs": len(model.metadata.signature.inputs.input_names()),
           "signature_outputs": model.metadata.signature.outputs.input_names(),
           "label_set_sha256": r.data.tags.get("lakematch.label_set_sha256"),
           "dataset_contexts": contexts,
           "metrics": {k: round(v, 4) for k, v in sorted(r.data.metrics.items())
                       if k.startswith(("pairwise_", "candidate_recall", "reload_"))},
           "accepted": r.data.tags.get("lakematch.accepted") == "true", "model_mb": r.data.metrics.get("model_mb"),
           "mlflow_seconds": run.get("seconds")}
    if cfg.get("mlflow.registry"):
        name, alias = tracking.registered_name(cfg), cfg.get("mlflow.alias")
        mv = client.get_model_version_by_alias(name, alias)
        out["registered"] = {"name": name, "alias": alias, "version": str(mv.version), "source_run_id": mv.run_id,
                             "versions": sorted(int(v.version) for v in client.search_model_versions(f"name='{name}'"))}
    return out, model


def main() -> int:
    import pandas as pd
    laptop, m_lap = side("examples/febrl4.yaml", ROOT / "data/runs/febrl4/run_summary.json")
    uc, m_uc = side("examples/febrl4_uc.yaml", ROOT / "data/runs/febrl4_uc/run_summary.json")
    feats = m_lap.metadata.signature.inputs.input_names()[2:]
    probe = pd.DataFrame([{**{f: v for f in feats}, "l_id": f"l{i}", "r_id": f"r{i}"}
                          for i, v in enumerate((0.0, 0.25, 0.5, 0.75, 1.0))])
    p_lap, p_uc = m_lap.predict(probe)["p"].tolist(), m_uc.predict(probe)["p"].tolist()
    out = {"generated": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
           "laptop": laptop, "fourth_pat": uc,
           "same_label_set": laptop["label_set_sha256"] == uc["label_set_sha256"],
           "probe_max_abs_diff_p": max(abs(a - b) for a, b in zip(p_lap, p_uc))}
    path = ROOT / "bench/results/mlflow.json"
    path.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
