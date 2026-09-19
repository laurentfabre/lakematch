#!/usr/bin/env python3
"""Render measured ZR-2 reports; never trains, chooses seeds or scores holdouts."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def interval(values):
    return f"[{values[0]:.4f}, {values[1]:.4f}]"


def main():
    ledger = [json.loads(line) for line in (ROOT / "experiments/runs.jsonl").read_text().splitlines() if line]
    lines = ["# Feature ablations on validation data", "",
        "These are validation-selection measurements, not ZR-3 confirmation results. "
        "The confirmation seed and all confirmation/test scores remain untouched. "
        "The fixed configurations and sampling rules are in [ABLATION_PLAN.md](ABLATION_PLAN.md).", "",
        "Every interval uses 2,000 paired anchor/group bootstrap resamples, seed 2026091902. "
        "Thresholds are independently selected on validation; the intervals describe sampling uncertainty "
        "and do not correct for threshold or feature selection optimism. Removing a family does not "
        "isolate its causal value because the GBT is refitted.", ""]
    index = {}
    for name in ("febrl4", "bpid", "abt_buy", "affiliations"):
        events = [r for r in ledger if r["phase"] == "ZR-2" and r["kind"] == "ablation-" + name and r["status"] == "passed"]
        if not events:
            raise ValueError(f"No completed {name} ablation; do not publish a partial passing table")
        event = events[-1]
        manifest = json.loads((ROOT / event["manifest"]).read_text())
        artifact = next(a for a in manifest["artifacts"] if Path(a["path"]).name == "report.json")
        path = ROOT / artifact["path"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != artifact["sha256"]:
            raise ValueError(f"Changed report: {path}")
        report = json.loads(path.read_text())
        if report["status"] != "completed" or report["confirmation_scored"]:
            raise ValueError(f"Unfinished or contaminated report: {path}")
        index[name] = {"run_id": event["run_id"], "report": artifact, "source_digest": event["source_digest"]}
        lines += [f"## {report['corpus']}", "", f"Run [`{event['run_id']}`](../{event['manifest']}); "
                  f"complete corpus-run wall time {report['total_seconds_including_start_stop']:.2f}s. "
                  "This includes all ablations and is not the single-run latency gate.", "",
                  "| Configuration | Validation F1 [95% CI] | Paired change CI vs native-all | Precision | Recall | Threshold | Feature / fit / score seconds |",
                  "|---|---|---|---:|---:|---:|---|"]
        for row in report["rows"]:
            lines.append(f"| {row['variant']} | {row['f1']:.4f} {interval(row['f1_95ci'])} | {interval(row['paired_delta_95ci'])} | "
                         f"{row['precision']:.4f} | {row['recall']:.4f} | {row['threshold']:.2f} | "
                         f"{row['feature_seconds']:.2f} / {row['train_seconds']:.2f} / {row['score_seconds']:.2f} |")
        lines += ["", "Precomputed candidates and training IDF are shared across variants; feature, fit and score "
                  "times exclude that shared work and model preparation. Native variants' explain plans have "
                  "no Python UDF evaluation. Optional similarities are explicitly outside that claim.", ""]
        if report["candidate_recall_validation"] is not None:
            lines += [f"Validation candidate recall@5: **{report['candidate_recall_validation']:.4f}**. "
                      f"Projected join rows before/after cap: {report['candidate_budget']['join_rows_before_cap']:,} / "
                      f"{report['candidate_budget']['join_rows_after_cap']:,}; final candidates "
                      f"{report['candidate_budget']['candidate_pairs']:,}. Both training endpoints are restricted to "
                      "training records; validation retrieval uses the full unlabeled universe.", ""]
        else:
            lines += ["Supplied labeled-pair evaluation: candidate recall is not applicable. "
                      "Unlabeled pairs are never silently treated as negatives.", ""]
        for baseline in report.get("baselines", []):
            lines += [f"Baseline `{baseline['variant']}`: F1 {baseline['f1']:.4f} "
                      f"{interval(baseline['f1_95ci'])}, threshold {baseline['threshold']:.2f}.", ""]
        meta = report["manifest"]
        lines += [f"Split: {meta['split_method']}. "
                  f"Duplicate/reversed pair keys removed: {meta.get('duplicate_or_reversed_pairs_removed', 0)}; "
                  f"conflicting keys excluded: {meta.get('conflicting_pair_keys_excluded', 0)}. "
                  f"Shared records: `{json.dumps(meta.get('shared_records_between_splits', {}), sort_keys=True)}`.", ""]
        embedding = next((r for r in report["rows"] if r["variant"] == "embedding_on"), None)
        if embedding:
            observations = embedding["embedding_preparation"]
            records = sum(o["records"] for o in observations.values())
            seconds = sum(o["seconds"] for o in observations.values())
            index[name]["embedding"] = {"paired_delta_95ci": embedding["paired_delta_95ci"],
                "positive_interval": embedding["paired_delta_95ci"][0] > 0,
                "records": records, "seconds": seconds, "seconds_per_100000_extrapolated": 100000 * seconds / records}
            lines += [f"Local MiniLM preparation: {records:,} record-side inputs in **{seconds:.2f}s**; "
                      f"**{100000 * seconds / records:.1f}s per 100,000 records**, linearly extrapolated, "
                      "not a measured 100,000-record throughput result. Empty values produce missing embeddings. "
                      "The model snapshot and output vectors are content-hashed in the raw report.", ""]
    lines += ["## Interpretation and retained failures", "",
        "Embedding features are **off by default** (`fields_of_type: []`): neither corpus's paired "
        "interval excludes zero in the positive direction. The optional offline MiniLM provider remains "
        "available for explicit selection. Its weights are pinned to the revision in the ablation plan.", "",
        "Use the paired intervals to distinguish a measured improvement from an inconclusive difference. "
        "The full ZR-3 cross-corpus method comparison is still required before shipping benchmark winners. "
        "The original FEBRL corpus has historical development exposure, explicitly disclosed in the split manifest.", "",
        "The first FEBRL attempt was canceled after a training-partition audit; its partial validation "
        "results are invalid for selection and remain archived. Two offline attempts failed before feature "
        "selection because Java dual-stack worker sockets were denied by macOS. A loopback probe isolated "
        "the cause; local Spark now uses IPv4, and the subsequent sweep asserts external network denial. "
        "Failures and cleanup results remain in the append-only run ledger.", "",
        "All runs use public/synthetic corpora locally. Remote spend and live-label usage are zero for "
        "this sweep; this does not reconcile the earlier FEVM canary billing.", ""]
    (ROOT / "bench/ABLATION.md").write_text("\n".join(lines))
    (ROOT / "bench/ablation_index.json").write_text(json.dumps(index, indent=2) + "\n")
    print("Wrote bench/ABLATION.md and bench/ablation_index.json from completed evidence")


if __name__ == "__main__":
    main()
