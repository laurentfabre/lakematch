#!/usr/bin/env python3
"""Validate sealed retrieval artifacts and publish observations, never acceptance."""
import hashlib
import json
from collections import Counter
from pathlib import Path
import tarfile

from evidence import ROOT, sha256

DEPENDENCIES = {"src/lakematch/" + name + ".py" for name in (
    "blocking", "candidates", "config", "entity", "runtime", "tracking", "benchmark/corpora", "benchmark/retrieval", "benchmark/metrics")}
DEPENDENCIES |= {"tools/run_retrieval.py", "tools/offline.sb", "tools/offline_run.py", "bench/METHOD_PLAN.md", "bench/PROTOCOL.md"}
DEPENDENCIES |= {"pyproject.toml", "requirements-local.lock"}
EXPECTED = ["febrl4-all", "febrl4-no_ssn", "febrl4-no_ssn_dob", "bpid", "abt_buy", "affiliations",
            "amazon_google", "walmart_amazon", "dblp_acm"]


def main():
    current, failures = {}, []
    for line in (ROOT / "experiments/runs.jsonl").read_text().splitlines():
        event = json.loads(line)
        if not event["kind"].startswith("retrieval-"):
            continue
        manifest = json.loads((ROOT / event["manifest"]).read_text())
        if event["status"] != "passed":
            failures.append({"run_id": event["run_id"], "status": event["status"], "manifest": event["manifest"]})
        if all(manifest["source_files"].get(p) == sha256(ROOT / p) for p in DEPENDENCIES):
            current[event["kind"][10:]] = (event, manifest)
    lines = ["# Retrieval observations — ZR-3 iteration 1", "",
        "Validation candidate recall only. These results do not select the final classifier or prove the FEBRL F1/latency gates.", "",
        "All methods use k=5, at most 100,000 final pairs, and a 50-million retained pre-top-k join limit.",
        "Alternative methods rerank by unweighted gram cosine; gram top-k uses IDF weighting. Unlabelled pairs are not assumed negative.",
        "Fitted state uses training records only. Transductive retrieval queries the complete unlabelled universe.",
        "Disjoint retrieval queries validation records after removing identities seen on either training side; its denominator may differ.", "",
        "| Corpus | Scope | Method | Recall [95% CI] | Δ recall CI vs gram | Pairs | Join rows before/after cap | Fit/save s | Retrieval s |",
        "|---|---|---|---|---|---:|---:|---:|---:|"]
    index = {"status": "partial", "confirmation_scored": False, "runs": {}, "failures": failures, "missing": []}
    sources = []
    overview = []
    for name in EXPECTED:
        if name not in current or current[name][0]["status"] != "passed":
            index["missing"].append(name)
            continue
        event, manifest = current[name]
        paths = {}
        for artifact in manifest["artifacts"]:
            path = ROOT / artifact["path"]
            if not path.is_file() or sha256(path) != artifact["sha256"]:
                raise ValueError(f"Changed or missing evidence: {path}")
            paths[path.name] = path
        report = json.loads(paths["report.json"].read_text())
        assert report["status"] == "completed" and report["cleanup"] == "succeeded"
        assert report["confirmation_scored"] is False and report["unlabelled_pairs_are_negatives"] is False
        assert "no live members" in manifest["cleanup"]
        assert "Verified OS denies non-loopback network access" in paths["stdout.txt"].read_text()
        with tarfile.open(paths["retrieval-evidence.tar.gz"], "r:gz") as archive:
            assert archive.extractfile("report.json").read() == paths["report.json"].read_bytes()
            for member, digest in report["evidence_files"].items():
                assert hashlib.sha256(archive.extractfile(member).read()).hexdigest() == digest
            ceilings = {}
            for row in report["methods"]:
                if row["status"] != "completed" or row["scope"] in ceilings:
                    continue
                payload = json.load(archive.extractfile(f"{row['method']}.{row['scope']}.predictions.json"))
                degree = Counter(a for a, b, group in payload["validation_positives"])
                ceilings[row["scope"]] = sum(min(report["config"]["candidates"]["k"], n) for n in degree.values()) / sum(degree.values())
        index["runs"][name] = {"run_id": event["run_id"], "manifest": event["manifest"],
            "report": str(paths["report.json"].relative_to(ROOT)), "report_sha256": sha256(paths["report.json"])}
        assert len(report["methods"]) == 10
        assert {(r["method"], r["scope"]) for r in report["methods"]} == {
            (method, scope) for method in ("gram_topk", "learned_blocker", "minhash_lsh", "field_blocks", "union")
            for scope in ("transductive", "disjoint")}
        values = {r["method"]: f"{100*r['candidate_recall']:.1f}%" if r["status"] == "completed" else r["status"]
                  for r in report["methods"] if r["scope"] == "transductive"}
        overview.append("| " + report["corpus"] + " | " + " | ".join(values[m] for m in
            ("gram_topk", "learned_blocker", "minhash_lsh", "field_blocks", "union")) + " |")
        for row in report["methods"]:
            if row["status"] != "completed":
                lines.append(f"| {report['corpus']} | {row['scope']} | {row['method']} | {row['status']}: {row['reason']} | — | — | — | — | — |")
                continue
            ci = row["recall_95ci"]
            delta = row["paired_recall_delta_95ci"]
            delta_text = f"[{delta[0]:+.3f}, {delta[1]:+.3f}]" if delta else "reference over budget"
            budget = row["budget"]
            lines.append(f"| {report['corpus']} | {row['scope']} | {row['method']} | {row['candidate_recall']:.3f} [{ci[0]:.3f}, {ci[1]:.3f}] | {delta_text} | {budget['candidate_pairs']} | {budget['join_rows_before_cap']}/{budget['join_rows_after_cap']} | {row['fit_and_save_seconds']:.2f} | {row['retrieval_seconds']:.2f} |")
        disjoint = report["scopes"]["disjoint"]
        sources += [f"- [{event['run_id']}](../{event['manifest']}): {report['wall_seconds_including_spark']:.2f}s. "
                    f"Disjoint universe: {disjoint['left_records']} left / {disjoint['right_records']} right; "
                    f"{disjoint['validation_positives']} of {disjoint['original_validation_positives']} original validation positives remain. "
                    f"Training-overlap removals: {disjoint['training_overlapping_records_removed']}. "
                    f"Ideal recall ceilings at k=5: " + ", ".join(f"{scope} {value:.3f}" for scope, value in ceilings.items()) + "."]
    lines += ["", "Bootstrap: 2,000 paired group resamples, seed 2026091902. Fit/save time is shared by both scopes.",
              "Retrieval time includes full-universe budget validation plus validation-anchor collection; it excludes fit/save and Spark startup.",
              "Complete run wall time includes corpus preparation, Spark startup, both scopes, state writes and Spark cleanup; archive compression follows.",
              "The ideal recall ceiling sums min(k, labelled-positive degree) per anchor. Many-to-many tasks may have a ceiling below 1 even with perfect ranking.",
              "Remote and live-label spend: zero (offline local runs). No confirmation/test partition has been scored.", "", *sources]
    if index["missing"]:
        lines += ["", "Still missing compatible completed comparisons: " + ", ".join(index["missing"]) + "."]
    else:
        index["status"] = "retrieval_comparison_completed"
    if failures:
        lines += ["", "Retained failures:", "", *[f"- [{r['run_id']}](../{r['manifest']}): {r['status']}." for r in failures]]
    insert_at = next(i for i, line in enumerate(lines) if line.startswith("| Corpus |"))
    lines[insert_at:insert_at] = ["Full-universe candidate recall:", "",
        "| Corpus | Gram top-k | Learned blocker | MinHash | Field blocks | Union |",
        "|---|---:|---:|---:|---:|---:|", *overview, "",
        "A rejected method has no recall measurement under this budget. No corpus is dropped to compute an apparently complete macro score.",
        "Union reranking at fixed k can discard a true match retained by a child. The SSN+DOB-hidden row is diagnostic only.",
        "", "Detailed scope, uncertainty and work measurements:", ""]
    (ROOT / "bench/RETRIEVAL.md").write_text("\n".join(lines) + "\n")
    (ROOT / "bench/retrieval_index.json").write_text(json.dumps(index, indent=2) + "\n")
    print(json.dumps({"completed": list(index["runs"]), "missing": index["missing"], "failures": len(failures)}))


if __name__ == "__main__":
    main()
