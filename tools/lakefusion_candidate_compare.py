#!/usr/bin/env python3
"""Evaluate four frozen retrieval alternatives on validation, never confirmation."""
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import resource
import subprocess
import sys
import time

from lakematch.mastering.contracts import DomainContract, SourceMapping
from lakematch.benchmark.company_pilot import matching_projection
from lakematch.mastering.retrieval import ALTERNATIVES, Limits, retrieve

ROOT = Path(__file__).resolve().parents[1]


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metrics(result, truth):
    expected = {r["erp_key"]: r for r in truth}
    if len(expected) != len(truth) or set(expected) != {r["left_id"] for r in result["rows"]}:
        raise ValueError("Every truth anchor must have one retrieval result")
    counts = {s: Counter() for s in sorted({t["stratum"] for t in truth})}
    methods, method_positives = Counter(), Counter()
    for row in result["rows"]:
        target = expected[row["left_id"]]
        counts[target["stratum"]]["positives"] += 1
        retained = {c["right_id"] for c in row["candidates"]}
        after = target["crm_key"] in retained
        before = after or target["crm_key"] in row["dropped_right_ids"]
        counts[target["stratum"]]["pre_cap_found"] += int(before)
        counts[target["stratum"]]["post_cap_found"] += int(after)
        counts[target["stratum"]]["cap_losses"] += int(before and not after)
        for candidate in row["candidates"]:
            methods.update(candidate["methods"])
            if candidate["right_id"] == target["crm_key"]:
                method_positives.update(candidate["methods"])
    found = sum(c["post_cap_found"] for c in counts.values())
    return {"known_positives": len(truth), "found_positives": found,
            "candidate_recall": found / len(truth),
            "truncated_anchors": sum(r["truncated"] for r in result["rows"]),
            "max_pre_cap_per_anchor": max(r["pre_cap_count"] for r in result["rows"]),
            "max_post_cap_per_anchor": max(len(r["candidates"]) for r in result["rows"]),
            "cap_positive_losses": sum(c["cap_losses"] for c in counts.values()),
            "by_stratum": {s: {**dict(c), "recall": c["post_cap_found"] / c["positives"]} for s, c in counts.items()},
            "retained_pairs_by_method": dict(methods), "retained_positives_by_method": dict(method_positives)}


def main():
    output = ROOT / "bench/lakefusion/candidates-validation-v0.1.json"
    raw_dir = ROOT / "data/lakefusion/candidate-validation-v0.1"
    if output.exists() or raw_dir.exists():
        raise SystemExit("Use a new versioned plan and fresh paths; do not overwrite comparison evidence")
    subprocess.run([sys.executable, "-m", "pytest", "-q", "tests/test_mastering_contracts.py",
                    "tests/test_mastering_retrieval.py", "--junitxml=bench/lakefusion/candidate-tests-v0.1.xml"],
                   check=True, timeout=120)
    freeze = json.loads((ROOT / "spec/lakefusion/frozen/phase-a-v0.1.json").read_text())
    for name, expected in freeze["files"].items():
        if sha(ROOT / name) != expected:
            raise ValueError(f"Frozen input changed: {name}")
    source = ROOT / "data/lakefusion/company-pilot-v0.1"
    manifest_path = ROOT / "bench/lakefusion/company-pilot-v0.1.json"
    manifest = json.loads(manifest_path.read_text())
    inputs = ["validation.erp_vendor.jsonl", "validation.crm_account.jsonl", "validation.truth.jsonl"]
    for name in inputs:
        if sha(source / name) != manifest["files"][name]["sha256"]:
            raise ValueError(f"Source checksum mismatch: {name}")
    fixture = ROOT / "examples/mastering/company_pilot"
    domain = DomainContract.from_dict(json.loads((fixture / "domain.json").read_text()))
    prepared = {}
    prep_started = time.monotonic()
    for source_name in ("erp_vendor", "crm_account"):
        mapping = SourceMapping.from_dict(json.loads((fixture / f"{source_name}_mapping.json").read_text()), domain)
        prepared[source_name] = matching_projection(mapping, read_jsonl(source / f"validation.{source_name}.jsonl"))
    truth = read_jsonl(source / "validation.truth.jsonl")
    limits = Limits(seconds=120)
    report = {"schema_version": 1, "phase": "LF-B", "package": "LM-002", "partition": "validation",
              "started_at": datetime.now(timezone.utc).isoformat(), "limits": asdict(limits),
              "source_manifest_sha256": sha(manifest_path), "confirmation_materialized": False,
              "input_hashes": {n: sha(source / n) for n in inputs},
              "feature_preparation_wall_seconds": time.monotonic() - prep_started,
              "memory_limit_bytes": 4 * 1024**3, "memory_enforcement": "measured peak gate",
              "cost": {"cloud_resources_started": [], "status": "local CPU only; no billed cloud operation"},
              "alternatives": []}
    raw_dir.mkdir(parents=True)
    for alternative in ALTERNATIVES:
        result = retrieve(prepared["erp_vendor"], prepared["crm_account"], alternative, limits)
        raw_path = raw_dir / f"{alternative}.json"
        raw_path.write_text(json.dumps(result, separators=(",", ":")) + "\n")
        peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        peak_bytes = peak_rss if sys.platform == "darwin" else peak_rss * 1024
        summary = {k: result[k] for k in ("alternative", "retained_pairs", "posting_visits", "wall_seconds")}
        summary.update(metrics(result, truth), process_peak_rss_bytes=peak_bytes,
                       raw_artifact=str(raw_path.relative_to(ROOT)), raw_sha256=sha(raw_path))
        summary["candidate_gate_passed"] = summary["candidate_recall"] >= .95 and peak_bytes <= report["memory_limit_bytes"]
        report["alternatives"].append(summary)
        output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps({k: summary[k] for k in ("alternative", "candidate_recall", "retained_pairs", "posting_visits", "wall_seconds", "candidate_gate_passed")}), flush=True)
        del result
    passed = [s for s in report["alternatives"] if s["candidate_gate_passed"]]
    report["selected"] = min(passed, key=lambda s: (s["retained_pairs"], s["posting_visits"]))["alternative"] if passed else None
    report["ended_at"] = datetime.now(timezone.utc).isoformat()
    report["limitations"] = "Validation candidate recall only; not merge precision, scoring, online serving, remote scale or general customer quality"
    output.write_text(json.dumps(report, indent=2) + "\n")
    return int(not passed)


if __name__ == "__main__":
    raise SystemExit(main())
